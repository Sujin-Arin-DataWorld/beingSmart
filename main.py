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

from src.data.fetcher import fetch_history
from src.data.macro import fetch_macro_snapshot, compute_breadth
from src.data.fundamentals import fetch_fundamentals_batch, days_to_earnings
from src.data.news import fetch_news_batch
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
from src.regime.classifier import classify as classify_regime
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
        + [h["ticker"] for h in portfolio.get("holdings", [])]
    ))
    print(f"[beingSmart] universe = {len(tickers)} tickers")

    print(f"[beingSmart] downloading history...")
    history = fetch_history(
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
    print(f"[beingSmart] regime = {regime_assessment.regime.value}")

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

    # === AI 해석 (Tier 2 컨텍스트 포함) ===
    ai_context = {
        "regime": regime_assessment.regime.value,
        "regime_reasons": regime_assessment.reasons,
        "diversification": div_score,
        "sector_exposure": sect_exp,
        "portfolio_beta": portfolio_beta,
        "news": news_by_ticker,
        "fundamentals": {t: fundamentals.get(t) for t in candidate_tickers if fundamentals.get(t)},
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
    )

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    path = save_report(report, reports_dir)
    print(f"[beingSmart] report saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
