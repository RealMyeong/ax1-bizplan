# 문안 수치 구분: 정량·정성, 실행 목표값 대 미래 기대값

- 사용자 효과: `bizplan-draft`가 원천 자료의 수치를 옮겨 적을 때 정량·정성 수치를 구분하고, 당장 실행에 필요한 목표값과 사업 종료 후 기대값을 구분해 후자를 참고 수준으로만 다룸
- 변경 범위: `shared/core/04-kpi-framework.md`와 빌드 동기화 대상인 `bizplan-draft`·`bizplan-review`·`bizplan-revise`·`bizplan-preflight`의 KPI 참조
- 제외 범위: 지표 원장 템플릿의 열 추가, 기존 KPI 목표값 자동 변경, 미래 기대값 삭제
- 검증: `scripts/build_release.py` 전체 빌드에서 공용 원문과 4개 스킬 사본 동기화 및 스킬 패키지 검증 통과, `git diff --check` 통과
- 호환성: 기존 사용 흐름과 KPI 표 구조를 유지하며 수치 해석 우선순위만 명확히 함
- 기여자: gslee / soccer3731 (PR #3, with Claude Code), AX1_JM (선별 통합)
