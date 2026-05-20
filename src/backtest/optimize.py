"""Grid search 룰 파라미터 튜닝.

핵심 파라미터의 합리적 범위에 대해 grid 백테스트. criterion 기준 정렬.
단일 기간 결과만 보지 말고 walk-forward로 over-fit 재검증할 것.
"""
from __future__ import annotations
import argparse
import copy
import itertools
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest.engine import run_backtest
from src.backtest.metrics import compute_metrics
from src.data.fetcher import fetch_history


@dataclass
class OptimizeResult:
    params: Dict[str, float]
    metrics: Dict[str, float]
    n_trades: int


def _set_nested(cfg: dict, path: str, value) -> None:
    """'buy.rsi_below' → cfg['buy']['rsi_below'] = value."""
    keys = path.split(".")
    obj = cfg
    for k in keys[:-1]:
        obj = obj[k]
    obj[keys[-1]] = value


def run_grid_search(
    history: Dict[str, pd.DataFrame],
    base_strategy_cfg: dict,
    param_grid: Dict[str, List],
    start_date=None,
    end_date=None,
    initial_capital: float = 100_000.0,
    max_positions: int = 10,
    slippage_pct: float = 0.001,
    max_hold_days: int = 60,
    verbose: bool = True,
) -> List[OptimizeResult]:
    keys = list(param_grid.keys())
    values_lists = [param_grid[k] for k in keys]
    combos = list(itertools.product(*values_lists))
    if verbose:
        print(f"[optimize] {len(combos)} combos")

    results: List[OptimizeResult] = []
    for i, combo in enumerate(combos):
        cfg = copy.deepcopy(base_strategy_cfg)
        params = {}
        for k, v in zip(keys, combo):
            _set_nested(cfg, k, v)
            params[k] = v
        try:
            result = run_backtest(
                history=history,
                strategy_cfg=cfg,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                max_positions=max_positions,
                slippage_pct=slippage_pct,
                max_hold_days=max_hold_days,
            )
            metrics = compute_metrics(result)
            results.append(OptimizeResult(
                params=params, metrics=metrics, n_trades=len(result.trades),
            ))
            if verbose:
                print(f"  [{i+1}/{len(combos)}] {params} → "
                      f"Sharpe {metrics.get('sharpe', 0):.2f}, "
                      f"PF {metrics.get('profit_factor', 0):.2f}, "
                      f"trades {len(result.trades)}")
        except Exception as e:
            if verbose:
                print(f"  [{i+1}/{len(combos)}] FAIL: {e}")
    return results


def rank_results(
    results: List[OptimizeResult],
    criterion: str = "sharpe",
    min_trades: int = 10,
) -> List[OptimizeResult]:
    filtered = [r for r in results if r.n_trades >= min_trades]
    return sorted(filtered, key=lambda r: -r.metrics.get(criterion, -float("inf")))


def format_optimize_report(
    results: List[OptimizeResult],
    criterion: str = "sharpe",
    top_n: int = 20,
    min_trades: int = 10,
) -> str:
    ranked = rank_results(results, criterion=criterion, min_trades=min_trades)
    lines = [
        f"# 룰 파라미터 grid search — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- 총 조합: {len(results)}",
        f"- 정렬: **{criterion}** (높을수록 좋음)",
        f"- 필터: 최소 {min_trades} trades",
        f"- 통과 조합: {len(ranked)}",
        "",
        "## Top 결과",
        "",
        "| 순위 | 파라미터 | Sharpe | Max DD% | Win% | PF | Return% | Trades |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(ranked[:top_n], 1):
        params_str = ", ".join(f"{k.split('.')[-1]}={v}" for k, v in r.params.items())
        m = r.metrics
        lines.append(
            f"| {i} | {params_str} | "
            f"{m.get('sharpe', 0):.2f} | "
            f"{m.get('max_drawdown_pct', 0):.2f}% | "
            f"{m.get('win_rate_pct', 0):.1f}% | "
            f"{m.get('profit_factor', 0):.2f} | "
            f"{m.get('total_return_pct', 0):+.2f}% | "
            f"{r.n_trades} |"
        )

    if ranked:
        best = ranked[0]
        lines += [
            "",
            "## 최적 조합 (적용 권장)",
            "",
            "```yaml",
            "strategy:",
        ]
        for k, v in best.params.items():
            parts = k.split(".")
            indent = "  " * len(parts)
            lines.append(f"  {parts[0]}:")
            for p in parts[1:-1]:
                indent_inner = "  " * (parts.index(p) + 2)
                lines.append(f"{indent_inner}{p}:")
            last_indent = "  " * (len(parts))
            lines.append(f"{last_indent}{parts[-1]}: {v}")
        lines += [
            "```",
            "",
            f"**주의**: 단일 기간 top → **over-fit 가능성 높음**.",
            "실전 적용 전 `python -m src.backtest.walkforward` 로 모든 window 통과 확인.",
            "최적 조합이 walk-forward에서 평균 이하 결과 내면 기본값 유지.",
        ]
    return "\n".join(lines)


DEFAULT_GRID = {
    "buy.rsi_below": [30, 35, 40, 45],
    "sell.stop_loss_atr_mult": [1.5, 2.0, 2.5],
    "sell.take_profit_atr_mult": [2.0, 3.0, 4.0],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="beingSmart 룰 파라미터 grid search")
    parser.add_argument("--start", help="YYYY-MM-DD")
    parser.add_argument("--end")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--days", type=int, default=1500)
    parser.add_argument("--criterion", default="sharpe",
                        choices=["sharpe", "profit_factor", "cagr_pct",
                                 "total_return_pct", "sortino"])
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--min-trades", type=int, default=10)
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    universe = yaml.safe_load((ROOT / "universe.yaml").read_text(encoding="utf-8"))
    tickers = sorted(set(
        (universe.get("etf") or [])
        + (universe.get("stocks") or [])
        + (universe.get("bonds") or [])
        + (universe.get("commodities") or [])
    ))

    print(f"[optimize] universe={len(tickers)}, downloading {args.days}d...")
    history = fetch_history(tickers, days=args.days)
    print(f"[optimize] loaded {len(history)} tickers")

    results = run_grid_search(
        history=history,
        base_strategy_cfg=config["strategy"],
        param_grid=DEFAULT_GRID,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
    )

    bt_dir = ROOT / "backtests"
    bt_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = bt_dir / f"optimize_{ts}.md"
    md_path.write_text(
        format_optimize_report(results, criterion=args.criterion,
                               top_n=args.top_n, min_trades=args.min_trades),
        encoding="utf-8",
    )
    json_path = bt_dir / f"optimize_{ts}.json"
    json_path.write_text(json.dumps(
        [{"params": r.params, "metrics": r.metrics, "n_trades": r.n_trades} for r in results],
        indent=2,
    ), encoding="utf-8")
    print(f"[optimize] saved: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
