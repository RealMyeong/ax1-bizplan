# 개정 이력 개정내역 칸 글자 벌어짐 방지

- 사용자 효과: 긴 개정내역이 개정 이력표 칸에서 여러 줄로 접혀도 양쪽 정렬로 글자 사이가 벌어지지 않고 왼쪽 정렬로 표시됨
- 변경 범위: `bizplan-hwpx` 경량 생성기 `build_headless_artifact.py`(개정 이력 기록 칸의 양쪽 정렬 문단모양을 왼쪽 정렬 복제본에 연결), 참조 문서 08·10·15, `scripts/hwpx_metadata_test.py` 회귀 테스트
- 제외 범위: 승인 템플릿 자산·매니페스트, 개정 이력표 열 너비·행 수·행 높이, 문서 정보표 정렬, 검사기 규칙(사람이 직접 채운 양쪽 정렬 이력은 계속 정상으로 봄)
- 검증: `python scripts/hwpx_metadata_test.py`, `headless_hwpx_acceptance_test.py`, `headless_media_test.py`, `headless_table_layout_test.py`, `skill_contract_test.py`, `python scripts/build_release.py` 통과. 한컴 PDF로 수정 전·후 개정 이력표 비교
- 호환성: 개정 이력 기록값·readback·누적 규칙 동일. 표지 공유 문단모양 정의는 그대로이며 새 문단모양 1개가 추가될 수 있음
- 기여자: bmmmnmm (with Claude Code)
