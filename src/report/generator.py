"""마크다운 리포트 생성. macro / regime / score 통합."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


def generate_report(
    buy_signals: List[dict],
    sell_signals: List[dict],
    holdings_status: List[dict],
    cash_usd: float,
    ai_summary: Optional[str],
    config: dict,
    macro: Optional[Dict[str, Dict]] = None,
    regime: Optional[Any] = None,           # RegimeAssessment
    breadth: Optional[float] = None,
) -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    strategy = config["strategy"]
    report_cfg = config["report"]

    lines = [
        f"# beingSmart 데일리 리포트 — {today}",
        "",
        "> **투자조언이 아닙니다.** 매매 결정·실행·손익은 사용자 책임.",
        "",
    ]

    # === 시장 regime ===
    if regime is not None:
        regime_name = regime.regime.value
        emoji = {"BULL": "🟢", "CHOPPY": "🟡", "BEAR": "🔴", "RISK_OFF": "⚫"}.get(regime_name, "")
        lines += [
            f"## 시장 상태 — {emoji} **{regime_name}**",
            "",
        ]
        for r in regime.reasons:
            lines.append(f"- {r}")
        if breadth is not None:
            lines.append(f"- breadth (advance/total): {breadth:.2f}")
        lines.append("")

    # === 거시 dashboard ===
    if macro:
        lines += ["## 거시 변수 스냅샷", "", "| 자산 | 현재가 | 1일 | 5일 | 20일 | 200SMA 위 |", "|---|---:|---:|---:|---:|:---:|"]
        order = ["VIX", "SP500", "DOW", "NASDAQ", "DXY", "Y10", "Y30", "GOLD", "OIL"]
        for k in order:
            if k not in macro:
                continue
            m = macro[k]
            above = "✓" if m["above_sma_200"] else "✗"
            lines.append(
                f"| {k} ({m['ticker']}) | {m['price']:,.2f} | "
                f"{m['change_1d_pct']:+.2f}% | {m['change_5d_pct']:+.2f}% | "
                f"{m['change_20d_pct']:+.2f}% | {above} |"
            )
        lines.append("")

    # === 포트폴리오 요약 ===
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

    # === 매도 검토 ===
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

    # === 보유 종목 상세 ===
    lines += ["## 보유 종목 상세", ""]
    if holdings_status:
        lines += [
            "| 티커 | 수량 | 평단 | 현재 | 손익% | 손절선 | 익절선 | 손절거리 | 익절거리 |",
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

    # === 매수 후보 (점수 순) ===
    lines += ["## 매수 후보 (점수 순)", ""]
    top_n = report_cfg["top_n_recommendations"]
    has_score = bool(buy_signals) and "score" in buy_signals[0]
    top_buys = buy_signals[:top_n]
    if top_buys:
        if has_score:
            lines += [
                "| 티커 | 점수 | 가격 | RSI | 손절선 | 목표가 | 거래량 | 근거 |",
                "|---|---:|---:|---:|---:|---:|---:|---|",
            ]
            for b in top_buys:
                lines.append(
                    f"| {b['ticker']} | **{b['score']:.1f}** | "
                    f"${b['price']:.2f} | {b['rsi']:.1f} | "
                    f"${b['suggested_stop']:.2f} | ${b['suggested_target']:.2f} | "
                    f"{b['vol_ratio']:.2f}x | {'; '.join(b['reasons'])} |"
                )
        else:
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

        # 1등 종목 점수 breakdown
        if has_score and "score_breakdown" in top_buys[0]:
            bd = top_buys[0]["score_breakdown"]
            lines += [
                "",
                f"### 1위 {top_buys[0]['ticker']} 점수 breakdown",
                "",
                f"- RSI depth: {bd['rsi']:.1f}",
                f"- MACD 강도: {bd['macd']:.1f}",
                f"- 거래량: {bd['volume']:.1f}",
                f"- SMA200 거리: {bd['trend']:.1f}",
                f"- regime 정합성: {bd['regime']:.1f}",
                f"- 거시 안정성: {bd['macro']:.1f}",
                f"- **종합: {bd['total']:.1f}**",
            ]
    else:
        lines.append("오늘 매수 룰 + 점수 임계치를 만족하는 종목 없음.")
    lines.append("")

    # === 적용 설정 ===
    buy = strategy["buy"]
    sell = strategy["sell"]
    lines += [
        "## 적용 설정",
        "",
        f"- 매수: RSI < {buy['rsi_below']}, 종가 > SMA(200), "
        f"MACD 양전환, 거래량 ≥ {buy['min_volume_ratio']}x",
        f"- 매도: RSI > {sell['rsi_above']}, SMA(50) 이탈, "
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
