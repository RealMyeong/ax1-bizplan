"""HWPX 산출물 서식 공용 모듈.

표준 라이브러리만 사용한다. 한/글 COM 이나 외부 패키지에 의존하지 않으므로
한컴오피스가 없는 환경에서도 검사와 수정이 가능하다.
"""

from __future__ import annotations

import math
import re
import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# --- 규칙 상수 (references/01-format-rules.md 와 같은 값이어야 함) ------------

FONT_FACE = "맑은 고딕"
HEADER_FILL = "#D9D9D9"
BODY_LINE_SPACING = 160
CELL_LINE_SPACING = 160  # 표 셀도 본문과 같은 160%
BODY_TEXT_HEIGHT = 1000  # 10pt. HWPUNIT = pt * 100
# 줄바꿈 계산 여유. 한/글의 줄나눔을 정확히 재현할 수 없으므로 조금 좁게 잡아
# 줄 수를 적게 세지 않도록 한다. 적게 세면 그만큼 글자가 겹친다.
WRAP_SAFETY = 0.97
ALLOWED_HEIGHTS = (1000, 1050, 1200, 1500)  # 본문 10 / 항 10.5 / 절 12 / 장 15

# 제목 계층. 4수준은 3수준과 서식이 같고 개요 스타일 태그만 다르다.
# HEADING_MARGIN 은 (문단 위, 문단 아래) 간격이며 단위는 HWPUNIT (1pt = 100).
HEADING_HEIGHT = {1: 1500, 2: 1200, 3: 1050, 4: 1050}
HEADING_MARGIN = {1: (0, 1000), 2: (1400, 500), 3: (1000, 300), 4: (1000, 300)}
HEADING_STYLE = {1: "개요 1", 2: "개요 2", 3: "개요 3", 4: "개요 4"}

# 목차 항목 - 장(굵게)·절(들여쓰기) 2단계. 항 이하는 목차에 넣지 않는다.
TOC_INDENT = 1000
TOC_STYLE = {1: "차례 1", 2: "차례 2"}

# 리스트 - 단계별 불릿 기호. 4수준 기호는 3수준과 같고 들여쓰기만 한 단계 더 는다.
# 접히는 줄이 글자 시작점에 맞춰지도록 내어쓰기(intent 음수)를 함께 쓴다.
BULLETS = {1: "●", 2: "-", 3: "·", 4: "·"}
LIST_INDENT_STEP = 1000  # 단계당 왼쪽여백 증가분
GANADA = "가나다라마바사아자차카타파하"

MALGUN = Path(r"C:\Windows\Fonts\malgun.ttf")
MALGUN_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

# 맑은 고딕에 글리프가 없는 문자와 권장 대체
GLYPH_REPLACEMENTS = {
    "\u2610": "\u25a1",  # 빈 네모칸 -> 흰 네모
    "\u2611": "\u25a1",
    "\u2612": "\u25a1",
    "\u2713": "\u221a",  # 체크 -> 제곱근 기호
}

SECTION = "Contents/section0.xml"
HEADER = "Contents/header.xml"
PREVIEW = "Preview/PrvText.txt"


# --- ZIP 입출력 --------------------------------------------------------------


def must_be_stored(name: str) -> bool:
    """한/글이 무압축으로 기록하는 항목.

    여기를 DEFLATE 로 바꿔 저장하면 한/글이 무결성 검사에서 변조로 판정해
    "문서가 손상되었거나 변조되었을 가능성이 있습니다" 대화상자를 띄우고 열지 않는다.
    바이트 내용이 같아도 저장 방식이 다르면 걸린다. 그림이 든 문서에서만 드러난다.
    """
    return name == "mimetype" or name.startswith("BinData/")


@dataclass
class Entry:
    name: str
    data: bytes
    compress_type: int
    external_attr: int = 0
    internal_attr: int = 0
    create_system: int = 0
    date_time: tuple = (1980, 1, 1, 0, 0, 0)


