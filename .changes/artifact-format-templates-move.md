# 산출물 서식: 표지 양식을 스킬 안 assets/templates/ 로 이동

- 사용자 효과: 표지 양식이 저장소 최상위 `document_form/` 대신 `skills/bizplan-artifact-format/assets/templates/` 에 들어감. 스킬 ZIP에 양식이 함께 묶이므로 링크 설치가 아닌 사본·ZIP 설치에서도 `--template` 없이 새 산출물을 만들 수 있음. 사업마다 산출물 양식은 하나이므로 사업별 표지(청년바우처)도 같은 폴더에 둠
- 변경 범위: document_form/ 3개 hwpx → skills/bizplan-artifact-format/assets/templates/ 이동, scripts/build_artifact.py(default_template 탐색 순서: assets/templates 우선, 예전 document_form 후순위), SKILL.md·references/03·04 경로 설명, .gitignore 예외 경로, scripts/build_release.py·validate_pr.py 승인 바이너리 목록(ARTIFACT_FORMAT_TEMPLATES), bizplan-hwpx references/12 문구
- 제외 범위: 양식 내용·서식 변경 없음. bizplan-hwpx 의 승인 템플릿·매니페스트는 그대로임. 양식 SHA-256 매니페스트는 만들지 않음
- 검증: `--template` 생략 생성이 assets/templates 의 빈 양식을 찾는지 확인, `python scripts/build_release.py` 실행 결과는 PR 본문에 기록
- 호환성: 예전 `document_form/` 이 남아 있는 사본에서도 후순위로 계속 찾음. `--template` 직접 지정은 종전과 같음
- 기여자: gslee (with Claude Code)
