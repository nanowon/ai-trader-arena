# ai-trader-arena

AI 주식 투자 에이전트 경쟁 플랫폼. 4개의 서로 다른 투자 전략 에이전트가 동일한 초기 자본($100,000)으로 실제 시장 데이터를 기반으로 포트폴리오를 운용하고, 일별 퍼포먼스를 누적 기록/시각화합니다.

## 4 에이전트

| 에이전트 | 전략 요약 |
|---------|---------|
| Aggressive | 고변동성/고베타 종목 집중, 높은 회전율 |
| Balanced | 팩터 균형(모멘텀 + 퀄리티 + 밸류) |
| Conservative | 저변동성/배당 중심, 낮은 회전율 |
| ETF-Only | 섹터 ETF만 사용한 패시브 로테이션 |

벤치마크: SPY

## Phase 로드맵

- **Phase 0** (현재): 저장소 스켈레톤, CI skeleton, pyproject 구성
- **Phase 1**: 4 에이전트 전략 로직 구현 + 단위 테스트
- **Phase 2**: DB 스키마, daily orchestrator, legacy 마이그레이션, 실제 체결·포트폴리오 로직
- **Phase 3**: 분석 메트릭(샤프/드로다운/팩터 기여), 대시보드 정적 사이트, Discord·Email 알림
- **Phase 4+**: 백테스트, 전략 튜닝, 추가 에이전트

## 개발 상태

**Phase 0 진행 중** — 실제 투자 로직/데이터 파이프라인은 구현되지 않았습니다.

## 설치

```bash
pip install -e ".[dev]"
pytest -q
arena --help
```

## 환경 변수

`.env.example`를 `.env`로 복사 후 값 채우기.

## 라이선스

(TBD)
