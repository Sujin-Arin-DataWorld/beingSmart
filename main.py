"""beingSmart 데일리 러너.

실행:
    python main.py

환경:
    ANTHROPIC_API_KEY      Claude API 키 (없으면 룰 기반 결과만 출력)
    DISABLE_AI=true        AI 해석 비활성화
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
from src.indicators.technical import compute_all
from src.screener.rules import check_buy, check_sell
from src.screener.scoring import score_buy_signal
from src.portfolio.manager import load_portfolio, compute_holding_status
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

    print(f"[beingSmart] downloading universe history...")
    history = fetch_history(
        tickers, days=config["strategy"]["screening"]["lookback_days"]
    )
    print(f"[beingSmart] history loaded for {len(history)} tickers")

    print(f"[beingSmart] fetching macro snapshot...")
    macro = fetch_macro_snapshot(days=250)
    print(f"[beingSmart] macro: {list(macro.keys())}")

    enriched = {t: compute_all(df) for t, df in history.items()}
    breadth = compute_breadth(history)

    # 시장 regime 분류
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

    # 매수 후보 추출 + 점수화
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
    print(f"[beingSmart] buy candidates: {len(buy_signals)} (after score ≥ {min_score})")

    # 매도 검토
    sell_signals: list = []
    holdings_status: list = []
    for h in portfolio.get("holdings", []):
        t = h["ticker"]
        if t not in enriched:
            print(f"[warn] {t} 데이터 없음 — 보유 종목 검토 스킵")
            continue
        df = enriched[t]
        last = df.iloc[-1]

        sig = check_sell(t, df, h, strategy_cfg)
        if sig:
            sell_signals.append(sig.__dict__)

        atr_val = float(last["atr_14"]) if not pd.isna(last["atr_14"]) else None
        status = compute_holding_status(h, float(last["Close"]), atr_val, strategy_cfg)
        holdings_status.append(status)
    print(f"[beingSmart] sell signals: {len(sell_signals)}, holdings tracked: {len(holdings_status)}")

    # AI 해석
    ai = get_ai_summary(buy_signals, sell_signals, holdings_status)
    if ai:
        print(f"[beingSmart] AI summary ok ({len(ai)} chars)")
    else:
        print(f"[beingSmart] AI summary skipped (no API key / disabled)")

    # 리포트
    report = generate_report(
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        holdings_status=holdings_status,
        cash_usd=portfolio.get("cash_usd", 0.0),
        ai_summary=ai,
        config=config,
        macro=macro,
        regime=regime_assessment,
        breadth=breadth,
    )

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    path = save_report(report, reports_dir)
    print(f"[beingSmart] report saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
