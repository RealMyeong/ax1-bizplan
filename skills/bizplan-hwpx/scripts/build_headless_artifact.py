"""승인된 AX1 표지 양식에 확정 본문을 채워 HWPX를 만든다.

    python build_headless_artifact.py --content <본문.md> -o <출력_v0.1.hwpx> [표지 정보]

양식의 표지~목차 제목은 손대지 않고 그 뒤에 목차 항목과 본문을 이어붙인 뒤,
서식 규칙을 적용한다. 마크다운 앞부분의 표지·문서정보·개정이력·목차는 양식이
이미 갖고 있으므로 건너뛴다.

지원하는 마크다운
    #/##/###/####   장·절·항·세부항 제목   | ... |   표 (첫 줄이 머리행)
    빈 줄 구분  본문 문단          -, *     리스트
    1. 2. 3.   번호 목록 (번호를 글자로 남기고 각각 별개 문단)
표준 라이브러리만 사용하며 한컴오피스·COM 창을 실행하지 않는다. 임의 템플릿은
받지 않고 스킬에 포함된 SHA-256 승인 템플릿만 사용한다.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True

import headless_hwpx as H  # noqa: E402
import format_headless_artifact as A  # noqa: E402
import check_headless_artifact as C  # noqa: E402

# 제목 계층 (references/08-headless-format-rules.md 의 글자 크기 계층과 같아야 함)
HEADING_HEIGHT = {1: 1500, 2: 1200, 3: 1050, 4: 1050}
HEADING_STYLE = {1: "개요 1", 2: "개요 2", 3: "개요 3", 4: "개요 4"}
OUTLINE_PREFIX_SPACES = {1: 0, 2: 3, 3: 5, 4: 7}
BODY_LIST_PREFIX_SPACES = 9
TABLE_OUT_MARGIN = 283
CELL_MARGIN = (510, 510, 141, 141)  # left right top bottom
MIN_COL_WIDTH = 3000

# 표 기본 속성 (한/글 [표 속성] 대화상자와 대응)
#   글자처럼 취급   -> treat_as_char   (해제)
#   쪽 경계에서     -> page_break      (셀 단위로 나눔 = CELL)
#   제목 줄 자동 반복 -> repeat_header   (끔). 셀의 header 속성도 함께 0
TABLE_TREAT_AS_CHAR = 0
TABLE_PAGE_BREAK = "CELL"
TABLE_REPEAT_HEADER = 0


def esc(s: str) -> str:
    """XML 문법 문자만 이스케이프하고 한글은 UTF-8 실제 문자로 보존한다."""
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

        m = re.match(r"^(#{1,})\s+(.*)$", stripped)
        if m:
            flush()
            level = len(m.group(1))
            heading_text = strip_inline(m.group(2))
            if level <= 4:
                blocks.append(("h", level, heading_text))
            else:
                heading_text = re.sub(r"^\d+(?:\.\d+){4,}\.?\s+", "", heading_text)
                blocks.append(("li", 1, heading_text))
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
        m = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if m:
            flush()
            blocks.append(("p", strip_inline(line.strip())))
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

    def para_indent(self, left: int) -> str:
        block = self.paras[self.base_para]
        block = re.sub(r'(<hc:left value=")-?\d+(")', lambda m: m.group(1) + str(left) + m.group(2), block)
        if left == 0:
            block = re.sub(r'(<hc:intent value=")-?\d+(")', r'\g<1>0\2', block)
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
                 regular: H.Font, boldfont: H.Font, styles: dict[str, str]):
        self.pool = pool
        self.text_width = text_width
        self.plain_fill = plain_fill
        self.regular = regular
        self.boldfont = boldfont
        self.styles = styles
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

    def heading(self, level: int, text: str) -> str:
        height = HEADING_HEIGHT[level]
        text = " " * OUTLINE_PREFIX_SPACES[level] + text.lstrip()
        return self.para(
            text, self.pool.para_indent(0), self.pool.char(height, True), height,
            page_break=(level == 1), bold=True,
            style=self.styles[HEADING_STYLE[level]],
        )

    def body(self, text: str) -> str:
        return self.para(text, self.pool.base_para, self.pool.char(H.BODY_TEXT_HEIGHT, False), H.BODY_TEXT_HEIGHT)

    def item(self, level: int, text: str) -> str:
        del level  # 경량 기본 목록은 한 단계이며 실제 U+0020 공백 9개로 들여쓴다.
        text = " " * BODY_LIST_PREFIX_SPACES + "• " + text.lstrip()
        return self.para(
            text,
            self.pool.para_indent(0),
            self.pool.char(H.BODY_TEXT_HEIGHT, False),
            H.BODY_TEXT_HEIGHT,
            horzsize=self.text_width,
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


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_template() -> Path:
    """스킬 안에 포함된 SHA-256 승인 템플릿만 반환한다."""
    return H.approved_template(skill_root())


def text_width_of(section: str) -> int:
    m = re.search(r'<hp:pagePr[^>]*width="(\d+)"[^>]*>.*?<hp:margin[^>]*left="(\d+)" right="(\d+)"', section, re.S)
    if not m:
        return 42520
    return int(m.group(1)) - int(m.group(2)) - int(m.group(3))



def relayout_paragraph(para_xml: str, char_prs: dict, regular: H.Font, boldfont: H.Font) -> str:
    """글자를 바꾼 문단의 줄 배치 정보를 다시 만든다.

    양식의 자리표시자를 더 긴 글자로 바꾸면 원래 줄 배치가 그대로 남아
    여러 줄이 한 자리에 겹쳐 그려진다. 글자를 건드렸으면 배치도 다시 계산해야 한다.
    글꼴·크기·정렬은 그대로 두고 줄 수와 세로 위치만 고친다.
    """
    parts = para_xml.split("<hp:linesegarray>")
    if len(parts) < 2:
        return para_xml
    head = parts[0]
    inner, _, rest = parts[1].partition("</hp:linesegarray>")
    first = re.search(r"<hp:lineseg ([^>]*)/>", inner)
    if not first:
        return para_xml
    attrs = first.group(1)

    def num(name, default):
        m = re.search(rf'{name}="(-?\d+)"', attrs)
        return int(m.group(1)) if m else default

    vertsize = num("vertsize", 1000)
    textheight = num("textheight", vertsize)
    baseline = num("baseline", round(vertsize * 0.85))
    spacing = num("spacing", 0)
    horzpos = num("horzpos", 0)
    horzsize = num("horzsize", 42520)
    vertpos0 = num("vertpos", 0)
    flags = (re.search(r'flags="(\d+)"', attrs) or [None, "393216"])[1]

    text, widths = H.paragraph_runs(head, char_prs, regular, boldfont)
    starts = H.wrap_widths(text, widths, horzsize)
    line_h = vertsize + spacing
    segs = "".join(
        f'<hp:lineseg textpos="{pos}" vertpos="{vertpos0 + i * line_h}" vertsize="{vertsize}"'
        f' textheight="{textheight}" baseline="{baseline}" spacing="{spacing}"'
        f' horzpos="{horzpos}" horzsize="{horzsize}" flags="{flags}"/>'
        for i, pos in enumerate(starts)
    )
    return head + "<hp:linesegarray>" + segs + "</hp:linesegarray>" + rest


def fill_cover(section: str, header: str, values: dict[str, str], log: list) -> str:
    """승인 템플릿의 고정 자리표시자만 치환하고 해당 문단을 재배치한다."""
    body_start = H.body_start_offset(section)
    if body_start is None:
        raise H.HeadlessHwpxError("승인 템플릿에서 목차 경계를 찾지 못함")
    char_prs = H.parse_char_prs(header)
    regular, boldfont = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)
    placeholders = {
        "[발주기관]": values["agency"],
        "[사업명]": values["program"],
        "[과제번호]": values["project_number"],
        "[세부 사업명]": values["project"],
        "[산출물 제목]": values["title"],
        "[문서 유형]": values["document_type"],
    }
    if any(not str(value).strip() for value in placeholders.values()):
        raise H.HeadlessHwpxError("표지 정보에 빈 값이 있음")

    plan = {}
    for off, _, body in H.paragraphs(section):
        if off >= body_start:
            continue
        plain = H.unescape("".join(re.findall(r"<hp:t>([^<]*)</hp:t>", body)))
        changed = plain
        for placeholder, value in placeholders.items():
            changed = changed.replace(placeholder, value)
        if changed != plain:
            plan[off] = (plain, changed)
    found = {placeholder for placeholder in placeholders if placeholder in section[:body_start]}
    if found != set(placeholders):
        missing = sorted(set(placeholders) - found)
        raise H.HeadlessHwpxError("승인 템플릿 자리표시자 누락: " + ", ".join(missing))

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
        old_text, new_text = plan[off]
        para = re.sub(
            rf"(<hp:t>){re.escape(esc(old_text))}(</hp:t>)",
            lambda m: m.group(1) + esc(new_text) + m.group(2),
            para,
            count=1,
        )
        para = relayout_paragraph(para, char_prs, regular, boldfont)
        section = section[:off] + para + section[end:]
        relaid += 1
    if any(placeholder in section for placeholder in placeholders):
        raise H.HeadlessHwpxError("표지 자리표시자가 모두 치환되지 않음")
    log.append(f"표지 자리표시자 6종과 문단 {relaid}개의 줄 배치 갱신")
    return section


def record_initial_revision(
    section: str,
    header: str,
    *,
    version: str,
    revision_date: str,
    note: str,
    author: str,
    log: list,
) -> str:
    """승인 AX1 빈 개정표의 데이터 첫 행에 최초 기록만 추가한다."""
    body_start = H.body_start_offset(section)
    if not H.ax1_front_matter_signature(section, body_start):
        raise H.HeadlessHwpxError("승인 AX1 템플릿의 표지 구조를 확인할 수 없음")
    spans = H.revision_table_spans(section, body_start)
    if len(spans) != 1:
        raise H.HeadlessHwpxError(f"개정 이력표를 정확히 하나로 식별할 수 없음: {len(spans)}개")
    start, end = spans[0]
    table = section[start:end]
    analysis = H.analyze_revision_table(table, require_record=False, require_empty_row=True)
    if analysis.issues:
        raise H.HeadlessHwpxError("개정 이력표 사전검사 실패: " + "; ".join(analysis.issues))
    if analysis.records:
        raise H.HeadlessHwpxError("새 일반 산출물은 빈 개정 이력표에서만 생성할 수 있음")
    if not analysis.empty_rows or analysis.empty_rows[0] != 1:
        raise H.HeadlessHwpxError("개정 이력의 데이터 첫 행이 비어 있지 않음")

    char_prs = H.parse_char_prs(header)
    regular, boldfont = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)

    def relayout(paragraph: str) -> str:
        return relayout_paragraph(paragraph, char_prs, regular, boldfont)

    values = (revision_date, version, note, author)
    for column, value in enumerate(values):
        if value:
            table = H.set_revision_cell_text(
                table,
                1,
                column,
                value,
                require_empty=True,
                paragraph_transform=relayout,
            )
    verified = H.analyze_revision_table(table, require_record=True, require_empty_row=True)
    if verified.issues or len(verified.records) != 1:
        details = verified.issues or [f"개정 기록 수가 1개가 아님: {len(verified.records)}"]
        raise H.HeadlessHwpxError("개정 이력표 기록 후 검사 실패: " + "; ".join(details))
    record = verified.records[0]
    if (record.date, record.version, record.note, record.author, record.confirmer) != (
        revision_date,
        version,
        note,
        author,
        "",
    ):
        raise H.HeadlessHwpxError("개정 이력표 기록값 readback이 요청값과 일치하지 않음")
    log.append(
        f"개정 이력 첫 행 기록: {revision_date} / {version} / {note!r}"
        + (f" / 작성자 {author!r}" if author else " / 작성자 미입력")
        + " / 확인자 미입력"
    )
    return section[:start] + table + section[end:]


def build(
    template: Path,
    content: Path,
    out: Path,
    cover: dict[str, str],
    make_toc=True,
    artifact_version="v0.1",
    revision_note="최초 작성",
    revision_author="",
    revision_date=None,
) -> list:
    artifact_version = H.validate_artifact_version(artifact_version)
    revision_date = H.normalize_revision_date(revision_date)
    if not isinstance(revision_note, str) or not revision_note.strip():
        raise H.HeadlessHwpxError("개정내역은 비어 있을 수 없음")
    if not isinstance(revision_author, str):
        raise H.HeadlessHwpxError("개정 작성자는 문자열이어야 함")
    out = H.require_new_artifact_output(Path(out), artifact_version)
    template = Path(template)
    approved = default_template()
    if template.resolve() != approved.resolve():
        raise H.HeadlessHwpxError("경량 생성은 스킬에 포함된 승인 AX1 템플릿만 사용할 수 있음")

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
               f"리스트 {kinds.get('li', 0)}, 표 {kinds.get('table', 0)})")

    pool = StylePool(header)
    regular, boldfont = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)
    styles = H.style_ids_by_name(header)
    missing_styles = [name for name in HEADING_STYLE.values() if name not in styles]
    if missing_styles:
        raise H.HeadlessHwpxError("승인 템플릿 제목 스타일 누락: " + ", ".join(missing_styles))
    emitter = Emitter(
        pool,
        text_width_of(section),
        plain_border_fill(header),
        regular,
        boldfont,
        styles,
    )

    parts = []

    # 목차 항목 - 장 제목에서 뽑는다. 목차 제목 문단까지가 양식이고 항목부터가 생성물이다.
    if make_toc:
        chapters = [b[2] for b in blocks if b[0] == "h" and b[1] == 1]
        for name in chapters:
            parts.append(emitter.body(name))
        log.append(f"목차 항목 {len(chapters)}개 생성")

    for block in blocks:
        if block[0] == "h":
            parts.append(emitter.heading(block[1], block[2]))
        elif block[0] == "p":
            parts.append(emitter.body(block[1]))
        elif block[0] == "li":
            parts.append(emitter.item(block[1], block[2]))
        elif block[0] == "table":
            parts.append(emitter.table(block[1], regular, boldfont))

    section = fill_cover(section, header, cover, log)
    section = record_initial_revision(
        section,
        header,
        version=artifact_version,
        revision_date=revision_date,
        note=revision_note,
        author=revision_author,
        log=log,
    )
    try:
        preview = H.get_text(entries, H.PREVIEW)
        for placeholder, key in (
            ("[발주기관]", "agency"),
            ("[사업명]", "program"),
            ("[과제번호]", "project_number"),
            ("[세부 사업명]", "project"),
            ("[산출물 제목]", "title"),
            ("[문서 유형]", "document_type"),
        ):
            preview = preview.replace(placeholder, cover[key])
        H.set_text(entries, H.PREVIEW, preview)
    except KeyError:
        pass
    if "</hs:sec>" not in section:
        raise SystemExit("section0.xml 에서 </hs:sec> 를 찾지 못했다")
    section = section.replace("</hs:sec>", "".join(parts) + "</hs:sec>", 1)

    source_texts = list(cover.values()) + [revision_note, revision_author]
    for block in blocks:
        if block[0] in {"h", "li"}:
            source_texts.append(block[2])
        elif block[0] == "p":
            source_texts.append(block[1])
        elif block[0] == "table":
            source_texts.extend(cell for row in block[1] for cell in row)
    missing_hangul = H.missing_hangul_runs(source_texts, section)
    encoded_hangul = H.encoded_hangul_references(section)
    if missing_hangul or encoded_hangul:
        details = []
        if missing_hangul:
            details.append("원문 불일치: " + ", ".join(missing_hangul[:8]))
        if encoded_hangul:
            details.append("코드 표기: " + ", ".join(encoded_hangul[:8]))
        raise H.HeadlessHwpxError("한글 원문 보존 검사 실패: " + "; ".join(details))
    log.append(f"표지·본문·표 셀 한글 원문 보존 확인: {sum(len(H.hangul_runs(text)) for text in source_texts)}개 묶음")

    H.set_text(entries, H.HEADER, pool.finish())
    H.set_text(entries, H.SECTION, section)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_manager = tempfile.TemporaryDirectory(
        prefix=".ax1-headless-build-",
        dir=out.parent,
        ignore_cleanup_errors=True,
    )
    temp_root = Path(temp_manager.name)
    build_error = None
    try:
        raw_path = temp_root / f"raw_{artifact_version}.hwpx"
        fmt_path = temp_root / f"formatted_{artifact_version}.hwpx"
        H.write_hwpx(entries, raw_path)
        log.append("승인 양식 뒤에 본문 삽입 완료")
        log.append("--- 경량 서식 적용 ---")
        log += A.apply(raw_path, fmt_path)
        issues = C.check(fmt_path)
        if issues:
            summary = "; ".join(f"{item['rule']}: {item['detail']}" for item in issues[:8])
            raise H.HeadlessHwpxError("경량 생성 후 자동검사 실패: " + summary)
        H.publish_new_file(fmt_path, out)
    except Exception as exc:
        build_error = exc
    finally:
        temp_manager.cleanup()
    cleanup_pending = temp_root.exists()
    if build_error is not None:
        if cleanup_pending:
            raise H.HeadlessHwpxError(
                f"{build_error}; 민감정보가 포함될 수 있는 임시 폴더를 삭제하지 못함: {temp_root}"
            ) from build_error
        raise build_error
    if cleanup_pending:
        log.append(
            "[경고] 출력은 생성했지만 민감정보가 포함될 수 있는 임시 폴더를 "
            f"삭제하지 못함. 수동 삭제 필요: {temp_root}"
        )
    log.append(f"구조·서식 자동검사 통과 후 저장 -> {out}")
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description="표지 양식에 본문을 채워 산출물 HWPX 를 만든다")
    ap.add_argument("--content", required=True, type=Path, help="본문 마크다운")
    ap.add_argument("-o", "--out", required=True, type=Path)
    ap.add_argument("--agency", required=True, help="발주기관")
    ap.add_argument("--program", required=True, help="상위 사업명")
    ap.add_argument("--project-number", required=True, help="과제번호")
    ap.add_argument("--project", required=True, help="세부 사업명")
    ap.add_argument("--title", required=True, help="산출물 제목")
    ap.add_argument("--document-type", required=True, help="문서 유형")
    ap.add_argument("--no-toc", action="store_true", help="목차 항목을 만들지 않음")
    ap.add_argument("--artifact-version", default="v0.1", help="산출물 버전 (기본: v0.1)")
    ap.add_argument("--revision-note", default="최초 작성", help="개정 이력의 개정내역 (기본: 최초 작성)")
    ap.add_argument("--revision-author", default="", help="개정 이력의 작성자; 확인자는 자동 입력하지 않음")
    ap.add_argument("--revision-date", default=None, help="테스트·재현용 개정일자 YYYY-MM-DD; 기본은 한국 날짜")
    args = ap.parse_args()

    try:
        template = default_template()
    except H.HeadlessHwpxError as exc:
        print(f"[중단] {exc}")
        return 2
    print(f"승인 템플릿: {template.name} ({H.sha256_file(template)})")
    for p in (template, args.content):
        if not p.is_file():
            print(f"파일 없음: {p}")
            return 2
    cover = {
        "agency": args.agency,
        "program": args.program,
        "project_number": args.project_number,
        "project": args.project,
        "title": args.title,
        "document_type": args.document_type,
    }
    try:
        for line in build(
            template,
            args.content,
            args.out,
            cover,
            not args.no_toc,
            args.artifact_version,
            args.revision_note,
            args.revision_author,
            args.revision_date,
        ):
            print(line)
    except (H.HeadlessHwpxError, OSError, ValueError) as exc:
        print(f"[중단] {exc}")
        return 2
    print("\ncheck_headless_artifact.py 로 검사하고 최종본은 한컴에서 직접 확인할 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
