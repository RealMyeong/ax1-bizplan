# AX1 Bizplan 팀원 안내

이 문서는 AX1 사업계획서 스킬을 설치하고 실제 프로젝트에서 사용하는 팀원을 위한 안내입니다. 터미널 명령을 직접 입력하기보다 아래 요청문을 Codex 또는 Claude에 그대로 전달하는 방식을 권장합니다.

## 핵심 요약

- 사용자 범위에 한 번 설치하면 다른 프로젝트에서도 계속 사용할 수 있습니다.
- 새 프로젝트를 만들 때마다 다시 설치할 필요는 없습니다.
- 새 버전 안내를 받았을 때만 업데이트합니다.
- 실제 사업계획서, 기관명, 개인정보와 비공개 RFP는 GitHub나 개선 요청 Form에 직접 올리지 않습니다.
- 오류·개선 아이디어는 [AX1 사업계획서 스킬 개선 요청 Form](https://forms.gle/GG6GYrgboA4pnkVE6)으로 전달합니다.

## 설치 전에 준비할 것

다음 중 하나가 필요합니다.

1. GitHub 저장소 접근 권한
   - 저장소: <https://github.com/RealMyeong/ax1-bizplan>
2. GitHub 접근 권한이 없는 경우
   - 배포자가 공유한 `ax1-bizplan-v버전.zip`
   - 함께 제공된 `SHA256SUMS.txt`

GitHub에서 404 또는 권한 오류가 발생하면 반복 시도하지 말고 배포자에게 최신 Release ZIP을 요청합니다.

## Codex에 설치 요청하기

Codex의 새 작업에서 다음 내용을 그대로 요청합니다.

```text
$skill-installer를 사용해서 AX1 Bizplan 스킬을 사용자 범위에 설치해줘.

설치 원본: https://github.com/RealMyeong/ax1-bizplan
대상: 저장소의 skills 폴더에 있는 6개 스킬 전체

1. VERSION과 최신 안정 Release를 확인해줘.
2. 기존에 설치된 AX1 사업계획서 스킬이 있으면 버전과 위치를 확인하고 백업해줘.
3. 최신 버전을 사용자 범위에 설치해 새 프로젝트에서도 사용할 수 있게 해줘.
4. SKILL.md와 참조·에셋 파일이 빠짐없이 설치됐는지 확인해줘.
5. 설치 전후 버전, 설치된 스킬 목록, 검증 결과를 알려줘.
6. 다시 시작이 필요하면 알려줘.
```

GitHub에 접근할 수 없다면 Release ZIP을 Codex에 첨부하고 첫 줄을 다음과 같이 바꿉니다.

```text
첨부한 AX1 Bizplan Release ZIP과 SHA256SUMS.txt를 사용해 체크섬을 확인한 뒤 사용자 범위에 설치해줘.
```

Codex가 변경을 바로 감지하지 못할 때만 Codex를 다시 시작합니다.

## Claude Code에 설치 요청하기

Claude Code가 설치되어 있지 않다면 먼저 공식 설치 안내에 따라 설치하고 로그인합니다. Windows에서는 공식 WinGet 설치를 사용할 수 있습니다.

```powershell
winget install Anthropic.ClaudeCode
```

그다음 Claude Code에서 다음 내용을 요청합니다.

```text
AX1 Bizplan 스킬을 모든 프로젝트에서 사용할 수 있도록 사용자 스킬로 설치해줘.

설치 원본: https://github.com/RealMyeong/ax1-bizplan
원본 폴더: skills
설치 위치: ~/.claude/skills

1. VERSION과 최신 안정 Release를 확인해줘.
2. 기존 AX1 사업계획서 스킬이 있으면 먼저 백업해줘.
3. skills 폴더의 6개 스킬 디렉터리를 참조·에셋·스크립트와 함께 설치해줘.
4. 설치 전후 버전과 설치된 스킬 목록을 알려줘.
5. Claude Code가 스킬을 인식하는지 확인해줘.
```

GitHub에 접근할 수 없다면 Release ZIP을 내려받은 폴더에서 Claude Code를 열고 다음과 같이 요청합니다.

```text
이 폴더의 AX1 Bizplan Release ZIP을 풀고, 기존 버전을 백업한 뒤 skills 폴더의 6개 스킬을 ~/.claude/skills에 설치해줘. 설치 결과도 검증해줘.
```

Claude Code는 일반적으로 사용자 스킬 폴더의 변경을 실행 중에도 감지합니다. 사용자 스킬 폴더를 처음 만든 경우에만 다시 시작이 필요할 수 있습니다.

## 설치 확인

다음 6개 스킬이 보여야 합니다.

| 스킬 | 언제 사용하는가 |
|---|---|
| `bizplan-prepare` | 새 사업계획서 프로젝트의 폴더와 준비현황을 구성할 때 |
| `bizplan-draft` | 아이디어·구현방식을 구체화하고 초안을 작성할 때 |
| `bizplan-review` | 작성본을 평가위원 관점에서 검토할 때 |
| `bizplan-revise` | 검토·평가의견을 문서 전체에 일관되게 반영할 때 |
| `bizplan-preflight` | 제출 직전에 형식·수치·도표·버전을 점검할 때 |
| `bizplan-evidence-update` | 새 근거를 스킬 자체에 반영할 때. 일반 팀원은 실행하지 않고 Form으로 접수 |

Codex에서는 `$bizplan-prepare`처럼 `$`로 스킬을 지정합니다. Claude Code에서는 `/bizplan-prepare`처럼 `/`로 호출합니다. 자연어 요청만으로도 자동 선택될 수 있지만 중요한 작업은 스킬 이름을 명시하는 편이 안전합니다.

## 권장 사용 순서

### 1. 프로젝트 준비

프로젝트 최상위 폴더를 만든 뒤 공고문, RFP, 작성 양식과 참고자료를 준비합니다.

Codex:

```text
$bizplan-prepare를 사용해서 현재 프로젝트 폴더를 사업계획서 작성 작업공간으로 준비해줘. 기존 파일은 이동하거나 덮어쓰지 마.
```

Claude Code:

```text
/bizplan-prepare 현재 프로젝트 폴더를 사업계획서 작성 작업공간으로 준비해줘. 기존 파일은 이동하거나 덮어쓰지 마.
```

### 2. 초안 작성

```text
$bizplan-draft를 사용해 공고문·RFP·양식을 먼저 분석해줘.
바로 큰 틀만 쓰지 말고, 사업 아이디어와 구현 방식이 부족하면 먼저 질문하고 실행대안을 제시해줘.
내 답변을 실현 가능한 과업, 연차, KPI, 실증, 사업화 구조로 다듬은 뒤 DOCX 초안을 작성해줘.
근거가 없는 수치는 가정으로 표시해줘.
```

Claude Code에서는 `$bizplan-draft`를 `/bizplan-draft`로 바꿉니다.

### 3. 사전 검토

```text
$bizplan-review를 사용해서 작성본을 공고문·RFP·평가배점표와 대조해줘. 치명적 누락, 논리·수치 불일치, KPI 증빙 가능성을 우선순위별로 정리하고 교정문안도 제시해줘.
```

### 4. 검토의견 반영

```text
$bizplan-revise를 사용해서 검토의견을 반영해줘. 한 항목을 고치면 관련 목표, KPI, 연차, 역할과 표도 함께 동기화하고 반영 대장을 만들어줘.
```

### 5. 제출 직전 점검

```text
$bizplan-preflight를 사용해서 제출 직전 상태를 점검해줘. 빈칸, 페이지, 도표, 수치, 기관명, KPI, 파일명, 버전과 민감정보를 확인하고 마지막 조치 목록을 만들어줘.
```

## 결과물 사용 원칙

- 문서 산출물은 DOCX를 기본으로 사용합니다.
- HWPX는 변환과 렌더링을 실제로 검증할 수 있을 때만 사용합니다.
- 생성된 수치·일정·기관 역할은 담당자가 공식 자료와 대조합니다.
- 제출본은 항상 `bizplan-preflight` 점검 후 사람이 최종 승인합니다.
- 스킬 저장소에는 프로젝트 원본과 결과물을 넣지 않습니다.

## 업데이트 방법

배포자가 새 버전을 안내하면 최초 설치 때 사용한 요청문에서 `설치`를 `업데이트`로 바꿔 요청합니다.

```text
AX1 Bizplan을 최신 안정 버전으로 업데이트해줘. 기존 버전을 백업하고, 설치 원본의 VERSION과 Release를 확인한 뒤 6개 스킬을 함께 교체해줘. 업데이트 전후 버전과 변경된 스킬, 검증 결과를 알려줘.
```

업데이트가 끝나면 새 작업을 열어 변경된 스킬을 한 번 호출합니다. 문제가 생기면 백업본 또는 이전 Release로 되돌려 달라고 에이전트에게 요청합니다.

## 오류·개선사항 전달 방법

[개선 요청 Form](https://forms.gle/GG6GYrgboA4pnkVE6)에 다음 내용을 적습니다.

- 사용한 에이전트와 스킬
- 사용한 스킬 버전
- 에이전트에게 요청한 내용
- 실제 결과와 기대 결과
- 사람이 직접 보완한 내용
- 반복 발생 여부와 추가 메모

실제 사업계획서 내용, 기관명, 개인정보와 비공개 평가의견은 Form에 붙여넣지 않습니다. 원본은 접근이 통제된 Drive 폴더에 두고 위치만 기록합니다. 제한 폴더 접근 권한이 없다면 배포자에게 별도로 전달합니다.

## 공식 참고자료

- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code: Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Claude Code: Getting started](https://code.claude.com/docs/en/getting-started)
