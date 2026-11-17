# 경량 HWPX 본문 글머리표를 한/글 글머리표 기능으로 전환

- 사용자 효과: 생성한 본문 목록이 글자 `• `가 아니라 한/글 글머리표 기능으로 들어감. 한/글에서 F6 「글머리표 1」로 같은 서식을 고를 수 있고, 긴 항목의 둘째 줄은 한/글 자동 내어쓰기로 첫 글자에 맞음. 본문을 복사·검색할 때 기호가 글에 섞이지 않음
- 변경 범위: `bizplan-hwpx` 경량 생성기(`headless_hwpx.py` 글머리표 정의·스타일 도우미, `build_headless_artifact.py` 글머리표 문단, `layout_headless_artifact.py` 목록 판정, `check_headless_artifact.py` 글머리표 검사), 08·11 참조, SKILL.md, 배포자 안내, 수용 테스트와 개별 스킬 ZIP readback
- 제외 범위: 번호 목록(번호 글자 보존 hanging indent 유지), 표 칸 안 글머리표, 2단계 이상 글머리표, 승인 템플릿 자산 변경(정의는 생성 시 header에 추가)
- 검증: `scripts/headless_hwpx_acceptance_test.py`(글머리표 정의·스타일·위치·머리 표시 비트, 기호 중복·글자 기호·머리 표시 누락·앞 공백·줄 배치 결함 주입 탐지), `scripts/headless_table_layout_test.py`, `scripts/headless_media_test.py`, `scripts/build_release.py` 통과. 익명 예시를 한컴 PDF로 바꿔 기호 표시(3200)·본문 시작(4700)·둘째 줄 정렬·☑ 보존 확인
- 호환성: 본문 시작 위치가 4000에서 4700 HWPUNIT으로 바뀜(한/글 글머리표 기본 간격). 기호 위치 3200은 유지. 기존 생성 파일은 그대로이며 다시 생성하면 새 방식이 적용됨
- 기여자: bmmmnmm (with Claude Code)
