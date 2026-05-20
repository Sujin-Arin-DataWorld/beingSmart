"""Claude API로 종합 해석. API key 없으면 None 반환."""
from __future__ import annotations
import os
from typing import List, Optional


def get_ai_summary(
    buy_signals: List[dict],
    sell_signals: List[dict],
    holdings_status: List[dict],
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
    prompt = _build_prompt(buy_signals, sell_signals, holdings_status)

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in resp.content if hasattr(b, "text")]
        return "\n".join(parts) if parts else None
    except Exception as e:
        return f"[AI 해석 실패: {e}]"


def _build_prompt(buys: List[dict], sells: List[dict], status: List[dict]) -> str:
    lines = [
        "당신은 보수적인 미국 주식 투자 어드바이저입니다.",
        "데일리 룰 기반 스크리너 결과를 받아 종합 해석을 한국어로 작성해주세요.",
        "",
        "## 보유 종목 현황",
    ]
    if status:
        for s in status:
            lines.append(
                f"- {s['ticker']}: {s['shares']:g}주, 평단 ${s['avg_cost']:.2f}, "
                f"현재 ${s['current_price']:.2f} ({s['pnl_pct']:+.2f}%), "
                f"손절선 ${s['effective_stop']:.2f}, 목표 ${s['target_atr']:.2f}"
            )
    else:
        lines.append("- 없음")

    lines += ["", "## 매수 후보 (룰 통과)"]
    if buys:
        for b in buys[:10]:
            lines.append(
                f"- {b['ticker']}: ${b['price']:.2f}, RSI {b['rsi']:.1f}, "
                f"손절 ${b['suggested_stop']:.2f}, 목표 ${b['suggested_target']:.2f} | "
                f"{', '.join(b['reasons'])}"
            )
    else:
        lines.append("- 없음")

    lines += ["", "## 매도 검토 신호 발생"]
    if sells:
        for s in sells:
            lines.append(f"- {s['ticker']}: ${s['price']:.2f} | {', '.join(s['reasons'])}")
    else:
        lines.append("- 없음")

    lines += [
        "",
        "## 요청",
        "다음 세 가지를 간결하게 작성해주세요:",
        "",
        "1. **오늘의 한 줄 요약** — 시장 톤(공격/방어), 주의할 점",
        "2. **포지션 액션** — 보유 종목별로 보유/일부매도/전량매도 의견과 1-2문장 근거",
        "3. **신규 진입 우선순위** — 매수 후보 중 Top 3, 각 종목 짧은 근거",
        "",
        "투자조언이 아님을 명시. 룰만으로 판단 말고 거시·실적 일정·뉴스도 직접 확인할 것을 환기.",
    ]
    return "\n".join(lines)
