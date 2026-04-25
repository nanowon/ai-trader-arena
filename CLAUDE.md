# CLAUDE.md — ai-trader-arena

## 프로젝트 성격

Python 프로젝트. Godot/GDScript와 무관.
에이전트 워크플로우: **planner → implementer → reviewer** 순서 준수.
메인 세션에서 Python 소스 파일 직접 수정 금지.

## 핵심 원칙

**파이프라인 불변**: `orchestrator.py`의 일별 파이프라인은 예외 없이 완료까지 실행되어야 한다.
예외 발생 시 try/except로 격리하고 graceful skip 처리. 파이프라인 자체를 중단시키지 말 것.

## 주요 파일 맵

| 파일/디렉터리 | 역할 |
|---|---|
| `src/arena/cli.py` | 모든 CLI 진입점 (`arena run-daily`, `build-web`, `notify`, `backup`) |
| `src/arena/engine/orchestrator.py` | 핵심 일별 파이프라인 |
| `src/arena/agents/` | 4 에이전트 전략 모듈 |
| `src/arena/db/` | SQLite 스키마, 레포지터리, 마이그레이션 |
| `src/arena/analytics/` | 샤프/드로다운/팩터 기여 메트릭 |
| `src/arena/notify/` | Discord, 이메일 알림 |
| `src/arena/web/` | Jinja2 + Plotly.js 정적 사이트 빌더 |
| `tests/` | pytest 테스트 (현재 36+ pass) |

## 에이전트 전략 요약

| 에이전트 | 전략 |
|---|---|
| `aggressive` | 고변동성/고베타 종목 집중, 높은 회전율 |
| `balanced` | 팩터 균형 (모멘텀 + 퀄리티 + 밸류) |
| `conservative` | 저변동성/배당 중심, 낮은 회전율 |
| `etf_only` | 섹터 ETF만 사용한 패시브 로테이션 |

## 절대 수정 금지

- **DB 스키마** (`src/arena/db/schema.sql`): 변경 시 반드시 마이그레이션 스크립트 작성 후 planner 승인 필요.
- **파이프라인 불변 원칙**: orchestrator의 단계 순서 및 격리 구조 임의 변경 금지.

## 환경 변수

`.env.example` 참조. GitHub Actions에서는 Secrets/Variables로 주입.
