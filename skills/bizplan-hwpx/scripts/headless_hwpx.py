"""승인된 AX1 템플릿용 HWPX 경량 처리 공용 모듈.

표준 라이브러리만 사용하며 한컴오피스, COM, pyhwpx를 실행하지 않는다. 이 모듈은
일반 HWPX 편집기가 아니다. 단일 섹션인 승인 템플릿과 그 템플릿에서 이 모듈이 만든
문서만 처리하며, 지원 범위 밖의 패키지는 결과를 쓰기 전에 중단한다.
"""

from __future__ import annotations

import math
import hashlib
import json
import os
import re
import struct
import tempfile
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# --- 규칙 상수 (references/08-headless-format-rules.md 와 같은 값이어야 함) ---

FONT_FACE = "맑은 고딕"
HEADER_FILL = "#D9D9D9"
BODY_LINE_SPACING = 160
CELL_LINE_SPACING = 160  # 표 셀도 본문과 같은 160%
BODY_TEXT_HEIGHT = 1000  # 10pt. HWPUNIT = pt * 100
# 줄바꿈 계산 여유. 한/글의 줄나눔을 정확히 재현할 수 없으므로 조금 좁게 잡아
# 줄 수를 적게 세지 않도록 한다. 적게 세면 그만큼 글자가 겹친다.
WRAP_SAFETY = 0.97
ALLOWED_HEIGHTS = (1000, 1050, 1200, 1500)  # 본문 10 / 항 10.5 / 절 12 / 장 15

MALGUN = Path(r"C:\Windows\Fonts\malgun.ttf")
MALGUN_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

# 체크 상태를 나타내는 문자는 의미 정보이므로 자동 치환하지 않는다. 글꼴 메트릭을
# 읽을 수 없는 환경에서도 이 집합은 그대로 보존하고 최종 시각 검증 대상으로 남긴다.
SEMANTIC_SYMBOLS = frozenset({"☐", "☑", "☒", "✓", "✔", "□", "■"})
HANGUL_RANGES = (
    (0x1100, 0x11FF),
    (0x3130, 0x318F),
    (0xA960, 0xA97F),
    (0xAC00, 0xD7AF),
    (0xD7B0, 0xD7FF),
    (0xFFA0, 0xFFDC),
)

SECTION = "Contents/section0.xml"
HEADER = "Contents/header.xml"
PREVIEW = "Preview/PrvText.txt"
REQUIRED_PARTS = {"mimetype", "Contents/content.hpf", HEADER, SECTION}
MIMETYPE = b"application/hwp+zip"


