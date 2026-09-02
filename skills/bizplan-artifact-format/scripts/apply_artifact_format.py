"""산출물 HWPX 에 서식 규칙을 적용한다.

    python apply_artifact_format.py <입력.hwpx> [-o 출력.hwpx] [--in-place]

글꼴·줄간격·표 서식에 더해 제목 문단 서식(위아래 간격·개요 스타일·장 쪽나눔),
목차 항목(장 굵게 + 절 들여쓰기 2단계, 본문 제목에서 재생성), 리스트 계층
(단계별 기호 ● - · · 와 내어쓰기)을 기존 문서에 소급 적용한다.
목차 항목을 재생성하면 문단 수가 원본과 달라질 수 있다. 로그에 증감을 남긴다.

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

    def margins_of(self, pid) -> dict:
        """intent(내어쓰기)/left/prev(위)/next(아래) 여백. 단위 HWPUNIT."""
        body = self.blocks.get(pid, "")
        out = {}
        for name in ("intent", "left", "prev", "next"):
            m = re.search(rf'<hc:{name} value="(-?\d+)"', body)
            out[name] = int(m.group(1)) if m else 0
        return out

    def _render(self, pid: str, spacing: int, align, margins=None) -> str:
        block = self.blocks[pid]
        block = re.sub(
            r'(<hh:lineSpacing type="PERCENT" value=")-?\d+(")',
            lambda m: m.group(1) + str(spacing) + m.group(2),
            block,
        )
        if align:
            block = re.sub(r'(<hh:align horizontal=")\w+(")', lambda m: m.group(1) + align + m.group(2), block)
        if margins:
            # 여백은 hp:switch 의 case/default 두 분기에 중복돼 있어 모두 치환한다
            for name, val in margins.items():
                if val is None:
                    continue
                block = re.sub(rf'(<hc:{name} value=")-?\d+(")', lambda m, v=val: m.group(1) + str(v) + m.group(2), block)
        return block

    def variant(self, pid: str, spacing: int, align=None, margins=None) -> str:
        """줄간격/정렬/여백이 맞는 문단모양 id 를 돌려준다.

        내용이 똑같은 문단모양이 이미 있으면 그것을 재사용한다. 매번 복제하면
        같은 파일에 두 번 적용했을 때 쓰이지 않는 문단모양이 계속 쌓인다.
        """
        key = (pid, spacing, align, tuple(sorted(margins.items())) if margins else None)
        if key in self.cache:
            return self.cache[key]

        want = self._strip_id(self._render(pid, spacing, align, margins))
        for other_id, block in self.blocks.items():
            if self._strip_id(block) == want:
                self.cache[key] = other_id
                return other_id

        new_id = str(self.next_id)
        self.next_id += 1
        block = re.sub(r'^<hh:paraPr id="\d+"', f'<hh:paraPr id="{new_id}"', self._render(pid, spacing, align, margins))
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


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ensure_body_chars(header: str, log: list):
    """맑은 고딕 10pt 보통/굵게 글자모양 id 를 확보한다. 굵게가 없으면 보통을 복제한다.

    목차 장 항목(굵게)과 절 항목(보통)을 재생성할 때 쓴다.
    """
    char_prs = H.parse_char_prs(header)
    malgun = H.malgun_font_ids(header)
    plain = bold = None
    for cid, cp in sorted(char_prs.items(), key=lambda x: int(x[0])):
        if cp.height != H.BODY_TEXT_HEIGHT or not set(cp.font_ids) <= malgun:
            continue
        if cp.bold and bold is None:
            bold = cid
        elif not cp.bold and plain is None:
            plain = cid
    if plain is None:
        log.append(f"[경고] {H.FONT_FACE} 10pt 글자모양이 없어 목차 항목을 재생성하지 못함")
        return header, None, None
    if bold is None:
        m = re.search(rf'<hh:charPr id="{plain}".*?</hh:charPr>', header, re.S)
        new_id = str(max(int(i) for i in char_prs) + 1)
        block = re.sub(r'^<hh:charPr id="\d+"', f'<hh:charPr id="{new_id}"', m.group(0))
        if "<hh:underline" in block:
            block = block.replace("<hh:underline", "<hh:bold/><hh:underline", 1)
        else:
            block = block.replace("</hh:charPr>", "<hh:bold/></hh:charPr>", 1)
        mm = re.search(r'<hh:charProperties itemCnt="(\d+)">', header)
        header = header.replace(mm.group(0), f'<hh:charProperties itemCnt="{int(mm.group(1)) + 1}">', 1)
        header = header.replace("</hh:charProperties>", block + "</hh:charProperties>", 1)
        log.append(f"{H.FONT_FACE} 10pt 굵게 글자모양 {new_id} 생성 (목차 장 항목용)")
        bold = new_id
    return header, plain, bold


def retrofit_hierarchy(section: str, pool: ParaPrPool, char_prs: dict, styles: dict,
                       body_start: int, regular: H.Font, boldfont: H.Font,
                       plain_cid, bold_cid, log: list) -> str:
    """제목·목차·리스트 계층을 기존 문서에 소급 적용한다.

    - 제목(15/12/10.5pt 굵게): 위아래 간격, 개요 스타일 태그, 장 쪽나눔
    - 목차 항목: 본문 장·절 제목에서 재생성 (장 굵게, 절 들여쓰기).
      문단 수가 원본과 달라질 수 있으므로 증감을 로그에 남긴다
    - 리스트: 단계별 기호(● - · ·)와 내어쓰기. 번호 목록도 내어쓰기 적용
    """
    width = H.text_width_of(section)
    spans = H.table_spans(section)

    paras = []  # (시작, 여는태그 끝, 속성, 본문)
    for a, attrs, body in H.paragraphs(section):
        paras.append((a, a + 7 + len(attrs), attrs, body))  # 7 = len("<hp:p ") + len(">")

    headings = []  # (paras 인덱스, 수준, 제목 글자)
    for i, (a, ta, attrs, body) in enumerate(paras):
        if a < body_start or H.in_any_span(spans, a):
            continue
        level = H.heading_level_of(body, char_prs)
        if level:
            headings.append((i, level, "".join(t for _, t in H.para_visible_runs(body, char_prs))))
    if not headings:
        log.append("[경고] 제목 문단(15/12/10.5pt 굵게)을 찾지 못해 제목·목차·리스트 계층을 건너뜀")
        return section

    first_heading_at = paras[headings[0][0]][0]
    edits = []  # (시작, 끝, 대체 문자열)

    # 1) 제목 문단
    fixed_headings = 0
    for i, level, _text in headings:
        a, ta, attrs, body = paras[i]
        pid = re.search(r'paraPrIDRef="(\d+)"', attrs).group(1)
        prev_v, next_v = H.HEADING_MARGIN[level]
        new_pid = pool.variant(pid, pool.spacing_of(pid) or H.BODY_LINE_SPACING, None,
                               margins={"left": 0, "intent": 0, "prev": prev_v, "next": next_v})
        new_attrs = re.sub(r'paraPrIDRef="\d+"', f'paraPrIDRef="{new_pid}"', attrs)
        sid = styles.get(H.HEADING_STYLE[level])
        if sid:
            new_attrs = re.sub(r'styleIDRef="\d+"', f'styleIDRef="{sid}"', new_attrs)
        if level == 1:
            new_attrs = re.sub(r'pageBreak="\d+"', 'pageBreak="1"', new_attrs)
        if new_attrs != attrs:
            edits.append((a, ta, f"<hp:p {new_attrs}>"))
            fixed_headings += 1
    log.append(f"제목 문단 서식(간격·개요 스타일·장 쪽나눔) : {fixed_headings}/{len(headings)}개 수정")

    # 2) 목차 항목 재생성 - 기존 항목이 있을 때만. --no-toc 문서는 그대로 둔다
    expected = [(lv, tx) for _, lv, tx in headings if lv <= 2]
    toc_list = [(i,) + paras[i][0:1] for i, (a, ta, attrs, body) in enumerate(paras)
                if body_start <= a < first_heading_at and not H.in_any_span(spans, a)]
    toc_idx = [i for i, _ in toc_list]
    if toc_idx and plain_cid and bold_cid and expected:
        got = []
        bad = None
        for i in toc_idx:
            a, ta, attrs, body = paras[i]
            text = "".join(t for _, t in H.para_visible_runs(body, char_prs))
            if not text.strip():
                continue
            if not re.match(r"\d", text):
                bad = text
                break
            got.append((i, text))
        if bad is not None:
            log.append(f"[경고] 목차 구간에 제목이 아닌 문단이 있어 목차를 재생성하지 않음 :: {bad[:30]}")
        else:
            regen = [tx for _, tx in got] != [tx for _, tx in expected]
            if not regen:
                for (i, _text), (lv, _tx) in zip(got, expected):
                    a, ta, attrs, body = paras[i]
                    pid = re.search(r'paraPrIDRef="(\d+)"', attrs).group(1)
                    runs = [r for r in H.para_visible_runs(body, char_prs) if r[0]]
                    is_bold = bool(runs) and all(cp.bold for cp, _ in runs)
                    left = pool.margins_of(pid)["left"]
                    if (lv == 1) != is_bold or (H.TOC_INDENT if lv == 2 else 0) != left:
                        regen = True
                        break
            if regen:
                base_pid = re.search(r'paraPrIDRef="(\d+)"', paras[toc_idx[0]][2]).group(1)
                spacing = pool.spacing_of(base_pid) or H.BODY_LINE_SPACING
                sp = round(H.BODY_TEXT_HEIGHT * (spacing - 100) / 100)
                line_h = H.BODY_TEXT_HEIGHT + sp
                out = []
                for k, (lv, text) in enumerate(expected):
                    left = 0 if lv == 1 else H.TOC_INDENT
                    cid = bold_cid if lv == 1 else plain_cid
                    new_pid = pool.variant(base_pid, spacing, None,
                                           margins={"left": left, "intent": 0, "prev": 0, "next": 0})
                    sid = styles.get(H.TOC_STYLE[lv], "0")
                    avail = width - left
                    segs = "".join(
                        f'<hp:lineseg textpos="{p}" vertpos="{j * line_h}" vertsize="{H.BODY_TEXT_HEIGHT}"'
                        f' textheight="{H.BODY_TEXT_HEIGHT}" baseline="{round(H.BODY_TEXT_HEIGHT * 0.85)}"'
                        f' spacing="{sp}" horzpos="0" horzsize="{avail}" flags="393216"/>'
                        for j, p in enumerate(H.wrap_lines(text, H.BODY_TEXT_HEIGHT, lv == 1, regular, boldfont, avail))
                    )
                    out.append(
                        f'<hp:p id="{1300000000 + k}" paraPrIDRef="{new_pid}" styleIDRef="{sid}"'
                        f' pageBreak="0" columnBreak="0" merged="0">'
                        f'<hp:run charPrIDRef="{cid}"><hp:t>{esc(text)}</hp:t></hp:run>'
                        f"<hp:linesegarray>{segs}</hp:linesegarray></hp:p>"
                    )
                n1 = sum(1 for lv, _ in expected if lv == 1)
                edits.append((paras[toc_idx[0]][0], first_heading_at, "".join(out)))
                log.append(
                    f"목차 항목 재생성: 기존 {len(got)}개 -> 장 {n1} + 절 {len(expected) - n1} = "
                    f"{len(expected)}개 (문단 수 {len(expected) - len(toc_idx):+d})"
                )
            else:
                log.append(f"목차 항목 {len(got)}개 규칙 충족 (재생성 없음)")
    elif not toc_idx:
        log.append("목차 항목이 없는 문서 (--no-toc). 목차는 만들지 않음")

    # 3) 리스트 - 불릿 기호와 내어쓰기
    fixed_bullets = fixed_ordered = 0
    for i, (a, ta, attrs, body) in enumerate(paras):
        if a < first_heading_at or H.in_any_span(spans, a):
            continue
        runs = [r for r in H.para_visible_runs(body, char_prs) if r[0]]
        if not runs:
            continue
        cp0 = runs[0][0]
        if cp0.height != H.BODY_TEXT_HEIGHT or cp0.bold:
            continue
        text = "".join(t for _, t in runs)
        m_b = H.BULLET_MARKER_RE.match(text)
        m_o = None if m_b else H.ORDERED_MARKER_RE.match(text)
        if not m_b and not m_o:
            continue
        pid = re.search(r'paraPrIDRef="(\d+)"', attrs).group(1)
        margins = pool.margins_of(pid)
        old_marker = text.split(" ", 1)[0]
        if m_b:
            if margins["intent"] < 0:
                level = H.list_level_of(margins)
                if old_marker == H.BULLETS[level]:
                    continue  # 이미 규칙 충족
            else:
                # 옛 방식: 왼쪽여백 = 단계*1000, 기호는 · 고정
                level = max(1, min(4, margins["left"] // H.LIST_INDENT_STEP or 1))
            marker = H.BULLETS[level]
        else:
            if margins["intent"] < 0:
                continue  # 이미 규칙 충족
            level = 1  # 옛 문서의 번호 목록은 들여쓰기 정보가 없어 1수준으로 본다
            marker = old_marker
        hang = H.marker_hang(marker, regular, boldfont)
        left = (level - 1) * H.LIST_INDENT_STEP + hang
        new_pid = pool.variant(pid, pool.spacing_of(pid) or H.BODY_LINE_SPACING, None,
                               margins={"left": left, "intent": -hang, "prev": 0, "next": 0})
        new_attrs = re.sub(r'paraPrIDRef="\d+"', f'paraPrIDRef="{new_pid}"', attrs)
        close = body.find("</hp:p>")
        if close < 0:
            continue
        para_xml = f"<hp:p {new_attrs}>" + body[: close + 7]
        if marker != old_marker:
            replaced = para_xml.replace(f"<hp:t>{old_marker} ", f"<hp:t>{marker} ", 1)
            if replaced == para_xml:
                log.append(f"[경고] 불릿 기호를 바꾸지 못한 문단 :: {text[:30]}")
                continue
            para_xml = replaced
        para_xml = H.relayout_paragraph(para_xml, char_prs, regular, boldfont, horzsize=width - left)
        edits.append((a, ta + close + 7, para_xml))
        if m_b:
            fixed_bullets += 1
        else:
            fixed_ordered += 1
    log.append(f"리스트 내어쓰기 적용: 불릿 {fixed_bullets}개, 번호 {fixed_ordered}개")

    for a, b, repl in sorted(edits, key=lambda e: e[0], reverse=True):
        section = section[:a] + repl + section[b:]
    return section


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

    header, plain_cid, bold_cid = ensure_body_chars(header, log)
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

    # 5-1. 제목·목차·리스트 계층
    styles = H.style_ids_by_name(header)
    section = retrofit_hierarchy(section, pool, char_prs, styles, body_start,
                                 regular, boldfont, plain_cid, bold_cid, log)
    spans = H.table_spans(section)  # 목차 재생성으로 오프셋이 밀렸을 수 있다
    body_start = H.body_start_offset(section)

    # 6. 표 - 글자처럼 취급 / 머리행 서식 / 셀 줄간격 / 열 너비
    pieces, last = [], 0
    widened = 0
    header_rows = 0
    treat_fixed = 0
    for (start, end) in spans:
        tbl = section[start:end]
        if start < body_start:
            pieces.append(section[last:end])
            last = end
            continue

        label_col = H.is_label_column_table(tbl, fill_ids)

        # 6-0. 글자처럼 취급 On. 첫 hp:pos 가 표 자신의 것이다
        fixed = re.sub(r'(<hp:pos treatAsChar=")0(")', r"\g<1>1\g<2>", tbl, count=1)
        if fixed != tbl:
            tbl = fixed
            treat_fixed += 1

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
    log.append(f"표 글자처럼 취급 On : {treat_fixed}개 표 수정")

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
