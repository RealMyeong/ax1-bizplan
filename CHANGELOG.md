# 변경이력

## Unreleased

- 현재 버전의 변경이력으로 주요 변경사항·설치 안내·스킬 버전을 포함한 GitHub Release 노트를 자동 생성하고, 자산·태그를 바꾸지 않은 채 기존 Release 본문도 보완하도록 개선

## v0.5.0 - 2026-08-20

- 팀원용 Codex·Claude 설치, 활용, 업데이트 안내 추가
- 배포자용 Form 접수, GitHub Issue 전환, 검증, 릴리스, 공지와 롤백 절차 추가
- 팀원용과 배포자용 내용을 전환하고 요청문을 복사할 수 있는 단일 HTML 안내문 추가
- Google Form을 공식 개선 요청 창구로 연결
- `bizplan-hwpx`를 추가해 확정 문안을 HWPX 양식에 원본 보존·dry-run·readback 방식으로 반영
- HWPX 구조 검증, 페이지 프리뷰와 Windows 한컴 전체 페이지 관찰을 분리해 정직한 제출 상태를 기록
- upstream 검증 기준을 source ref `b7ab90a1db826c5fa5db024ad01dc5132d073953`, `python-hwpx 6.2.1`, `python-hwpx-automation 7.0.2`, `hwpx-plugin 2.0.1`로 고정
- 초안·수정·최종점검·작업준비 스킬이 HWPX 요청을 새 전용 스킬로 연결하도록 갱신
- 실제 문서·인증서가 스킬 하위에 들어오면 빌드를 중단하도록 배포 안전장치 강화
- Windows에서 별도 form-fill 렌더 verifier가 멈출 수 있는 upstream 제한을 구조·값 영수증, readback, 프리뷰와 한컴 관찰로 분리해 정직하게 기록

## v0.4.0 - 2026-08-20

- AX1 팀 배포용 `ax1-bizplan` 플러그인·Git 저장소 구조 도입
- `bizplan-prepare`를 포함한 6개 스킬을 한 묶음으로 구성
- 저장소 버전과 개별 스킬 버전을 분리해 독립 업데이트 지원
- 검증, 개별 스킬 ZIP, 전체 플러그인 ZIP, 체크섬 생성 자동화
- GitHub 태그 생성 시 자동 Release를 만드는 워크플로 추가
- 실제 RFP·계획서·산출물이 저장소에 섞이지 않도록 제외 규칙 추가

## v0.3.2

- `bizplan-draft`가 초안 작성 전 사업 아이디어와 구현 방식을 구체화하고 실현 가능한 과업·KPI·실증 구조로 다듬도록 개선
- 실제 문서 산출물의 기본 형식을 DOCX로 변경하고 검증 가능한 경우에만 HWPX 사용

## v0.3.0

- Draft, Review, Revise, Preflight, Evidence Update 스킬의 호출 경계와 검증 구조 정비
- 범용 코어, 사업 프로파일, 근거 레지스터를 분리