class HeadlessHwpxError(RuntimeError):
    """지원 범위 밖이거나 안전 검증에 실패한 HWPX."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_hangul_codepoint(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in HANGUL_RANGES)


def hangul_runs(text: str) -> list[str]:
    """문자열에서 연속된 한글 코드포인트 묶음을 입력 순서대로 반환한다."""
    runs: list[str] = []
    current: list[str] = []
    for char in text:
        if is_hangul_codepoint(ord(char)):
            current.append(char)
        elif current:
            runs.append("".join(current))
            current.clear()
    if current:
        runs.append("".join(current))
    return runs


def missing_hangul_runs(source_texts: list[str], rendered: str) -> list[str]:
    """입력의 실제 한글 묶음 중 출력 원문에 그대로 남지 않은 값을 찾는다."""
    expected = {run for text in source_texts for run in hangul_runs(text)}
    return sorted((run for run in expected if run not in rendered), key=lambda value: (-len(value), value))


def encoded_hangul_references(text: str) -> list[str]:
    """실제 한글 대신 기록된 유니코드 이스케이프·숫자 문자참조를 찾는다."""
    found: list[str] = []
    for match in re.finditer(r"\\(?:u([0-9A-Fa-f]{4})|U([0-9A-Fa-f]{8}))", text):
        codepoint = int(match.group(1) or match.group(2), 16)
        if is_hangul_codepoint(codepoint):
            found.append(match.group(0))
    for match in re.finditer(r"&#(?:(?:x|X)([0-9A-Fa-f]+)|(\d+));", text):
        codepoint = int(match.group(1), 16) if match.group(1) else int(match.group(2), 10)
        if is_hangul_codepoint(codepoint):
            found.append(match.group(0))
    return found


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
    path = Path(path)
    if path.suffix.lower() != ".hwpx" or not path.is_file():
        raise HeadlessHwpxError(f"HWPX 파일이 아님: {path}")
    try:
        with zipfile.ZipFile(path) as zf:
            bad_crc = zf.testzip()
            if bad_crc:
                raise HeadlessHwpxError(f"ZIP CRC 오류: {bad_crc}")
            entries = [
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
    except zipfile.BadZipFile as exc:
        raise HeadlessHwpxError(f"유효한 HWPX ZIP이 아님: {path}") from exc
    validate_entries(entries)
    return entries


def write_hwpx(entries: list, path) -> None:
    """검증된 항목을 같은 폴더의 임시 파일에 쓴 뒤 원자적으로 교체한다.

    mimetype 은 첫 항목이어야 하고, mimetype 과 BinData/* 는 무압축이어야 한다.
    원본이 잘못 압축되어 있었더라도 여기서 바로잡는다.
    """
    validate_entries(entries)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(entries, key=lambda e: e.name != "mimetype")
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp.hwpx", dir=path.parent)
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w") as zf:
            for e in ordered:
                info = zipfile.ZipInfo(e.name, date_time=e.date_time)
                info.compress_type = zipfile.ZIP_STORED if must_be_stored(e.name) else e.compress_type
                info.external_attr = e.external_attr
                info.internal_attr = e.internal_attr
                info.create_system = e.create_system
                zf.writestr(info, e.data)
        read_hwpx(temp_path)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def validate_entries(entries: list[Entry]) -> None:
    """경량 모드가 안전하게 처리할 수 있는 단일 섹션 패키지만 허용한다."""
    if not entries:
        raise HeadlessHwpxError("빈 HWPX 패키지")
    names = [entry.name for entry in entries]
    if len(names) != len(set(names)):
        raise HeadlessHwpxError("중복 ZIP 항목이 있음")
    missing = sorted(REQUIRED_PARTS - set(names))
    if missing:
        raise HeadlessHwpxError("필수 HWPX 항목 누락: " + ", ".join(missing))
    if names[0] != "mimetype" or entries[0].compress_type != zipfile.ZIP_STORED:
        raise HeadlessHwpxError("mimetype은 첫 항목이자 무압축이어야 함")
    if entries[0].data.strip() != MIMETYPE:
        raise HeadlessHwpxError("지원하지 않는 HWPX mimetype")
    sections = sorted(name for name in names if re.fullmatch(r"Contents/section\d+\.xml", name))
    if sections != [SECTION]:
        raise HeadlessHwpxError("경량 모드는 단일 Contents/section0.xml 문서만 지원함")
    forbidden_names = [name for name in names if re.search(r"encrypt|signature", name, re.I)]
    if forbidden_names:
        raise HeadlessHwpxError("암호화·전자서명 패키지는 경량 모드에서 지원하지 않음")
    for entry in entries:
        if must_be_stored(entry.name) and entry.compress_type != zipfile.ZIP_STORED:
            raise HeadlessHwpxError(f"무압축이어야 하는 ZIP 항목: {entry.name}")
        if entry.name.lower().endswith((".xml", ".hpf")):
            try:
                ET.fromstring(entry.data)
            except ET.ParseError as exc:
                raise HeadlessHwpxError(f"XML 파싱 실패: {entry.name}: {exc}") from exc


def load_template_manifest(skill_root: Path) -> dict:
    manifest_path = skill_root / "assets" / "templates" / "template-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HeadlessHwpxError(f"템플릿 매니페스트를 읽을 수 없음: {manifest_path}") from exc
    if manifest.get("schemaVersion") != "ax1.hwpx-template/v1":
        raise HeadlessHwpxError("지원하지 않는 템플릿 매니페스트 버전")
    return manifest


def approved_template(skill_root: Path) -> Path:
    manifest = load_template_manifest(skill_root)
    template = skill_root / "assets" / "templates" / str(manifest.get("file", ""))
    expected = str(manifest.get("sha256", "")).lower()
    if not template.is_file() or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise HeadlessHwpxError("승인 템플릿 파일 또는 SHA-256 정보가 올바르지 않음")
    actual = sha256_file(template)
    if actual != expected:
        raise HeadlessHwpxError(f"승인 템플릿 SHA-256 불일치: {actual}")
    read_hwpx(template)
    return template


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

    def __init__(self, path: Path | None = None):
        self.portable = path is None or not path.is_file()
        if self.portable:
            self.buf = b""
            self._cache = {}
            return
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
        if self.portable:
            category = unicodedata.category(chr(cp))
            return 0 if category in {"Cc", "Cs", "Co", "Cn"} else max(cp, 1)
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
        if self.portable:
            ch = chr(cp)
            if self.glyph_id(cp) == 0:
                return None
            if unicodedata.combining(ch):
                return 0.0
            if ch.isspace():
                return 0.5
            return 1.0 if unicodedata.east_asian_width(ch) in {"W", "F", "A"} else 0.55
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
    """paraPr id -> {"spacing": %, "align": 가로정렬}"""
    out = {}
    for m in re.finditer(r'<hh:paraPr id="(\d+)"[^>]*>(.*?)</hh:paraPr>', header, re.S):
        body = m.group(2)
        ls = re.search(r'<hh:lineSpacing type="PERCENT" value="(-?\d+)"', body)
        al = re.search(r'<hh:align horizontal="(\w+)"', body)
        out[m.group(1)] = {
            "spacing": int(ls.group(1)) if ls else None,
            "align": al.group(1) if al else None,
        }
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
