"""AX1 경량 생성 HWPX 서식·패키지 검사.

    python check_headless_artifact.py <파일.hwpx> [--json]

규칙은 references/08-headless-format-rules.md 를 따른다. 표지~목차 제목의 불가침 구간은
글리프 검사만 하고 서식 검사에서 제외한다.

종료 코드: 위반이 없으면 0, 있으면 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True

import headless_hwpx as H  # noqa: E402

# 한/글은 셀 안에서 글자를 조금 압축해 넣으므로 실제 글자 폭이 줄 용량을 다소 넘어도
# 정상이다. 한/글이 직접 배치한 문서를 재어 정한 값이다.
OVERLAP_TOLERANCE = 1.5


def check(path: Path) -> list:
    entries = H.read_hwpx(path)
    header = H.get_text(entries, H.HEADER)
    section = H.get_text(entries, H.SECTION)

    char_prs = H.parse_char_prs(header)
    para_prs = H.parse_para_prs(header)
    malgun_ids = H.malgun_font_ids(header)
    fill_ids = H.header_fill_ids(header)
    shaded_ids = H.shaded_fill_ids(header)
    spans = H.table_spans(section)
    body_start = H.body_start_offset(section)

    regular = H.Font(H.MALGUN)
    boldfont = H.Font(H.MALGUN_BOLD)

    issues = []

    def add(rule, detail, where=""):
        issues.append({"rule": rule, "detail": detail, "where": where})

    # 0-1. ZIP 무결성 - 이게 어긋나면 한/글이 파일 자체를 열지 않는다
    if entries[0].name != "mimetype":
        add("파일 구조", f"mimetype 이 첫 항목이 아님 (현재 {entries[0].name})")
    for e in entries:
        if H.must_be_stored(e.name) and e.compress_type != 0:
            add(
                "파일 구조",
                f"{e.name} 이 압축되어 있음. 한/글이 변조로 판정해 열지 않는다",
            )

    # 0. 불가침 구간 경계
    if body_start is None:
        add("불가침 구간", "목차 문단을 찾지 못해 본문 시작 위치를 판정할 수 없음. 사용자 확인 필요")
        body_start = 0
    front_fills = H.front_matter_fill_ids(section, body_start)

    # 1. 글꼴 - 불가침 표지는 템플릿 그대로 두고 생성 본문만 검사한다.
    if not malgun_ids:
        add("글꼴", f"{H.FONT_FACE} 이 글꼴 목록에 없음")
    else:
        used_body_char_ids = {
            match.group(1)
            for match in H.re.finditer(r'<hp:run charPrIDRef="(\d+)">', section[body_start:])
        }
        bad = sorted(
            cid
            for cid in used_body_char_ids
            if cid in char_prs and any(i not in malgun_ids for i in char_prs[cid].font_ids)
        )
        if bad:
            add("글꼴", f"{H.FONT_FACE} 이 아닌 글자모양 {len(bad)}개", "charPr id " + ", ".join(bad))

    # 2. 제어·개인영역 문자는 중단한다. 체크박스 등 의미 기호는 절대 치환하지 않는다.
    missing = {}
    for m in H.re.finditer(r"<hp:t>([^<]*)</hp:t>", section):
        for ch in H.unescape(m.group(1)):
            if ch not in H.SEMANTIC_SYMBOLS and regular.glyph_id(ord(ch)) == 0:
                missing[ch] = missing.get(ch, 0) + 1
    for ch, n in sorted(missing.items()):
        add("지원하지 않는 문자", f"{ch!r} U+{ord(ch):04X} 제어·개인영역 문자 x{n}; 자동 치환하지 않음")

    # 승인 템플릿 자리표시자가 결과에 남으면 실패한다.
    residue = [
        token
        for token in (
            "[발주기관]",
            "[사업명]",
            "[과제번호]",
            "[세부 사업명]",
            "[산출물 제목]",
            "[문서 유형]",
        )
        if token in section
    ]
    if residue:
        add("템플릿 잔여값", "결과에 남은 값: " + ", ".join(residue))

    # 3. 줄간격 - 본문과 표 셀 모두 규칙값
    body_ids, cell_ids = set(), set()
    for offset, attrs, _ in H.paragraphs(section):
        if offset < body_start:
            continue
        pid = H.re.search(r'paraPrIDRef="(\d+)"', attrs)
        if not pid:
            continue
        (cell_ids if H.in_any_span(spans, offset) else body_ids).add(pid.group(1))

    for pid in sorted(body_ids):
        got = para_prs.get(pid, {}).get("spacing")
        if got != H.BODY_LINE_SPACING:
            add("줄간격", f"본문 문단모양 {pid} 이 {got}% (규칙 {H.BODY_LINE_SPACING}%)")
    for pid in sorted(cell_ids):
        got = para_prs.get(pid, {}).get("spacing")
        if got != H.CELL_LINE_SPACING:
            add("줄간격", f"표 셀 문단모양 {pid} 이 {got}% (규칙 {H.CELL_LINE_SPACING}%)")
    # 본문과 표 셀 줄간격이 다를 때만 문단모양 공유가 문제가 된다
    if H.BODY_LINE_SPACING != H.CELL_LINE_SPACING:
        shared = body_ids & cell_ids
        if shared:
            add("줄간격", f"본문과 표 셀이 문단모양 {', '.join(sorted(shared))} 을 공유해 한쪽이 반드시 틀어짐")

    # 4. 글자 크기 - 본문 구간
    used_heights = {}
    for offset, _, body in H.paragraphs(section):
        if offset < body_start:
            continue
        for m in H.re.finditer(r'<hp:run charPrIDRef="(\d+)">(.*?)</hp:run>', body, H.re.S):
            if not H.re.search(r"<hp:t>[^<]", m.group(2)):
                continue  # 빈 run 은 크기 무관
            cp = char_prs.get(m.group(1))
            if cp:
                used_heights.setdefault(cp.height, set()).add(m.group(1))
    for height in sorted(h for h in used_heights if h not in H.ALLOWED_HEIGHTS):
        ids = ", ".join(sorted(used_heights[height]))
        add("글자 크기", f"{height / 100:g}pt 는 허용 목록 밖 (허용 {[h / 100 for h in H.ALLOWED_HEIGHTS]})", f"charPr id {ids}")

    # 4-1. 글자 겹침
    #  (가) 한 문단의 줄들이 모두 같은 세로 위치에 놓이면 반드시 겹친다. 확정적 결함이다.
    #  (나) 줄이 여러 개 필요한 문단에 배치 정보가 하나뿐인 경우. 한/글은 열 때 다시 계산하므로
    #       늘 겹치지는 않지만, 생성기가 만든 문서라면 거의 확실히 겹친다.
    # 표지 구간도 검사한다. 자리표시자를 더 긴 글자로 바꾸면 거기서도 겹친다.
    for offset, _, body in H.paragraphs(section):
        head = body.split("<hp:linesegarray>")[0]
        if "<hp:tbl " in head:
            continue  # 표를 담은 문단은 글자가 없다
        parts = body.split("<hp:linesegarray>")
        if len(parts) < 2:
            continue
        seg_block = parts[1].split("</hp:linesegarray>")[0]
        segs = H.re.findall(r'<hp:lineseg [^>]*vertpos="(-?\d+)"[^>]*horzsize="(\d+)"', seg_block)
        if not segs:
            continue

        total, text = 0.0, ""
        for m in H.re.finditer(r'<hp:run charPrIDRef="(\d+)">((?:(?!</hp:run>).)*)</hp:run>', head, H.re.S):
            cp = char_prs.get(m.group(1))
            if not cp:
                continue
            piece = H.unescape("".join(H.re.findall(r"<hp:t>([^<]*)</hp:t>", m.group(2))))
            text += piece
            w, _ = H.text_width(piece, cp.height, cp.bold, regular, boldfont, cp.ratio, cp.spacing)
            total += w
        if not text.strip():
            continue

        if len(segs) > 1 and len({v for v, _ in segs}) == 1:
            add("글자 겹침", f"줄 {len(segs)}개가 모두 같은 세로 위치에 놓임 :: {text[:34]}")
            continue
        capacity = int(segs[0][1]) * len(segs)
        if capacity and total / capacity > OVERLAP_TOLERANCE:
            add(
                "글자 겹침",
                f"글자 폭이 배치된 줄 용량의 {total / capacity:.1f}배 :: {text[:34]}",
            )

    # 5. 표 머리행 - 음영 / 세로 중간 / 가로 가운데, 6. 열 너비
    for tno, tbl in enumerate(H.tables(section), start=1):
        offset = spans[tno - 1][0]
        if offset < body_start:
            continue
        if H.is_label_column_table(tbl, shaded_ids):
            continue  # 라벨열 표는 머리행이 없다

        head_cells = sorted((c for c in H.cells(tbl) if c.row == 0), key=lambda c: c.col)
        if not head_cells:
            continue
        if any(c.fill not in fill_ids for c in head_cells):
            add("표 머리행 색", f"1행 배경이 {H.HEADER_FILL} 이 아님", f"표 {tno}")
        elif any(c.fill in front_fills for c in head_cells):
            add(
                "표 머리행 색",
                f"표지~목차와 borderFill 을 공유함. 본문 색을 바꾸면 양식까지 바뀜",
                f"표 {tno}",
            )
        if any(c.vert_align != "CENTER" for c in head_cells):
            add("표 머리행 맞춤", "1행이 세로 중간이 아님", f"표 {tno}")
        aligns = {para_prs.get(p, {}).get("align") for c in head_cells for p in c.para_ids}
        if aligns - {"CENTER"}:
            add("표 머리행 맞춤", f"1행이 가로 가운데가 아님 ({', '.join(sorted(str(a) for a in aligns))})", f"표 {tno}")

        for c in H.cells(tbl):
            if c.colspan != 1:
                continue
            for cid, text in c.runs():
                cp = char_prs.get(cid)
                if not cp or not text.strip():
                    continue
                need, word = H.longest_word_width(text, cp.height, cp.bold, regular, boldfont, cp.ratio, cp.spacing)
                if need > c.usable_width:
                    add(
                        "열 너비",
                        f"'{word}' 가 셀보다 넓어 단어 중간이 잘림 (가용 {c.usable_width} < 필요 {need:.0f})",
                        f"표 {tno} r{c.row}c{c.col}",
                    )
                    break
    return issues


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"파일 없음: {path}")
        return 2

    try:
        issues = check(path)
    except H.HeadlessHwpxError as exc:
        if "--json" in sys.argv:
            print(json.dumps([{"rule": "파일 구조", "detail": str(exc), "where": ""}], ensure_ascii=False, indent=2))
        else:
            print(f"[중단] {exc}")
        return 2
    if "--json" in sys.argv:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
        return 1 if issues else 0

    print(f"검사 대상: {path.name}")
    if not issues:
        print("위반 없음. 산출물 서식 규칙을 모두 만족한다.")
        return 0

    grouped = {}
    for i in issues:
        grouped.setdefault(i["rule"], []).append(i)
    print(f"위반 {len(issues)}건\n")
    for rule, items in grouped.items():
        print(f"[{rule}] {len(items)}건")
        for i in items[:12]:
            where = f" ({i['where']})" if i["where"] else ""
            print(f"  - {i['detail']}{where}")
        if len(items) > 12:
            print(f"  ... 외 {len(items) - 12}건")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
