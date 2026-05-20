"""CLI: python -m src.backtest [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--capital N]"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.data.fetcher import fetch_history
from src.backtest.engine import run_backtest
from src.backtest.metrics import compute_metrics, format_trade_table, format_equity_ascii


def main() -> int:
    parser = argparse.ArgumentParser(description="beingSmart 백테스트")
    parser.add_argument("--start", help="시작일 YYYY-MM-DD")
    parser.add_argument("--end", help="종료일 YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--days", type=int, default=1500, help="다운로드 영업일 (약 6년)")
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--slippage", type=float, default=0.001, help="0.001 = 0.1%")
    parser.add_argument("--max-hold", type=int, default=60)
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    universe = yaml.safe_load((ROOT / "universe.yaml").read_text(encoding="utf-8"))
    tickers = sorted(set((universe.get("etf") or []) + (universe.get("stocks") or [])))

    print(f"[backtest] universe={len(tickers)}, downloading {args.days} days history...")
    history = fetch_history(tickers, days=args.days)
    print(f"[backtest] loaded {len(history)} tickers with sufficient history")

    result = run_backtest(
        history=history,
        strategy_cfg=config["strategy"],
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        max_positions=args.max_positions,
        slippage_pct=args.slippage,
        max_hold_days=args.max_hold,
    )
    metrics = compute_metrics(result)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    bt_dir = ROOT / "backtests"
    bt_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    md_path = bt_dir / f"{ts}.md"
    md_path.write_text(_render_report(result, metrics, args), encoding="utf-8")

    json_path = bt_dir / f"{ts}.json"
    json_path.write_text(
        json.dumps(
            {
                "args": vars(args),
                "metrics": metrics,
                "start_date": result.start_date.isoformat(),
                "end_date": result.end_date.isoformat(),
                "n_trades": len(result.trades),
                "n_universe": result.n_universe,
                "initial_capital": result.initial_capital,
                "final_capital": result.final_capital,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"[backtest] saved: {md_path}")
    print(f"[backtest] saved: {json_path}")
    return 0


def _render_report(result, metrics: dict, args) -> str:
    lines = [
        f"# 백테스트 — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- 기간: **{result.start_date.strftime('%Y-%m-%d')} ~ {result.end_date.strftime('%Y-%m-%d')}**",
        f"- universe: {result.n_universe} tickers",
        f"- 초기 자본: ${args.capital:,.0f}",
        f"- 최종 자본: ${result.final_capital:,.0f}",
        f"- 최대 동시 포지션: {args.max_positions}",
        f"- 슬리피지: {args.slippage * 100:.2f}% (편도)",
        f"- 최대 보유 일수: {args.max_hold}d",
        "",
        "## 핵심 지표",
        "",
        "| 지표 | 값 |",
        "|---|---:|",
    ]
    for k, v in metrics.items():
        if isinstance(v, float):
            lines.append(f"| {k} | {v:,.2f} |")
        else:
            lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "### 해석 기준",
        "",
        "- **Sharpe > 1**: 양호. 0.5 미만은 보통 시장 대비 열위.",
        "- **Max DD < -20%**: 실전 견딜 수 있는 수준의 경계선.",
        "- **Profit factor > 1.5**: 룰 양호. 1.0 미만은 룰 실패.",
        "- **Win rate**: 추세 추종 룰은 30~50%가 정상 (큰 익절이 작은 손실 상쇄).",
        "",
        "## 트레이드 (최근 20개)",
        "",
        format_trade_table(result, top_n=20),
        "",
        "## Equity Curve",
        "",
        "```",
        format_equity_ascii(result),
        "```",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
