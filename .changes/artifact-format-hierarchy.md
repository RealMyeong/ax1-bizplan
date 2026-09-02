# 산출물 서식: 제목·목차·리스트 계층과 표 글자처럼 취급

- 사용자 효과: 제목 4수준(15/12/10.5/10.5pt bold, 4수준은 3수준과 동일 서식)에 위아래 간격·개요 스타일 태그·장 쪽나눔이 붙고, 목차가 장(굵게)·절(들여쓰기 10pt) 2단계로 생성·재생성되며, 리스트가 단계별 기호(불릿 `●` `-` `·` `·`, 번호 `1.` `가.` `1)` `1)`)와 내어쓰기를 갖는다. 본문 표는 글자처럼 취급이 지정(On)된다. 기존 문서에도 `apply_artifact_format.py` 가 소급 적용한다
- 변경 범위: bizplan-artifact-format — SKILL.md, references/01-format-rules.md, references/04-content-authoring.md, scripts/hwpx_format.py, scripts/build_artifact.py, scripts/apply_artifact_format.py, scripts/check_artifact_format.py
- 제외 범위: 개요 번호(OUTLINE heading) 자동 매김은 본문의 글자 번호와 겹쳐 보여 쓰지 않음(스타일 태그만 부여). 목차 쪽번호, 그림, 병합 셀은 종전대로 미지원
- 검증: 실제 정의서 1건 소급 적용 후 check 위반 0건 / 불가침 구간 바이트 동일 / XML 적합 / 표 12·ZIP 12 유지, 문단 +20은 목차 절 항목 재생성 로그와 일치 / 재적용 멱등(0건 수정) / build 경로는 4수준 제목·중첩 불릿·중첩 번호 샘플 생성 후 검사 통과. 한컴 시각 검증 대기. `scripts/build_release.py` 는 confirmation gate map 에 bizplan-artifact-format 이 없어 실패했으나, 확인 게이트 등록(별도 조각 artifact-format-confirmation-gate) 반영 후 8개 스킬 전부 통과함
- 호환성: 옛 형식 문서(불릿 `·` 고정, 번호 목록 내어쓰기 없음, 장만 있는 목차)는 apply 실행 시 새 규칙으로 소급 변환됨. 목차 재생성으로 문단 수가 원본과 달라질 수 있어 SKILL.md 검증 문구를 갱신함
- 기여자: gslee (with Claude Code)
