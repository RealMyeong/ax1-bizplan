# HWPX 내부 구조와 규칙 매핑

HWPX는 ZIP이다. 규칙별로 고쳐야 할 위치가 정해져 있으므로 추측하지 않는다.

```text
Contents/header.xml     글꼴 · 문단모양(줄간격) · 테두리채우기(표 음영)
Contents/section0.xml   본문 문단 · 표 · 셀 · 줄 배치 캐시
Preview/PrvText.txt     미리보기 텍스트 (본문 수정 시 함께 반영)
BinData/                삽입 이미지
```

ZIP 재작성 시 `mimetype`을 **첫 항목 · 무압축(stored)** 으로 유지한다. 순서가 바뀌면 한/글이 열지 못한다.

## 규칙 → XML 매핑

| 규칙 | 위치 | 요소 |
|---|---|---|
| 글꼴 맑은 고딕 | header.xml | `hh:fontface` 에 맑은 고딕 항목 확보 후 모든 `hh:fontRef` 의 7개 언어 슬롯을 그 id로 |
| 글자 크기 | header.xml | `hh:charPr@height` (1000 = 10pt, HWPUNIT = pt × 100) |
| 줄간격 | header.xml | `hh:lineSpacing type="PERCENT" value="160"` — 본문·표 셀 모두 |
| 표 1행 배경색 | header.xml | 머리행이 참조하는 `hh:borderFill` 의 `hc:winBrush@faceColor` |
| 표 1행 세로 중간 | section0.xml | 머리행 셀 `hp:subList@vertAlign="CENTER"` |
| 표 1행 가로 가운데 | header.xml + section0.xml | 가운데 정렬 `hh:paraPr` 를 만들고 머리행 문단이 그 id를 참조 |
| 열 너비 | section0.xml | `hp:cellSz@width` — 같은 열의 모든 행을 함께 고침. 열 합계 = `hp:sz@width` 유지 |

## 문단모양과 전역 정의 다루기

문단모양은 문서 전역이다. 본문과 표 셀 줄간격이 **같은 값이면 같은 문단모양을 공유해도 된다.** 값이 달라지면 표 셀 전용 문단모양을 따로 만들어야 하며, 한쪽만 고치면 반드시 다른 쪽이 틀어진다.

`apply_artifact_format.py` 의 `ParaPrPool` 은 필요한 문단모양을 만들기 전에 **내용이 같은 것이 이미 있는지 먼저 찾아 재사용한다.** 매번 복제하면 같은 파일에 두 번 적용했을 때 쓰이지 않는 문단모양이 계속 쌓인다.

표 배경색(`borderFill`)도 전역이다. 표지 구간이 참조하는 정의는 그 자리에서 고치지 않고 사본을 만들어 본문에만 물린다. [불가침 구간](03-front-matter-lock.md) 참조.

`hp:lineseg@spacing` 은 줄 배치 캐시다. 한/글이 열 때 다시 계산하지만 캐시가 어긋난 채로 두면 다른 뷰어에서 간격이 틀어져 보인다. `spacing = round(vertsize x (줄간격% - 100) / 100)` 으로 함께 맞춘다.

## 글자 깨짐 판정

맑은 고딕(`C:\Windows\Fonts\malgun.ttf`)의 cmap을 직접 읽어 glyph id가 0이면 그 문자는 렌더되지 않는다. 눈으로 보고 판단하지 않는다.

실제로 걸린 사례:

| 문자 | 코드 | 상태 | 대체 |
|---|---|---|---|
| ☐ | U+2610 | 없음 | □ U+25A1 |
| ✓ | U+2713 | 없음 | ○ 또는 √ U+221A |
| · → ※ □ ● | | 있음 | 그대로 사용 |

## 열 너비 판정

`hmtx` 테이블에서 실제 글자 폭을 재서 판단한다.

```text
셀 가용폭 = hp:cellSz@width - hp:cellMargin@left - hp:cellMargin@right
필요폭    = 셀 안 가장 긴 단어의 실제 폭
```

필요폭 > 가용폭이면 단어 중간이 잘린다. 한글은 글자 단위로 끊기므로 `사용성` 이 `사용` / `성` 으로 갈라진다.

## ZIP 무결성 - 열리지 않는 파일 만들지 않기

`mimetype` 과 `BinData/*` 는 한/글이 **무압축(STORED)** 으로 기록한다. 여기를 DEFLATE 로 바꿔 저장하면 바이트 내용이 같아도 한/글이 무결성 검사에서 변조로 판정한다.

> 문서가 손상되었거나 변조되었을 가능성이 있습니다.
> 이 문서를 복구하려면 [문서 보안 설정]을 [낮음]으로 설정해야 합니다.

**그림이 든 문서에서만 드러난다.** 이미지가 없으면 `BinData/` 자체가 없어 정상으로 보이므로 원인을 찾기 어렵다. 실제로 `데이터수집App_정의서_v0.2` 의 최초 커밋본(01119d2)이 `BinData/image1.PNG` 를 DEFLATE 로 담고 있었다.

`write_hwpx()` 는 원본의 `compress_type`·`external_attr`·`internal_attr`·`create_system`·`date_time` 을 그대로 복제하되, `mimetype` 과 `BinData/*` 는 원본이 잘못되어 있었어도 STORED 로 바로잡는다. `check_artifact_format.py` 가 이를 검사한다.

확인법:

```python
import zipfile
[i.filename for i in zipfile.ZipFile(out).infolist()
 if (i.filename == "mimetype" or i.filename.startswith("BinData/")) and i.compress_type != 0]
# 빈 리스트여야 정상
```

이 항목은 별도 스킬 `hwpx-report-builder` 의 알려진 이슈 #10 에서 가져왔다.
