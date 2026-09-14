---
name: ax1-budget
description: AX1 사업비·예산·구매비용 관리대장을 포함된 공통 XLSX 양식으로 작성하거나 갱신한다. 승인예산과 구매·집행 자료를 연결하고 수식·차트·입력 규칙을 보존한다. 사업계획서 본문 작성이나 HWPX 일반 문서에는 사용하지 않는다.
metadata:
  version: "0.1.1"
  architecture: "template-preserving-budget-ledger"
  updated: "2026-09-14"
---

# 목적과 경계

사업비·예산·구매비용 관리대장을 포함된 공통 XLSX 양식으로 작성·갱신한다. 새 원장을 임의 설계하거나 HWPX·PDF로만 대체하지 않는다. 예산 승인·발주·지급·정산 승인 같은 외부 업무는 수행하지 않는다.

# 작업 시작 전 사용자 이해 확인

[사용자 이해 확인](references/01-user-confirmation-gate.md)에 따라 목적·입력·대상 사업/기간·수정 범위와 제외·XLSX 산출물·가정을 설명하고, 별도 메시지의 동의 뒤 파일·도구를 사용한다. [범위와 실행 판단](references/14-task-execution.md)을 적용하며 이미 확정된 값은 반복 질문하지 않는다.

# 양식과 입력

- [공통 XLSX 양식](assets/templates/ax1-budget-ledger.xlsx)을 스킬 폴더 기준으로 찾는다. 사용자 PC 원본 경로나 저장소 연결에 의존하지 않는다. 계약·제출기관 필수 양식은 기본 템플릿보다 우선한다.
- 기본 양식의 [매니페스트](assets/templates/template-manifest.json)와 [검사기](scripts/check_budget_template.py)로 해시·빈 입력영역·구조를 확인하고 작업공간에 사본을 만든다. 기존 원장 갱신은 기준본의 사본에서 진행한다. 설치된 양식은 수정하지 않는다.
- 대상 사업코드·관리기간·승인예산 근거·구매/집행자료·현재 원장을 확인한다. 자료가 없으면 사본·미확보 항목까지만 제공하고 금액·거래·기관을 지어내지 않는다.

# 작성·검증

[관리대장 작성 기준](references/02-ledger-authoring.md)을 읽는다. 현재 환경의 스프레드시트 스킬·도구로 XLSX 보존·계산·검증을 수행하며 Codex와 Claude에서 같은 결과 기준을 적용한다. 도구가 없거나 기능 보존이 안 되면 매핑·사본까지 제공하고 실제 작성 완료라고 하지 않는다. 임의 외부 전송·패키지 자동 설치는 요구하지 않는다.

1. 승인예산을 `02_승인예산`에 매핑하고 품목·용역을 `01_구매비용원장`의 예산라인ID에 연결한다.
2. 입력 셀만 채우고 수식·표·차트·드롭다운·서식을 보존한다.
3. 재계산 후 예산→원장→통합현황의 금액·경고를 대조한다. 원/천원 단위를 구분하고 승인·정산 상태는 근거로 확인한다.
4. [파일명·버전](references/03-artifact-version-management.md)의 `DXS-[사업코드]-BUD-[파일제목]-[YYYYMMDD]-vX.Y.xlsx`를 적용한다. 템플릿 v1.1과 문서 버전은 별개다.
5. [최신본 연동](references/04-artifact-synchronization.md)으로 예산 변경의 영향 문서만 검토한다. 필수 후보 검증 전 현재본을 덮어쓰거나 이전본을 이동하지 않는다. [버전 이력](assets/artifact-version-ledger-template.md)과 [연동현황](assets/artifact-sync-ledger-template.md)을 갱신한다.

# 완료 보고

XLSX, 기준자료·단위, 반영·미확정 항목, 수식·구조·재계산·시각 검증과 미검증 사항을 보고한다. 템플릿 해시 검사가 실제 거래·금액·정산 검증을 대신하지 않는다.

설치·업데이트 요청에만 [직전 설치본 백업](references/13-skill-backup-retention.md)을 적용한다.