def read_hwpx(path) -> list:
    with zipfile.ZipFile(path) as zf:
        return [
            Entry(
                name=i.filename,
                data=zf.read(i.filename),
                compress_type=i.compress_type,
                external_attr=i.external_attr,
                internal_attr=i.internal_attr,
                create_system=i.create_system,
                date_time=i.date_time,
            )
            for i in zf.infolist()
        ]


def write_hwpx(entries: list, path) -> None:
    """항목 순서와 ZIP 속성을 유지해 다시 쓴다.

    mimetype 은 첫 항목이어야 하고, mimetype 과 BinData/* 는 무압축이어야 한다.
    원본이 잘못 압축되어 있었더라도 여기서 바로잡는다.
    """
    ordered = sorted(entries, key=lambda e: e.name != "mimetype")
    with zipfile.ZipFile(path, "w") as zf:
        for e in ordered:
            info = zipfile.ZipInfo(e.name, date_time=e.date_time)
            info.compress_type = zipfile.ZIP_STORED if must_be_stored(e.name) else e.compress_type
            info.external_attr = e.external_attr
            info.internal_attr = e.internal_attr
            info.create_system = e.create_system
            zf.writestr(info, e.data)


def get_text(entries: list, name: str) -> str:
    for e in entries:
        if e.name == name:
            return e.data.decode("utf-8")
    raise KeyError(name)


def set_text(entries: list, name: str, text: str) -> None:
    for e in entries:
        if e.name == name:
            e.data = text.encode("utf-8")
            return
    raise KeyError(name)


# --- TrueType 메트릭 ---------------------------------------------------------


