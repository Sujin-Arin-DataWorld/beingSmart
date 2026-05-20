"""마크다운 리포트 생성."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def generate_report(
    buy_signals: List[dict],
    sell_signals: List[dict],
    holdings_status: List[dict],
    cash_usd: float,
    ai_summary: Optional[str],
    config: dict,
) -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    strategy = config["strategy"]
    report_cfg = config["report"]

    lines = [
        f"# beingSmart 데일리 리포트 — {today}",
        "",
        "> **투자조언이 아닙니다.** 모든 매매 결정과 손익은 사용자 책임.",
        "",
    ]

    # 포트폴리오 요약
    total_market = sum(h["market_value"] for h in holdings_status)
    total_cost = sum(h["avg_cost"] * h["shares"] for h in holdings_status)
    total_pnl = total_market - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
    total_equity = total_market + cash_usd

    lines += [
        "## 포트폴리오 요약",
        "",
        f"- **총 자산**: ${total_equity:,.2f}",
        f"- **주식 평가액**: ${total_market:,.2f} ({total_pnl:+,.2f} / {total_pnl_pct:+.2f}%)",
        f"- **현금**: ${cash_usd:,.2f}",
        "",
    ]

    if ai_summary:
        lines += ["## AI 종합 해석", "", ai_summary, ""]

    # 매도 검토
    lines += ["## 매도 검토 신호", ""]
    if sell_signals:
        lines += ["| 티커 | 현재가 | RSI | 사유 |", "|---|---:|---:|---|"]
        for s in sell_signals:
            lines.append(
                f"| {s['ticker']} | ${s['price']:.2f} | {s['rsi']:.1f} | "
                f"{'; '.join(s['reasons'])} |"
            )
    else:
        lines.append("매도 신호 없음. 모든 보유 종목 정상 범위 안.")
    lines.append("")

    # 보유 종목 상세
    lines += ["## 보유 종목 상세", ""]
    if holdings_status:
        lines += [
            "| 티커 | 수량 | 평단 | 현재 | 손익% | 손절선 | 익절선 | 손절까지 | 익절까지 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for h in holdings_status:
            lines.append(
                f"| {h['ticker']} | {h['shares']:g} | "
                f"${h['avg_cost']:.2f} | ${h['current_price']:.2f} | "
                f"{h['pnl_pct']:+.2f}% | "
                f"${h['effective_stop']:.2f} | ${h['target_atr']:.2f} | "
                f"{h['distance_to_stop_pct']:+.2f}% | "
                f"{h['distance_to_target_pct']:+.2f}% |"
            )
    else:
        lines.append("보유 종목 없음.")
    lines.append("")

    # 매수 후보
    lines += ["## 매수 후보 (룰 통과)", ""]
    top_n = report_cfg["top_n_recommendations"]
    top_buys = sorted(buy_signals, key=lambda x: x["rsi"])[:top_n]
    if top_buys:
        lines += [
            "| 티커 | 가격 | RSI | 손절선 | 목표가 | 거래량 | 근거 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        for b in top_buys:
            lines.append(
                f"| {b['ticker']} | ${b['price']:.2f} | {b['rsi']:.1f} | "
                f"${b['suggested_stop']:.2f} | ${b['suggested_target']:.2f} | "
                f"{b['vol_ratio']:.2f}x | {'; '.join(b['reasons'])} |"
            )
    else:
        lines.append("오늘 매수 룰을 만족하는 종목 없음.")
    lines.append("")

    # 적용 설정
    buy = strategy["buy"]
    sell = strategy["sell"]
    lines += [
        "## 적용 설정",
        "",
        f"- 매수 조건: RSI < {buy['rsi_below']}, 종가 > SMA(200), "
        f"MACD 양전환, 거래량 ≥ {buy['min_volume_ratio']}x",
        f"- 매도 조건: RSI > {sell['rsi_above']}, SMA(50) 이탈, "
        f"ATR×{sell['stop_loss_atr_mult']} 손절, ATR×{sell['take_profit_atr_mult']} 익절, "
        f"평단가 ×{sell['break_below_avg_cost_mult']} 안전망",
        "",
    ]
    return "\n".join(lines)


def save_report(content: str, reports_dir: Path) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    path = reports_dir / f"{today}.md"
    path.write_text(content, encoding="utf-8")
    (reports_dir / "latest.md").write_text(content, encoding="utf-8")
    return path
