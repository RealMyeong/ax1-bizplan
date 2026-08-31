"""산출물 HWPX 에 서식 규칙을 적용한다.

    python apply_artifact_format.py <입력.hwpx> [-o 출력.hwpx] [--in-place]

표지~목차 불가침 구간은 글자 깨짐 교정만 하고 서식은 건드리지 않는다.
적용 후 check_artifact_format.py 로 반드시 재검사한다.
"""

from __future__ import annotations

import math
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True

import hwpx_format as H  # noqa: E402


class ParaPrPool:
    """문단모양을 조회하고 필요하면 복제해 새로 만든다."""

    def __init__(self, header: str):
        self.header = header
        self.blocks = {
            m.group(1): m.group(0)
            for m in re.finditer(r'<hh:paraPr id="(\d+)".*?</hh:paraPr>', header, re.S)
        }
        self.next_id = max((int(i) for i in self.blocks), default=-1) + 1
        self.new_blocks = []
        self.cache = {}

    def spacing_of(self, pid):
        m = re.search(r'<hh:lineSpacing type="PERCENT" value="(-?\d+)"', self.blocks.get(pid, ""))
        return int(m.group(1)) if m else None

    def align_of(self, pid):
        m = re.search(r'<hh:align horizontal="(\w+)"', self.blocks.get(pid, ""))
        return m.group(1) if m else None

    def set_spacing(self, pid, spacing):
        """기존 문단모양의 줄간격을 그 자리에서 바꾼다."""
        block = self.blocks[pid]
        new = re.sub(
            r'(<hh:lineSpacing type="PERCENT" value=")-?\d+(")',
            lambda m: m.group(1) + str(spacing) + m.group(2),
            block,
        )
        if new != block:
            self.blocks[pid] = new
            self.header = self.header.replace(block, new, 1)

    @staticmethod
    def _strip_id(block: str) -> str:
        return re.sub(r'^<hh:paraPr id="\d+"', '<hh:paraPr', block)

    def _render(self, pid: str, spacing: int, align) -> str:
        block = self.blocks[pid]
        block = re.sub(
            r'(<hh:lineSpacing type="PERCENT" value=")-?\d+(")',
            lambda m: m.group(1) + str(spacing) + m.group(2),
            block,
        )
        if align:
            block = re.sub(r'(<hh:align horizontal=")\w+(")', lambda m: m.group(1) + align + m.group(2), block)
        return block

    def variant(self, pid: str, spacing: int, align=None) -> str:
        """줄간격/정렬이 맞는 문단모양 id 를 돌려준다.

        내용이 똑같은 문단모양이 이미 있으면 그것을 재사용한다. 매번 복제하면
        같은 파일에 두 번 적용했을 때 쓰이지 않는 문단모양이 계속 쌓인다.
        """
        key = (pid, spacing, align)
        if key in self.cache:
            return self.cache[key]

        want = self._strip_id(self._render(pid, spacing, align))
        for other_id, block in self.blocks.items():
            if self._strip_id(block) == want:
                self.cache[key] = other_id
                return other_id

        new_id = str(self.next_id)
        self.next_id += 1
        block = re.sub(r'^<hh:paraPr id="\d+"', f'<hh:paraPr id="{new_id}"', self._render(pid, spacing, align))
        self.blocks[new_id] = block
        self.new_blocks.append(block)
        self.cache[key] = new_id
        return new_id

    def finish(self) -> str:
        """새로 만든 문단모양을 헤더에 넣고 itemCnt 를 맞춘다."""
        if not self.new_blocks:
            return self.header
        added = "".join(self.new_blocks)
        m = re.search(r'<hh:paraProperties itemCnt="(\d+)">', self.header)
        count = int(m.group(1)) + len(self.new_blocks)
        header = self.header.replace(m.group(0), f'<hh:paraProperties itemCnt="{count}">', 1)
        return header.replace("</hh:paraProperties>", added + "</hh:paraProperties>", 1)


def ensure_malgun(header: str, log: list) -> str:
    """모든 글꼴 참조를 맑은 고딕으로 바꾼다."""
    ids = H.malgun_font_ids(header)
    if not ids:
        log.append(f"[중단] 글꼴 목록에 {H.FONT_FACE} 가 없다. 한/글에서 한 번 지정한 뒤 다시 실행할 것")
        return header
    target = sorted(ids, key=int)[0]
    count = 0

    def fix(m):
        nonlocal count
        new = re.sub(r'(hangul|latin|hanja|japanese|other|symbol|user)="\d+"', lambda a: f'{a.group(1)}="{target}"', m.group(0))
        if new != m.group(0):
            count += 1
        return new

    header = re.sub(r"<hh:fontRef [^>]*/>", fix, header)
    log.append(f"글꼴 -> {H.FONT_FACE}(id {target}) : 글자모양 {count}개")
    return header


