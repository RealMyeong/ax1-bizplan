# Upstream HWPX 호환성과 설치

이 문서는 AX1 정책 스킬이 의존하는 외부 HWPX 실행 환경의 설치·버전 경계를 정의함

## 검증 기준 조합

2026-08-20 AX1 검증 기준:

| 구성요소 | 버전 |
|---|---:|
| `python-hwpx` | `6.2.1` |
| `python-hwpx-automation` | `7.0.2` |
| `hwpx-plugin` | `2.0.1` |
| upstream source ref | `b7ab90a1db826c5fa5db024ad01dc5132d073953` |

플러그인 버전 하나만 보고 전체 실행환경을 같다고 판단하지 않음. 작업 시작 시 `mcp_server_health()`에서 세 구성요소의 실제 버전과 도구 표면을 기록함

근거:

- <https://github.com/airmang/hwpx-plugins/tree/b7ab90a1db826c5fa5db024ad01dc5132d073953>
- <https://github.com/airmang/hwpx-plugins/blob/b7ab90a1db826c5fa5db024ad01dc5132d073953/packaging/product-identity.json>
- <https://github.com/airmang/hwpx-plugins/blob/b7ab90a1db826c5fa5db024ad01dc5132d073953/SKILL.md>

## Codex 설치

Windows에서는 먼저 `uvx`가 PATH에서 실행되어야 함. Astral 공식 설치 안내를 따름

<https://docs.astral.sh/uv/getting-started/installation/>

```powershell
codex plugin marketplace add airmang/hwpx-plugins --ref b7ab90a1db826c5fa5db024ad01dc5132d073953
codex plugin add hwpx-plugin@hwpx
```

설치 후 Codex 앱을 완전히 다시 시작하고 새 작업에서 `$hwpx`와 MCP 도구를 확인함

## Claude Code 설치

```powershell
claude plugin marketplace add airmang/hwpx-plugins@b7ab90a1db826c5fa5db024ad01dc5132d073953
claude plugin install hwpx-plugin@hwpx
```

Claude Code에서도 새 세션에서 `/hwpx`와 MCP 연결 상태를 확인함

## 시작 건강검사

`mcp_server_health()` 결과에서 다음을 모두 확인함

- `toolSurface.status == "ok"`
- `toolSurface.missingKeyTools == []`
- `version`, `pythonHwpxVersion`, `skillBundleVersion` 존재
- 실제 값이 AX1 검증 기준 조합과 일치

불일치하면 현재 작업에서 억지로 계속하지 않고 플러그인 마켓플레이스를 갱신·재설치한 뒤 새 작업에서 재검사함

## 업데이트 정책

- upstream 새 버전이 나와도 팀 전체에 즉시 자동 승격하지 않음
- 익명화된 샘플로 생성·사본 편집·readback·preview·한컴 재개방 검증 후 AX1 기준 조합을 갱신함
- 기준 조합 변경은 source ref와 세 구성요소 버전을 함께 바꾸고 AX1 마이너 또는 패치 버전의 변경이력과 배포자 안내에 기록함
- 실제 RFP·계획서·개인정보를 upstream 이슈나 공개 테스트에 첨부하지 않음

## 라이선스 경계

upstream은 Apache-2.0 라이선스임. AX1은 코드를 복제하지 않고 별도 의존성으로 사용함. 향후 코드를 복사·수정해 배포할 경우 원 저작권·LICENSE·NOTICE를 유지하고 수정 사실을 표시해야 함

<https://github.com/airmang/hwpx-plugins/blob/b7ab90a1db826c5fa5db024ad01dc5132d073953/LICENSE>
