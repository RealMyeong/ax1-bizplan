# Windows HWPX 문제 해결

## `uvx`를 찾을 수 없음

- Astral 공식 Windows 설치 방법으로 `uv`를 설치함: <https://docs.astral.sh/uv/getting-started/installation/>
- `uv --version`, `uvx --version`을 확인함
- 설치 직후 기존 Codex 프로세스에는 PATH가 반영되지 않을 수 있으므로 앱을 완전히 종료한 뒤 다시 시작함

## 플러그인은 설치됐지만 `$hwpx`나 MCP 도구가 보이지 않음

- 기존 작업은 설치 전 도구 목록을 유지할 수 있음
- Codex 또는 Claude를 다시 시작하고 새 작업을 만듦
- 새 작업에서 `mcp_server_health()`를 호출함
- 버전·핵심 도구가 불일치하면 upstream 플러그인을 제거·재설치한 뒤 다시 시작함

## 한컴오피스가 설치됐지만 자동 실한컴 검증이 되지 않음

- 로컬 `Hwp.exe` 설치와 자동 real-Hancom 렌더 큐는 별개임
- Windows에서는 `Hwp.exe`를 명시적으로 열어 전체 페이지를 사람이 관찰하고 화면 증거를 남김
- 자동 `render_checked` 영수증이 필요하면 별도 mTLS 렌더 큐 구성이 필요함
- 자동 뷰어 탐지 실패를 문서 실패로 오인하지 않음

## `Hwp.exe` 직접 실행 시 빈 문서 또는 스킨 파일 오류

- 문서 경로에 공백이나 한글이 있으면 전체 경로를 큰따옴표로 묶음
- `Hwp.exe` 설치 폴더를 working directory로 지정함
- 이 조건을 지키지 않아 생긴 빈 문서·스킨 오류를 HWPX 손상으로 판정하지 않음

```powershell
$hwpPath = "C:\Program Files (x86)\Hnc\Office 2024\HOffice130\Bin\Hwp.exe"
$hwpxPath = (Resolve-Path -LiteralPath ".\검토본.hwpx").Path
Start-Process -FilePath $hwpPath `
  -WorkingDirectory (Split-Path -Parent $hwpPath) `
  -ArgumentList ('"' + $hwpxPath + '"')
```

## `.hwp` 파일만 있음

- 바이너리 HWP를 직접 편집하지 않음
- 원본을 보존하고 한컴오피스의 다른 이름으로 저장 기능으로 HWPX 사본을 만듦
- 변환된 HWPX를 열어 표·그림·수식·글꼴·페이지 수를 원본과 비교한 뒤 작업함

## 한글 경로나 콘솔 글자가 깨져 보임

- 터미널의 경로 표시 깨짐만으로 HWPX 본문이 손상됐다고 판단하지 않음
- `get_document_text` readback과 한컴 실제 화면을 각각 확인함
- 자동화 도구가 경로를 처리하지 못하는 경우 원본은 그대로 두고 ASCII 임시 작업 경로의 사본으로 재현한 뒤 결과를 원래 프로젝트에 돌려놓음

## `visual_review_required == true`

- 구조 검증이 실패했다는 뜻이 아니라 열린 문서 관찰이 남았다는 뜻임
- screenshot과 실제 관찰 없이 상태를 통과로 바꾸지 않음
- 제출 일정이 임박해도 `한컴 시각 검증 대기`를 숨기지 않음
