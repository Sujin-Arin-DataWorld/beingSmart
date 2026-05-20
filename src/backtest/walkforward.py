"""Walk-forward (rolling out-of-sample) 백테스트.

룰의 historical 일관성 검증. 매 step_months마다 test_window_years 기간 백테스트.
Sharpe/DD/win rate가 window 간 일관되는지 → over-fit 검출.

룰 hyperparameter optimization 없음 — 정적 룰을 다른 시기에 적용해 robustness 확인.
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest.engine import run_backtest
from src.backtest.metrics import compute_metrics
from src.data.fetcher import fetch_history


@dataclass
class WalkForwardWindow:
    start_date: str
    end_date: str
    metrics: Dict[str, float]
    n_trades: int
    final_capital: float


@dataclass
class WalkForwardResult:
    windows: List[WalkForwardWindow]
    summary: Dict[str, Dict[str, float]] = field(default_factory=dict)
    test_window_years: float = 1.0
    step_months: int = 12
    universe_size: int = 0


def run_walkforward(
    history: Dict[str, pd.DataFrame],
    strategy_cfg: dict,
    test_window_years: float = 1.0,
    step_months: int = 12,
    initial_capital: float = 100_000.0,
    max_positions: int = 10,
    slippage_pct: float = 0.001,
    max_hold_days: int = 60,
) -> WalkForwardResult:
    """rolling window 백테스트."""
    if not history:
        raise ValueError("history is empty")

    all_dates_set = set()
    for df in history.values():
        all_dates_set.update(df.index)
    all_dates = sorted(all_dates_set)
    if len(all_dates) < 400:
        raise ValueError("walk-forward는 최소 400 영업일 데이터 필요")

    test_days = int(test_window_years * 252)
    step_days = max(int(step_months * 21), 1)

    windows: List[WalkForwardWindow] = []
    i = 200  # 200일 워밍업
    while i + test_days <= len(all_dates):
        win_start = all_dates[i]
        win_end = all_dates[min(i + test_days - 1, len(all_dates) - 1)]
        try:
            result = run_backtest(
                history=history,
                strategy_cfg=strategy_cfg,
                start_date=win_start.strftime("%Y-%m-%d"),
                end_date=win_end.strftime("%Y-%m-%d"),
                initial_capital=initial_capital,
                max_positions=max_positions,
                slippage_pct=slippage_pct,
                max_hold_days=max_hold_days,
            )
            metrics = compute_metrics(result)
        except ValueError:
            i += step_days
            continue
        windows.append(WalkForwardWindow(
            start_date=win_start.strftime("%Y-%m-%d"),
            end_date=win_end.strftime("%Y-%m-%d"),
            metrics=metrics,
            n_trades=len(result.trades),
            final_capital=result.final_capital,
        ))
        i += step_days

    summary = _summarize(windows)
    return WalkForwardResult(
        windows=windows,
        summary=summary,
        test_window_years=test_window_years,
        step_months=step_months,
        universe_size=len(history),
    )


def _summarize(windows: List[WalkForwardWindow]) -> Dict[str, Dict[str, float]]:
    if not windows:
        return {}
    keys = ["sharpe", "max_drawdown_pct", "win_rate_pct", "profit_factor", "total_return_pct", "cagr_pct"]
    summary: Dict[str, Dict[str, float]] = {}
    for k in keys:
        vals = [w.metrics.get(k, 0.0) for w in windows if k in w.metrics]
        if not vals:
            continue
        summary[k] = {
            "mean": round(statistics.mean(vals), 2),
            "std": round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0,
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
        }
    return summary


def format_walkforward_report(result: WalkForwardResult) -> str:
    lines = [
        f"# Walk-forward 백테스트 — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- 테스트 window: **{result.test_window_years}년**, step: **{result.step_months}개월**",
        f"- 총 window: {len(result.windows)}",
        f"- universe: {result.universe_size} tickers",
        "",
        "## Window별 결과",
        "",
        "| 기간 | Sharpe | Max DD% | Win% | PF | Return% | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for w in result.windows:
        m = w.metrics
        lines.append(
            f"| {w.start_date} ~ {w.end_date} | "
            f"{m.get('sharpe', 0):.2f} | "
            f"{m.get('max_drawdown_pct', 0):.2f}% | "
            f"{m.get('win_rate_pct', 0):.1f}% | "
            f"{m.get('profit_factor', 0):.2f} | "
            f"{m.get('total_return_pct', 0):+.2f}% | "
            f"{w.n_trades} |"
        )

    lines += [
        "",
        "## 일관성 (std/mean 작을수록 robust)",
        "",
        "| 지표 | 평균 | std | min | max |",
        "|---|---:|---:|---:|---:|",
    ]
    for k, v in result.summary.items():
        lines.append(f"| {k} | {v['mean']} | {v['std']} | {v['min']} | {v['max']} |")

    lines += [
        "",
        "## 해석",
        "",
        "- **std / |mean| < 0.5**: 룰이 시기에 무관하게 일관적 → 실전 후보",
        "- **min Sharpe > 0**: 모든 기간 양의 risk-adjusted 수익 → 매우 양호",
        "- **window 간 격차 크면**: regime 의존 강함 (BEAR 기간 약함 등) — Tier 1 regime 필터 사용 권장",
        "- **모든 window Profit factor < 1.2**: 룰 자체 검증 실패. 파라미터 재검토",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="beingSmart walk-forward 백테스트")
    parser.add_argument("--test-years", type=float, default=1.0)
    parser.add_argument("--step-months", type=int, default=12)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--days", type=int, default=2000, help="다운로드 영업일 (≈8년)")
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--slippage", type=float, default=0.001)
    parser.add_argument("--max-hold", type=int, default=60)
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    universe = yaml.safe_load((ROOT / "universe.yaml").read_text(encoding="utf-8"))
    tickers = sorted(set((universe.get("etf") or []) + (universe.get("stocks") or [])))

    print(f"[walkforward] universe={len(tickers)}, downloading {args.days} days...")
    history = fetch_history(tickers, days=args.days)
    print(f"[walkforward] loaded {len(history)} tickers")

    result = run_walkforward(
        history=history,
        strategy_cfg=config["strategy"],
        test_window_years=args.test_years,
        step_months=args.step_months,
        initial_capital=args.capital,
        max_positions=args.max_positions,
        slippage_pct=args.slippage,
        max_hold_days=args.max_hold,
    )
    print(f"[walkforward] {len(result.windows)} windows computed")
    for k, v in result.summary.items():
        print(f"  {k}: mean={v['mean']}, std={v['std']}")

    bt_dir = ROOT / "backtests"
    bt_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = bt_dir / f"walkforward_{ts}.md"
    md_path.write_text(format_walkforward_report(result), encoding="utf-8")
    print(f"[walkforward] saved: {md_path}")

    json_path = bt_dir / f"walkforward_{ts}.json"
    json_path.write_text(
        json.dumps({
            "test_window_years": result.test_window_years,
            "step_months": result.step_months,
            "n_windows": len(result.windows),
            "summary": result.summary,
            "windows": [
                {
                    "start": w.start_date, "end": w.end_date,
                    "metrics": w.metrics, "n_trades": w.n_trades,
                    "final_capital": w.final_capital,
                }
                for w in result.windows
            ],
        }, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
