# beingSmart

미국 주식/ETF 데일리 매매 추천 시스템.
**룰 기반 스크리닝 + Claude 종합 해석** 으로 매일 자동 리포트 생성.

> 투자조언이 아닙니다. 모든 매매와 손익은 사용자 책임입니다.

## 무엇을 하는가

매 영업일(미국 장 마감 후) 자동으로:

1. 감시 유니버스(ETF + 대형주) 전체 일봉 데이터 수집 (yfinance)
2. 거시 변수 스냅샷 (VIX, DXY, 10Y/30Y, 금, 원유, 3대 지수)
3. 기술 지표 계산 (SMA, RSI, MACD, ATR, Volume Ratio)
4. **시장 regime 분류** (BULL/CHOPPY/BEAR/RISK_OFF)
5. 매수 룰 적용 → **신호 점수화 (0~100)** → 신규 진입 후보 추출
6. 보유 종목별 매도 신호 점검 → **매도 검토 리스트**
7. 보유 종목 손절선·익절선·손익률 갱신
8. Claude로 종합 해석 (포지션 액션, 우선순위)
9. `reports/YYYY-MM-DD.md` 마크다운 리포트 저장 + GitHub에 자동 commit

추가로 **백테스트 엔진** (`python -m src.backtest`)으로 룰의 historical 효과 검증.

## 폴더 구조

```
beingSmart/
├── config.yaml          # 전략 파라미터 (SSoT)
├── portfolio.yaml       # 보유 종목 (직접 수정)
├── universe.yaml        # 감시 종목 리스트
├── main.py              # 진입점
├── src/
│   ├── data/            # yfinance 다운로드
│   ├── indicators/      # 지표 계산
│   ├── screener/        # 매수·매도 룰
│   ├── portfolio/       # 보유 현황·손절선
│   ├── recommender/     # Claude API 해석
│   └── report/          # 마크다운 리포트
├── reports/             # 일자별 리포트 (자동 commit)
├── docs/
│   ├── strategy.md      # 매매 룰 상세
│   └── indicators.md    # 지표 정의
└── .github/workflows/daily.yml
```

## 빠른 시작 (로컬)

```bash
git clone https://github.com/Sujin-Arin-DataWorld/beingSmart.git
cd beingSmart

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# AI 해석을 사용할 경우:
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력

# 보유 종목 입력
$EDITOR portfolio.yaml

# 실행
python main.py

# 결과 확인
open reports/latest.md
```

`ANTHROPIC_API_KEY` 없이도 동작 — 룰 기반 결과만 출력됩니다.

## GitHub Actions 자동 실행 설정

### 1. Secrets 등록

GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:

| 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |

### 2. 워크플로 활성화

[`.github/workflows/daily.yml`](.github/workflows/daily.yml)이 평일 **22:30 UTC** (NY 장 마감 후 2시간)에 자동 실행됩니다.

수동 실행: GitHub repo → **Actions → Daily Report → Run workflow**.

### 3. 결과 확인

- 봇이 `reports/YYYY-MM-DD.md`를 자동 commit
- `reports/latest.md`는 항상 최신 리포트의 사본

## 백테스트로 룰 검증

실거래 적용 전 historical 효과 확인:

```bash
python -m src.backtest --start 2020-01-01 --end 2024-12-31
```

결과는 `backtests/YYYY-MM-DD_HHMMSS.md`에 저장. Sharpe, max DD, win rate, profit factor 등 자동 계산. 통과 기준과 해석: [`docs/backtest.md`](docs/backtest.md).

## 매매 후 portfolio.yaml 동기화

자동 주문 없음. 매수/매도는 본인 broker에서 직접 실행 후 `portfolio.yaml` 수동 갱신:

```yaml
cash_usd: 8500.00          # 매수 시 차감, 매도 시 증액

holdings:
  - ticker: NVDA           # 새로 매수한 종목 추가
    shares: 3
    avg_cost: 425.10
    purchase_date: 2026-05-20

  # - ticker: AAPL         # 매도한 종목 삭제 또는 주석
  #   shares: 10
  #   ...
```

## 전략 요약

- **매수 룰**: 종가 > SMA(200), RSI < 40, MACD 양전환, 거래량 ≥ 1.2x
- **매도 룰**: RSI > 75, SMA(50) 이탈, ATR×2 손절, ATR×3 익절, 평단가 -8% 안전망
- **시장 regime**: VIX + S&P 200SMA + breadth → BULL/CHOPPY/BEAR/RISK_OFF
- **신호 점수화 (0~100)**: 룰 통과 종목 가중합, threshold 이상만 추천
- **거시 dashboard**: VIX, DXY, 10Y/30Y, 금, 원유, 3대 지수 매일 갱신

상세: [`docs/strategy.md`](docs/strategy.md), [`docs/backtest.md`](docs/backtest.md)

## 한계와 주의

- yfinance는 비공식 데이터 — 누락·지연 가능
- 백테스트 미포함, historical 수익률 보장 없음
- 거시/실적/뉴스 미반영 — Claude 해석 단계에서 일부 보완
- **자동 매매 아님** — 모든 주문은 사용자 직접 실행
- 페니주식·저유동성 종목 자동 제외 (config.yaml 필터)

## 면책

이 도구의 분석·추천은 **투자 자문이 아닙니다**. 매매 결정·실행·손익은 전적으로 사용자 책임입니다.
