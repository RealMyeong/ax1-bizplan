# AX1 Bizplan

AX1 팀의 국가 R&D·공모 사업계획서 업무를 위한 배포 전용 저장소입니다. 실제 공고문, RFP, 사업계획서 원본과 생성 산출물은 이 저장소에 넣지 않고 접근이 통제된 공유 드라이브에서 관리합니다.

## 바로가기

| 대상 | 문서·창구 |
|---|---|
| 전체 안내 | [HTML 안내문](docs/ax1-bizplan-guide.html) |
| 팀원 | [설치·활용·업데이트 안내](docs/team-guide.md) |
| 배포자 | [개선 접수·개발·릴리스 운영 안내](docs/maintainer-guide.md) |
| 기여자·PR | [기여 안내](CONTRIBUTING.md) · [PR 운영 원칙](docs/pr-operating-policy.md) |
| 개선 요청 | [AX1 사업계획서 스킬 개선 요청 Form](https://forms.gle/GG6GYrgboA4pnkVE6) |
| 배포 파일 | [GitHub Releases](https://github.com/RealMyeong/ax1-bizplan/releases) |

GitHub 접근 권한이 없는 팀원에게는 배포자가 최신 Release ZIP과 `SHA256SUMS.txt`를 공유 드라이브로 전달합니다. 팀원은 설치 경로를 직접 다루기보다 Codex 또는 Claude에게 설치·백업·검증을 요청하는 방식을 기본으로 합니다.

## 포함 스킬

| 스킬 | 용도 |
|---|---|
| `bizplan-prepare` | 표준 작업공간, 준비현황과 이전버전 보관함 생성 |
| `bizplan-draft` | 대화형 사업 설계, 양식 배분 및 밀도 있는 신규 초안 작성 |
| `bizplan-hwpx` | 승인 템플릿 경량 HWPX 생성, 공식 양식 반영과 한컴 검증 |
| `bizplan-review` | 평가위원 관점 사전 검토와 교정문안 작성 |
| `bizplan-revise` | 검토의견 반영과 관련 항목 전역 동기화 |
| `bizplan-preflight` | 제출 직전 형식·수치·도표·버전 최종 점검 |
| `bizplan-evidence-update` | 새 근거를 레지스터·프로파일·테스트에 누적 |

## 작업 시작 전 확인

7개 스킬은 실제 작업에 들어가기 전에 에이전트가 이해한 목적, 예상 입력자료, 작업 범위, 산출물과 핵심 가정을 먼저 설명합니다. 사용자가 그 설명을 본 뒤 별도 메시지로 `맞아, 진행해줘`처럼 동의해야 파일 조회와 도구 실행을 시작합니다. 처음 요청에 `바로 진행` 또는 `질문 없이`라고 적어도 이 확인은 생략되지 않습니다.

설명이 다르면 수정할 내용을 알려주면 됩니다. 에이전트는 바뀐 이해 내용을 다시 제시하고 재확인을 기다립니다. 작업 중 목적·수정 대상·산출물이 실질적으로 달라질 때도 같은 방식으로 재확인하며, 초안 구현 브리프 확정·HWPX 실제 반영·외부 배포 같은 후속 승인은 별도로 유지합니다.

## HWPX 사용 방식

승인된 AX1 표지 템플릿에 확정 Markdown을 넣어 새 산출물을 만드는 경량 모드는 Python 표준 라이브러리만 사용합니다. 한컴오피스·COM·pyhwpx를 실행하지 않아 창이나 승인 팝업 없이 생성할 수 있고, 본문과 표 셀 줄간격을 모두 160%로 적용합니다.

공식 양식의 빈칸 채움, 기존 HWPX 수정, 다중 섹션·그림·병합 셀 등은 [airmang/hwpx-plugins](https://github.com/airmang/hwpx-plugins)를 별도 의존성으로 사용합니다. 이 기능이 필요한 팀원은 한 번만 다음 플러그인을 설치하고 Codex 또는 Claude를 다시 시작합니다.

```powershell
codex plugin marketplace add airmang/hwpx-plugins --ref b7ab90a1db826c5fa5db024ad01dc5132d073953
codex plugin add hwpx-plugin@hwpx
```

```powershell
claude plugin marketplace add airmang/hwpx-plugins@b7ab90a1db826c5fa5db024ad01dc5132d073953
claude plugin install hwpx-plugin@hwpx
```

Windows에서는 `uvx`가 PATH에 있어야 하며, 실제 제출 후보는 한컴오피스에서 전체 페이지를 다시 확인해야 합니다. AX1 검증 기준 조합은 source ref `b7ab90a1db826c5fa5db024ad01dc5132d073953`, `python-hwpx 6.2.1`, `python-hwpx-automation 7.0.2`, `hwpx-plugin 2.0.1`입니다.

경량 모드도 실제 한컴 조판을 대신하지 않습니다. 생성 후 구조·readback·프리뷰를 검사하고 제출 후보는 한컴에서 전체 페이지를 확인합니다.

## 저장소 구성

```text
.codex-plugin/   Codex 플러그인 정보
skills/          팀에 배포할 독립 스킬
shared/          공통 코어, 사업 프로파일, 익명화·요약 근거
examples/        회귀 테스트 예시
scripts/         검증 및 릴리스 패키지 생성 도구
docs/            팀 운영 양식
.changes/        팀원 PR의 사용자 영향 변경 조각
```

## 운영 흐름

```text
팀 사용 → 공유 드라이브 개선 인박스 → 근거 분류 → 스킬 수정
       → 검증 → Unreleased 누적 → 배포 승인 → 버전·태그
       → GitHub Release → 팀원 업데이트
```

- `main`에는 팀에서 사용할 수 있는 안정 상태만 유지합니다.
- 변경은 짧은 작업 브랜치에서 검토한 뒤 `main`에 합칩니다.
- 팀원과 팀원 에이전트는 [기여 안내](CONTRIBUTING.md)와 [PR 운영 원칙](docs/pr-operating-policy.md)을 따릅니다. 기여 PR은 `.changes/`에 변경 조각을 추가하고 버전·태그·릴리즈 파일은 수정하지 않습니다.
- 저장소 버전은 루트 `VERSION`과 `.codex-plugin/plugin.json`에 동일하게 기록합니다.
- 개별 스킬 버전은 각 `SKILL.md`의 `metadata.version`으로 별도 관리합니다.
- 릴리스 태그는 `vX.Y.Z` 형식으로 생성합니다.
- v0.7.0 이후 변경사항은 먼저 `CHANGELOG.md`의 `Unreleased`에 누적하며, 커밋이나 개선 요청마다 태그를 만들지 않습니다.
- 기존 스킬의 호환 가능한 질문·출력·템플릿·안전·검증 개선은 패치를 기본으로 하고, 새 스킬·새 필수 의존성·팀 사용법의 실질적 전환일 때만 관리자가 마이너를 승인합니다.
- `VERSION`, 플러그인·개별 스킬 버전과 태그는 배포 묶음이 확정될 때 한 번에 올립니다. 현재 안정 버전은 `v0.7.3`이며 다음 호환 개선 묶음은 기본적으로 패치 후보로 둡니다.

## 프로젝트 산출물 버전 운영

- `08_작성중`, `09_검토_수정`, `10_제출본`에는 산출물군별 최신 검증본 한 묶음만 둡니다. 사업계획서 본문, 발표자료, 검토보고서와 반영대장은 서로 다른 산출물군입니다.
- 관리 산출물의 KPI·예산·기관 역할·기간·과업·실증 등 의미가 바뀌면 다른 현재 산출물의 영향 위치를 비교하고, 필요한 파일만 각각 새 버전으로 함께 갱신합니다. 기준 원천과 결과는 프로젝트의 `산출물_연동현황.md`에 기록합니다.
- 발표자료·PDF·검토보고서의 고유 문구를 상위 원장이나 계획서로 자동 역전파하지 않습니다. 필수 연동본 하나라도 검증하지 못하면 에이전트가 만든 후보는 부분 승격하지 않고 기존 현재본을 유지합니다.
- 새 버전 검증이 끝나면 이전 버전의 주 파일과 같은 버전의 PDF·프리뷰·검증기록을 `98_이전버전`으로 옮기고 `산출물_버전이력.md`에 상대경로와 SHA-256을 남깁니다.
- 공고문·RFP·공식 양식·근거자료와 서로 다른 제출 사건의 서명·접수 증거는 자동 이동하지 않습니다. 접수번호·서명·제출시각이 특정 해시와 연결된 실제 제출 완료 파일도 이동·이름변경·덮어쓰기하지 않고, 정정은 별도 재제출 후보로 만듭니다. 버전이 모호하거나 검증에 실패해도 기존 현재본을 유지합니다.
- 이 보관함과 연동현황은 실제 프로젝트 폴더에 생성됩니다. 별도 `최신 산출물` 복제 폴더를 만들지 않고 세 작업단계의 현재본을 최신 영역으로 사용합니다. GitHub Release ZIP을 공유 Drive의 `latest/archive`로 나누는 배포 운영과는 별개입니다.

## 검증 및 패키징

```powershell
python scripts/build_release.py
```

검증이 통과하면 `dist/`에 전체 플러그인 ZIP, 개별 스킬 ZIP, SHA-256 체크섬과 `CHANGELOG.md` 기반 `RELEASE_NOTES.md`가 생성됩니다. `v*` 태그를 GitHub에 올리면 GitHub Actions가 같은 검증을 수행하고 주요 변경사항이 포함된 Release를 생성합니다.

## 팀원 업데이트 요청 예시

Codex에서는 다음처럼 요청합니다. 비공개 저장소에 접근할 수 없다면 공유 드라이브에서 받은 Release ZIP을 첨부하고 같은 요청을 사용합니다.

```text
$skill-installer를 사용해서 AX1의 GitHub ax1-bizplan 저장소에서
최신 안정 릴리스를 확인하고 AX1 사업계획서 스킬 7개를 사용자 범위에 설치 또는 업데이트해줘.
기존 버전은 먼저 백업하고, 설치 전후 버전과 검증 결과도 알려줘.
저장소: https://github.com/RealMyeong/ax1-bizplan
```

Claude에서는 같은 저장소의 `skills/`를 `~/.claude/skills/`에 설치합니다. 자세한 요청문과 활용 예시는 [팀원 안내](docs/team-guide.md)를 따릅니다. 스킬 본문·참조자료는 공통으로 유지하고 제품별 설치 과정만 분리합니다.

## 저장 금지 자료

- 실제 사업계획서와 발표자료 원본
- 공개되지 않은 RFP, 평가의견서, 계약·고객 자료
- 개인정보, 계정정보, API 키와 인증서
- 작업 중간파일과 자동 생성된 DOCX·HWP·HWPX·PDF. 단, 매니페스트 SHA-256과 익명화 검사를 통과한 `bizplan-hwpx` 승인 템플릿 한 개는 예외

새 사례에서 얻은 내용은 원문을 올리는 대신 `docs/feedback-intake-template.md`로 정리하고, 재사용 가능한 규칙·테스트만 저장소에 반영합니다.

## 참고

- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [OpenAI: Build plugin skills](https://developers.openai.com/plugins/build/skills)
