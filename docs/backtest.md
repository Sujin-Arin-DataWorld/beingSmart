# 백테스트

룰의 historical 효과 검증. **실거래 전 반드시** 백테스트로 sanity check.

## 사용법

```bash
python -m src.backtest --start 2020-01-01 --end 2024-12-31 --capital 100000
```

옵션:

| 옵션 | 기본 | 설명 |
|---|---|---|
| `--start YYYY-MM-DD` | 자동 | 시작일 |
| `--end YYYY-MM-DD` | 자동 | 종료일 |
| `--capital N` | 100000 | 초기 자본 ($) |
| `--days N` | 1500 | 다운로드 영업일 (≈6년) |
| `--max-positions N` | 10 | 최대 동시 보유 종목 |
| `--slippage F` | 0.001 | 편도 슬리피지 (0.001 = 0.1%) |
| `--max-hold N` | 60 | 최대 보유 영업일 |

## 결과 위치

`backtests/YYYY-MM-DD_HHMMSS.md` (사람용) + `.json` (회귀 테스트용).

## 지표 정의 + 판단 기준

| 지표 | 의미 | 양호 기준 |
|---|---|---|
| `total_return_pct` | 기간 누적 수익률 | — |
| `cagr_pct` | 연복리 수익률 (CAGR) | S&P 장기 평균(8~10%) 대비 |
| `sharpe` | 변동성 조정 수익 | **> 1.0 양호, > 2.0 우수** |
| `sortino` | 하방 변동성만 기준 | > 1.5 양호 |
| `max_drawdown_pct` | 최대 평가손 (peak → trough) | **> -25% 실전 견딤** |
| `n_trades` | 전체 트레이드 수 | 너무 적으면 통계 무의미 (≥ 30 권장) |
| `win_rate_pct` | 이긴 트레이드 비율 | 추세 추종은 30~50%가 정상 |
| `avg_win_pct` / `avg_loss_pct` | 평균 승/패 수익률 | abs(win/loss) ≥ 1.5 |
| `profit_factor` | 총이익 / 총손실 | **> 1.5 양호, > 2.0 우수** |
| `expectancy_pct` | 트레이드당 기대값 (%) | **> 0** 이면 룰 유효 |
| `avg_bars_held` | 평균 보유 기간 | 너무 짧으면 노이즈, 너무 길면 효율 저하 |

## 시뮬레이션 가정 (현재 버전)

- **진입가**: 신호 발생 **다음** 거래일 시가 (look-ahead 방지) + 슬리피지
- **청산가**: 매도 신호 같은 날 종가 − 슬리피지
- **Position size**: 현재 equity / max_positions (균등 분할)
- **Commission**: 0 (미국 무료 가정) — 향후 옵션 추가 가능
- **배당**: 미반영. yfinance `auto_adjust=True`로 split만 처리
- **워밍업**: 첫 200일은 시뮬레이션 제외 (SMA200 안정화)
- **데이터 누락 종목**: 그 종목만 skip, 시뮬레이션 계속
- **단일 시장**: 미국만

## 현재 미통합 (다음 phase)

- regime 분류기 / 신호 점수화는 데일리 리포트에는 통합됐지만 **백테스트에는 아직 미적용** (단순 RSI 정렬 진입). 통합 시 결과 분리해서 비교.
- earning 직전 진입 제외 (펀더멘털 미통합)
- 거래량 spike 가중치

## 권장 검증 절차

1. **베이스라인**: `python -m src.backtest --days 1500` (5~6년 전체)
2. **out-of-sample**: 최근 1년만 따로 (`--start 2024-01-01 --end 2024-12-31`)로 over-fit 점검
3. **민감도 분석**: `config.yaml`의 `rsi_below`를 35/40/45로 바꿔가며 결과 차이
4. **regime 분리** (수동): BULL/BEAR 기간을 따로 돌려 룰이 모든 시장에서 동작하는지

## 통과 기준

다음 4개 동시 만족 못하면 **실전 금지**:

- Sharpe > 1.0
- Max DD > -25% (값 자체는 음수)
- Profit factor > 1.5
- n_trades ≥ 30

## 한계 — 솔직히

- yfinance 데이터는 무료/비공식. corporate action 누락 가능.
- Survivorship bias: universe.yaml에 현재 살아있는 종목만 — 상장폐지된 종목 없음.
- Look-ahead 가능성: enriched 데이터 indexer 실수 시 미래 정보 새어들 수 있음. 코드 리뷰 권장.
- Out-of-sample 부족: 6년 데이터는 1.5~2개 시장 사이클만 포함. 더 넓은 historical은 별도 데이터 소스.

## 결과 해석 예시

```
Sharpe 1.45 / Max DD -18.2% / Win 42% / PF 1.8
→ 통과. 실전 deploy 후보.

Sharpe 0.7 / Max DD -32% / Win 38% / PF 1.2
→ DD 너무 큼. position size 줄이거나 룰 보강.

Sharpe 2.1 / Max DD -8% / Win 75% / PF 4.5 (n_trades = 8)
→ 너무 좋은 결과 + 트레이드 부족 = over-fit 의심. 다른 기간으로 재검증.
```

## Walk-forward (rolling out-of-sample)

단일 기간 백테스트는 over-fit 위험 — 룰이 특정 시기에만 잘 작동했을 수도. Walk-forward는 매 step마다 window를 굴려 robustness 검증:

```bash
python -m src.backtest.walkforward --test-years 1 --step-months 12 --days 2000
```

옵션:
- `--test-years 1`: 각 window 1년
- `--step-months 12`: 1년씩 굴림 (겹침 없음)
- `--days 2000`: 다운로드 영업일 (≈8년)

### 통과 기준 (Walk-forward)

| 지표 | 양호 |
|---|---|
| 모든 window Sharpe > 0 | 최소 조건 |
| Sharpe 평균 > 1.0, std < 0.5 | 일관적 alpha |
| 모든 window Profit factor > 1.0 | 룰 자체 손실 안 봄 |
| Max DD 평균 > -25%, min > -35% | 실전 견딜 수 있음 |

**모든 window 양호 = 룰이 시기/regime에 무관하게 안정** → 실전 deploy 후보.
**일부 window만 양호 = regime 의존** → Tier 1 regime 필터 조합 권장.
**대부분 window 부진 = 룰 자체 실패** → 파라미터 재검토 또는 룰 변경.

### `--use-regime`과의 조합

단일 백테스트는 `--use-regime`으로 비교 가능. walk-forward는 현재 미통합 (다음 phase). 수동으로 BULL/BEAR 기간을 따로 walk-forward 돌려 비교.
