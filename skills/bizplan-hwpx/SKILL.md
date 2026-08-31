---
name: bizplan-hwpx
description: 확정된 국가 R&D·공모 사업계획서 내용을 HWPX 양식에 안전하게 반영하고 원본 보존, 모의 편집, 구조·텍스트 검증, 페이지 프리뷰와 한컴 재개방 확인을 수행한다. 사용자가 한글 양식, HWPX 작성본·수정본·제출본을 요청할 때 사용한다. 사업 아이디어 구체화나 본문 초안 작성만 필요한 경우에는 bizplan-draft를 사용하고, 바이너리 HWP 직접 편집에는 사용하지 않는다.
metadata:
  version: "0.2.0"
  architecture: "ax1-policy-wrapper-over-hwpx-plugin"
  updated: "2026-08-31"
---

# 목적

AX1 사업계획서의 내용 판단과 HWPX 문서 편집을 분리하고, 검증된 내용을 공식 양식에 넣되 원본·서식·표·페이지를 보존한 결과와 정직한 검증 증거를 제공함

# 역할과 경계

- 사업 내용이 비어 있거나 구현 방식이 미확정이면 먼저 `bizplan-draft`로 구체화함
- 검토의견 반영 문안이 필요한 경우 `bizplan-revise`, 제출 전 내용·형식 최종점검은 `bizplan-preflight`와 함께 사용함
- 실제 HWPX 읽기·생성·편집은 별도 설치된 upstream `hwpx` 스킬과 `python-hwpx-automation` MCP를 1차 경로로 사용함
- upstream 코드를 복제하거나 raw ZIP/XML을 직접 편집해 문서 충실도를 주장하지 않음
- `.hwp`는 직접 편집하지 않음. 한컴오피스에서 `.hwpx`로 변환한 사본을 받은 뒤 진행함
- upstream 플러그인이나 MCP가 준비되지 않았으면 설치·재시작 필요 상태를 보고하고, 사용자가 허용한 경우에만 설치함. 긴급 산출물은 DOCX 대안을 제시함

# 시작 점검

1. 입력 파일이 `.hwpx`인지, 바이너리 `.hwp`인지 확인함
2. `scripts/check_hwpx_environment.ps1`을 실행해 `uvx`, 플러그인, 한컴 뷰어와 렌더 큐 상태를 확인함
3. MCP가 연결되어 있으면 `mcp_server_health()`를 호출해 다음을 기록함
   - `version`
   - `pythonHwpxVersion`
   - `skillBundleVersion`
   - `toolSurface.status == "ok"`
   - `toolSurface.missingKeyTools == []`
4. 호환 버전과 설치 절차가 필요하면 [upstream 호환성](references/01-upstream-compatibility.md)을 읽음
5. 기준 양식, 작성할 항목, 확정 문안, 미확정 표시, 산출물군·현재본, 출력 위치와 제출 형식을 확인함

핵심 도구가 없거나 버전 표면이 불일치하면 문서 작업을 시작하지 않고 새 작업에서 재확인함

# 작업 절차

## 1. 내용 준비도 확인

- 확정 문안과 `〈자료 필요: 값·담당〉`, 가정, 결정 필요 항목을 구분함
- 미확정 정보가 양식 위치 선택이나 문서 구조를 바꾸면 먼저 사용자에게 결정받음
- 확정 문안이 없으면 HWPX 빈칸부터 채우지 않고 `bizplan-draft` 또는 `bizplan-revise` 결과를 준비함

## 2. 원본과 출력 경로 확정

- [산출물 최신본·이전버전 관리](references/05-artifact-version-management.md)를 읽고 같은 산출물군의 현재본과 버전 묶음을 `08_작성중`, `09_검토_수정`, `10_제출본` 전체에서 확인함
- 원본 SHA-256을 기록하고 직접 덮어쓰지 않음
- 출력은 원본과 다른 경로에 `원본명_AX1_작업단계_vNN.hwpx`처럼 식별 가능한 이름으로 만듦
- 새 출력은 가능하면 `99_임시작업/버전전환/<산출물군>/<새버전>`에서 먼저 만들고 검증 전에는 기존 현재본을 이동하지 않음
- 작성 중 파일은 프로젝트의 `08_작성중`, 수정본은 `09_검토_수정`, 승인된 제출 후보만 `10_제출본`에 둠
- 문서가 한컴이나 다른 편집기에서 열려 있을 가능성이 있으면 닫은 뒤 진행하도록 안내함
- 버전 번호·이력표·사용자 지정 기준본이 충돌하거나 같은 버전의 해시가 다르면 자동으로 최신본을 정하지 않음

## 3. 양식 지도와 삽입 계획 작성

[사업계획서 HWPX 양식 작업](references/02-business-form-workflow.md)을 읽고 요청 유형에 맞는 경로를 선택함

- 기존 양식 채움: `get_document_map`으로 제목·표·필드·앵커·revision을 확보함
- 낯선 혼합 양식: `analyze_form_fill`로 native field, 라벨 셀, canonical path와 본문 앵커를 포함한 하나의 계획을 만듦
- 확정 좌표의 복합 편집: canonical path를 확정한 뒤 `apply_document_commands`를 사용함
- 새 문서 생성: 제출기관이 자유양식을 허용할 때만 document plan을 검증한 뒤 생성함
- 항목별로 `원문 근거 → 확정 문안 → 양식 위치 → 편집 방식 → 검증 방식` 매핑을 남김

