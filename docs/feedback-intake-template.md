# AX1 Skill Pack 개선 PR 준비 브리프

GitHub Pull Request가 공식 개선 접수 채널이다. 이 브리프를 에이전트에게 제공하면 익명 재현, 수정, 검증과 PR 작성에 사용할 수 있다. 실제 사업자료와 제한 Drive 내부 경로는 공개 PR에 기록하지 않는다.

## 기본정보

- 사용한 에이전트와 스킬:
- 사용한 스킬 버전:
- HWPX 사용 시 core / automation / plugin 버전:
- 입력 형식: HWP / HWPX / DOCX / PPTX / 기타
- 자료 공개 범위: 공개 가능 / 익명화 필요 / 제한 근거 별도 확인 필요

## 재현과 기대 결과

- 재현 요청문:
- 현재 실제 동작:
- 기대 동작:
- 반복 발생 여부:
- 사람이 직접 보완한 내용:
- 민감정보 없는 최소 재현 예시:

## 제안 변경

- 관련 스킬·문서·스크립트:
- 변경할 범위:
- 이번 PR에서 제외할 범위:
- 범용 규칙 또는 특정 프로파일 여부:
- 기존 규칙과의 충돌 가능성:

## 검증

- 직접 테스트와 결과:
- `python scripts/build_release.py` 결과:
- HWPX 구조·readback·프리뷰·한컴 관찰 상태:
- 미검증 항목과 이유:

## 에이전트 요청문

```text
AX1 Skill Pack 저장소를 최신 main으로 준비하고 AGENTS.md, CONTRIBUTING.md와 docs/pr-operating-policy.md를 먼저 읽어줘.
이 브리프를 민감정보 없는 예시로 재현한 뒤 한 가지 목적의 contrib 브랜치에서 수정해줘.
.changes 변경 조각과 관련 테스트를 추가하고 전체 빌드를 실행해줘.
VERSION, 릴리즈용 CHANGELOG, 플러그인 버전과 태그는 수정하지 마.
검증 후 커밋·푸시하고 PR을 생성한 다음 PR 링크와 미검증 항목을 알려줘.
```
