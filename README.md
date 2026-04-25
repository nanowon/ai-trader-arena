# ai-trader-arena

AI 주식 투자 에이전트 경쟁 플랫폼. 4개의 서로 다른 투자 전략 에이전트가 동일한 초기 자본($100,000)으로 실제 시장 데이터를 기반으로 포트폴리오를 운용하고, 일별 퍼포먼스를 SQLite에 누적 기록하며 GitHub Pages로 시각화합니다. Discord 및 이메일 알림을 지원합니다.

## 4 에이전트

| 에이전트 | 전략 요약 |
|---------|---------|
| Aggressive | 고변동성/고베타 종목 집중, 높은 회전율 |
| Balanced | 팩터 균형(모멘텀 + 퀄리티 + 밸류) |
| Conservative | 저변동성/배당 중심, 낮은 회전율 |
| ETF-Only | 섹터 ETF만 사용한 패시브 로테이션 |

벤치마크: SPY

## Phase 로드맵

- **Phase 0** ✅: 저장소 스켈레톤, CI skeleton, pyproject 구성
- **Phase 1** ✅: 4 에이전트 전략 로직 구현 + 단위 테스트
- **Phase 2** ✅: DB 스키마, daily orchestrator, legacy 마이그레이션, 실제 체결·포트폴리오 로직
- **Phase 3** ✅: 분석 메트릭(샤프/드로다운/팩터 기여), ETF-Only 전략 완성
- **Phase 4** ✅: 웹 대시보드 정적 사이트(Jinja2 + Plotly.js) 빌드
- **Phase 5** ✅: Discord·이메일 알림 시스템
- **Phase 6** ✅: 주간 리뷰, commentary, DB 백업
- **Phase 7** 🚧: GitHub Actions 자동화 배포 (일별 파이프라인 + Pages)
- **Phase 8+**: 백테스트, 전략 튜닝, 추가 에이전트

## 빠른 시작

```bash
pip install -e ".[dev]"
arena run-daily
arena build-web
arena notify --all
arena backup
```

## GitHub 설정

### 1. 저장소 생성

```bash
gh repo create ai-trader-arena --private --source=. --remote=origin --push
```

### 2. Secrets 설정

저장소 Settings → Secrets and variables → Actions에서 아래 항목을 등록합니다.

| Secret | 설명 | 필수 |
|---|---|---|
| DISCORD_WEBHOOK_URL | arena 전용 Discord 채널 webhook | 선택 |
| GH_TOKEN | ai-stock-selector raw URL 접근용 PAT | 선택 |
| SMTP_HOST | 이메일 발송 SMTP 호스트 | 선택 |
| SMTP_PORT | 이메일 발송 SMTP 포트 | 선택 |
| SMTP_USER | 이메일 발송 SMTP 사용자명 | 선택 |
| SMTP_PASS | 이메일 발송 SMTP 비밀번호 | 선택 |
| ARENA_EMAIL_FROM | 발신 이메일 주소 | 선택 |
| ARENA_EMAIL_TO | 수신 이메일 주소 | 선택 |

Variables(Secrets가 아닌 일반 변수)로 등록할 항목:

| Variable | 설명 |
|---|---|
| EDGAR_EMAIL | SEC EDGAR User-Agent용 이메일 |

### 3. GitHub Pages 활성화

저장소 Settings → Pages → Source: **"GitHub Actions"** 선택.

이후 `Daily Arena Run` 워크플로우가 성공하면 `Deploy Arena Pages`가 자동으로 트리거됩니다.

## 프로젝트 구조

```
src/arena/
  cli.py              # 모든 CLI 진입점 (arena run-daily, build-web, notify, backup)
  engine/
    orchestrator.py   # 핵심 일별 파이프라인
    portfolio.py      # 포트폴리오 체결/평가
  agents/             # 4 에이전트 전략 (aggressive, balanced, conservative, etf_only)
  db/                 # SQLite 스키마, 레포지터리, 마이그레이션
  analytics/          # 샤프/드로다운/팩터 기여 메트릭
  notify/             # Discord, 이메일 알림
  web/                # Jinja2 + Plotly.js 정적 사이트 빌더
data/
  arena.db            # SQLite DB (git-tracked, 자동 커밋)
docs/site/            # 빌드된 정적 사이트 (자동 배포)
tests/                # pytest 테스트
```

## 웹 대시보드

배포 후 아래 URL에서 확인할 수 있습니다:

```
https://<user>.github.io/ai-trader-arena/
```

## 라이선스

(TBD)
