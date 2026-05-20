"""Claude API 종합 해석. Tier 2 컨텍스트 (regime, 분산도, 뉴스, 펀더멘털) 통합."""
from __future__ import annotations
import os
from typing import Dict, List, Optional


def get_ai_summary(
    buy_signals: List[dict],
    sell_signals: List[dict],
    holdings_status: List[dict],
    context: Optional[Dict] = None,
) -> Optional[str]:
    if os.environ.get("DISABLE_AI", "").lower() == "true":
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    client = Anthropic(api_key=api_key)
    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    prompt = _build_prompt(buy_signals, sell_signals, holdings_status, context or {})

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in resp.content if hasattr(b, "text")]
        return "\n".join(parts) if parts else None
    except Exception as e:
        return f"[AI 해석 실패: {e}]"


def _build_prompt(
    buys: List[dict],
    sells: List[dict],
    status: List[dict],
    ctx: Dict,
) -> str:
    lines = [
        "당신은 보수적인 미국 주식 투자 어드바이저입니다.",
        "데일리 룰 기반 스크리너 + 거시/펀더멘털/catalyst 데이터를 받아 종합 해석을 한국어로 작성해주세요.",
        "",
    ]

    # === 시장 상태 ===
    regime = ctx.get("regime")
    regime_reasons = ctx.get("regime_reasons") or []
    if regime:
        lines.append(f"## 시장 regime: **{regime}**")
        for r in regime_reasons:
            lines.append(f"- {r}")
        lines.append("")

    # === 보유 + 분산도 ===
    lines.append("## 보유 종목 현황")
    if status:
        for s in status:
            sec = s.get("sector") or "-"
            lines.append(
                f"- {s['ticker']} ({sec}): {s['shares']:g}주, 평단 ${s['avg_cost']:.2f}, "
                f"현재 ${s['current_price']:.2f} ({s['pnl_pct']:+.2f}%), "
                f"손절 ${s['effective_stop']:.2f}, 목표 ${s['target_atr']:.2f}"
            )
    else:
        lines.append("- 없음")
    lines.append("")

    div = ctx.get("diversification")
    if div:
        lines.append(
            f"분산도: total={div['total']}/100, 평균 상관={div.get('avg_correlation')}, "
            f"최대 섹터={div['max_sector_pct']}%"
        )
    sec_exp = ctx.get("sector_exposure") or {}
    if sec_exp:
        sec_str = ", ".join(f"{k}={v * 100:.1f}%" for k, v in sec_exp.items())
        lines.append(f"섹터 노출: {sec_str}")
    beta = ctx.get("portfolio_beta")
    if beta is not None:
        lines.append(f"포트폴리오 베타: {beta:.2f}")
    lines.append("")

    # === 매수 후보 ===
    lines.append("## 매수 후보 (점수 순, 룰+점수 통과)")
    if buys:
        funds = ctx.get("fundamentals") or {}
        news = ctx.get("news") or {}
        for b in buys[:10]:
            t = b["ticker"]
            score = b.get("score", 0)
            sz = b.get("sizing") or {}
            shares = sz.get("shares", 0)
            risk = sz.get("risk_amount", 0)
            d2e = b.get("days_to_earnings")
            d2e_str = f", 어닝 D-{d2e}" if d2e is not None else ""
            corr = b.get("corr_with_holdings")
            corr_str = f", 보유상관 {corr:.2f}" if corr is not None else ""

            line = (
                f"- **{t}** (점수 {score:.1f}): ${b['price']:.2f}, RSI {b['rsi']:.1f}, "
                f"손절 ${b['suggested_stop']:.2f}, 목표 ${b['suggested_target']:.2f}, "
                f"추천 {shares}주 (리스크 ${risk:.0f}){d2e_str}{corr_str}"
            )
            lines.append(line)

            f = funds.get(t) or {}
            pe = f.get("trailing_pe") or f.get("forward_pe")
            mcap = f.get("market_cap")
            if pe or mcap:
                fund_parts = []
                if f.get("sector"):
                    fund_parts.append(f"sector={f['sector']}")
                if pe:
                    fund_parts.append(f"PE={pe:.1f}")
                if mcap:
                    fund_parts.append(f"mcap=${mcap / 1e9:.1f}B")
                if f.get("beta") is not None:
                    fund_parts.append(f"beta={f['beta']:.2f}")
                lines.append(f"  - fundamentals: {', '.join(fund_parts)}")

            if t in news and news[t]:
                lines.append(f"  - 최근 뉴스 ({len(news[t])}건):")
                for n in news[t][:3]:
                    lines.append(f"    - [{n['hours_ago']}h] {n['title']}")
    else:
        lines.append("- 없음")
    lines.append("")

    # === 매도 검토 ===
    lines.append("## 매도 검토 신호")
    if sells:
        for s in sells:
            lines.append(f"- {s['ticker']}: ${s['price']:.2f} | {', '.join(s['reasons'])}")
    else:
        lines.append("- 없음")
    lines.append("")

    # === 요청 ===
    lines += [
        "## 요청",
        "다음 네 가지를 간결하게 작성해주세요:",
        "",
        "1. **오늘의 한 줄 요약** — 시장 톤(공격/방어), regime 기반 행동 지침, 주의할 점",
        "2. **포트폴리오 진단** — 분산도/섹터 집중/베타 관점에서 약점 1-2가지",
        "3. **포지션 액션** — 보유 종목별 보유/일부매도/전량매도 의견과 1-2문장 근거",
        "4. **신규 진입 우선순위** — 매수 후보 Top 3 (점수·R:R·catalyst·펀더 종합), 각 짧은 근거",
        "",
        "원칙: ",
        "- 룰 점수만 맹신하지 말고 catalyst/펀더멘털을 함께 고려",
        "- 보유 종목과 상관 높은 후보는 분산 효과 없으므로 우선순위 ↓",
        "- 어닝 임박(D-7) 종목은 별도 표시",
        "- 투자조언이 아님을 명시하고, 사용자가 직접 뉴스·실적·거시 일정 확인할 것을 환기",
    ]
    return "\n".join(lines)
