# 사업계획서 HWPX 양식 작업

## 경로 선택

| 상황 | 권장 경로 |
|---|---|
| 승인된 AX1 표지 템플릿 + 확정 Markdown으로 새 산출물 생성 | `build_headless_artifact.py` → `check_headless_artifact.py` → upstream 구조 검증 → 프리뷰·한컴 관찰 |
| 공식 HWPX 양식의 필드·표·본문 빈칸 채움 | `get_document_map` → `analyze_form_fill` → dry-run → `apply_form_fill`의 `verificationReceipt` → readback |
| 이미 위치가 확정된 본문·표 셀의 복합 편집 | canonical path 확인 → `apply_document_commands` dry-run → commit |
| 단일 명확한 텍스트 치환 | 전용 치환 도구의 dry-run → commit |
| 제출기관이 허용한 자유양식 새 문서 | `validate_document_plan` → `create_document_from_plan` |
| 바이너리 HWP | 한컴에서 HWPX 사본으로 변환 후 다시 시작 |
| MCP 사용 불가·긴급 작성 | DOCX 대안 생성 후 HWPX 미검증 상태 명시 |

경량 경로는 포함된 템플릿 매니페스트의 SHA-256이 일치할 때만 사용함. 본문과 표 셀 줄간격은 모두 160%이며, 임의 양식이나 기존 문서를 경량 스크립트로 재서식하지 않음

일반 사업계획서 양식 채움을 여러 저수준 셀 편집으로 쪼개지 않음. 전문 form-fill 경로가 지원하는 경우 한 계획과 한 트랜잭션으로 처리함

## 혼합 양식 검증 영수증

`apply_form_fill` 확정 결과의 `verificationReceipt`를 필수 1차 영수증으로 사용함. 다음이 모두 맞아야 반영 성공으로 판단함

- `schemaVersion == "hwpx.form-verification-receipt/v1"`
- `phase == "apply"`, `status == "committed"`, `ok == true`
- `committed == true`, `rolledBack == false`
- `sourcePreservation.preserved == true`
- `openSafety.ok == true`

`valueVerification.status == "checked"`이면 `ok == true`와 `matchedCount == checkCount`도 요구함. `deferred`이면 이를 값 검증 통과로 표현하지 않고 계획의 native field, label cell, canonical path, body anchor 각각을 전용 읽기 도구로 다시 읽어 기대값과 비교함

별도 `verify_form_fill`은 값과 렌더 오라클을 확인하는 추가 경로임. 검증된 Windows 조합에서는 렌더 큐가 없을 때 호출이 멈추거나 MCP 표준출력에 경고를 섞을 수 있으므로, 본 작업과 분리된 제한시간 검사에서 한 번만 시도함. 제한시간 초과나 통신 오류는 `별도 렌더 검증 차단`으로 기록하고 통과로 바꾸지 않음. 이 경우 위 commit 영수증, 모든 대상의 readback, `render_preview`, Windows 한컴 전체 페이지 관찰을 각각 완료해야 함

## 내용에서 양식으로 매핑

편집 전에 다음 원장을 만듦

| 항목 | 기록 내용 |
|---|---|
| 양식 위치 | 장·절·표·행·열·필드·앵커 |
| 확정 문안 | 실제 삽입할 텍스트·표 데이터 |
| 근거 | RFP·공식자료·승인된 프로젝트 자료 |
| 상태 | 확정 / 가정 / 자료 필요 / 결정 필요 |
| 편집 방식 | form field / label cell / canonical path / body anchor |
| 검증 | readback 검색어·표 좌표·시각 확인 포인트 |

한 항목을 여러 위치에 반복해야 하면 모든 위치를 명시함. 기관명·기간·KPI·예산처럼 전역 정합성이 필요한 값은 수정 후 문서 전체를 다시 검색함

## 원본 보존과 버전

- 입력과 출력 경로를 같게 하지 않음
- 원본 SHA-256을 편집 전후 비교함
- 출력명 예시: `제출양식_AX1_초안_v01.hwpx`, `제출양식_AX1_검토반영_v02.hwpx`
- 같은 버전의 HWPX, PDF·preview, 추출 JSON, readback과 화면 증거를 하나의 버전 묶음으로 연결함
- 검증 중인 새 묶음과 현재본의 검증 증거는 프로젝트의 `99_임시작업`에 두고 저장소에 커밋하지 않음
- 새 버전이 단계별 검증을 통과하면 같은 산출물군의 이전 현재본과 검증 증거를 함께 `98_이전버전`에 보관하고, 주 작업공간에는 새 현재본 묶음만 둠
- 작성·수정 단계의 요구 검증을 통과한 파일만 `08_작성중`·`09_검토_수정` 현재본으로 승격하고, 승인된 제출 후보만 `10_제출본` 현재본으로 승격함
- `98_이전버전`의 파일은 그 자리에서 편집하거나 자동 삭제하지 않고, 경로와 주 파일 SHA-256을 `산출물_버전이력.md`에 기록함

## 표·페이지 보존 판단

- 기존 표의 행·열을 늘리기 전에 양식 지침과 페이지 제한을 확인함
- 셀에 긴 문안을 넣을 때 문단 분리, 글자 크기, 행 높이와 다음 페이지 분할 위험을 검토함
- 서식 축소로 내용을 억지로 맞추기 전에 중복 문구를 줄이고 핵심 주장·근거·검증 중심으로 다듬음
- 양식에 없는 새 장·절·표를 추가해야 하면 제출 규정 허용 여부를 먼저 확인함

## 미확정 표시

`〈자료 필요: 값·담당〉` 같은 표시는 초안 단계에서만 허용함. 제출 후보에서는 다음을 모두 검색함

- `〈자료 필요`
- `TODO`
- `작성 필요`
- `○○`
- `□□□□`
- 원래 양식의 안내문·샘플값

필수 위치의 잔여 표시가 하나라도 있으면 제출 후보 상태로 올리지 않음
