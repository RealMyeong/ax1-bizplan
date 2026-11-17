# HWPX 경량 생성 원고의 명시적 쪽 나눔 표시

- 사용자 효과: 확정 Markdown에 `<!-- 쪽나눔 -->` 한 줄을 넣으면 다음 블록(제목·문단·목록·표·그림)이 새 쪽에서 시작함(한/글 Ctrl+Enter와 같은 문단 `pageBreak=1`). 시험절차서처럼 절마다 새 쪽이 필요한 문서를 생성 후 손으로 고치지 않아도 됨
- 변경 범위: `bizplan-hwpx` 경량 생성기 원고 파서·조립, references 08·11, 합성 회귀 `scripts/headless_page_break_test.py`와 빌드 수용 검사 목록
- 제외 범위: 자연 쪽 넘김 판정, 쪽 번호, 목차, 표 나눔 규칙 변경, 공식 양식 경로
- 검증: 합성 회귀 6건(표시 인식·문단 안 표시 무시·연속/끝 표시 처리, 제목·문단·목록·표 앵커 새 쪽, 새 쪽 첫 문단 윗간격 0과 표 뒤 12pt 유지, 다른 문단 무변경, `check_headless_artifact`·`check_layout` 위반 0), 기존 경량 수용 테스트, `python scripts/build_release.py`
- 호환성: 표시를 쓰지 않은 원고의 출력은 바뀌지 않음. 새 쪽 첫 문단 윗간격 0은 기존 layout 규칙(명시적 새 쪽 예외)을 그대로 사용함
- 기여자: bmmmnmm (with Claude Code)
