"""표지 양식에 본문을 채워 산출물 HWPX 를 만든다.

    python build_artifact.py --content <본문.md> -o <출력.hwpx> [--template <양식.hwpx>]

양식의 표지~목차 제목은 손대지 않고 그 뒤에 목차 항목과 본문을 이어붙인 뒤,
서식 규칙을 적용한다. 마크다운 앞부분의 표지·문서정보·개정이력·목차는 양식이
이미 갖고 있으므로 건너뛴다.

지원하는 마크다운
    #/##/###/####  장·절·항 제목 (4수준은 3수준과 같은 서식)
    | ... |     표 (첫 줄이 머리행)      빈 줄 구분   본문 문단
    -, *        불릿 리스트. 들여쓰기 2칸마다 한 단계, 기호는 모든 단계 •
    1. 2. 3.    번호 목록. 단계별 1. 가. 1) 로 바꾸고 내어쓰기를 준다
개정 이력표에는 오늘 날짜와 v0.1(양식이 비어 있을 때)을 기입하고, 출력 파일
이름의 버전 조각도 같은 값으로 맞춘다.
아직 안 되는 것: 그림, 쪽번호, 병합 셀, 각주
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True

import hwpx_format as H  # noqa: E402
import apply_artifact_format as A  # noqa: E402

TABLE_OUT_MARGIN = 283
CELL_MARGIN = (510, 510, 141, 141)  # left right top bottom
MIN_COL_WIDTH = 3000

# 표 기본 속성 (한/글 [표 속성] 대화상자와 대응)
#   글자처럼 취급   -> treat_as_char   (지정 = 1. 표가 문단 안에서 글자처럼 흐른다)
#   쪽 경계에서     -> page_break      (셀 단위로 나눔 = CELL)
#   제목 줄 자동 반복 -> repeat_header   (끔). 셀의 header 속성도 함께 0
TABLE_TREAT_AS_CHAR = 1
TABLE_PAGE_BREAK = "CELL"
TABLE_REPEAT_HEADER = 0


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- 마크다운 -----------------------------------------------------------------


def strip_inline(s: str) -> str:
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("**", "").replace("`", "")
    return s.strip()


def parse_markdown(text: str) -> list:
    """본문 블록 목록을 만든다. 목차 다음부터만 읽는다."""
    lines = text.splitlines()

    start = 0
    for i, line in enumerate(lines):
        if re.fullmatch(r"#{1,3}\s*목\s*차\s*", line):
            # 목차 다음의 첫 장 제목부터가 본문이다
            for j in range(i + 1, len(lines)):
                if re.match(r"^#\s+", lines[j]):
                    start = j
                    break
            break
    if start == 0:
        for i, line in enumerate(lines):
            if re.match(r"^#\s+", line):
                start = i
                break

    blocks, buf, i = [], [], start

    def flush():
        if buf:
            joined = " ".join(x.strip() for x in buf).strip()
            if joined:
                blocks.append(("p", strip_inline(joined)))
            buf.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or re.fullmatch(r"-{3,}", stripped):
            flush()
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush()
            blocks.append(("h", min(len(m.group(1)), 4), strip_inline(m.group(2))))
            i += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append([strip_inline(c) for c in cells])
                i += 1
            if rows:
                width = max(len(r) for r in rows)
                blocks.append(("table", [r + [""] * (width - len(r)) for r in rows]))
            continue

        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            flush()
            blocks.append(("li", len(m.group(1)) // 2 + 1, strip_inline(m.group(2))))
            i += 1
            continue

        # 번호 목록은 번호를 글자로 남기고 각각 별개 문단으로 둔다.
        # 한 문단으로 뭉치면 아주 긴 문단이 되어 줄바꿈이 어긋난다.
        # 번호는 단계별 형식(1. / 가. / 1))으로 바꾸므로 숫자만 넘긴다.
        m = re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", line)
        if m:
            flush()
            blocks.append(("ol", len(m.group(1)) // 2 + 1, int(m.group(2)), strip_inline(m.group(3))))
            i += 1
            continue

        buf.append(line)
        i += 1

    flush()
    return blocks


# --- 스타일 확보 ---------------------------------------------------------------


class StylePool:
    """필요한 글자모양·문단모양을 확보한다. 같은 것이 있으면 재사용한다."""

    def __init__(self, header: str):
        self.header = header
        self.chars = {
            m.group(1): m.group(0)
            for m in re.finditer(r'<hh:charPr id="(\d+)".*?</hh:charPr>', header, re.S)
        }
        self.paras = {
            m.group(1): m.group(0)
            for m in re.finditer(r'<hh:paraPr id="(\d+)".*?</hh:paraPr>', header, re.S)
        }
        self.new_chars, self.new_paras = [], []
        self.parsed = H.parse_char_prs(header)
        malgun = H.malgun_font_ids(header)
        if not malgun:
            raise SystemExit(f"양식에 {H.FONT_FACE} 글꼴이 없다. 한/글에서 한 번 지정한 뒤 다시 실행할 것")
        # 본문 기준 글자모양: 맑은 고딕 10pt, 굵기 없음
        self.base_char = next(
            (i for i, c in sorted(self.parsed.items(), key=lambda x: int(x[0]))
             if c.height == H.BODY_TEXT_HEIGHT and not c.bold and set(c.font_ids) <= malgun),
            None,
        )
        if self.base_char is None:
            raise SystemExit(f"양식에 {H.FONT_FACE} 10pt 글자모양이 없다")
        paras = H.parse_para_prs(header)
        self.base_para = next(
            (i for i, p in sorted(paras.items(), key=lambda x: int(x[0]))
             if p["align"] in ("JUSTIFY", "LEFT") and p["spacing"] == H.BODY_LINE_SPACING),
            None,
        )
        self.center_para = next(
            (i for i, p in sorted(paras.items(), key=lambda x: int(x[0]))
             if p["align"] == "CENTER" and p["spacing"] == H.BODY_LINE_SPACING),
            None,
        )
        if self.base_para is None or self.center_para is None:
            raise SystemExit("양식에 본문/가운데 정렬 문단모양이 없다")

    @staticmethod
    def _strip(block: str, tag: str) -> str:
        return re.sub(rf'^<hh:{tag} id="\d+"', f"<hh:{tag}", block)

    def char(self, height: int, bold: bool) -> str:
        block = self.chars[self.base_char]
        block = re.sub(r'height="\d+"', f'height="{height}"', block, count=1)
        block = re.sub(r"<hh:bold\s*/>", "", block)
        if bold:
            block = block.replace("<hh:underline", "<hh:bold/><hh:underline", 1)
        want = self._strip(block, "charPr")
        for cid, existing in self.chars.items():
            if self._strip(existing, "charPr") == want:
                return cid
        new_id = str(max(int(i) for i in self.chars) + 1)
        block = re.sub(r'^<hh:charPr id="\d+"', f'<hh:charPr id="{new_id}"', block)
        self.chars[new_id] = block
        self.new_chars.append(block)
        return new_id

    def para_variant(self, left=0, intent=0, prev=0, next_=0) -> str:
        """본문 문단모양에서 여백만 바꾼 변형을 확보한다.

        여백은 hp:switch 의 case/default 두 분기에 중복돼 있으므로
        count 제한 없이 치환해 두 분기를 함께 고친다.
        """
        block = self.paras[self.base_para]
        for name, val in (("left", left), ("intent", intent), ("prev", prev), ("next", next_)):
            block = re.sub(rf'(<hc:{name} value=")-?\d+(")', lambda m, v=val: m.group(1) + str(v) + m.group(2), block)
        want = self._strip(block, "paraPr")
        for pid, existing in self.paras.items():
            if self._strip(existing, "paraPr") == want:
                return pid
        new_id = str(max(int(i) for i in self.paras) + 1)
        block = re.sub(r'^<hh:paraPr id="\d+"', f'<hh:paraPr id="{new_id}"', block)
        self.paras[new_id] = block
        self.new_paras.append(block)
        return new_id

    def finish(self) -> str:
        header = self.header
        for tag, plural, blocks in (
            ("charPr", "charProperties", self.new_chars),
            ("paraPr", "paraProperties", self.new_paras),
        ):
            if not blocks:
                continue
            m = re.search(rf'<hh:{plural} itemCnt="(\d+)">', header)
            header = header.replace(m.group(0), f'<hh:{plural} itemCnt="{int(m.group(1)) + len(blocks)}">', 1)
            header = header.replace(f"</hh:{plural}>", "".join(blocks) + f"</hh:{plural}>", 1)
        return header


# --- XML 생성 -----------------------------------------------------------------


class Emitter:
    def __init__(self, pool: StylePool, text_width: int, plain_fill: str,
                 regular: H.Font, boldfont: H.Font, styles: dict = None):
        self.pool = pool
        self.text_width = text_width
        self.plain_fill = plain_fill
        self.regular = regular
        self.boldfont = boldfont
        self.styles = styles or {}
        self.next_id = 1200000000

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id

    def _linesegs(self, text: str, height: int, bold: bool, horzsize: int) -> str:
        """실제로 접히는 줄 수만큼 lineseg 를 만든다.

        한 개만 넣으면 여러 줄이 같은 자리에 겹쳐 그려진다.
        """
        spacing = round(height * (H.BODY_LINE_SPACING - 100) / 100)
        line_h = height + spacing
        starts = H.wrap_lines(text, height, bold, self.regular, self.boldfont, horzsize)
        segs = "".join(
            f'<hp:lineseg textpos="{pos}" vertpos="{i * line_h}" vertsize="{height}"'
            f' textheight="{height}" baseline="{round(height * 0.85)}" spacing="{spacing}"'
            f' horzpos="0" horzsize="{horzsize}" flags="393216"/>'
            for i, pos in enumerate(starts)
        )
        return f"<hp:linesegarray>{segs}</hp:linesegarray>"

    def para(self, text: str, para_id: str, char_id: str, height: int, horzsize=None,
             page_break=False, bold=False, style="0") -> str:
        run = f"<hp:run charPrIDRef=\"{char_id}\">{'<hp:t>' + esc(text) + '</hp:t>' if text else ''}</hp:run>"
        width = horzsize if horzsize is not None else self.text_width
        return (
            f'<hp:p id="{self._id()}" paraPrIDRef="{para_id}" styleIDRef="{style}"'
            f' pageBreak="{1 if page_break else 0}" columnBreak="0" merged="0">'
            f"{run}{self._linesegs(text, height, bold, width)}</hp:p>"
        )

    def heading(self, level: int, text: str, after_h1: bool = False) -> str:
        level = min(level, 4)
        height = H.HEADING_HEIGHT[level]
        prev, next_ = H.HEADING_MARGIN[level]
        if level == 2 and after_h1:
            prev = H.H2_AFTER_H1_PREV  # 장 바로 다음의 절은 위 간격을 줄인다
        return self.para(
            text,
            self.pool.para_variant(prev=prev, next_=next_),
            self.pool.char(height, True),
            height,
            page_break=(level == 1),
            bold=True,
            style=self.styles.get(H.HEADING_STYLE[level], "0"),
        )

    def body(self, text: str) -> str:
        return self.para(text, self.pool.base_para, self.pool.char(H.BODY_TEXT_HEIGHT, False), H.BODY_TEXT_HEIGHT)

    def _list_para(self, level: int, marker: str, text: str) -> str:
        """머리 글자 + 내어쓰기 리스트 문단. 접힌 줄이 글자 시작점에 맞춰진다."""
        hang = H.marker_hang(marker, self.regular, self.boldfont)
        left = (level - 1) * H.LIST_INDENT_STEP + hang
        return self.para(
            marker + " " + text,
            self.pool.para_variant(left=left, intent=-hang),
            self.pool.char(H.BODY_TEXT_HEIGHT, False),
            H.BODY_TEXT_HEIGHT,
            horzsize=self.text_width - left,
        )

    def item(self, level: int, text: str) -> str:
        level = min(level, 4)
        return self._list_para(level, H.BULLETS[level], text)

    def ordered_item(self, level: int, n: int, text: str) -> str:
        level = min(level, 4)
        return self._list_para(level, H.ordered_marker(level, n), text)

    def toc_entry(self, level: int, text: str) -> str:
        """목차 항목. 장은 굵게, 절은 들여쓰기. 항 이하는 만들지 않는다."""
        if level == 1:
            return self.para(
                text, self.pool.base_para, self.pool.char(H.BODY_TEXT_HEIGHT, True),
                H.BODY_TEXT_HEIGHT, bold=True, style=self.styles.get(H.TOC_STYLE[1], "0"),
            )
        return self.para(
            text,
            self.pool.para_variant(left=H.TOC_INDENT),
            self.pool.char(H.BODY_TEXT_HEIGHT, False),
            H.BODY_TEXT_HEIGHT,
            horzsize=self.text_width - H.TOC_INDENT,
            style=self.styles.get(H.TOC_STYLE[2], "0"),
        )

    def table(self, rows: list, regular: H.Font, boldfont: H.Font) -> str:
        n_col = len(rows[0])
        total = self.text_width - 2 * TABLE_OUT_MARGIN - 4
        pad = CELL_MARGIN[0] + CELL_MARGIN[1]

        # 열 너비: 열별 최장 내용에 비례해 나누고 최소 폭을 보장한다.
        # 단어 잘림은 이후 서식 적용 단계가 다시 잡아준다.
        weights = []
        for c in range(n_col):
            longest = 0
            for r in rows:
                w, _ = H.text_width(r[c], H.BODY_TEXT_HEIGHT, False, regular, boldfont)
                longest = max(longest, w)
            weights.append(max(longest + pad, MIN_COL_WIDTH))
        scale = (total - sum(MIN_COL_WIDTH for _ in range(n_col))) / max(1, sum(weights))
        widths = [MIN_COL_WIDTH + int(w * scale) for w in weights]
        widths[-1] += total - sum(widths)

        head_char = self.pool.char(H.BODY_TEXT_HEIGHT, True)
        body_char = self.pool.char(H.BODY_TEXT_HEIGHT, False)
        line_h = round(H.BODY_TEXT_HEIGHT * H.BODY_LINE_SPACING / 100)

        trs, total_h = [], 0
        for r_i, row in enumerate(rows):
            is_head = r_i == 0
            heights = []
            for c_i, cell in enumerate(row):
                usable = widths[c_i] - pad - 2
                lines = H.wrap_lines(cell, H.BODY_TEXT_HEIGHT, is_head, regular, boldfont, usable)
                heights.append(len(lines))
            row_h = max(heights) * line_h + CELL_MARGIN[2] + CELL_MARGIN[3]
            total_h += row_h
            tcs = []
            for c_i, cell in enumerate(row):
                inner = self.para(
                    cell,
                    self.pool.center_para if is_head else self.pool.base_para,
                    head_char if is_head else body_char,
                    H.BODY_TEXT_HEIGHT,
                    horzsize=widths[c_i] - pad - 2,
                    bold=is_head,
                )
                tcs.append(
                    f'<hp:tc name="" header="{TABLE_REPEAT_HEADER if is_head else 0}" hasMargin="0" protect="0"'
                    f' editable="0" dirty="0" borderFillIDRef="{self.plain_fill}">'
                    f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER"'
                    f' linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0"'
                    f' hasTextRef="0" hasNumRef="0">{inner}</hp:subList>'
                    f'<hp:cellAddr colAddr="{c_i}" rowAddr="{r_i}"/>'
                    f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                    f'<hp:cellSz width="{widths[c_i]}" height="{row_h}"/>'
                    f'<hp:cellMargin left="{CELL_MARGIN[0]}" right="{CELL_MARGIN[1]}"'
                    f' top="{CELL_MARGIN[2]}" bottom="{CELL_MARGIN[3]}"/></hp:tc>'
                )
            trs.append("<hp:tr>" + "".join(tcs) + "</hp:tr>")

        tbl = (
            f'<hp:tbl id="{self._id()}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM"'
            f' textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="{TABLE_PAGE_BREAK}"'
            f' repeatHeader="{TABLE_REPEAT_HEADER}"'
            f' rowCnt="{len(rows)}" colCnt="{n_col}" cellSpacing="0"'
            f' borderFillIDRef="{self.plain_fill}" noAdjust="0">'
            f'<hp:sz width="{sum(widths)}" widthRelTo="ABSOLUTE" height="{total_h}"'
            f' heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="{TABLE_TREAT_AS_CHAR}" affectLSpacing="0" flowWithText="1" allowOverlap="0"'
            f' holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP"'
            f' horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="{TABLE_OUT_MARGIN}" right="{TABLE_OUT_MARGIN}"'
            f' top="{TABLE_OUT_MARGIN}" bottom="{TABLE_OUT_MARGIN}"/>'
            f'<hp:inMargin left="{CELL_MARGIN[0]}" right="{CELL_MARGIN[1]}"'
            f' top="{CELL_MARGIN[2]}" bottom="{CELL_MARGIN[3]}"/>'
            + "".join(trs)
            + "</hp:tbl>"
        )
        return (
            f'<hp:p id="{self._id()}" paraPrIDRef="{self.pool.base_para}" styleIDRef="0"'
            f' pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{body_char}">{tbl}</hp:run>'
            f"{self._linesegs('', H.BODY_TEXT_HEIGHT, False, self.text_width)}</hp:p>"
        )


def plain_border_fill(header: str) -> str:
    """네 변이 실선이고 채움이 없는 borderFill id."""
    for m in re.finditer(r'<hh:borderFill id="(\d+)"[^>]*>(.*?)</hh:borderFill>', header, re.S):
        solid = len(re.findall(r'<hh:(?:left|right|top|bottom)Border type="SOLID"', m.group(2)))
        if solid == 4 and not re.search(r'faceColor="#[0-9A-Fa-f]{6}"', m.group(2)):
            return m.group(1)
    raise SystemExit("양식에 테두리 실선 borderFill 이 없다. 표를 만들 수 없다")


def default_template():
    """저장소의 표지 양식을 스스로 찾는다.

    스킬이 `<저장소>/skills/bizplan-artifact-format/` 에 있으므로 스크립트의 실제
    위치에서 위로 올라가며 `document_form/` 을 찾는다. `~/.claude/skills/` 에
    정션(심볼릭 링크)으로 설치했더라도 resolve() 가 실제 위치를 따라가므로
    어느 폴더에서 실행해도 같은 양식을 쓴다.
    """
    for parent in Path(__file__).resolve().parents:
        d = parent / "document_form"
        if not d.is_dir():
            continue
        forms = sorted(d.glob("*.hwpx"))
        blank = [f for f in forms if "양식" in f.name]
        return (blank or forms or [None])[0]
    return None


def fill_cover(section: str, header: str, title: str, project: str, log: list) -> str:
    """표지의 제목·과제번호 자리표시자를 채운다.

    표지 자체는 양식이므로 글꼴·크기·배치는 건드리지 않고 글자만 바꾼다.
    다만 글자가 바뀌면 줄 수가 달라질 수 있으므로 그 문단의 줄 배치는 다시 계산한다.
    """
    body_start = H.body_start_offset(section)
    if body_start is None:
        return section
    char_prs = H.parse_char_prs(header)
    regular, boldfont = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)
    spans = H.table_spans(section)

    targets = []  # (오프셋, 종류, 원래글자)
    for off, _, body in H.paragraphs(section):
        if off >= body_start or H.in_any_span(spans, off):
            continue
        m = re.search(r'<hp:run charPrIDRef="(\d+)"><hp:t>([^<]*)</hp:t>', body)
        if not m:
            continue
        cp = char_prs.get(m.group(1))
        text = H.unescape(m.group(2))
        if cp and cp.height >= 3000:
            targets.append((off, "title", text))
        elif "과제번호" in text:
            targets.append((off, "project", text))

    titles = [x for x in targets if x[1] == "title"]
    plan = {}
    if title and titles:
        plan[titles[0][0]] = title
        for off, _, _ in titles[1:]:
            plan[off] = ""
        log.append(f"표지 제목 -> {title!r} (남은 제목 줄 {len(titles) - 1}개 비움)")
    if project:
        for off, kind, _ in targets:
            if kind == "project":
                plan[off] = project
                log.append(f"표지 과제번호 줄 -> {project!r}")
                break
    if not plan:
        return section

    # 뒤에서부터 고쳐야 앞쪽 오프셋이 밀리지 않는다
    paras = H.paragraphs(section)
    bounds = {}
    for i, (off, _, _) in enumerate(paras):
        end = paras[i + 1][0] if i + 1 < len(paras) else len(section)
        bounds[off] = end
    relaid = 0
    for off in sorted(plan, reverse=True):
        end = bounds[off]
        para = section[off:end]
        new_text = plan[off]
        para = re.sub(
            r"(<hp:run charPrIDRef=\"\d+\"><hp:t>)[^<]*(</hp:t>)",
            lambda m: m.group(1) + esc(new_text) + m.group(2),
            para,
            count=1,
        )
        para = H.relayout_paragraph(para, char_prs, regular, boldfont)
        section = section[:off] + para + section[end:]
        relaid += 1
    log.append(f"바뀐 표지 문단 {relaid}개의 줄 배치 재계산")
    return section


def build(template: Path, content: Path, out: Path, title="", project="", make_toc=True,
          rev_note="최초 작성", rev_author="", revision=True) -> list:
    log = []
    entries = H.read_hwpx(template)
    header = H.get_text(entries, H.HEADER)
    section = H.get_text(entries, H.SECTION)

    blocks = parse_markdown(content.read_text(encoding="utf-8"))
    if not blocks:
        raise SystemExit("본문 블록을 찾지 못했다. 마크다운에 목차 뒤 '# 제목' 이 있는지 확인할 것")
    kinds = {}
    for b in blocks:
        kinds[b[0]] = kinds.get(b[0], 0) + 1
    log.append(f"본문 블록 {len(blocks)}개 (제목 {kinds.get('h', 0)}, 문단 {kinds.get('p', 0)}, "
               f"불릿 {kinds.get('li', 0)}, 번호 {kinds.get('ol', 0)}, 표 {kinds.get('table', 0)})")

    pool = StylePool(header)
    regular, boldfont = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)
    styles = H.style_ids_by_name(header)
    emitter = Emitter(pool, H.text_width_of(section), plain_border_fill(header), regular, boldfont, styles)

    parts = []

    # 목차 항목 - 장·절 제목에서 뽑는다. 목차 제목 문단까지가 양식이고 항목부터가 생성물이다.
    if make_toc:
        toc_items = [(b[1], b[2]) for b in blocks if b[0] == "h" and b[1] <= 2]
        for lv, name in toc_items:
            parts.append(emitter.toc_entry(lv, name))
        n1 = sum(1 for lv, _ in toc_items if lv == 1)
        log.append(f"목차 항목 {len(toc_items)}개 생성 (장 {n1}, 절 {len(toc_items) - n1})")

    prev_h = None  # 직전 블록이 장 제목이면 다음 절 제목의 위 간격을 줄인다
    for block in blocks:
        if block[0] == "h":
            parts.append(emitter.heading(block[1], block[2], after_h1=(block[1] == 2 and prev_h == 1)))
            prev_h = min(block[1], 4)
        elif block[0] == "p":
            parts.append(emitter.body(block[1]))
            prev_h = None
        elif block[0] == "li":
            parts.append(emitter.item(block[1], block[2]))
            prev_h = None
        elif block[0] == "ol":
            parts.append(emitter.ordered_item(block[1], block[2], block[3]))
            prev_h = None
        elif block[0] == "table":
            parts.append(emitter.table(block[1], regular, boldfont))
            prev_h = None

    section = fill_cover(section, header, title, project, log)

    # 개정 이력 - 빈 양식이면 오늘 날짜와 v0.1 을 기입한다
    version = None
    if revision:
        body_start = H.body_start_offset(section)
        section, version = A.record_revision(section, body_start, header,
                                             regular, boldfont, rev_note, rev_author, log)
    if version:
        wanted = H.versioned_name(out, version)
        if wanted.name != out.name:
            log.append(f"출력 이름을 개정 이력 버전에 맞춤: {out.name} -> {wanted.name}")
            out = wanted

    if "</hs:sec>" not in section:
        raise SystemExit("section0.xml 에서 </hs:sec> 를 찾지 못했다")
    section = section.replace("</hs:sec>", "".join(parts) + "</hs:sec>", 1)

    H.set_text(entries, H.HEADER, pool.finish())
    H.set_text(entries, H.SECTION, section)
    H.write_hwpx(entries, out)
    log.append(f"양식 뒤에 본문 삽입 완료 -> {out}")

    log.append("--- 서식 적용 ---")
    log += A.apply(out, out, revision=False)  # 개정 이력은 위에서 이미 기록했다
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description="표지 양식에 본문을 채워 산출물 HWPX 를 만든다")
    ap.add_argument("--template", type=Path, default=None,
                    help="표지 양식 .hwpx. 생략하면 저장소 document_form/ 에서 자동으로 찾음")
    ap.add_argument("--content", required=True, type=Path, help="본문 마크다운")
    ap.add_argument("-o", "--out", required=True, type=Path)
    ap.add_argument("--title", default="", help="표지 제목 자리표시자를 이 글자로 채움")
    ap.add_argument("--project", default="", help="표지의 [과제번호 ...] 줄 전체를 이 글자로 교체")
    ap.add_argument("--no-toc", action="store_true", help="목차 항목을 만들지 않음")
    ap.add_argument("--rev-note", default="최초 작성", help="개정 이력의 개정내역 칸 (기본: 최초 작성)")
    ap.add_argument("--rev-author", default="", help="개정 이력의 작성자 칸")
    ap.add_argument("--no-revision", action="store_true", help="개정 이력·파일명 버전을 건드리지 않음")
    args = ap.parse_args()

    template = args.template or default_template()
    if template is None:
        print("표지 양식을 찾지 못했다. --template 으로 직접 지정할 것")
        return 2
    if not args.template:
        print(f"표지 양식 자동 선택: {template}")
    for p in (template, args.content):
        if not p.is_file():
            print(f"파일 없음: {p}")
            return 2

    for line in build(template, args.content, args.out, args.title, args.project, not args.no_toc,
                      args.rev_note, args.rev_author, not args.no_revision):
        print(line)
    print("\ncheck_artifact_format.py 로 검사하고 한/글에서 직접 열어 확인할 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
