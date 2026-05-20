"""beingSmart 데일리 러너. Tier 2 통합.

실행:  python main.py

환경:
    ANTHROPIC_API_KEY    Claude API 키
    DISABLE_AI=true      AI 해석 비활성화
"""
from __future__ import annotations
import sys
from datetime import datetime
from pathlib import Path

import yaml
import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.data.alpaca import fetch_with_fallback, is_alpaca_available
from src.data.macro import fetch_macro_snapshot, compute_breadth
from src.data.fundamentals import fetch_fundamentals_batch, days_to_earnings
from src.data.news import fetch_news_batch
from src.data.fred import fetch_fred_snapshot, recession_indicator, is_fred_available
from src.indicators.technical import compute_all
from src.screener.rules import check_buy, check_sell
from src.screener.scoring import score_buy_signal
from src.portfolio.manager import load_portfolio, compute_holding_status
from src.portfolio.diversification import (
    compute_correlation_matrix,
    sector_exposure,
    beta_weighted_exposure,
    diversification_score,
    correlation_with_existing,
)
from src.portfolio.sizing import compute_position_size, reward_to_risk_ratio
from src.portfolio.drawdown import (
    append_equity_point,
    compute_drawdowns,
    load_equity_history,
    should_disable_new_entries,
)
from src.portfolio.asset_class import asset_class_exposure, diversification_warnings
from src.portfolio.optimizer import inverse_volatility_weights, compare_actual_vs_target
from src.regime.classifier import classify as classify_regime
from src.regime.ml_classifier import fit_and_predict as ml_classify, compare_with_rule_based
from src.recommender.ai import get_ai_summary
from src.report.generator import generate_report, save_report


