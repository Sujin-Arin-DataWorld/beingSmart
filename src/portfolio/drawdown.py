"""포트폴리오 drawdown 추적.

매일 main.py 실행 시 현재 equity를 equity_history.yaml에 누적.
MTD/YTD/all-time DD 계산. 임계 초과 시 신규 진입 disable.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def load_equity_history(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return data if isinstance(data, list) else []


def save_equity_history(path: Path, history: List[Dict]) -> None:
    path.write_text(yaml.safe_dump(history, default_flow_style=False), encoding="utf-8")


def append_equity_point(path: Path, today_str: str, equity: float) -> None:
    """오늘 equity 기록. 같은 날짜 있으면 덮어쓰기."""
    history = load_equity_history(path)
    for entry in history:
        if entry.get("date") == today_str:
            entry["equity"] = float(equity)
            history.sort(key=lambda x: x.get("date", ""))
            save_equity_history(path, history)
            return
    history.append({"date": today_str, "equity": float(equity)})
    history.sort(key=lambda x: x.get("date", ""))
    save_equity_history(path, history)


def compute_drawdowns(history: List[Dict]) -> Optional[Dict]:
    """MTD, YTD, all-time DD + current DD."""
    if not history:
        return None
    valid = [(e["date"], float(e["equity"])) for e in history
             if "date" in e and "equity" in e]
    if not valid:
        return None
    valid.sort()
    dates = [datetime.fromisoformat(d) for d, _ in valid]
    equities = [eq for _, eq in valid]

    running_max = -float("inf")
    cummax: List[float] = []
    for v in equities:
        running_max = max(running_max, v)
        cummax.append(running_max)
    dds = [(e - c) / c if c > 0 else 0.0 for e, c in zip(equities, cummax)]

    current_dd = dds[-1]
    max_dd = min(dds)

    today = dates[-1]
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    def _window_dd(start_dt) -> float:
        window = [(d, e) for d, e in zip(dates, equities) if d >= start_dt]
        if not window:
            return 0.0
        ws_equities = [e for _, e in window]
        ws_max = max(ws_equities)
        if ws_max <= 0:
            return 0.0
        return (window[-1][1] - ws_max) / ws_max

    return {
        "current_dd_pct": round(current_dd * 100, 2),
        "max_dd_pct": round(max_dd * 100, 2),
        "mtd_dd_pct": round(_window_dd(month_start) * 100, 2),
        "ytd_dd_pct": round(_window_dd(year_start) * 100, 2),
        "n_records": len(valid),
        "first_date": valid[0][0],
        "last_date": valid[-1][0],
    }


def should_disable_new_entries(
    dd_metrics: Optional[Dict],
    threshold_pct: float = -15.0,
) -> bool:
    """current DD이 임계치 이하면 True (신규 진입 disable)."""
    if dd_metrics is None:
        return False
    return dd_metrics["current_dd_pct"] <= threshold_pct