def ensure_header_fill(header: str, front_fills: set, log: list):
    """본문 표 머리행이 쓸 #D9D9D9 배경 borderFill id 를 확보한다.

    표지~목차가 참조하는 borderFill 은 절대 고치지 않는다. 그 정의를 본문과
    공유하고 있으면 색만 바꾼 사본을 새로 만들어 본문에만 물린다.
    """
    usable = H.header_fill_ids(header) - front_fills
    if usable:
        fid = sorted(usable, key=int)[0]
        log.append(f"본문 표 머리행 배경색 {H.HEADER_FILL} 확인 (borderFill {fid})")
        return header, fid

    # 사본을 뜰 원본 고르기: 테두리가 있는 음영 정의를 우선한다
    template = None
    for m in re.finditer(r'<hh:borderFill id="(\d+)"[^>]*>(.*?)</hh:borderFill>', header, re.S):
        has_fill = re.search(r'faceColor="(#[0-9A-Fa-f]{6})"', m.group(2))
        if has_fill and re.search(r'<hh:leftBorder type="SOLID"', m.group(2)):
            template = m
            if m.group(1) in front_fills:
                break  # 표지가 쓰는 머리행 정의가 가장 비슷하다
    if template is None:
        log.append("[경고] 음영용 borderFill 을 찾지 못해 본문 표 머리행 색을 적용하지 못함")
        return header, None

    ids = [int(i) for i in re.findall(r'<hh:borderFill id="(\d+)"', header)]
    new_id = str(max(ids) + 1)
    block = re.sub(r'^<hh:borderFill id="\d+"', f'<hh:borderFill id="{new_id}"', template.group(0))
    block = re.sub(r'faceColor="#[0-9A-Fa-f]{6}"', f'faceColor="{H.HEADER_FILL}"', block)

    m = re.search(r'<hh:borderFills itemCnt="(\d+)">', header)
    header = header.replace(m.group(0), f'<hh:borderFills itemCnt="{int(m.group(1)) + 1}">', 1)
    header = header.replace("</hh:borderFills>", block + "</hh:borderFills>", 1)
    log.append(
        f"본문 표 머리행용 borderFill {new_id} 생성 ({H.HEADER_FILL}). "
        f"표지~목차가 쓰는 borderFill {template.group(1)} 은 그대로 둠"
    )
    return header, new_id


def replace_missing_glyphs(text: str, regular: H.Font, log: list, label: str) -> str:
    """맑은 고딕에 없는 문자를 대체 문자로 바꾼다. 불가침 구간에도 적용한다."""
    seen = {}
    for m in re.finditer(r"<hp:t>([^<]*)</hp:t>", text):
        for ch in H.unescape(m.group(1)):
            if regular.glyph_id(ord(ch)) == 0:
                seen[ch] = seen.get(ch, 0) + 1
    for ch, n in sorted(seen.items()):
        repl = H.GLYPH_REPLACEMENTS.get(ch)
        if repl is None:
            log.append(f"[경고] {label}: {ch!r} U+{ord(ch):04X} 는 {H.FONT_FACE} 에 없으나 대체 문자가 정의되지 않음 x{n}")
            continue
        text = text.replace(ch, repl)
        log.append(f"글자 깨짐 교정 {ch!r} U+{ord(ch):04X} -> {repl!r} : {n}건")
    return text


