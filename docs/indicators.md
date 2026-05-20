# 기술 지표 정의

모든 지표는 `src/indicators/technical.py`에 pandas로 직접 구현. 외부 ta 라이브러리 미사용.

## SMA (Simple Moving Average)

```
SMA_n = (P_t + P_t-1 + ... + P_t-n+1) / n
```

- **SMA(50)**: 단기 추세 — 이탈 시 매도 신호
- **SMA(200)**: 장기 추세 — 위에 있을 때만 매수

## EMA (Exponential Moving Average)

가중 평균. 최근 가격에 더 큰 가중치.

```
α = 2 / (n + 1)
EMA_t = α × P_t + (1 - α) × EMA_t-1
```

MACD 계산에 사용 (12, 26 기간).

## RSI (Relative Strength Index) — 14일

```
RS = (n일 평균 상승폭) / (n일 평균 하락폭)
RSI = 100 - 100 / (1 + RS)
```

- 0 ~ 100 범위
- < 30: 과매도 (반등 가능성)
- > 70: 과매수 (조정 가능성)
- 본 시스템: 매수 < 40, 매도 > 75 (보수적)

Wilder의 원본 방식: 첫 평균은 단순 평균, 이후는 지수 평활 (1/14 weight).

## MACD (Moving Average Convergence Divergence)

```
MACD line = EMA(12) - EMA(26)
Signal line = EMA(9 of MACD line)
Histogram = MACD - Signal
```

- 히스토그램 > 0: 상승 모멘텀
- 히스토그램이 음수에서 양수로 전환: 골든크로스
- 본 시스템: 히스토그램 양수 또는 직전 3봉 내 골든크로스 시 매수 조건 충족

## ATR (Average True Range) — 14일

변동성 측정. Wilder 정의.

```
TR_t = max(
  High_t - Low_t,
  |High_t - Close_t-1|,
  |Low_t - Close_t-1|
)
ATR_t = ((ATR_t-1 × 13) + TR_t) / 14
```

손절/익절선 계산의 기준. 변동성이 큰 종목은 자동으로 손절폭이 넓어짐.

## Bollinger Bands (참고용, 현재 미사용)

```
Middle = SMA(20)
Upper = Middle + 2 × StdDev(20)
Lower = Middle - 2 × StdDev(20)
```

향후 확장 시 변동성 squeeze 감지에 활용 가능.

## Volume Ratio

```
Volume Ratio = (최근 5일 평균 거래량) / (20일 평균 거래량)
```

> 1.2면 거래량 증가 — 추세 신호 신뢰도 ↑.

## 신호 우선순위

여러 지표가 동시에 가리킬 때:

1. **위험 우선**: 손절선 도달은 다른 모든 신호보다 우선.
2. **추세 우선**: SMA(200) 이탈 시 매수 신호 모두 무효.
3. **거래량 확인**: 거래량 없는 가격 움직임은 fake-out 가능성.

이 우선순위는 `src/screener/rules.py`에 코드로 반영.
