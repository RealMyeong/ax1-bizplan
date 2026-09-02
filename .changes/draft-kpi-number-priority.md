# 문안 수치 구분: 정량·정성, 실행 목표값 대 미래 기대값

- 사용자 효과: bizplan-draft 가 원천 자료의 수치를 옮겨 적을 때 정량/정성 수치를 구분하고, 당장 실행에 필요한 목표값과 사업 종료 후 기대값을 구분해 후자를 참고 수준으로만 다룬다
- 변경 범위: shared/core/04-kpi-framework.md (8절 신설). 빌드 동기화로 bizplan-draft·bizplan-review·bizplan-revise·bizplan-preflight 의 references/04-kpi-framework.md 사본이 함께 갱신됨
- 제외 범위: 지표 원장 템플릿의 열 추가 없음
- 검증: `python scripts/build_release.py` 통과 (공용 원문과 스킬 사본 동기화 포함)
- 호환성: 기존 사용 흐름 영향 없음
- 기여자: gslee (with Claude Code)
