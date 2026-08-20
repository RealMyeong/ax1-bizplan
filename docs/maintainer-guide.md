# AX1 Bizplan 배포자 운영 안내

이 문서는 AX1 Bizplan의 관리자인 AX1_JM이 개선 요청을 취합하고, 스킬을 수정·검증·릴리스하고, 팀원에게 업데이트를 안내하는 절차를 정의합니다.

## 운영 원칙

- GitHub는 재사용 가능한 스킬, 익명화된 규칙, 테스트와 버전만 관리합니다.
- 실제 공고문, RFP, 사업계획서, 평가의견 원본과 개인정보는 제한된 Google Drive에서 관리합니다.
- 팀원은 GitHub Issue를 직접 만들지 않아도 됩니다. 개선 요청 Form이 단일 접수 창구입니다.
- Form 접수 내용을 검토한 뒤 재현 가능하고 범용적인 항목만 익명화하여 GitHub Issue로 전환합니다.
- `main`에는 팀이 바로 설치해도 되는 안정 버전만 둡니다.

## 운영 링크

| 용도 | 링크 |
|---|---|
| 팀 개선 요청 Form | <https://forms.gle/GG6GYrgboA4pnkVE6> |
| 응답 관리 시트 | <https://docs.google.com/spreadsheets/d/18VbGQ4ofPvqrTujPDSwcatgOiBWrbrcr_afOqd8T1Sg/edit> |
| AX1 관리 Drive | <https://drive.google.com/drive/folders/1phJEIHpeJvLnRPNn6YxogUDxjL4knlUv> |
| 원본근거 제한 폴더 | <https://drive.google.com/drive/folders/1YvjZxSAYpI1nDDvXmGSIztazosajhnJU> |
| GitHub 저장소 | <https://github.com/RealMyeong/ax1-bizplan> |
| GitHub Releases | <https://github.com/RealMyeong/ax1-bizplan/releases> |

## 권장 운영 주기

- 개선 요청: Form으로 상시 접수
- 분류·추가정보 요청: 주 1회
- 일반 릴리스: 2~4주 단위로 묶어서 배포
- 업무 중단 수준 오류: 검증 후 패치 버전으로 즉시 배포

요청이 들어올 때마다 바로 배포하면 검증 비용과 팀원의 업데이트 피로가 커집니다. 접수는 상시로 받고, 재현·분류는 주기적으로 하며, 검증된 변경을 일정 단위로 묶어 배포합니다.

## 1. 개선 요청 분류

응답 관리 시트에서 `처리상태`를 다음 순서로 관리합니다.

| 상태 | 의미 |
|---|---|
| 신규 | 아직 확인하지 않은 요청 |
| 추가정보 필요 | 재현 조건, 버전 또는 근거가 부족함 |
| 검토 중 | 중복·영향 범위·재현 여부를 확인 중 |
| 채택 | 스킬 변경 대상으로 확정 |
| 보류 | 단일 사례이거나 근거가 부족해 관찰 필요 |
| GitHub 이관 | 민감정보를 제거한 Issue를 생성함 |
| 수정 중 | 브랜치에서 수정·테스트 중 |
| 릴리스 완료 | 배포 버전과 안내까지 완료함 |

각 요청에는 가능하면 관리번호, 관련 요청, 담당자, GitHub Issue 링크와 반영 버전을 기록합니다.

## 2. 민감정보와 근거 처리

다음 내용은 GitHub Issue, 커밋 메시지와 스킬 예시에 넣지 않습니다.

- 실제 기관명, 고객명과 담당자 개인정보
- 미공개 사업계획서와 평가의견 원문
- 계약·예산·성과 등 외부 공개가 제한된 수치
- 계정정보, API 키, 인증서와 공유 토큰

원본은 `01_원본근거_제한공유` 폴더에서 관리하고, GitHub에는 다음처럼 일반화합니다.

```text
특정 기관명 → 주관기관 A
특정 사업명 → 제조 AI 실증형 R&D
실제 수치 → 범위 또는 구조만 유지한 예시 값
평가의견 원문 → 재사용 가능한 판단 규칙과 실패 패턴
```

## 3. GitHub Issue 전환 기준

다음 조건을 충족할 때 Issue로 전환합니다.

- 사용한 버전과 대상 스킬이 식별됨
- 입력·결과·기대 결과가 구분됨
- 같은 조건에서 재현되거나 근거가 충분함
- 한 프로젝트에만 맞춘 요구가 아니라 범용 규칙 또는 사업 프로파일로 분리 가능함
- 민감정보가 제거됨

Issue에는 다음 항목을 기록합니다.

```text
제목: [스킬명] 문제 또는 개선 내용

- 접수 관리번호:
- 영향 버전:
- 재현 요청문:
- 실제 동작:
- 기대 동작:
- 근거 유형:
- 영향 범위:
- 완료 조건:
- 원본 근거 위치: 제한 Drive 내부 경로만 기재
```

## 4. 수정 작업

저장소 최신 상태에서 짧은 작업 브랜치를 만듭니다.

```powershell
git switch main
git pull --ff-only
git switch -c fix/간단한-작업명
```

변경 유형에 맞게 작업합니다.

- 단순 문구·호출 조건 수정: 해당 `SKILL.md`와 관련 테스트만 변경
- 신규 근거·선정/탈락 사례 반영: `bizplan-evidence-update`를 사용해 근거 레지스터, 프로파일, 검토 렌즈와 테스트를 함께 갱신
- 출력 구조 변경: 관련 스킬의 참조자료·에셋·예상 동작 예시까지 동기화
- 공통 규칙 변경: 6개 스킬에 미치는 영향을 확인하고 필요한 복사본을 함께 갱신

