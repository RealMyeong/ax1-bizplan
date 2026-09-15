# HWPX 문서 목적 분기 게이트

- 사용자 효과: HWPX 요청이 명확하면 에이전트가 최종 산출물을 기준으로 사업계획서 작성 또는 일반 산출물 작성을 자동 선택해 기존 이해 확인문에 근거와 양식 기준을 설명하고, 목적이 모호할 때만 두 경로를 질문함. 두 경로의 입력·범위·산출물·위험까지 설명된 뒤에는 사용자가 선택과 진행 동의를 한 메시지로 답할 수 있음
- 변경 범위: `bizplan-hwpx` 진입 흐름과 문서 라우팅 참조, `ax1-work` 장기 설계의 confirmation envelope, README·팀원·배포자·HTML 안내, 기대 동작과 빌드 라우팅 불변조건
- 제외 범위: 아직 설계 상태인 `ax1-work` 스킬 구현, 기존 공통 사용자 확인 게이트 완화, 사업계획서 공식 양식이나 승인 AX1 템플릿 변경
- 검증: `skill-creator` quick validation, `scripts/build_release.py`, `scripts/validate_pr.py --base main`, HTML 구문 검사와 `git diff --check` 통과. 실제 대화형 분기의 전향 조건은 `examples/expected-behavior.md`에 고정
- 호환성: 기존 `$bizplan-hwpx` 호출과 별도 메시지 동의 조건을 유지함. 명확한 요청의 불필요한 선택 질문만 줄이고, 완전한 이해 설명이 없으면 선택 뒤 별도 동의를 계속 요구함
- 기여자: AX1_JM