후보 위치가 여러 개이거나 표 구조를 바꿔야 하는 경우에는 임의로 첫 후보를 선택하지 않고 계획을 보여준 뒤 결정함

## 4. 모의 편집 후 확정

- 지원되는 모든 쓰기 경로는 먼저 dry-run을 수행함
- `semanticDiff`에서 의도한 문단·셀·표만 바뀌는지 확인함
- dry-run과 commit은 서로 다른 idempotency key를 사용하고, commit 재시도에만 같은 key를 재사용함
- 읽기 단계에서 받은 `expected_revision`을 commit에 전달함
- 여러 편집이 한꺼번에 성공하거나 실패해야 하면 하나의 트랜잭션 경로를 사용함
- commit 결과에서 `ok == true`, `rolledBack == false`, `openSafety.ok == true` 또는 해당 도구의 동등한 검증 영수증을 확인함
- 혼합 양식은 `apply_form_fill.verificationReceipt`의 source preservation을 확인함. value verification이 deferred이면 모든 대상의 전용 readback으로 보완하고, 별도 렌더 verifier가 차단된 경우 그 상태를 명시함

## 5. 내용·구조·시각 검증

[검증과 제출 증거](references/03-verification-evidence.md)를 읽고 다음을 순서대로 확인함

1. 패키지·문서·재개방·editor-open-safety
2. 본문·표 readback과 잔여 플레이스홀더
3. 원본 SHA-256 불변과 출력 파일 분리
4. `render_preview` 페이지 검토
5. Windows 한컴오피스 실제 재개방과 전체 페이지 관찰
6. `bizplan-preflight`의 제출 전 내용·수치·민감정보 점검

`render_preview`만 성공했거나 한컴을 실행만 한 상태는 최종 검증 완료가 아님. 사람이 전체 페이지를 실제로 관찰하고 화면 증거를 남기지 못하면 `한컴 시각 검증 대기`로 보고함

## 6. 현재본 전환과 이전본 보관

- `08_작성중`·`09_검토_수정` 현재본은 최소한 구조·재개방·open-safety·readback과 단계에 필요한 프리뷰 검토를 통과해야 함
- `10_제출본` 현재본은 한컴 전체 페이지 관찰, `bizplan-preflight`와 담당자 승인까지 끝난 `submission_candidate`만 승격함
- 단계에 필요한 검증이 끝난 뒤에만 기존 현재 HWPX와 그 버전의 PDF·프리뷰·readback·화면 증거를 하나의 버전 묶음으로 `98_이전버전/<원래단계>/<산출물군>/<버전>`에 보관함
- 보관 전후 SHA-256과 읽기 가능 여부를 확인하고 기존 보관본을 덮어쓰지 않음. 일부 이동이나 파일 잠금이 발생하면 전환을 중단하고 현재 위치와 복구 조치를 보고함
- 검증된 새 묶음을 알맞은 작업단계에 두고 `98_이전버전/산출물_버전이력.md`에서 이전 버전은 `보관`, 새 버전은 `현재`로 갱신함
- 보관된 HWPX는 그 자리에서 수정하지 않음. 과거 버전으로 되돌릴 때도 이를 기준으로 번호가 올라간 새 버전을 만들어 다시 검증함

# 완료 보고

- 기준 HWPX와 원본 SHA-256
- 생성한 출력 파일과 버전
- 산출물군의 현재본, 보관한 이전 버전 묶음과 `산출물_버전이력.md`
- 반영한 항목·표·셀과 미반영 항목
- dry-run의 주요 semantic diff와 commit 결과
- 패키지·문서·재개방·open-safety·readback 결과
- 프리뷰 및 한컴 실제 관찰 상태와 증거 파일
- 남은 자료 필요·결정 필요·사람 승인 항목

# 금지

- 원본 HWPX·HWP 직접 덮어쓰기
- `.docx`의 확장자만 `.hwp` 또는 `.hwpx`로 변경
- 바이너리 `.hwp` 직접 편집 또는 HWP 편집 가능하다고 주장
- raw ZIP/XML 편집 결과를 exact·원본 보존으로 표현
- dry-run 없이 복합 편집 확정
- open-safety 실패, rollback, 잔여 필수 플레이스홀더가 있는 파일 전달
- 프리뷰나 파일 열기만으로 `실한컴 검증 완료` 또는 `제출 준비 완료`라고 보고
- 실제 사업계획서·기관명·개인정보가 포함된 파일을 스킬 저장소나 공개 테스트 자료에 추가
- 새 출력의 단계별 검증이 끝나기 전에 기존 현재본을 이동하거나, 이전 HWPX·검증증거를 삭제 또는 덮어쓰기

# 문제 해결

Windows 설치·재시작·뷰어·버전 불일치 문제는 [Windows 문제 해결](references/04-windows-troubleshooting.md)을 읽음