에이전트 요청 예시:

```text
$bizplan-evidence-update를 사용해 제한 Drive의 새 근거를 분석해줘. 단일 사례를 바로 범용 규칙으로 승격하지 말고 기존 규칙과의 충돌, 적용 범위, 테스트 사례를 먼저 제안해줘. 승인할 변경과 보류할 변경을 분리해줘.
```

## 5. 버전 결정

| 변경 | 권장 버전 |
|---|---|
| 오탈자, 명확한 오류 수정, 호환되는 소규모 개선 | 패치: `0.4.0 → 0.4.1` |
| 새 스킬, 의미 있는 기능·워크플로 추가 | 마이너: `0.4.0 → 0.5.0` |
| 설치 방식이나 사용법이 크게 깨지는 변경 | 메이저: `0.x → 1.0.0` 이후 메이저 증가 |

다음을 함께 확인합니다.

- 루트 `VERSION`: 전체 묶음 버전
- `.codex-plugin/plugin.json`: 전체 묶음과 같은 버전
- 변경된 스킬 `SKILL.md`의 `metadata.version`: 개별 스킬 버전
- `CHANGELOG.md`: 사용자에게 보이는 변경사항

## 6. 검증과 패키징

```powershell
python scripts/build_release.py
```

검증이 통과하면 다음을 확인합니다.

- `dist/ax1-bizplan-v버전.zip`
- `dist/skills/`의 개별 스킬 ZIP
- `dist/SHA256SUMS.txt`
- 실제 RFP, 계획서, 평가의견, 산출물이 ZIP에 포함되지 않았는지
- 변경된 스킬의 대표 요청문과 경계 사례가 기대대로 동작하는지

검증 후 변경 내용을 확인합니다.

```powershell
git status --short
git diff --check
git diff
```

## 7. 검토·병합·릴리스

변경을 커밋하고 작업 브랜치를 GitHub에 올려 검토한 뒤 `main`에 병합합니다.

```powershell
git add README.md CHANGELOG.md VERSION .codex-plugin skills shared examples docs scripts
git commit -m "Update AX1 Bizplan to vX.Y.Z"
git push -u origin fix/간단한-작업명
```

병합 후 태그를 올리면 GitHub Actions가 검증하고 Release 파일을 생성합니다.

```powershell
git switch main
git pull --ff-only
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

태그 값은 반드시 `VERSION` 앞에 `v`를 붙인 값과 같아야 합니다.

## 8. GitHub 계정이 없는 팀원에게 배포

GitHub Release에서 다음 두 파일을 받아 공유 드라이브의 배포 폴더에 올립니다.

- `ax1-bizplan-vX.Y.Z.zip`
- `SHA256SUMS.txt`

배포 폴더에는 최신 버전만 `latest`로 표시하고, 이전 버전은 `archive`에 보관합니다. ZIP 파일을 다시 압축하거나 이름만 바꾸지 않습니다. 체크섬 검증이 달라질 수 있습니다.

팀 공지에는 다음 내용을 포함합니다.

- 새 버전
- 주요 변경 1~3개
- 업데이트가 필요한 사람
- Codex·Claude 업데이트 요청문
- Release ZIP 또는 GitHub Release 링크
- 개선 요청 Form 링크
- 문제 발생 시 이전 버전으로 되돌리는 방법

## 9. 팀 공지 예시

```text
[AX1 Bizplan vX.Y.Z 배포]

주요 변경
- 변경사항 1
- 변경사항 2

대상
- AX1 Bizplan을 사용하는 모든 팀원

업데이트 방법
Codex 또는 Claude에게 "AX1 Bizplan을 최신 안정 버전으로 업데이트하고 기존 버전을 백업한 뒤 설치 결과를 검증해줘"라고 요청하세요.

GitHub: https://github.com/RealMyeong/ax1-bizplan/releases/tag/vX.Y.Z
GitHub 접근이 없으면 공유 드라이브의 ax1-bizplan-vX.Y.Z.zip을 사용하세요.

오류·개선 요청: https://forms.gle/GG6GYrgboA4pnkVE6
```

## 10. 릴리스 완료 처리

배포가 끝나면 응답 관리 시트에서 다음을 갱신합니다.

- 처리상태: `릴리스 완료`
- GitHub Issue: Issue 또는 Release 링크
- 반영버전: `vX.Y.Z`
- 관리메모: 검증 결과와 예외사항

Issue에는 반영 버전을 기록하고 닫습니다. 추가 검증이 필요한 요청은 닫지 말고 후속 테스트 결과를 연결합니다.

## 11. 롤백

새 버전에 문제가 있으면 다음 순서로 처리합니다.

1. 팀에 업데이트 중지 안내
2. 이전 Release ZIP으로 사용자 스킬 복원
3. 문제 버전과 영향 범위를 관리 시트에 기록
4. 수정 브랜치에서 재현 테스트 추가
5. 패치 버전으로 다시 릴리스

이미 배포한 Git 태그와 Release를 임의로 덮어쓰지 않습니다. 수정 사항은 새 버전으로 배포해 이력을 보존합니다.

## 공식 참고자료

- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code: Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Claude Code: Create plugins](https://code.claude.com/docs/en/plugins)
