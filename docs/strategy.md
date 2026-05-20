# 매매 전략

## 개요

beingSmart는 **추세 추종 + 평균 회귀** 하이브리드. 장기 상승 추세 안에서 단기 과매도 구간을 매수하고, 추세 이탈 또는 과매수 시 매도.

자동 주문 없음 — **모든 매매는 수동**.

## 매수 룰 (Long Entry)

다음을 **모두** 만족할 때 매수 후보:

1. **장기 추세 상승 중**: 종가 > 200일 SMA
2. **단기 과매도**: RSI(14) < 40
3. **MACD 회복**: MACD 히스토그램 양수 또는 직전 3봉 내 골든크로스
4. **거래량 확인**: 최근 5일 평균 거래량 > 20일 평균 × 1.2

→ 룰 통과 종목 중 RSI 낮은 순으로 상위 N개 추천.

### 진입가 / 손절선 / 익절선

- **진입가**: 다음 거래일 시가 (참고용)
- **손절선**: 진입가 − ATR(14) × 2
- **익절선**: 진입가 + ATR(14) × 3
- **포지션 크기**: (자본 × 0.02) ÷ (진입가 − 손절선) 주

리스크/리워드 = 1 : 1.5. 손절폭이 ATR로 동적 조정되어 종목별 변동성 반영.

## 매도 룰 (Exit)

보유 종목에 다음 중 **하나라도** 해당하면 매도 신호:

1. **과매수**: RSI(14) > 75
2. **추세 이탈**: 종가 < 50일 SMA
3. **손절선 도달**: 종가 ≤ 진입가 − ATR × 2
4. **익절선 도달**: 종가 ≥ 진입가 + ATR × 3
5. **안전망 손절**: 종가 ≤ 평단가 × 0.92 (−8%)

신호 발생 시 리포트에 "매도 검토" 표시. 실제 매도는 사용자 판단.

## 보유 (Hold)

매수·매도 신호 모두 없으면 **HOLD**. 다만 다음 정보는 매일 갱신:

- 현재가 vs 평단가 (손익률)
- 손절선 도달까지 남은 폭 (%)
- 익절선 도달까지 남은 폭 (%)
- 현재 RSI, MACD 상태

## 스크리닝 필터 (사전)

지표 계산 전 다음 종목 제외:

- 일평균 거래량 < 500,000주 (유동성 부족)
- 현재가 < $5 (페니주식 제외)
- 250일 데이터 부족 (신규 상장 등)

## 시장 regime 분류

매일 거시 변수로 시장 상태 판정. 룰의 active/inactive와 점수 multiplier 결정.

| Regime | 조건 (우선순위 순) | 매수 | 점수 ×factor |
|---|---|---|---:|
| 🟢 **BULL** | VIX < 20, S&P > SMA(200), breadth ≥ 0.4 | 풀 적용 | 1.00 |
| 🟡 **CHOPPY** | VIX 20~30 **또는** breadth < 0.4 | 보수 적용 | 0.70 |
| 🔴 **BEAR** | S&P < SMA(200) | 신규 진입 비활성 | 0.30 |
| ⚫ **RISK_OFF** | VIX > 30 **또는** S&P 5일 ≤ -7% | 모든 진입 disable | 0.00 |

분류 우선순위: RISK_OFF > BEAR > CHOPPY > BULL.
임계값은 [`config.yaml`](../config.yaml)의 `regime:` 섹션에서 조정.

## 신호 점수화 (0~100)

매수 룰을 통과한 종목에 가중합 점수. 점수 높은 순으로 추천. `min_score_threshold` (기본 40) 미만 자동 제외.

| 항목 | 기본 가중치 | 평가 |
|---|---:|---|
| RSI depth | 0.20 | 깊을수록 ↑ (20~40 구간 가중) |
| MACD 강도 | 0.15 | hist / price 비율 |
| 거래량 | 0.10 | 5일/20일 평균 ratio |
| SMA200 거리 | 0.15 | 0~5% sweet spot, 너무 멀면 감점 |
| Regime 정합성 | 0.25 | BULL=100, CHOPPY=55, BEAR=20, RISK_OFF=0 |
| 거시 안정성 (VIX) | 0.15 | VIX 낮을수록 ↑ |

