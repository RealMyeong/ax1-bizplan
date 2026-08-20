# AX1 Bizplan

AX1 팀의 국가 R&D·공모 사업계획서 업무를 위한 배포 전용 저장소입니다. 실제 공고문, RFP, 사업계획서 원본과 생성 산출물은 이 저장소에 넣지 않고 접근이 통제된 공유 드라이브에서 관리합니다.

## 포함 스킬

| 스킬 | 용도 |
|---|---|
| `bizplan-prepare` | 표준 작업공간과 준비현황 체크리스트 생성 |
| `bizplan-draft` | 아이디어·구현방식 구체화 및 신규 초안 작성 |
| `bizplan-review` | 평가위원 관점 사전 검토와 교정문안 작성 |
| `bizplan-revise` | 검토의견 반영과 관련 항목 전역 동기화 |
| `bizplan-preflight` | 제출 직전 형식·수치·도표·버전 최종 점검 |
| `bizplan-evidence-update` | 새 근거를 레지스터·프로파일·테스트에 누적 |

## 저장소 구성

```text
.codex-plugin/   Codex 플러그인 정보
skills/          팀에 배포할 독립 스킬
shared/          공통 코어, 사업 프로파일, 익명화·요약 근거
examples/        회귀 테스트 예시
scripts/         검증 및 릴리스 패키지 생성 도구
docs/            팀 운영 양식
```

## 운영 흐름

```text
팀 사용 → 공유 드라이브 개선 인박스 → 근거 분류 → 스킬 수정
       → 검증 → 버전 태그 → GitHub Release → 팀원 업데이트
```

- `main`에는 팀에서 사용할 수 있는 안정 상태만 유지합니다.
- 변경은 짧은 작업 브랜치에서 검토한 뒤 `main`에 합칩니다.
- 저장소 버전은 루트 `VERSION`과 `.codex-plugin/plugin.json`에 동일하게 기록합니다.
- 개별 스킬 버전은 각 `SKILL.md`의 `metadata.version`으로 별도 관리합니다.
- 릴리스 태그는 `v0.4.0` 형식으로 생성합니다.

## 검증 및 패키징

```powershell
python scripts/build_release.py
```

검증이 통과하면 `dist/`에 전체 플러그인 ZIP, 개별 스킬 ZIP과 SHA-256 체크섬이 생성됩니다. `v*` 태그를 GitHub에 올리면 GitHub Actions가 같은 검증을 수행하고 Release를 생성합니다.

## 팀원 업데이트 요청 예시

Codex에서는 다음처럼 요청합니다.

```text
$skill-installer를 사용해서 AX1의 비공개 GitHub ax1-bizplan 저장소에서
최신 안정 릴리스를 확인하고 기존 버전을 백업한 다음 스킬을 업데이트해줘.
설치 전후 버전과 검증 결과도 알려줘.
```

Claude에서는 같은 저장소의 `skills/`를 기준으로 설치하되, 제품별 설치 경로와 지원 형식은 사용하는 Claude 환경에서 확인합니다. 스킬 본문·참조자료는 공통으로 유지하고 제품별 설치 과정만 분리합니다.

## 저장 금지 자료

- 실제 사업계획서와 발표자료 원본
- 공개되지 않은 RFP, 평가의견서, 계약·고객 자료
- 개인정보, 계정정보, API 키와 인증서
- 작업 중간파일과 자동 생성된 DOCX·HWP·PDF

새 사례에서 얻은 내용은 원문을 올리는 대신 `docs/feedback-intake-template.md`로 정리하고, 재사용 가능한 규칙·테스트만 저장소에 반영합니다.

## 참고

- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [OpenAI: Build plugin skills](https://developers.openai.com/plugins/build/skills)
