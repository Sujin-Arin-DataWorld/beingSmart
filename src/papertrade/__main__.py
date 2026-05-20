"""CLI: python -m src.papertrade

매일 한 번 실행. 룰을 가상 계좌에 실집행하고 P&L 누적.
state는 paper_state.yaml에 저장.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.papertrade.runner import run_papertrade


def main() -> int:
    parser = argparse.ArgumentParser(description="beingSmart paper trading")
    parser.add_argument("--capital", type=float, default=100_000.0,
                        help="첫 실행 시 초기 자본 (이후엔 무시)")
    parser.add_argument("--top-n", type=int, default=3,
                        help="매일 가상 매수 상위 N개")
    args = parser.parse_args()

    result = run_papertrade(ROOT, initial_capital=args.capital, top_n_buys=args.top_n)
    pnl = result["pnl"]

    print(f"[papertrade] regime={pnl['regime']}, candidates={pnl['candidates_count']}")
    print(f"[papertrade] today: buys={pnl['buys_today']}, sells={pnl['sells_today']}")
    print(f"[papertrade] equity ${pnl['total_equity']:,.2f} "
          f"({pnl['total_return_pct']:+.2f}%) | "
          f"cash ${pnl['cash']:,.0f}, holdings ${pnl['holding_value']:,.0f}")
    print(f"[papertrade] realized ${pnl['realized_pnl']:+,.2f}, "
          f"unrealized ${pnl['unrealized_pnl']:+,.2f}")
    print(f"[papertrade] state: {pnl['n_holdings']} holdings, {pnl['n_trades']} trades total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