class Font:
    """cmap 으로 글리프 존재를, hmtx 로 실제 글자 폭을 확인한다."""

    def __init__(self, path: Path):
        self.buf = path.read_bytes()
        b = self.buf
        num_tables = struct.unpack(">H", b[4:6])[0]
        self.tables = {}
        for i in range(num_tables):
            o = 12 + i * 16
            tag = b[o : o + 4].decode("latin1")
            self.tables[tag] = struct.unpack(">II", b[o + 8 : o + 16])
        head = self.tables["head"][0]
        self.units_per_em = struct.unpack(">H", b[head + 18 : head + 20])[0]
        hhea = self.tables["hhea"][0]
        self.num_h_metrics = struct.unpack(">H", b[hhea + 34 : hhea + 36])[0]
        self.hmtx = self.tables["hmtx"][0]
        self._parse_cmap()
        self._cache = {}

    def _parse_cmap(self) -> None:
        b, cm = self.buf, self.tables["cmap"][0]
        n = struct.unpack(">H", b[cm + 2 : cm + 4])[0]
        self.f4 = 0
        self.f12 = 0
        for i in range(n):
            o = cm + 4 + i * 8
            pid, eid, off = struct.unpack(">HHI", b[o : o + 8])
            so = cm + off
            fmt = struct.unpack(">H", b[so : so + 2])[0]
            if pid == 3 and eid == 1 and fmt == 4:
                self.f4 = so
            elif pid == 3 and eid == 10 and fmt == 12:
                self.f12 = so

    def glyph_id(self, cp: int) -> int:
        if cp in self._cache:
            return self._cache[cp]
        g = 0
        b = self.buf
        if self.f12:
            n = struct.unpack(">I", b[self.f12 + 12 : self.f12 + 16])[0]
            lo, hi = 0, n - 1
            while lo <= hi:
                mid = (lo + hi) // 2
                o = self.f12 + 16 + mid * 12
                start, end, gid = struct.unpack(">III", b[o : o + 12])
                if cp < start:
                    hi = mid - 1
                elif cp > end:
                    lo = mid + 1
                else:
                    g = gid + (cp - start)
                    break
        if not g and self.f4 and cp <= 0xFFFF:
            seg2 = struct.unpack(">H", b[self.f4 + 6 : self.f4 + 8])[0]
            end_o = self.f4 + 14
            start_o = end_o + seg2 + 2
            delta_o = start_o + seg2
            range_o = delta_o + seg2
            for i in range(seg2 // 2):
                end = struct.unpack(">H", b[end_o + i * 2 : end_o + i * 2 + 2])[0]
                if end < cp:
                    continue
                start = struct.unpack(">H", b[start_o + i * 2 : start_o + i * 2 + 2])[0]
                if start > cp:
                    break
                ro = struct.unpack(">H", b[range_o + i * 2 : range_o + i * 2 + 2])[0]
                delta = struct.unpack(">h", b[delta_o + i * 2 : delta_o + i * 2 + 2])[0]
                if ro == 0:
                    g = (cp + delta) & 0xFFFF
                else:
                    p = range_o + i * 2 + ro + (cp - start) * 2
                    g = struct.unpack(">H", b[p : p + 2])[0]
                    if g:
                        g = (g + delta) & 0xFFFF
                break
        self._cache[cp] = g
        return g

    def advance(self, cp: int):
        """em 대비 글자 폭. 글리프가 없으면 None."""
        g = self.glyph_id(cp)
        if not g:
            return None
        i = min(g, self.num_h_metrics - 1)
        p = self.hmtx + i * 4
        return struct.unpack(">H", self.buf[p : p + 2])[0] / self.units_per_em


def text_width(text: str, height: int, bold: bool, regular: Font, boldfont: Font, ratio=1.0, spacing=0.0):
    """HWPUNIT 폭과 글리프 누락 문자 목록을 함께 돌려준다."""
    font = boldfont if bold else regular
    width = 0.0
    missing = []
    for ch in text:
        adv = font.advance(ord(ch))
        if adv is None:
            missing.append(ch)
            adv = 1.0
        width += adv * height * ratio + height * spacing
    return width, missing


# --- 문서 파싱 ---------------------------------------------------------------

_UNESCAPE = (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&"))


def unescape(s: str) -> str:
    for a, b in _UNESCAPE:
        s = s.replace(a, b)
    return s


@dataclass
class CharPr:
    height: int
    bold: bool
    ratio: float
    spacing: float
    font_ids: list = field(default_factory=list)


def parse_char_prs(header: str) -> dict:
    out = {}
    for m in re.finditer(r'<hh:charPr id="(\d+)"([^>]*)>(.*?)</hh:charPr>', header, re.S):
        cid, attrs, body = m.group(1), m.group(2), m.group(3)
        ratio = re.search(r'<hh:ratio hangul="(\d+)"', body)
        spacing = re.search(r'<hh:spacing hangul="(-?\d+)"', body)
        ids = []
        for ref in re.finditer(r"<hh:fontRef ([^>]*?)/>", body):
            ids += re.findall(r'"(\d+)"', ref.group(1))
        out[cid] = CharPr(
            height=int(re.search(r'height="(\d+)"', attrs).group(1)),
            bold=bool(re.search(r"<hh:bold\s*/?>", body)),
            ratio=(int(ratio.group(1)) if ratio else 100) / 100,
            spacing=(int(spacing.group(1)) if spacing else 0) / 100,
            font_ids=ids,
        )
    return out


def parse_para_prs(header: str) -> dict:
    """paraPr id -> {"spacing": %, "align": 가로정렬, "intent"/"left"/"prev"/"next": HWPUNIT}

    여백은 hp:switch 의 case/default 두 분기에 중복돼 있으므로 첫 값을 읽는다.
    (수정할 때는 두 분기를 모두 고쳐야 한다.)
    """
    out = {}
    for m in re.finditer(r'<hh:paraPr id="(\d+)"[^>]*>(.*?)</hh:paraPr>', header, re.S):
        body = m.group(2)
        ls = re.search(r'<hh:lineSpacing type="PERCENT" value="(-?\d+)"', body)
        al = re.search(r'<hh:align horizontal="(\w+)"', body)
        d = {
            "spacing": int(ls.group(1)) if ls else None,
            "align": al.group(1) if al else None,
        }
        for name in ("intent", "left", "prev", "next"):
            mm = re.search(rf'<hc:{name} value="(-?\d+)"', body)
            d[name] = int(mm.group(1)) if mm else 0
        out[m.group(1)] = d
    return out


def style_ids_by_name(header: str) -> dict:
    """스타일 이름 -> id. 제목(개요 1~4)·목차(차례 1~2) 스타일 태그에 쓴다.

    스타일 태그는 겉모습을 바꾸지 않는다 (서식은 문단·글자모양이 정한다).
    다만 한/글 [도구]-[제목 차례]의 '스타일로 모으기'가 이 태그로 제목을 찾는다.
    문단모양의 heading 을 OUTLINE 으로 바꾸면 한/글이 개요 번호를 덧붙여
    본문의 번호와 겹쳐 보이므로, 스타일 태그만 쓴다.
    """
    out = {}
    for m in re.finditer(r"<hh:style ([^>]*?)/?>", header):
        i = re.search(r'id="(\d+)"', m.group(1))
        n = re.search(r'name="([^"]*)"', m.group(1))
        if i and n:
            out.setdefault(n.group(1), i.group(1))
    return out


def malgun_font_ids(header: str) -> set:
    """맑은 고딕으로 등록된 font id 집합."""
    return {m.group(1) for m in re.finditer(r'<hh:font id="(\d+)" face="([^"]*)"', header) if m.group(2) == FONT_FACE}


def header_fill_ids(header: str) -> set:
    """배경색이 규칙 색(#D9D9D9)인 borderFill id 집합."""
    ids = set()
    for m in re.finditer(r'<hh:borderFill id="(\d+)"[^>]*>(.*?)</hh:borderFill>', header, re.S):
        face = re.search(r'faceColor="([^"]*)"', m.group(2))
        if face and face.group(1).upper() == HEADER_FILL.upper():
            ids.add(m.group(1))
    return ids


def shaded_fill_ids(header: str) -> set:
    """색이 채워진 borderFill id 집합. 색을 가리지 않는다.

    라벨열 표 판정에 쓴다. 규칙 색으로 바꾸기 전에도 '음영이 있다'를 알아야 한다.
    """
    ids = set()
    for m in re.finditer(r'<hh:borderFill id="(\d+)"[^>]*>(.*?)</hh:borderFill>', header, re.S):
        if re.search(r'faceColor="#[0-9A-Fa-f]{6}"', m.group(2)):
            ids.add(m.group(1))
    return ids


def front_matter_fill_ids(section: str, body_start: int) -> set:
    """표지~목차 구간의 표 셀이 참조하는 borderFill id 집합.

    이 정의는 고치지 않는다. 본문과 공유하고 있으면 사본을 만들어 본문에만 물린다.
    """
    ids = set()
    for (a, b) in table_spans(section):
        if a >= body_start:
            continue
        for c in cells(section[a:b]):
            if c.fill:
                ids.add(c.fill)
    return ids


def table_spans(section: str) -> list:
    """표 (시작, 끝) 오프셋 목록. 표 안/밖 판정에 쓴다."""
    spans, pos = [], 0
    while True:
        a = section.find("<hp:tbl ", pos)
        if a < 0:
            return spans
        b = section.find("</hp:tbl>", a)
        if b < 0:
            return spans
        b += len("</hp:tbl>")
        spans.append((a, b))
        pos = b


def in_any_span(spans: list, offset: int) -> bool:
    return any(a <= offset < b for a, b in spans)


def body_start_offset(section: str):
    """불가침 구간의 끝 오프셋. 목차 제목 문단 바로 다음이다.

    표지·문서정보·개정이력·목차 **제목**까지가 기관 양식이고, 목차 항목부터는
    문서마다 새로 만든다. 따라서 목차 제목 문단이 끝나는 지점이 경계다.

    목차 제목을 찾지 못하면 None 을 돌려준다. 이때는 경계를 추정하지 않는다.
    """
    toc_pos = None
    for m in re.finditer(r"<hp:t>([^<]*)</hp:t>", section):
        if re.fullmatch(r"목\s*차", unescape(m.group(1)).strip()):
            toc_pos = m.start()
    if toc_pos is None:
        return None
    end = section.find("</hp:p>", toc_pos)
    return end + len("</hp:p>") if end >= 0 else None


def paragraphs(section: str) -> list:
    """(오프셋, 여는태그 속성, 문단 본문) 목록."""
    marks = list(re.finditer(r"<hp:p ([^>]*)>", section))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(section)
        out.append((m.start(), m.group(1), section[m.end() : end]))
    return out


def tables(section: str) -> list:
    """표 XML 문자열 목록."""
    return [section[a:b] for a, b in table_spans(section)]


CELL_RE = re.compile(
    r'<hp:tc ([^>]*)>(.*?)'
    r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"/>'
    r'<hp:cellSpan colSpan="(\d+)" rowSpan="(\d+)"/>'
    r'<hp:cellSz width="(\d+)" height="(\d+)"/>'
    r'<hp:cellMargin left="(\d+)" right="(\d+)"',
    re.S,
)


@dataclass
class Cell:
    attrs: str
    inner: str
    col: int
    row: int
    colspan: int
    rowspan: int
    width: int
    height: int
    margin_left: int
    margin_right: int

    @property
    def fill(self):
        m = re.search(r'borderFillIDRef="(\d+)"', self.attrs)
        return m.group(1) if m else None

    @property
    def vert_align(self):
        m = re.search(r'vertAlign="(\w+)"', self.inner)
        return m.group(1) if m else None

    @property
    def para_ids(self):
        return re.findall(r'<hp:p [^>]*paraPrIDRef="(\d+)"', self.inner)

    @property
    def usable_width(self):
        return self.width - self.margin_left - self.margin_right

    def runs(self):
        """(charPrIDRef, 텍스트) 목록."""
        return [
            (m.group(1), unescape("".join(re.findall(r"<hp:t>([^<]*)</hp:t>", m.group(2)))))
            for m in re.finditer(r'<hp:run charPrIDRef="(\d+)">(.*?)</hp:run>', self.inner, re.S)
        ]


def cells(table_xml: str) -> list:
    out = []
    for m in CELL_RE.finditer(table_xml):
        out.append(
            Cell(
                attrs=m.group(1),
                inner=m.group(2),
                col=int(m.group(3)),
                row=int(m.group(4)),
                colspan=int(m.group(5)),
                rowspan=int(m.group(6)),
                width=int(m.group(7)),
                height=int(m.group(8)),
                margin_left=int(m.group(9)),
                margin_right=int(m.group(10)),
            )
        )
    return out


def is_label_column_table(table_xml: str, fill_ids: set) -> bool:
    """1열만 음영인 라벨열 표는 머리행이 없는 표다."""
    first_row = [c for c in cells(table_xml) if c.row == 0]
    if len(first_row) < 2:
        return False
    first_row.sort(key=lambda c: c.col)
    return first_row[0].fill in fill_ids and all(c.fill not in fill_ids for c in first_row[1:])


def wrap_lines(text: str, height: int, bold: bool, regular: Font, boldfont: Font, avail: int, ratio=1.0, spacing=0.0):
    """줄바꿈 지점을 계산해 각 줄의 시작 글자 위치 목록을 돌려준다.

    줄 배치 캐시(hp:lineseg)는 **실제로 그려지는 줄마다 하나씩** 있어야 한다.
    문단이 세 줄로 접히는데 캐시가 한 개뿐이면 세 줄이 같은 자리에 겹쳐 그려진다.

    한글은 글자 단위로, 영문은 되도록 공백에서 끊는다.
    """
    if not text:
        return [0]
    # 한/글은 한글도 어절(공백) 단위로 끊는다. 글자 단위로 계산하면 줄 수를 적게 잡아
    # 캐시가 모자라고, 모자란 만큼 여러 줄이 한 자리에 겹쳐 그려진다.
    # 계산이 한/글과 정확히 같을 수는 없으므로 여유를 두어 **적게 잡지 않도록** 한다.
    avail = avail * WRAP_SAFETY
    font = boldfont if bold else regular
    starts, width, last_space = [0], 0.0, -1
    i = 0
    while i < len(text):
        ch = text[i]
        adv = font.advance(ord(ch))
        if adv is None:
            adv = 1.0
        w = adv * height * ratio + height * spacing
        if ch == " ":
            last_space = i
        if width + w > avail and i > starts[-1]:
            if last_space > starts[-1]:
                i = last_space + 1  # 어절 단위로 되돌린다
            starts.append(i)
            width, last_space = 0.0, -1
            continue
        width += w
        i += 1
    return starts


def wrap_widths(text: str, widths: list, avail: int) -> list:
    """글자별 폭이 이미 계산된 경우의 줄바꿈 지점. 여러 글자모양이 섞인 문단에 쓴다."""
    if not text:
        return [0]
    avail = avail * WRAP_SAFETY
    starts, width, last_space = [0], 0.0, -1
    i = 0
    while i < len(text):
        if text[i] == " ":
            last_space = i
        if width + widths[i] > avail and i > starts[-1]:
            if last_space > starts[-1]:
                i = last_space + 1
            starts.append(i)
            width, last_space = 0.0, -1
            continue
        width += widths[i]
        i += 1
    return starts


def paragraph_runs(para_head: str, char_prs: dict, regular: Font, boldfont: Font):
    """문단 앞부분에서 (전체 글자, 글자별 폭) 을 만든다. 표를 담은 문단은 빈 값."""
    text, widths = "", []
    for m in re.finditer(r'<hp:run charPrIDRef="(\d+)">((?:(?!</hp:run>).)*)</hp:run>', para_head, re.S):
        cp = char_prs.get(m.group(1))
        if not cp:
            continue
        piece = unescape("".join(re.findall(r"<hp:t>([^<]*)</hp:t>", m.group(2))))
        font = boldfont if cp.bold else regular
        for ch in piece:
            adv = font.advance(ord(ch))
            if adv is None:
                adv = 1.0
            widths.append(adv * cp.height * cp.ratio + cp.height * cp.spacing)
        text += piece
    return text, widths


def min_lines(total_width: float, avail: int) -> int:
    """폭만으로 정해지는 최소 줄 수. 이보다 적은 lineseg 는 반드시 겹친다."""
    return max(1, math.ceil(total_width / avail)) if avail > 0 else 1


def longest_word_width(text: str, height: int, bold: bool, regular: Font, boldfont: Font, ratio=1.0, spacing=0.0):
    """줄바꿈 지점으로 끊었을 때 가장 긴 조각의 폭."""
    best, word = 0.0, ""
    for token in re.split(r"[\s,()\[\]\u00b7]+", text):
        if not token:
            continue
        w, _ = text_width(token, height, bold, regular, boldfont, ratio, spacing)
        if w > best:
            best, word = w, token
    return best, word


# --- 제목·목차·리스트 계층 ------------------------------------------------------

# 리스트 머리 글자 판별. 뒤에 공백이 붙은 형태만 리스트로 본다.
BULLET_MARKER_RE = re.compile(r"^[●\-·] ")
ORDERED_MARKER_RE = re.compile(rf"^(\d{{1,2}}[.)]|[{GANADA}]\.) ")


def ordered_marker(level: int, n: int) -> str:
    """번호 목록의 단계별 머리 글자. 1수준 `1.` / 2수준 `가.` / 3·4수준 `1)`.

    2수준이 14(하)를 넘으면 숫자로 되돌린다.
    """
    if level == 2:
        return GANADA[n - 1] + "." if 1 <= n <= len(GANADA) else f"{n}."
    if level >= 3:
        return f"{n})"
    return f"{n}."


def marker_hang(marker: str, regular: Font, boldfont: Font) -> int:
    """머리 글자(기호·번호)와 뒤 공백의 폭. 내어쓰기 값으로 쓴다."""
    w, _ = text_width(marker + " ", BODY_TEXT_HEIGHT, False, regular, boldfont)
    return math.ceil(w)


def list_level_of(margins: dict) -> int:
    """리스트 문단모양의 여백에서 단계를 되짚는다.

    새 규칙: left = (단계-1)*STEP + 내어쓰기, intent = -내어쓰기
    -> left + intent = (단계-1)*STEP
    """
    base = margins.get("left", 0) + margins.get("intent", 0)
    return max(1, min(4, round(base / LIST_INDENT_STEP) + 1))


def para_visible_runs(body: str, char_prs: dict) -> list:
    """(CharPr, 텍스트) 목록. 글자가 없는 run 과 표를 담은 run 은 제외."""
    head = body.split("<hp:linesegarray>")[0]
    out = []
    for m in re.finditer(r'<hp:run charPrIDRef="(\d+)">((?:(?!</hp:run>).)*)</hp:run>', head, re.S):
        if "<hp:tbl" in m.group(2):
            continue
        text = unescape("".join(re.findall(r"<hp:t>([^<]*)</hp:t>", m.group(2))))
        if text:
            out.append((char_prs.get(m.group(1)), text))
    return out


def heading_level_of(body: str, char_prs: dict):
    """제목 문단이면 수준(1~4), 아니면 None.

    크기·굵기로 판정한다 (15/12/10.5pt bold). 10.5pt 는 3·4수준이 같은
    서식이므로 번호 깊이(1.1.1.1)로 가른다. 번호가 없으면 3수준으로 본다.
    """
    runs = [r for r in para_visible_runs(body, char_prs) if r[0]]
    if not runs:
        return None
    combos = {(cp.height, cp.bold) for cp, _ in runs}
    if len(combos) != 1:
        return None
    height, bold = combos.pop()
    if not bold:
        return None
    level = {1500: 1, 1200: 2, 1050: 3}.get(height)
    if level == 3 and re.match(r"\d+(\.\d+){3}", "".join(t for _, t in runs)):
        level = 4
    return level


def text_width_of(section: str) -> int:
    """본문 가용 폭 (쪽 폭 - 좌우 여백)."""
    m = re.search(r'<hp:pagePr[^>]*width="(\d+)"[^>]*>.*?<hp:margin[^>]*left="(\d+)" right="(\d+)"', section, re.S)
    if not m:
        return 42520
    return int(m.group(1)) - int(m.group(2)) - int(m.group(3))


def relayout_paragraph(para_xml: str, char_prs: dict, regular: Font, boldfont: Font, horzsize=None) -> str:
    """글자나 여백을 바꾼 문단의 줄 배치 정보를 다시 만든다.

    글자가 바뀌거나 가용 폭이 좁아지면 원래 줄 배치가 그대로 남아
    여러 줄이 한 자리에 겹쳐 그려진다. horzsize 를 주면 그 폭으로 다시 접는다.
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
    if horzsize is None:
        horzsize = num("horzsize", 42520)
    vertpos0 = num("vertpos", 0)
    flags = (re.search(r'flags="(\d+)"', attrs) or [None, "393216"])[1]

    text, widths = paragraph_runs(head, char_prs, regular, boldfont)
    starts = wrap_widths(text, widths, horzsize)
    line_h = vertsize + spacing
    segs = "".join(
        f'<hp:lineseg textpos="{pos}" vertpos="{vertpos0 + i * line_h}" vertsize="{vertsize}"'
        f' textheight="{textheight}" baseline="{baseline}" spacing="{spacing}"'
        f' horzpos="{horzpos}" horzsize="{horzsize}" flags="{flags}"/>'
        for i, pos in enumerate(starts)
    )
    return head + "<hp:linesegarray>" + segs + "</hp:linesegarray>" + rest
