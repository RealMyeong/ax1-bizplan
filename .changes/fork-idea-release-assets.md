# Fork 기반 제안 흐름과 통합 ZIP 배포

- 사용자 효과: 팀원의 에이전트가 아이디어는 Discussion, 정의된 문제는 Issue, 구현·검증된 변경은 Fork 기반 PR로 구분하고, 팀원은 Release에서 통합 ZIP 하나만 받아 8개 스킬을 함께 업데이트할 수 있음
- 변경 범위: 기여자·팀원·배포자·HTML 안내, AGENTS·Claude 진입점·PR 양식, 개선 제안 브리프, 공통 설계·로드맵 문구, Release 워크플로와 패키징·체크섬 검증
- 제외 범위: GitHub Discussions 기능의 저장소 설정 변경, 기존 Release 자산 삭제, 개별 스킬의 실행 기능·버전 변경, 새 태그와 Release 생성
- 검증: 전체 빌드, 공개 자산 목록·통합 ZIP 단일 체크섬·CI 내부 8개 개별 ZIP 격리 검사, HTML·Python·Git 검사를 수행
- 호환성: 통합 ZIP 설치 방식과 8개 스킬 구조는 유지함. 다음 Release부터 개별 스킬 ZIP은 공개 자산에서 제외되지만 태그의 저장소 경로와 CI 내부 격리 검증은 유지함
- 기여자: `jin_myeong`(AX1_JM), OpenAI Codex
