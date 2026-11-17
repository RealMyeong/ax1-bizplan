# 경량 HWPX 표 칸 안 나열과 열 너비 배분

- 사용자 효과: 합격 조건·시험절차·사전조건처럼 한 칸에 여러 항목을 `A / B`·`1) A 2) B`·`<br>`로 적으면 항목마다 줄을 나눈 `• `·번호 목록(내어쓰기)으로 나옴. 표 열 너비는 한컴의 어절 단위 줄 나눔 기준으로 행 높이와 낱말 중간 끊김이 가장 적은 배분을 골라, ID 열은 한 줄로 남고 긴 글 열이 한두 낱말씩 접히던 배분이 줄어듦. 줄을 나눈 뒤 다음 줄이 공백으로 시작하지 않음
- 변경 범위: `skills/bizplan-hwpx/scripts/build_headless_artifact.py`(cell_items·column_widths·cell_item), `layout_headless_artifact.py`(셀 여러 문단 재배치), `headless_hwpx.py`(wrap_widths 후속 줄 폭·줄 첫머리 공백), references 08·11, `scripts/headless_table_layout_test.py`
- 제외 범위: 한/글 글머리표 기능(`hh:bullet`) 전환, 1행·1열 축 셀 나열, 병합 셀, 기존 문서 재서식
- 검증: `python -X utf8 scripts/headless_table_layout_test.py` 26개 통과(신규 8개), `headless_hwpx_acceptance_test.py`·`headless_media_test.py` 통과, `python scripts/build_release.py` 통과, 합성 문서 한컴 PDF 시각 확인
- 호환성: 표 칸에 ` / `·`1) 2)`가 없는 기존 원고의 표는 열 너비만 달라짐. 칸에 ` / `를 나열이 아닌 뜻으로 쓴 경우 항목으로 나뉨
- 기여자: bmmmnmm (with Claude Code)
