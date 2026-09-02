# HWPX 검증과 제출 증거

## 검증 단계

### 1. 구조·열림 안전성

쓰기 결과가 제공하는 다음 항목 또는 도구별 동등한 영수증을 확인함

- `quality.validation.reopened == true`
- `validate_package.ok == true`
- `validate_document.ok == true`
- `verification.openSafety.ok == true`
- 편집 트랜잭션의 `ok == true`
- `rolledBack == false`

필드가 없는 도구에 존재하지 않는 성공값을 추정하지 않음. 해당 도구의 전용 verification receipt와 재개방 검증을 사용함

혼합 양식은 `apply_form_fill`이 돌려준 `hwpx.form-verification-receipt/v1`을 확인함. `committed`, `sourcePreservation.preserved`, `openSafety`가 통과하지 않으면 출력 파일이 생겼더라도 성공으로 보지 않음. `valueVerification`이 `checked`면 전 항목 일치를 요구하고, `deferred`면 각 대상의 전용 readback 결과로 값을 검증함. 별도 `verify_form_fill`이 렌더 오라클 문제로 제한시간을 넘긴 경우에는 `별도 렌더 검증 차단`을 명시하고, commit 영수증이나 프리뷰 성공을 자동 실한컴 검증으로 표현하지 않음

### 2. 의미 검증

- `get_document_text`로 핵심 제목·문안·기관 역할·기간·KPI readback
- `get_table_text`로 수정한 모든 중요 표 좌표 readback
- 이전 값이 남지 않았는지 전역 검색
- 필수 플레이스홀더와 양식 안내문 잔존 여부 검사
- 원본 SHA-256 불변 및 출력 SHA-256 기록
- 승인 AX1 경량 문서는 DXS 파일명의 사업코드·문서유형·날짜·버전, 개정 이력 최신 날짜·버전, PDF·프리뷰·readback과 `산출물_버전이력.md`의 일치 확인. 미승인 코드·불일치·복수 토큰·부분 개정행은 후보 저장·승격 전에 차단

### 3. 페이지 프리뷰

레이아웃 민감 작업 뒤 `render_preview`를 실행하고 다음을 확인함

- 페이지 수와 빈 페이지
- 표·그림·캡션 잘림
- 제목만 페이지 끝에 남는 고립 제목
- 글꼴 대체, 한글 글리프 깨짐, 지나치게 작은 글자
- 머리글·바닥글·쪽번호와 페이지 경계

프리뷰는 근사 증거이며 한컴 실제 조판과 동일하다고 표현하지 않음

### 4. Windows 한컴 실제 관찰

현재 Windows용 upstream 자동 뷰어 탐지는 로컬 `Hwp.exe`를 자동으로 최종 증거화하지 못할 수 있음. 이때 다음 절차를 따름

1. 명시적인 `Hwp.exe` 경로로 출력 HWPX를 열음
2. 복구·변환·경고 대화상자가 나타나지 않는지 확인함
3. 첫 페이지부터 마지막 페이지까지 실제로 이동하며 표·글자·페이지를 확인함
4. 한 페이지 문서는 해당 페이지 화면, 여러 페이지 문서는 모든 페이지 관찰을 입증하는 페이지별 화면 또는 검토용 묶음 이미지를 남김
5. upstream `visual_review.py`로 `hwpx.visual-review.v1` 증거를 만들고 파일 SHA-256, 뷰어 버전, 관찰 시간, 화면 경로와 결과를 기록함

한컴을 실행만 했거나 첫 페이지만 본 상태에서는 `observed_pass`로 기록하지 않음. 뷰어에서 파일을 임의 저장하지 않고 닫음

현재본과 검증 중인 새 버전의 증거는 `99_임시작업/HWPX_검증/<출력파일명>/visual-review.json`과 같은 프로젝트 내부 제한 경로에 두고 저장소에는 넣지 않음. 더 최신 버전이 승격되면 해당 HWPX의 프리뷰·readback·화면 증거 폴더도 같은 버전 묶음의 `98_이전버전` 보관 경로로 옮겨 이전 문서와 함께 확인할 수 있게 함. 증거 내부에 이동 전 절대경로가 기록되어 있으면 원본 증거는 고치지 않고, 같은 보관 폴더에 `evidence-relocation-map.json`을 추가해 증거 파일 SHA-256과 각 화면·프리뷰의 이동 전·후 프로젝트 상대경로를 기계 판독 가능한 형태로 기록함. 이력표 메모에도 해당 매핑 파일 경로를 남김. 제출 후보 판정에는 다음 필드를 모두 요구함

`evidence-relocation-map.json`은 `schemaVersion: "ax1.hwpx-evidence-relocation/v1"`, `documentVersion`, `evidenceReceiptSha256`과 `files` 배열을 포함함. 각 파일에는 `sha256`, `previousPath`, `archivedPath`를 프로젝트 기준 상대경로로 기록함

- `schemaVersion == "hwpx.visual-review.v1"`
- `target.sha256`이 제출 후보 SHA-256과 일치
- `viewer.available == true`
- `current.status == "observed_pass"`
- `current.screenshot_path`가 존재하고 모든 페이지 관찰을 입증
- `current.layout_risks == []`
- `summary.ready_for_submission_claim == true`

upstream 증거 도구가 없거나 위 필드를 만들 수 없으면 임의 AX1 형식으로 통과시키지 않고 `한컴 시각 검증 대기`로 둠

### 5. 자동 real-Hancom 영수증

`render_health` → `render_submit` → `render_status` 경로는 별도 렌더 큐가 구성된 경우에만 사용함. 로컬 한컴 설치만으로 자동 `render_checked == true`를 추정하지 않음

## 상태 표현

| 상태 | 의미 |
|---|---|
| `blocked` | 도구·버전·파일 형식 문제로 편집 시작 불가 |
| `structure_verified` | 패키지·문서·재개방·open-safety와 readback 통과 |
| `preview_reviewed` | 구조 검증과 근사 페이지 프리뷰 검토 통과 |
| `hancom_observed_pass` | 한컴에서 전체 페이지 실제 관찰과 화면 증거 확보 |
| `submission_candidate` | 위 검증과 `bizplan-preflight`, 담당자 승인이 모두 완료된 제출 후보 |

낮은 상태를 높은 상태처럼 표현하지 않음

## 완료 기록 최소 항목

- source/output 절대 경로와 SHA-256
- HWPX 엔진·자동화·플러그인 버전
- 변경 계획, dry-run diff, commit 영수증
- readback 결과와 잔여 표시 검사
- preview 산출물과 관찰 결과
- 한컴 실행 파일 버전, 전체 페이지 관찰 결과와 화면 증거
- 미확정 내용과 최종 승인자
- 산출물군, 문서 버전, 현재·보관 상태와 버전 이력 경로