가중치는 [`config.yaml`](../config.yaml)의 `scoring.weights`에서 수정.

## 어닝 블랙아웃

매수 신호 통과 종목 중 다음 어닝 발표가 **D-7 이내**면 신규 진입 제외. 이유:

- 어닝 surprise는 ±10~20% 갭으로 ATR 손절선 무력화
- 사전 정보 비대칭 (애널리스트·옵션 시장 vs 개인투자자)
- 룰의 historical edge가 어닝 직전 구간에선 무너지는 경우 많음

`config.yaml`의 `earnings.blackout_days`에서 조정. yfinance `get_earnings_dates`로 일자 fetch.

## Position sizing (자동)

매수 후보 추천 시 정수 단위 매수 수량 자동 계산:

```
risk_per_share = entry_price - stop_price
max_risk_dollar = capital × risk_per_trade
risk_based_shares = max_risk_dollar / risk_per_share

max_position_value = capital × max_position_pct
cap_based_shares = max_position_value / entry_price

shares = min(risk_based, cap_based)  # 보수적
```

| 파라미터 | 기본 | 의미 |
|---|---:|---|
| `risk_per_trade` | 0.02 | 트레이드당 자본의 2% 리스크 |
| `max_position_pct` | 0.15 | 단일 종목 최대 15% |

리포트에 "추천 N주 / 리스크 $X / R:R" 명시. 실거래 시 그대로 매수할 필요는 없고 참고용.

## 분산도 점검

매일 다음 자동 계산:

- **상관 매트릭스** (보유 + 매수 후보, 60일 일간 수익률)
- **섹터 노출** (시장가치 기준)
- **포트폴리오 베타** (보유 종목 가중평균)
- **diversification score** (0~100): 평균 상관과 최대 섹터 비중의 가중합

후보 종목이 보유 종목과 상관 > 0.7이면 표에 ⚠️ 표시. 단일 섹터 > 40%면 warning.

## 뉴스 catalyst

매수 후보 상위 N개에 대해 yfinance `Ticker.news`로 최근 72시간 헤드라인 fetch.
리포트에 종목별 링크와 발행 시간 표시. AI 해석 prompt에도 inject되어 종합 판단에 사용.

## Drawdown 가드

매일 portfolio equity를 `equity_history.yaml`에 누적. 다음 자동 계산:

- **current DD**: 최근 peak 대비 현재 손실
- **MTD DD**: 이번 달 시작 peak 대비 손실
- **YTD DD**: 이번 해 시작 peak 대비 손실
- **all-time max DD**

**자동 차단**: current DD ≤ `disable_entries_threshold_pct` (기본 -15%) 시 모든 신규 매수 차단.
DD 회복 후 자동 재개. 매도 신호는 계속 작동.

근거: drawdown 깊을수록 의사결정 품질 저하 + 회복까지 더 큰 수익률 필요 (예: -20% DD → 회복에 +25% 필요).

`config.yaml`의 `drawdown:` 섹션에서 임계 조정.

## 자료/근거

- **RSI**: Wilder, J. (1978). *New Concepts in Technical Trading Systems*.
- **MACD**: Appel, G. (1979). 12/26 EMA 조합 + 9 EMA 시그널.
- **ATR 기반 손절**: Wilder의 변동성 채널 접근. 한국에서는 "변동성 돌파 전략" 변형으로 알려짐.
- **추세 추종**: Faber, M. (2007). *A Quantitative Approach to Tactical Asset Allocation*. 200일선 위/아래로 진입/청산 단순화 모델의 효과 검증.

## 한계와 경고

- yfinance는 비공식 API. 데이터 누락·지연 가능.
- 백테스트 미포함 — 룰의 historical 수익은 검증되지 않음.
- 거시·뉴스·실적 발표 미반영 → Claude 해석 단계에서 일부 보완.
- 이 시스템은 **투자 조언이 아니다**. 모든 손익은 사용자 책임.
