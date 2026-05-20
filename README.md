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
6. **어닝 블랙아웃 필터** (D-7 이내 종목 자동 제외)
7. **펀더멘털 fetch** (P/E, EPS, sector, beta, market cap)
8. **자동 position sizing** (ATR 기반 추천 매수 수량 + 리스크 금액)
9. **분산도 점검** (상관 매트릭스, 섹터 노출, 포트폴리오 베타)
10. **뉴스 catalyst** (매수 후보 상위 종목 최근 72h 헤드라인)
11. 보유 종목별 매도 신호 점검 → 매도 검토 리스트
12. 보유 종목 손절선·익절선·손익률 갱신
13. Claude로 종합 해석 (regime/분산도/catalyst/펀더 종합)
14. `reports/YYYY-MM-DD.md` 마크다운 리포트 저장 + GitHub에 자동 commit

추가로 **백테스트 엔진** (`python -m src.backtest [--use-regime]`)으로 룰의 historical 효과 검증.

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
# 단일 기간 백테스트
python -m src.backtest --start 2020-01-01 --end 2024-12-31
python -m src.backtest --use-regime          # VIX/SP500 historical로 BEAR/RISK_OFF 차단

# Walk-forward (rolling out-of-sample) — over-fit 검출
python -m src.backtest.walkforward --test-years 1 --step-months 12

# 룰 파라미터 grid search
python -m src.backtest.optimize --criterion sharpe --top-n 20
```

결과는 `backtests/`에 마크다운+JSON으로 저장. Sharpe, max DD, win rate, profit factor 자동 계산. 통과 기준: [`docs/backtest.md`](docs/backtest.md).

## Paper trading 시뮬레이션

매일 추천을 가상 계좌에 실집행해 룰의 실시간 alpha 측정. 실거래에 영향 없음.

```bash
python -m src.papertrade --capital 100000 --top-n 3
```

state는 `paper_state.yaml`에 저장 (홀딩, 거래 이력, P&L). 매일 한 번 실행하면 누적.

## (옵션) Alpaca 데이터 fallback

yfinance 누락 종목을 Alpaca로 보완 (무료 IEX 데이터):

1. https://alpaca.markets/ 무료 가입
2. `.env`에 `ALPACA_API_KEY` / `ALPACA_SECRET` 추가
3. 자동 활성화 — yfinance 우선, 누락만 Alpaca 호출

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
- **신호 점수화 (0~100)**: 6요인 (RSI/MACD/거래량/추세/regime/macro) 가중합
- **어닝 블랙아웃**: 어닝 D-7 이내 신규 매수 차단
- **자동 sizing**: ATR 기반 정수 매수 수량 + 리스크 금액 자동 계산
- **분산도**: 상관 매트릭스 + 섹터 노출 + 포트폴리오 베타 + diversification score
- **catalyst**: 매수 후보 최근 72h 뉴스 자동 fetch (yfinance)
- **drawdown 가드**: 포트폴리오 current DD ≤ -15%면 신규 매수 자동 차단
- **walk-forward 백테스트**: rolling window로 over-fit 검출
- **paper trading**: 룰을 가상 계좌에 실집행해 실시간 alpha 측정
- **Alpaca fallback**: yfinance 누락 시 보완 (API key 등록 시 자동)
- **Multi-asset**: 채권/원자재/통화/해외주식 ETF + 자산 클래스별 노출 추적
- **ML regime**: KMeans 4-cluster (sklearn) + rule-based 비교
- **FRED 거시**: 실업률, CPI, 정책금리, 10Y-2Y spread (recession indicator)
- **Risk parity**: 보유 종목 inverse-volatility 권장 비중 + 리밸런스 추천
- **Grid search**: 룰 파라미터 grid 백테스트 (rsi_below × stop × target)

상세: [`docs/strategy.md`](docs/strategy.md), [`docs/backtest.md`](docs/backtest.md)

## 한계와 주의

- yfinance는 비공식 데이터 — 누락·지연 가능
- 백테스트 미포함, historical 수익률 보장 없음
- 거시/실적/뉴스 미반영 — Claude 해석 단계에서 일부 보완
- **자동 매매 아님** — 모든 주문은 사용자 직접 실행
- 페니주식·저유동성 종목 자동 제외 (config.yaml 필터)

## 면책

이 도구의 분석·추천은 **투자 자문이 아닙니다**. 매매 결정·실행·손익은 전적으로 사용자 책임입니다.