def rebalance_columns(tbl: str, char_prs: dict, regular: H.Font, boldfont: H.Font):
    """단어가 잘리는 열을 넓히고 여유 있는 열에서 그만큼 뺀다. 표 전체 폭은 유지."""
    m = re.search(r'<hp:sz width="(\d+)"', tbl)
    col_cnt = re.search(r'colCnt="(\d+)"', tbl)
    if not m or not col_cnt:
        return tbl, None
    total = int(m.group(1))
    n = int(col_cnt.group(1))
    need = [0] * n
    cur = [0] * n
    for c in H.cells(tbl):
        if c.colspan != 1:
            continue
        cur[c.col] = c.width
        pad = c.margin_left + c.margin_right
        for cid, text in c.runs():
            cp = char_prs.get(cid)
            if not cp or not text.strip():
                continue
            w, _ = H.longest_word_width(text, cp.height, cp.bold, regular, boldfont, cp.ratio, cp.spacing)
            need[c.col] = max(need[c.col], math.ceil(w) + pad)
    if sum(cur) != total or all(need[i] <= cur[i] for i in range(n)):
        return tbl, None

    new = list(cur)
    deficit = 0
    for i in range(n):
        if need[i] > new[i]:
            deficit += need[i] - new[i]
            new[i] = need[i]
    slack = [max(0, new[i] - need[i]) for i in range(n)]
    pool = sum(slack)
    if pool < deficit:
        return tbl, None  # 넓힐 여유가 없다. 사람이 판단해야 한다
    left = deficit
    for i in range(n):
        if left <= 0:
            break
        take = min(slack[i], round(deficit * slack[i] / pool)) if pool else 0
        take = min(take, left, new[i] - need[i])
        new[i] -= take
        left -= take
    for i in range(n):
        while left > 0 and new[i] - need[i] > 0:
            step = min(left, new[i] - need[i])
            new[i] -= step
            left -= step
    if sum(new) != total:
        return tbl, None

    def fix_cell(match):
        col, span = int(match.group(1)), int(match.group(3))
        width = sum(new[col : col + span])
        return re.sub(r'<hp:cellSz width="\d+"', f'<hp:cellSz width="{width}"', match.group(0))

    tbl = re.sub(
        r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"/><hp:cellSpan colSpan="(\d+)" rowSpan="\d+"/><hp:cellSz width="\d+"',
        fix_cell,
        tbl,
    )
    return tbl, (cur, new)


def fix_linesegs(xml: str, percent: int) -> str:
    """줄 배치 캐시의 줄간격을 문단 줄간격에 맞춘다."""
    factor = (percent - 100) / 100

    def fix(m):
        want = round(int(m.group(2)) * factor)
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{want}{m.group(5)}"

    return re.sub(r'(<hp:lineseg [^>]*?vertsize=")(\d+)("[^>]*?spacing=")(-?\d+)(")', fix, xml)


