# Experiments

본 디렉터리는 사전 등록된 퀀트 실험 문서를 보관한다.

## 파일 형식

- `EXP-NNN-<slug>.md` — 사전 등록 + 결과 기록 (NNN = 3자리 zero-pad)
- 번호는 양 프로젝트(ai-stock-engine + ai-trader-arena) 통합 카운터

## 등록 방법

```
/preregister <실험명>
→ quant-planner 에이전트가 EXP-NNN 문서 자동 생성
```

## 워크플로우

```
[1] quant-planner    : 가설/통과기준/데이터분할 잠금
[2] quant-implementer : EXP 범위만 구현 (exp/EXP-NNN 브랜치)
[3] quant-auditor    : 데이터 누수/편향 4대 영역 감사
[4] quant-runner     : 백테스트/평가 실행
[5] backtest-reviewer : 통계 유효성 5대 영역 검증
[6] quant-recorder   : 결과 기록 + baseline 갱신
```

상세: `~/.claude/projects/.../memory/workflow_quant.md`

## 작업 브랜치

`exp/EXP-NNN-<slug>` 형식. main 직접 커밋 금지.

## 절대 금지

- Test 구간 데이터를 학습/튜닝에 사용 (EXP 무효화)
- 통과 기준 사후 변경 (가설 무력화)
- reviewer 판정과 다른 status 기록

## 현황 조회

```
/exp-status
```
