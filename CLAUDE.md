# beingSmart — 프로젝트 가이드

미국 주식/ETF 데일리 추천 시스템. 룰 기반 스크리닝 + Claude 종합 판단.

## 1차 참조

- 전략 규칙: [`docs/strategy.md`](docs/strategy.md)
- 기술 지표 정의: [`docs/indicators.md`](docs/indicators.md)
- 매매 파라미터: [`config.yaml`](config.yaml) (SSoT)
- 보유 종목: [`portfolio.yaml`](portfolio.yaml) (SSoT)
- 감시 유니버스: [`universe.yaml`](universe.yaml) (SSoT)

## 폴더 구조

```
src/
├── data/
│   ├── fetcher.py       yfinance 일봉 다운로드
│   └── macro.py         거시 변수 (VIX, DXY, 금리, 금, 원유, 지수)
├── indicators/
│   └── technical.py     RSI, MACD, SMA, ATR (pandas 직접 계산)
├── regime/
│   └── classifier.py    BULL/CHOPPY/BEAR/RISK_OFF 분류 + buy modifier
├── screener/
│   ├── rules.py         매수/매도 룰 (config.yaml 기반)
│   └── scoring.py       매수 신호 0~100 점수화 (6요인 가중합)
├── portfolio/
│   └── manager.py       portfolio.yaml 로드, 손절선/익절선 계산
├── recommender/
│   └── ai.py            Claude API 종합 해석
├── report/
│   └── generator.py     마크다운 리포트 → reports/YYYY-MM-DD.md
└── backtest/
    ├── engine.py        historical OHLCV 시뮬레이션
    ├── metrics.py       Sharpe, max DD, profit factor 등
    └── __main__.py      python -m src.backtest CLI
```

## 실행 진입점

- 데일리 리포트: `python main.py`
- 백테스트: `python -m src.backtest [--start ...] [--end ...] [--capital ...]`

## 운영 원칙

- **수동 매매**: 시스템은 추천만, 자동 주문 없음. 모든 매수/매도는 Jin이 직접 broker에서.
- **portfolio.yaml 수동 동기화**: 매매 후 직접 수정.
- **데이터 출처**: yfinance (무료, 비공식 — 가끔 rate limit/missing data).
- **AI 폴백**: `ANTHROPIC_API_KEY` 없거나 `DISABLE_AI=true`면 룰 기반 결과만 출력.

## 코드 규칙

- 외부 ta 라이브러리 의존 금지 — 지표는 `src/indicators/technical.py`에 pandas로 직접 구현.
- 시크릿 (`.env`, API key) 절대 commit 금지. `.env.example`만.
- 리포트 (`reports/*.md`)는 commit. 이력 추적용.
- GitHub Actions가 자동 commit하는 봇 커밋만 main에 직접 push 허용.

## 절대 금지

- ❌ 자동 주문 실행 (broker API 연동 금지 — 추천만)
- ❌ 백테스트 결과를 미래 수익 보장처럼 표기
- ❌ portfolio.yaml에 실제 평단가/수량을 commit하기 전 한번 더 검토