def apply(src: Path, dst: Path) -> list:
    log = []
    entries = H.read_hwpx(src)
    header = H.get_text(entries, H.HEADER)
    section = H.get_text(entries, H.SECTION)

    regular = H.Font(H.MALGUN)
    boldfont = H.Font(H.MALGUN_BOLD)

    # 1. 글꼴
    header = ensure_malgun(header, log)

    # 2. 글자 깨짐 (불가침 구간 포함, 문서 전체)
    section = replace_missing_glyphs(section, regular, log, "본문")
    try:
        preview = H.get_text(entries, H.PREVIEW)
        fixed = preview
        for bad, good in H.GLYPH_REPLACEMENTS.items():
            fixed = fixed.replace(bad, good)
        if fixed != preview:
            H.set_text(entries, H.PREVIEW, fixed)
    except KeyError:
        pass

    # 3. 경계 판정 - 목차 다음부터가 서식 적용 구간이다
    body_start = H.body_start_offset(section)
    if body_start is None:
        log.append("[중단] 목차 문단을 찾지 못했다. 본문 시작 위치를 확인받기 전에는 서식을 바꾸지 않는다")
        H.set_text(entries, H.HEADER, header)
        H.set_text(entries, H.SECTION, section)
        H.write_hwpx(entries, dst)
        return log
    log.append(f"불가침 구간: 문서 시작 ~ 오프셋 {body_start} (표지·문서정보·개정이력·목차) 는 양식 그대로 둠")

    # 4. 본문 표 머리행 배경색 - 표지가 쓰는 정의는 건드리지 않는다
    front_fills = H.front_matter_fill_ids(section, body_start)
    header, fill_id = ensure_header_fill(header, front_fills, log)
    fill_ids = H.shaded_fill_ids(header)  # 라벨열 판정은 색을 가리지 않는다

    char_prs = H.parse_char_prs(header)
    spans = H.table_spans(section)
    pool = ParaPrPool(header)

    # 5. 본문 문단 줄간격 160%
    body_ids = set()
    for offset, attrs, _ in H.paragraphs(section):
        if offset < body_start or H.in_any_span(spans, offset):
            continue
        pid = re.search(r'paraPrIDRef="(\d+)"', attrs)
        if pid:
            body_ids.add(pid.group(1))
    for pid in sorted(body_ids):
        if pool.spacing_of(pid) != H.BODY_LINE_SPACING:
            pool.set_spacing(pid, H.BODY_LINE_SPACING)
    log.append(f"본문 문단 줄간격 {H.BODY_LINE_SPACING}% : 문단모양 {len(body_ids)}개")

    # 6. 표 - 머리행 서식 / 셀 줄간격 120% / 열 너비
    pieces, last = [], 0
    widened = 0
    header_rows = 0
    for (start, end) in spans:
        tbl = section[start:end]
        if start < body_start:
            pieces.append(section[last:end])
            last = end
            continue

        label_col = H.is_label_column_table(tbl, fill_ids)

        # 6-1. 머리행: 음영 + 세로 중간 + 가로 가운데 + 셀 줄간격
        tr_a = tbl.find("<hp:tr>")
        if tr_a < 0:
            log.append("[경고] 행을 찾지 못한 표를 건너뜀")
            pieces.append(section[last:end])
            last = end
            continue
        tr_b = tbl.find("</hp:tr>", tr_a) + len("</hp:tr>")
        prefix = tbl[:tr_a]  # <hp:tbl ...> 와 sz/pos/margin. 반드시 보존한다
        head_row = tbl[tr_a:tr_b]
        rest = tbl[tr_b:]

        if not label_col:
            if fill_id:
                head_row = re.sub(r'(<hp:tc [^>]*?)borderFillIDRef="\d+"', lambda m: m.group(1) + f'borderFillIDRef="{fill_id}"', head_row)
            head_row = re.sub(r'(<hp:subList [^>]*?)vertAlign="\w+"', lambda m: m.group(1) + 'vertAlign="CENTER"', head_row)
            head_row = re.sub(
                r'(<hp:p [^>]*?)paraPrIDRef="(\d+)"',
                lambda m: m.group(1) + f'paraPrIDRef="{pool.variant(m.group(2), H.CELL_LINE_SPACING, "CENTER")}"',
                head_row,
            )
            header_rows += 1
        else:
            head_row = re.sub(
                r'(<hp:p [^>]*?)paraPrIDRef="(\d+)"',
                lambda m: m.group(1) + f'paraPrIDRef="{pool.variant(m.group(2), H.CELL_LINE_SPACING, None)}"',
                head_row,
            )

        rest = re.sub(
            r'(<hp:p [^>]*?)paraPrIDRef="(\d+)"',
            lambda m: m.group(1) + f'paraPrIDRef="{pool.variant(m.group(2), H.CELL_LINE_SPACING, None)}"',
            rest,
        )

        tbl = prefix + head_row + rest
        tbl = fix_linesegs(tbl, H.CELL_LINE_SPACING)

        # 6-2. 열 너비
        tbl, changed = rebalance_columns(tbl, char_prs, regular, boldfont)
        if changed:
            widened += 1
            log.append(f"열 너비 재배분 {changed[0]} -> {changed[1]}")

        pieces.append(section[last:start] + tbl)
        last = end
    pieces.append(section[last:])
    section = "".join(pieces)
    log.append(f"표 머리행 서식(음영·세로중간·가로가운데) : {header_rows}개 표")
    log.append(f"표 셀 줄간격 {H.CELL_LINE_SPACING}% 적용, 열 너비 재배분 {widened}개 표")

    # 7. 본문(표 밖) 줄 배치 캐시
    spans = H.table_spans(section)
    body_start = H.body_start_offset(section)
    out, cursor = [], body_start
    out.append(section[:body_start])
    for (a, b) in spans:
        if b <= body_start:
            continue
        out.append(fix_linesegs(section[cursor:a], H.BODY_LINE_SPACING))
        out.append(section[a:b])
        cursor = b
    out.append(fix_linesegs(section[cursor:], H.BODY_LINE_SPACING))
    section = "".join(out)

    H.set_text(entries, H.HEADER, pool.finish())
    H.set_text(entries, H.SECTION, section)
    H.write_hwpx(entries, dst)
    log.append(f"저장: {dst}")
    return log


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        return 2
    src = Path(args[0])
    if not src.is_file():
        print(f"파일 없음: {src}")
        return 2

    if "--in-place" in sys.argv:
        backup = src.with_suffix(src.suffix + ".bak")
        shutil.copy2(src, backup)
        print(f"원본 백업: {backup}")
        dst = src
    elif "-o" in sys.argv:
        dst = Path(sys.argv[sys.argv.index("-o") + 1])
    else:
        dst = src.with_name(src.stem + "_fmt" + src.suffix)

    for line in apply(src, dst):
        print(line)
    print("\n적용이 끝나면 check_artifact_format.py 로 반드시 재검사할 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
