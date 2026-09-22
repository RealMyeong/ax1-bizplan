# 산출물 서식: 스킬 등록 누락과 계약 검사 실패 수정

- 사용자 효과: ⓪ `bizplan-artifact-format` 이 `ALL_SKILLS` 에는 있으나 설치 안내 문서 3종(README.md, docs/team-guide.md, docs/ax1-bizplan-guide.html)에 없어 **저장소 빌드가 실패하고 있었음**. 세 문서의 스킬 선택표에 항목을 넣고 배포 스킬 수를 9개에서 10개로 고침. 같은 이유로 `references/13-skill-backup-retention.md` 를 `SKILL.md` 가 가리키지 않아 백업 정책이 적용되지 않았으므로 다른 스킬과 같은 형태의 링크를 설치 절에 추가함 ① `references/14-task-execution.md` 는 전체 스킬 공통 실행 정책이고 파일은 있었으나 `SKILL.md` 가 이 파일을 가리키지 않았음. 링크가 없으면 규칙을 읽지 않으므로 **정책이 실제로 적용되지 않는 상태**였음. 나머지 9개 스킬과 같은 형태의 링크를 최초 확인 절에 추가해, 요청 범위에 맞는 작업량 판단·같은 요청의 동의와 자료 재사용·완료 판단 기준이 이 스킬에도 적용됨 ② `references/04-content-authoring.md` 의 인라인 문법 예시가 깨진 파일 링크로 판정됐음. 계약 검사는 `](` 를 모두 파일 링크로 읽으므로 예시를 `[글자]` 와 `(주소)` 로 나눠 적어 링크로 읽히지 않게 함. 그림 문법 예시도 같은 이유로 `!` + `[캡션]` + `(경로)` 형태로 나눠 적음. 문서에 보이는 설명은 같음
- 변경 범위: README.md·docs/team-guide.md·docs/ax1-bizplan-guide.html(스킬 선택표 항목과 배포 스킬 수), bizplan-artifact-format — SKILL.md(14-task-execution 링크, 13-skill-backup-retention 링크), references/04-content-authoring.md(예시 표기 2곳), references/13-skill-backup-retention.md·14-task-execution.md(shared/core 기준 원본과 바이트 일치하는 사본 추적 시작)
- 제외 범위: 스크립트·서식값·출력 HWPX 변경 없음. 다른 스킬의 SKILL.md·참조는 이미 규격을 만족하므로 건드리지 않음. 검사 규칙 자체를 느슨하게 바꾸지 않음
- 검증: `python scripts/build_release.py` 통과(종전 `README.md: installation guide is missing skills` 로 실패). `python scripts/skill_contract_test.py` 4건 통과(종전 1 failure, 1 error). `python scripts/validate_pr.py --base main` 통과. 그림 생성·검사 회귀 확인 위반 0건
- 호환성: 설치 안내 문서·규칙 문서와 링크만 바뀜. 스킬 자체는 이미 `ALL_SKILLS` 에 있었으므로 배포 구성은 달라지지 않음. 생성·적용·검사 동작은 종전과 같음
- 기여자: gslee (with Claude Code)
