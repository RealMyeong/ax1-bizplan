# 경량 HWPX 생성 절차

확정된 Markdown 본문과 표지 정보가 모두 준비됐을 때만 사용한다. 내용이 비었거나 구현 방식이 미확정이면 먼저 `bizplan-draft`를 사용한다.

```powershell
python <스킬>/scripts/build_headless_artifact.py `
  --content "본문.md" `
  --agency "발주기관" `
  --program "상위 사업명" `
  --project-number "과제번호" `
  --project "세부 사업명" `
  --title "산출물 제목" `
  --document-type "사업계획서" `
  -o "산출물_AX1_v01.hwpx"
```

별도 `--template`은 받지 않는다. 포함된 승인 템플릿만 사용한다.

## Markdown 지원

| 입력 | 결과 |
|---|---|
| `# 제목` | 장 제목 15pt, 새 쪽 시작 |
| `## 제목` | 절 제목 12pt |
| `### 제목` | 항 제목 10.5pt |
| 일반 문단 | 10pt, 160% |
| `- 항목` | 단계형 목록 |
| `1. 항목` | 번호가 포함된 별도 문단 |
| Markdown 표 | 첫 행 머리행, 모든 셀 160% |

그림·쪽번호·병합 셀·각주·미주는 생성하지 않는다. 필요한 문서는 upstream `hwpx` 편집 경로를 사용한다.

## 생성 후 검증

생성기는 구조·서식 자동검사를 통과한 경우에만 최종 경로에 파일을 둔다. 이어서 다음을 수행한다.

1. `check_headless_artifact.py` 재검사
2. upstream `hwpx`의 구조·open-safety·readback 검증
3. `render_preview` 검토
4. 제출 후보라면 Windows 한컴에서 전체 페이지 관찰

경량 생성 성공은 `structure_verified` 이전의 자동 생성 성공일 뿐이며, 한컴 시각 검증이나 제출 준비 완료를 뜻하지 않는다.