def main() -> int:
    print(f"[beingSmart] start {datetime.now().isoformat()}")

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    universe = yaml.safe_load((ROOT / "universe.yaml").read_text(encoding="utf-8"))
    portfolio = load_portfolio(ROOT / "portfolio.yaml")

    tickers = sorted(set(
        (universe.get("etf") or [])
        + (universe.get("stocks") or [])
        + (universe.get("bonds") or [])
        + (universe.get("commodities") or [])
        + (universe.get("currencies") or [])
        + (universe.get("international") or [])
        + [h["ticker"] for h in portfolio.get("holdings", [])]
    ))
    print(f"[beingSmart] universe = {len(tickers)} tickers (multi-asset)")

    print(f"[beingSmart] downloading history (yfinance + Alpaca fallback: "
          f"{'available' if is_alpaca_available() else 'unavailable'})...")
    history = fetch_with_fallback(
        tickers, days=config["strategy"]["screening"]["lookback_days"]
    )
    print(f"[beingSmart] history loaded for {len(history)} tickers")

    print(f"[beingSmart] fetching macro snapshot...")
    macro = fetch_macro_snapshot(days=250)
    enriched = {t: compute_all(df) for t, df in history.items()}
    breadth = compute_breadth(history)

    # === Regime 분류 ===
    regime_cfg = config.get("regime", {})
    regime_assessment = classify_regime(
        macro=macro,
        breadth_ratio=breadth,
        risk_off_vix=regime_cfg.get("risk_off_vix", 30.0),
        risk_off_sp_5d=regime_cfg.get("risk_off_sp_5d_pct", -7.0),
        choppy_vix=regime_cfg.get("choppy_vix", 20.0),
        choppy_breadth=regime_cfg.get("choppy_breadth", 0.40),
    )
    print(f"[beingSmart] regime (rule) = {regime_assessment.regime.value}")

    # === ML regime (옵션) ===
    ml_cfg = config.get("ml_regime", {})
    ml_regime_result = None
    ml_comparison = None
    if ml_cfg.get("enable", True):
        # ML은 historical macro 필요 — VIX/SP500 본격 다운로드
        try:
            import yfinance as yf
            macro_for_ml = yf.download(
                tickers="^VIX ^GSPC",
                period=f"{config['strategy']['screening']['lookback_days']}d",
                auto_adjust=True, progress=False, group_by="ticker", threads=True,
            )
            macro_hist_ml = {}
            for t in ["^VIX", "^GSPC"]:
                try:
                    sub = macro_for_ml[t].dropna()
                    if len(sub) >= 250:
                        macro_hist_ml[t] = sub
                except (KeyError, AttributeError):
                    continue
            ml_regime_result = ml_classify(
                macro_hist_ml,
                n_clusters=ml_cfg.get("n_clusters", 4),
            )
        except Exception as e:
            print(f"[beingSmart] ML regime skipped: {e}")
        ml_comparison = compare_with_rule_based(ml_regime_result, regime_assessment.regime)
        if ml_comparison.get("available"):
            print(f"[beingSmart] regime (ML)   = {ml_comparison['ml_regime']} "
                  f"({'동의' if ml_comparison['agreement'] else '불일치'})")

    # === FRED 거시 (옵션) ===
    fred_snapshot = {}
    fred_recession = None
    if is_fred_available():
        print(f"[beingSmart] fetching FRED macro indicators...")
        fred_snapshot = fetch_fred_snapshot()
        fred_recession = recession_indicator(fred_snapshot)
        if fred_recession:
            print(f"[beingSmart] {fred_recession}")

    # === 매수 후보 추출 + 점수화 ===
    strategy_cfg = config["strategy"]
    scoring_cfg = config.get("scoring", {})
    weights = scoring_cfg.get("weights")
    min_score = scoring_cfg.get("min_score_threshold", 0)
    vix_now = macro.get("VIX", {}).get("price")

    buy_signals: list = []
    for t, df in enriched.items():
        sig = check_buy(t, df, strategy_cfg)
        if not sig:
            continue
        score = score_buy_signal(
            sig.__dict__,
            regime=regime_assessment.regime,
            vix=vix_now,
            weights=weights,
        )
        if score["total"] < min_score:
            continue
        d = sig.__dict__.copy()
        d["score"] = score["total"]
        d["score_breakdown"] = score
        buy_signals.append(d)
    buy_signals.sort(key=lambda x: x["score"], reverse=True)
    print(f"[beingSmart] buy candidates (pre-earnings): {len(buy_signals)}")

    # === 어닝 블랙아웃 필터 ===
    earnings_cfg = config.get("earnings", {})
    blackout_days = earnings_cfg.get("blackout_days", 7)
    if buy_signals and blackout_days > 0:
        kept = []
        skipped: list = []
        for b in buy_signals[:30]:  # 상위 30개만 어닝 조회 (속도)
            try:
                d2e = days_to_earnings(b["ticker"], lookahead_days=blackout_days * 2)
            except Exception:
                d2e = None
            b["days_to_earnings"] = d2e
            if d2e is not None and 0 <= d2e <= blackout_days:
                b["earnings_blocked"] = True
                skipped.append(b["ticker"])
            else:
                b["earnings_blocked"] = False
                kept.append(b)
        buy_signals = kept
        if skipped:
            print(f"[beingSmart] earnings blackout: {skipped}")

    # === 펀더멘털 (후보 + 보유) ===
    holding_tickers = [h["ticker"] for h in portfolio.get("holdings", [])]
    candidate_tickers = [b["ticker"] for b in buy_signals[:20]]
    fundamental_tickers = sorted(set(candidate_tickers + holding_tickers))
    print(f"[beingSmart] fetching fundamentals for {len(fundamental_tickers)} tickers...")
    fundamentals = fetch_fundamentals_batch(fundamental_tickers)

    # === Position sizing ===
    sizing_cfg = config.get("sizing", {})
    risk_per_trade = sizing_cfg.get("risk_per_trade", 0.02)
    max_pos_pct = sizing_cfg.get("max_position_pct", 0.15)
    cash = portfolio.get("cash_usd", 0.0)
    holding_mv = sum(
        float(enriched[h["ticker"]].iloc[-1]["Close"]) * h["shares"]
        for h in portfolio.get("holdings", [])
        if h["ticker"] in enriched
    )
    total_capital = cash + holding_mv

    for b in buy_signals:
        b["sizing"] = compute_position_size(
            entry_price=b["price"],
            stop_price=b["suggested_stop"],
            capital=total_capital,
            risk_per_trade=risk_per_trade,
            max_position_pct=max_pos_pct,
        )
        b["reward_to_risk"] = reward_to_risk_ratio(
            b["price"], b["suggested_stop"], b["suggested_target"]
        )

    # === 분산도 ===
    div_cfg = config.get("diversification", {})
    corr_window = div_cfg.get("correlation_window", 60)
    high_corr = div_cfg.get("high_corr_warning", 0.70)

    div_tickers = sorted(set(candidate_tickers + holding_tickers))
    corr_matrix = compute_correlation_matrix(history, div_tickers, window=corr_window)
    current_prices = {t: float(enriched[t].iloc[-1]["Close"]) for t in enriched}
    sect_exp = sector_exposure(portfolio.get("holdings", []), fundamentals, current_prices)
    portfolio_beta = beta_weighted_exposure(portfolio.get("holdings", []), fundamentals, current_prices)
    div_score = diversification_score(corr_matrix, sect_exp)

    for b in buy_signals:
        corr = correlation_with_existing(b["ticker"], holding_tickers, corr_matrix)
        b["corr_with_holdings"] = corr
        b["high_corr_warning"] = corr is not None and corr > high_corr

    # === 뉴스 catalyst (상위 N개만) ===
    news_cfg = config.get("news", {})
    news_by_ticker: dict = {}
    if news_cfg.get("enable", True) and buy_signals:
        top_n_news = news_cfg.get("top_n_for_news", 5)
        top_for_news = [b["ticker"] for b in buy_signals[:top_n_news]]
        print(f"[beingSmart] fetching news for {top_for_news}...")
        news_by_ticker = fetch_news_batch(
            top_for_news,
            hours=news_cfg.get("hours_lookback", 72),
            per_ticker_limit=news_cfg.get("per_ticker_limit", 3),
        )

    print(f"[beingSmart] buy candidates (final): {len(buy_signals)}")

    # === 매도 검토 + 보유 종목 status ===
    sell_signals: list = []
    holdings_status: list = []
    for h in portfolio.get("holdings", []):
        t = h["ticker"]
        if t not in enriched:
            print(f"[warn] {t} 데이터 없음 — 검토 스킵")
            continue
        df = enriched[t]
        last = df.iloc[-1]
        sig = check_sell(t, df, h, strategy_cfg)
        if sig:
            sell_signals.append(sig.__dict__)
        atr_val = float(last["atr_14"]) if not pd.isna(last["atr_14"]) else None
        status = compute_holding_status(h, float(last["Close"]), atr_val, strategy_cfg)
        status["sector"] = (fundamentals.get(t) or {}).get("sector")
        holdings_status.append(status)
    print(f"[beingSmart] sell signals: {len(sell_signals)}, holdings: {len(holdings_status)}")

    # === 자산 클래스 노출 + Risk parity ===
    asset_class_pct = asset_class_exposure(
        portfolio.get("holdings", []), current_prices, fundamentals
    )
    asset_class_warnings = diversification_warnings(asset_class_pct)
    for w in asset_class_warnings:
        print(f"[beingSmart] {w}")

    # Inverse vol weights (보유 종목 기준)
    opt_cfg = config.get("optimizer", {})
    risk_parity_recs: list = []
    if opt_cfg.get("enable_inverse_vol", True) and portfolio.get("holdings"):
        h_tickers = [h["ticker"] for h in portfolio.get("holdings", [])]
        weights = inverse_volatility_weights(history, h_tickers, window=corr_window)
        if weights:
            risk_parity_recs = compare_actual_vs_target(
                portfolio.get("holdings", []), current_prices, weights,
            )
            threshold = opt_cfg.get("rebalance_threshold_pct", 5.0)
            risk_parity_recs = [r for r in risk_parity_recs if abs(r["diff_pct"]) >= threshold]
            if risk_parity_recs:
                print(f"[beingSmart] risk-parity rebalance suggestions: {len(risk_parity_recs)}")

    # === Drawdown 추적 ===
    cash_now = portfolio.get("cash_usd", 0.0)
    current_equity = cash_now + sum(h["market_value"] for h in holdings_status)
    today_str = datetime.now().strftime("%Y-%m-%d")
    dd_cfg = config.get("drawdown", {})
    equity_history_path = ROOT / "equity_history.yaml"
    if dd_cfg.get("track_history", True):
        append_equity_point(equity_history_path, today_str, current_equity)
    dd_history = load_equity_history(equity_history_path)
    dd_metrics = compute_drawdowns(dd_history)
    dd_threshold = dd_cfg.get("disable_entries_threshold_pct", -15.0)
    if should_disable_new_entries(dd_metrics, threshold_pct=dd_threshold):
        print(f"[beingSmart] ⚠️ DD {dd_metrics['current_dd_pct']:.2f}% ≤ {dd_threshold}% "
              "— 신규 매수 disable")
        buy_signals = []  # 후보 모두 제거

    # === AI 해석 (Tier 2 컨텍스트 포함) ===
    ai_context = {
        "regime": regime_assessment.regime.value,
        "regime_reasons": regime_assessment.reasons,
        "ml_regime": ml_comparison,
        "diversification": div_score,
        "sector_exposure": sect_exp,
        "asset_class_exposure": asset_class_pct,
        "asset_class_warnings": asset_class_warnings,
        "portfolio_beta": portfolio_beta,
        "news": news_by_ticker,
        "fundamentals": {t: fundamentals.get(t) for t in candidate_tickers if fundamentals.get(t)},
        "drawdown": dd_metrics,
        "fred": fred_snapshot,
        "fred_recession": fred_recession,
        "risk_parity_recs": risk_parity_recs,
    }
    ai = get_ai_summary(buy_signals, sell_signals, holdings_status, context=ai_context)
    if ai:
        print(f"[beingSmart] AI summary ok ({len(ai)} chars)")
    else:
        print(f"[beingSmart] AI summary skipped (no API key / disabled)")

    # === 리포트 생성 ===
    report = generate_report(
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        holdings_status=holdings_status,
        cash_usd=cash,
        ai_summary=ai,
        config=config,
        macro=macro,
        regime=regime_assessment,
        breadth=breadth,
        diversification=div_score,
        sector_exposure_pct=sect_exp,
        portfolio_beta=portfolio_beta,
        news_by_ticker=news_by_ticker,
        drawdown=dd_metrics,
        asset_class_pct=asset_class_pct,
        asset_class_warnings=asset_class_warnings,
        ml_comparison=ml_comparison,
        fred_snapshot=fred_snapshot,
        fred_recession=fred_recession,
        risk_parity_recs=risk_parity_recs,
    )

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    path = save_report(report, reports_dir)
    print(f"[beingSmart] report saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
