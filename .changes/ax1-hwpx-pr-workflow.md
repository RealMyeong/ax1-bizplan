# AX1 HWPX 산출물 경로와 개선 PR 운영 정비

- 사용자 효과: 사업계획서는 제출기관의 공식 양식을 유지하고, 정의서·보고서·회의록 등 일반 HWPX 산출물은 스킬에 포함된 승인 AX1 산출물 템플릿으로 작성함. 기본 제목은 `1. / 1.1 / 1.1.1 / 1.1.1.1`의 4단계까지 표시하고 그 아래는 본문 목록으로 전환함. 개선 요청은 Form 대신 팀원 에이전트가 익명 재현·수정·검증·PR 생성까지 수행하는 Git 흐름으로 통일함
- 변경 범위: `bizplan-hwpx`, `bizplan-draft`와 공통 서식 참조, 경량 HWPX 생성·검사·수용 테스트, 승인 템플릿 매니페스트, 전체·개별 ZIP 검증, 기여·PR 정책, README와 팀원·배포자·HTML·로드맵 안내
- 제외 범위: PR #2의 실제 과제정보·개인 작성자·날짜가 남은 원본 HWPX 반입, 새 `ax1-hwpx` 독립 스킬 추가, 공식 사업계획서 양식 자체 변경, 제품·개별 스킬 버전과 릴리즈 태그 변경
- 검증: `scripts/headless_hwpx_acceptance_test.py` 통과, `skill-creator` quick validation에서 `bizplan-hwpx`와 `bizplan-draft` 통과, `scripts/build_release.py` 전체 빌드와 개별 `bizplan-hwpx` ZIP 격리 생성·검사 통과, `git diff --check` 통과. 한컴 시각 검증 대기
- 호환성: 기존 `bizplan-hwpx` 이름과 8개 스킬 설치 구조를 유지함. 기존 3단계 기본 제목은 4단계로 확장되고 본문 목록 앞 공백은 7개에서 9개로 변경됨. Form 링크는 제거되며 개선 PR 제출에는 GitHub 인증과 저장소 쓰기 또는 fork 권한이 필요함
- 기여자: bmmmnmm (PR #2의 표준 라이브러리 산출물 서식 아이디어·구현 제안), AX1_JM (정책 결정·통합)
