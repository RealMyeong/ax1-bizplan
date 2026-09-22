# 산출물 서식 스킬 확인 게이트 등록

- 사용자 효과: bizplan-artifact-format 도 다른 스킬처럼 작업 시작 전 사용자 이해 확인 게이트를 적용함. 최초 응답에서 목적·입력·범위·산출물·검증 가정을 설명하고, 별도 메시지의 동의를 받은 뒤에만 파일 확인과 스크립트 실행을 시작함
- 변경 범위: skills/bizplan-artifact-format/SKILL.md (게이트 절 추가), references/05-user-confirmation-gate.md (공용 원문 사본), scripts/build_release.py (confirmation gate map 등록)
- 제외 범위: 게이트 원문(shared/core/12-user-confirmation-gate.md)의 내용 변경 없음
- 검증: `python scripts/build_release.py` 통과 (confirmation gate 검증 포함 8개 스킬 전부). 사본이 공용 원문과 바이트 단위 동일함을 cmp 로 확인
- 호환성: 스킬 호출 시 최초 1회 이해 확인이 추가되는 것 외에 기존 사용 흐름 영향 없음
- 기여자: gslee (with Claude Code)
