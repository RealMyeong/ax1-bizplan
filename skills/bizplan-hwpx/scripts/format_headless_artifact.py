"""AX1 경량 생성기가 만든 HWPX 본문에 확정 서식을 적용한다.

일반 문서를 임의로 고치는 공개 편집기가 아니다. 승인 템플릿에서 생성된 임시
산출물에만 build_headless_artifact.py가 내부적으로 호출한다. 표지~목차 제목은
건드리지 않고, 본문과 본문 표에만 160% 규칙을 적용한다. 생성기가 부여한 제목
윗간격과 목록 hanging indent 및 가로 lineseg 위치는 그대로 보존한다.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True

import headless_hwpx as H  # noqa: E402


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
    """줄 배치 캐시의 세로 줄간격만 맞추고 가로 hanging indent는 보존한다."""
    factor = (percent - 100) / 100

    def fix(m):
        want = round(int(m.group(2)) * factor)
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{want}{m.group(5)}"

    return re.sub(r'(<hp:lineseg [^>]*?vertsize=")(\d+)("[^>]*?spacing=")(-?\d+)(")', fix, xml)


def _assert_body_fonts(section: str, body_start: int, header: str) -> None:
    """경량 생성 본문이 이미 맑은 고딕 글자모양만 참조하는지 확인한다.

    전역 charPr을 고치면 표지 글꼴까지 바뀌므로, 맞지 않는 문서는 자동 교정하지
    않고 upstream HWPX 경로로 돌려보낸다.
    """
    char_prs = H.parse_char_prs(header)
    malgun_ids = H.malgun_font_ids(header)
    if not malgun_ids:
        raise H.HeadlessHwpxError(f"템플릿에 {H.FONT_FACE} 글꼴 정의가 없음")
    bad = set()
    for match in re.finditer(r'<hp:run charPrIDRef="(\d+)">', section[body_start:]):
        char_pr = char_prs.get(match.group(1))
        if char_pr and any(font_id not in malgun_ids for font_id in char_pr.font_ids):
            bad.add(match.group(1))
    if bad:
        raise H.HeadlessHwpxError(
            "본문에 맑은 고딕이 아닌 글자모양이 있어 경량 모드를 중단함: "
            + ", ".join(sorted(bad, key=int))
        )


def apply(src: Path, dst: Path) -> list:
    log = []
    entries = H.read_hwpx(src)
    header = H.get_text(entries, H.HEADER)
    section = H.get_text(entries, H.SECTION)

    # 경계 판정은 어떤 변경보다 먼저 한다. 경계를 찾지 못한 문서는 결과를 쓰지 않는다.
    body_start = H.body_start_offset(section)
    if body_start is None:
        raise H.HeadlessHwpxError("목차 문단을 찾지 못해 경량 서식 적용을 중단함")
    log.append(f"불가침 구간: 문서 시작 ~ 오프셋 {body_start} (표지·문서정보·개정이력·목차) 는 양식 그대로 둠")

    regular = H.Font(H.MALGUN)
    boldfont = H.Font(H.MALGUN_BOLD)
    _assert_body_fonts(section, body_start, header)

    # 4. 본문 표 머리행 배경색 - 표지가 쓰는 정의는 건드리지 않는다
    front_fills = H.front_matter_fill_ids(section, body_start)
    header, fill_id = ensure_header_fill(header, front_fills, log)
    fill_ids = H.shaded_fill_ids(header)  # 라벨열 판정은 색을 가리지 않는다

    char_prs = H.parse_char_prs(header)
    spans = H.table_spans(section)
    pool = ParaPrPool(header)

    # 본문 문단은 기존 전역 paraPr을 수정하지 않고 160% 변형을 본문에만 연결한다.
    body_para_ids = set()

    def format_body_segment(segment: str) -> str:
        def replace_para(match):
            body_para_ids.add(match.group(2))
            return match.group(1) + f'paraPrIDRef="{pool.variant(match.group(2), H.BODY_LINE_SPACING, None)}"'

        segment = re.sub(r'(<hp:p [^>]*?)paraPrIDRef="(\d+)"', replace_para, segment)
        return fix_linesegs(segment, H.BODY_LINE_SPACING)

    # 표 - 머리행 서식 / 셀 줄간격 160% / 열 너비
    pieces, last = [], 0
    widened = 0
    header_rows = 0
    for (start, end) in spans:
        tbl = section[start:end]
        if start < body_start:
            pieces.append(section[last:end])
            last = end
            continue

        pieces.append(format_body_segment(section[last:start]))

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

        pieces.append(tbl)
        last = end
    pieces.append(format_body_segment(section[last:]))
    section = "".join(pieces)
    log.append(f"본문 문단 줄간격 {H.BODY_LINE_SPACING}% : 문단모양 {len(body_para_ids)}개")
    log.append(f"표 머리행 서식(음영·세로중간·가로가운데) : {header_rows}개 표")
    log.append(f"표 셀 줄간격 {H.CELL_LINE_SPACING}% 적용, 열 너비 재배분 {widened}개 표")

    H.set_text(entries, H.HEADER, pool.finish())
    H.set_text(entries, H.SECTION, section)
    H.write_hwpx(entries, dst)
    log.append(f"저장: {dst}")
    return log


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args or "--generated-by-ax1" not in sys.argv:
        print(__doc__)
        print("\n직접 실행하려면 승인된 생성물임을 나타내는 --generated-by-ax1이 필요함")
        return 2
    src = Path(args[0])
    if not src.is_file():
        print(f"파일 없음: {src}")
        return 2

    if "-o" in sys.argv:
        dst = Path(sys.argv[sys.argv.index("-o") + 1])
    else:
        dst = src.with_name(src.stem + "_fmt" + src.suffix)

    if src.resolve() == dst.resolve():
        print("원본과 출력 경로는 달라야 함")
        return 2

    try:
        for line in apply(src, dst):
            print(line)
    except H.HeadlessHwpxError as exc:
        print(f"[중단] {exc}")
        return 2
    print("\n적용이 끝나면 check_headless_artifact.py 로 반드시 재검사할 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
