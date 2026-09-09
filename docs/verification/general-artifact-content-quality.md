# 일반 산출물 본문 품질 패치 검증

- 대상: v0.10.1 / bizplan-hwpx v0.4.5, 2026-09-09
- 제안: [Issue #5](https://github.com/RealMyeong/ax1-bizplan/issues/5), sooyeol-kim
- 비교: v0.10.0 및 패치 직전 main f1fd28c. 기존 내용 준비 단계는 일반 산출물까지 draft/revise로 보낼 수 있었고, readback·서식 검사와 별도인 일반 산출물 내용 검토 기준이 없었다. 이는 지침의 공백 확인이며 제보한 실제 세션의 단일 원인 확정은 아니다.

## 수동 내용 검토

작성 에이전트가 [합성 사례](../../examples/general-artifact-content-cases.md)를 새 참조 기준으로 직접 검토했다. 독립 평가자·새 모델 세션의 행동 시험이나 자동 의미 정확도 측정이 아니다.

| 사례 | 관찰·판정 |
|---|---|
| 지침 혼입·근거 연결 | 후보의 두 작업 규칙은 독자용 본문에서 분리. 공정 사실·합성 출처와 매핑 미정→R-01 집계 의존관계 유지 |
| 불확실성·인용 | 원인 가능성을 확정 원인으로 바꾼 후보는 보류. 출처·계약상 한계·검토 이력을 제거하지 않는 기준 확인 |
| ID·약어 | R-01·EQ-01·주소를 구분. QX 의미와 실제 대응 주소를 추측하지 않음 |
| 전역 재검토 | 첫 절 수정·ID 보존만으로 통과시키지 않고 마지막 절의 지침과 근거 없는 완료 주장을 다시 검사 |
| 목적·범위 예외 | 회의록 목차를 강제하지 않고 작성 지침 산출물은 지침 본문 보존. 서식 전용 요청에서 내용 자동 개작 금지 |
| 경로 선택 | 일반 산출물은 14번 참조로 준비. 사업계획서는 기존 공식 양식·전용 스킬·별도 확인 게이트 유지 |

[검토 후 합성 본문](../../examples/general-artifact-reviewed-sample.md)을 만들고 다시 읽는 과정에서 “수치나 승인 상태를 확정하지 않는다”라는 작성자용 표현이 남은 것을 발견했다. 이를 독자에게 필요한 “정지 판정 임계값은 제공되지 않아 결정이 필요하다”로 교정한 뒤 전체를 재검토했다. 중요한 미확정 매핑·임계값·QX 의미는 본문에 남았으므로 이 샘플은 제출 준비 완료가 아니라 내용 결정 필요 상태다.

## 생성·자동 검사

```powershell
python scripts/build_release.py
python scripts/pages_test.py
python <skill-creator>/scripts/quick_validate.py <각 스킬 폴더>
python skills/bizplan-hwpx/scripts/build_headless_artifact.py --content examples/general-artifact-reviewed-sample.md --agency "합성 발주기관" --program "합성 검증 사업" --project-number "TEST-0000" --project "합성 프로젝트" --title "본문품질 합성검증" --document-type "요구사항정의서" --artifact-version v0.1 --revision-note "최초 작성" --revision-author "합성 작성자" --revision-date 2026-09-09 -o "<새 임시폴더>/DXS-AX-REQ-본문품질_합성검증-20260909-v0.1.hwpx"
python skills/bizplan-hwpx/scripts/check_headless_artifact.py <생성 파일>
```

- 전체 빌드·9개 스킬 구조 검사·Pages 7건 통과. 기존 HWPX·표 배치·사업비·발표자료 회귀와 통합/개별 ZIP 격리 검사는 전체 빌드에 포함된다.
- 새 내용 참조가 개별 HWPX 스킬 ZIP에 반드시 포함되도록 패키지 필수 파일 검사를 추가했다.
- 합성 HWPX 14개 본문 블록 생성·내장 한글 보존 검사 127개 묶음·서식 검사 통과. ZIP에서 section0.xml을 재개방해 본문과 표를 직접 읽고 R-01·기능·미정 매핑·임계값·주소 예시·QX 미정이 보존된 것을 확인했다.
- 관찰 파일 SHA-256: `8d4f35b48a079dbca99f98edabb1908ee4e6e4c3041ec6413c1c362539db5d9c`. ZIP 타임스탬프에 따라 재생성 해시는 달라질 수 있다. 생성 HWPX는 로컬 검증용으로만 보관하며 공개 저장소에는 합성 Markdown만 추가했다.
- 표지~목차의 승인 템플릿 관리 지침은 불가침 영역이므로 본문 지침 정리 대상으로 삭제하지 않았다. 생성 엔진·승인 템플릿 파일·서식 규칙은 이번 패치에서 수정하지 않았다.

## 남은 제한

- 자동 검사 통과는 의미 품질·독립 세션의 개선 효과를 보장하지 않는다. 이번 변경은 문맥 검토 지침이며 자동 경고·삭제 기능은 추가하지 않았다.
- 원래 제보 문서를 재작성하지 않았으며 원인 확정·현장 재현은 미수행이다. Issue #5는 릴리즈 안내 후 재확인 대상으로 열어 둔다.
- 이번 합성 파일의 upstream open-safety·프리뷰·실제 한컴 전체 페이지 시각 검증은 미수행이다. 기존 엔진 회귀 통과를 새 파일의 실한컴 검증으로 표현하지 않는다.
