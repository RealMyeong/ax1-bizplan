"""Approved-generator-only table flow and boundary layout; no GUI/COM dependencies.

Cell widths must be final BEFORE reflow. Paragraph styles are cloned by the caller;
front matter is never rewritten. Height is a font-metric estimate, not a Hancom
page count. A fitting inline table moves intact when remaining page space is small.
"""
from __future__ import annotations

import math
import re
import headless_hwpx as H


def attr(xml: str, name: str, default='') -> str:
    m = re.search(rf'\b{re.escape(name)}="([^"]*)"', xml.split('>', 1)[0])
    return m.group(1) if m else default


def set_attr(xml: str, name: str, value) -> str:
    return re.sub(rf'(\b{re.escape(name)}=")[^"]*(")',
                  lambda m: m[1] + str(value) + m[2], xml, count=1)


def top_paragraphs(section: str):
    """Balanced full top-level paragraphs, including the table anchor's own cache."""
    depth, start = 0, None
    for m in re.finditer(r'<hp:p\b[^>]*>|</hp:p>', section):
        if m[0].startswith('</'):
            depth -= 1
            if depth == 0 and start is not None:
                yield start, m.end(), section[start:m.end()]
        elif not m[0].endswith('/>'):
            if depth == 0:
                start = m.start()
            depth += 1
    if depth:
        raise H.HeadlessHwpxError('본문 문단의 XML 중첩이 올바르지 않음')


def page_body_height(section: str) -> int:
    page = re.search(r'<hp:pagePr\b.*?</hp:pagePr>', section, re.S)
    margin = re.search(r'<hp:margin\b[^>]*/>', page[0] if page else '')
    if not page or not margin:
        raise H.HeadlessHwpxError('표 배치용 쪽 높이·위아래 여백을 읽을 수 없음')
    # Hancom reserves header/footer margins separately from top/bottom margins.
    # See references/08 and Hancom's grid origin definition; do not use Word's model.
    height = int(attr(page[0], 'height')) - sum(
        int(attr(margin[0], name, '0')) for name in ('top', 'bottom', 'header', 'footer'))
    if height <= 0:
        raise H.HeadlessHwpxError('쪽의 본문 높이가 0 이하임')
    return height


def list_margins(prefix: str, regular: H.Font, boldfont: H.Font):
    if prefix == '• ':
        return H.BODY_LIST_LEFT_INDENT, H.BODY_LIST_FIRST_LINE_INDENT
    width, _ = H.text_width(prefix, H.BODY_TEXT_HEIGHT, False, regular, boldfont)
    width = math.ceil(width)
    return H.BODY_LIST_BULLET_POSITION + width, -width


def line_cache(starts, height: int, width: int, spacing: int) -> str:
    return '<hp:linesegarray>' + ''.join(
        f'<hp:lineseg textpos="{pos}" vertpos="{i * (height + spacing)}"'
        f' vertsize="{height}" textheight="{height}" baseline="{round(height * .85)}"'
        f' spacing="{spacing}" horzpos="0" horzsize="{width}" flags="393216"/>'
        for i, pos in enumerate(starts)) + '</hp:linesegarray>'


def reflow_table(tbl: str, char_prs: dict, regular: H.Font, boldfont: H.Font) -> str:
    """Rewrap generated, unmerged cells after width allocation; recompute row/table heights."""
    row_heights = []

    def reflow_row(match):
        row = match[0]
        cells = []
        for cm in re.finditer(r'<hp:tc\b.*?</hp:tc>', row, re.S):
            cell = cm[0]
            span = re.search(r'<hp:cellSpan\b[^>]*/>', cell)[0]
            if attr(span, 'colSpan') != '1' or attr(span, 'rowSpan') != '1':
                raise H.HeadlessHwpxError('경량 표 재배치는 병합 셀을 지원하지 않음; upstream 경로 필요')
            size = re.search(r'<hp:cellSz\b[^>]*/>', cell)[0]
            margin = re.search(r'<hp:cellMargin\b[^>]*/>', cell)[0]
            width = int(attr(size, 'width')) - int(attr(margin, 'left')) - int(attr(margin, 'right')) - 2
            if width <= 0:
                raise H.HeadlessHwpxError('표 셀의 본문 폭이 0 이하임')
            paras = list(top_paragraphs(cell))
            if len(paras) != 1:
                raise H.HeadlessHwpxError('경량 표는 셀당 단일 문단만 재배치함; upstream 경로 필요')
            start, end, para = paras[0]
            text, widths = H.paragraph_runs(para, char_prs, regular, boldfont)
            starts = H.wrap_widths(text, widths, width)
            height = H.BODY_TEXT_HEIGHT
            spacing = round(height * (H.CELL_LINE_SPACING - 100) / 100)
            cache = line_cache(starts, height, width, spacing)
            para = re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>', '', para, flags=re.S)
            para = para.replace('</hp:p>', cache + '</hp:p>')
            cell = cell[:start] + para + cell[end:]
            need = len(starts) * (height + spacing) + int(attr(margin, 'top')) + int(attr(margin, 'bottom'))
            cells.append((cm.start(), cm.end(), cell, need))
        if not cells:
            raise H.HeadlessHwpxError('본문 표에 셀이 없는 행이 있음')
        row_h = max(c[3] for c in cells)
        row_heights.append(row_h)
        for start, end, cell, _ in reversed(cells):
            cell = re.sub(r'<hp:cellSz\b[^>]*/>', lambda m: set_attr(m[0], 'height', row_h), cell)
            row = row[:start] + cell + row[end:]
        return row

    tbl = re.sub(r'<hp:tr\b[^>]*>.*?</hp:tr>', reflow_row, tbl, flags=re.S)
    return re.sub(r'<hp:sz\b[^>]*/>', lambda m: set_attr(m[0], 'height', sum(row_heights)), tbl, count=1)


def describe(para: str, heading_styles: dict):
    if '<hp:tbl ' in para:
        return 'table', None
    level = next((i for i in (1, 2, 3) if attr(para, 'styleIDRef') == heading_styles.get(f'개요 {i}')), None)
    if level:
        return 'heading', level
    text = H.unescape(''.join(re.findall(r'<hp:t>([^<]*)</hp:t>', para)))
    return ('list' if re.match(r'^(?:• |\d+\.\s)', text.lstrip()) else 'body'), None


def layout_plan(section: str, header: str):
    boundary = H.body_start_offset(section)
    if boundary is None:
        raise H.HeadlessHwpxError('본문 경계 누락')
    height = page_body_height(section)
    styles = H.style_ids_by_name(header)
    plan = []
    for start, end, para in top_paragraphs(section):
        if start < boundary:
            continue
        kind, level = describe(para, styles)
        table = re.search(r'<hp:tbl\b.*?</hp:tbl>', para, re.S)
        size = re.search(r'<hp:sz\b[^>]*/>', table[0]) if table else None
        table_h = int(attr(size[0], 'height')) if size else 0
        plan.append(dict(start=start, end=end, xml=para, kind=kind, level=level,
                         table=table[0] if table else None, height=table_h,
                         floating=table_h > height, prev=0, top=0, bottom=0))
    for i, item in enumerate(plan):
        if not i or attr(item['xml'], 'pageBreak') == '1':
            continue
        previous = plan[i - 1]
        table_edge = item['kind'] == 'table' or previous['kind'] == 'table'
        heading_edge = item['level'] in {2, 3} and previous['kind'] in {'body', 'list', 'table'}
        gap = H.TABLE_BOUNDARY_SPACING if table_edge else H.HEADING_TOP_SPACING if heading_edge else 0
        # Exactly one owner per edge. Floating objects use external margins,
        # as paragraph spacing alone does not reliably reserve their wrap area.
        if previous['floating']:
            previous['bottom'] = gap
        elif item['floating']:
            item['top'] = gap
        else:
            item['prev'] = gap
    return plan


def normalize(section: str, header: str, pool, text_width: int) -> str:
    plan = layout_plan(section, header)
    page_height = page_body_height(section)
    for item in reversed(plan):
        para = item['xml']
        pid = pool.variant(attr(para, 'paraPrIDRef'), H.BODY_LINE_SPACING,
                           prev=item['prev'], next_spacing=0)
        para = set_attr(para, 'paraPrIDRef', pid)
        if item['table']:
            table = item['table']
            for row in re.findall(r'<hp:tr\b[^>]*>.*?</hp:tr>', table, re.S):
                if any(int(h) > page_height for h in re.findall(r'<hp:cellSz\b[^>]*height="(\d+)"', row)):
                    raise H.HeadlessHwpxError('한 셀이 한 쪽 본문 높이를 초과함; 셀 단위 나눔으로 해결 불가. 내용을 분리해야 함')
            table = set_attr(table, 'pageBreak', 'CELL')
            table = re.sub(r'<hp:pos\b[^>]*/>', lambda m: set_attr(set_attr(m[0], 'treatAsChar',
                              0 if item['floating'] else 1), 'affectLSpacing', 0), table, count=1)
            table = re.sub(r'<hp:outMargin\b[^>]*/>', lambda m: set_attr(set_attr(m[0],
                              'top', item['top']), 'bottom', item['bottom']), table, count=1)
            para = para.replace(item['table'], table, 1)
            # Replace only the anchor cache AFTER </hp:tbl>; never a cell cache.
            head, tail = para.rsplit('</hp:tbl>', 1)
            tail = re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>', '', tail, flags=re.S)
            cache_h = H.BODY_TEXT_HEIGHT if item['floating'] else item['height']
            spacing = round(H.BODY_TEXT_HEIGHT * (H.BODY_LINE_SPACING - 100) / 100)
            tail = tail.replace('</hp:p>', line_cache([0], cache_h, text_width, spacing) + '</hp:p>')
            para = head + '</hp:tbl>' + tail
        section = section[:item['start']] + para + section[item['end']:]
    return section


def check_layout(section: str, header: str):
    """Independent readback of table mode, boundary owner and anchor cache."""
    issues = []
    props = H.parse_para_prs(header)
    page_height = page_body_height(section)
    for item in layout_plan(section, header):
        para = item['xml']
        p = props.get(attr(para, 'paraPrIDRef'), {})
        if p.get('prev') != item['prev'] or p.get('next') != 0:
            issues.append(('경계 여백', f"{item['kind']} 문단 prev/next={p.get('prev')}/{p.get('next')}; 규칙 {item['prev']}/0"))
        if not item['table']:
            continue
        table = item['table']
        pos = re.search(r'<hp:pos\b[^>]*/>', table)[0]
        expected = '0' if item['floating'] else '1'
        if attr(pos, 'treatAsChar') != expected or attr(table, 'pageBreak') != 'CELL':
            issues.append(('표 배치', f"높이 {item['height']} 표는 treatAsChar={expected}, pageBreak=CELL이어야 함"))
        if any(attr(pos, key) != value for key, value in {
            'affectLSpacing': '0', 'flowWithText': '1', 'allowOverlap': '0',
            'vertRelTo': 'PARA', 'horzRelTo': 'COLUMN', 'vertOffset': '0', 'horzOffset': '0',
        }.items()):
            issues.append(('표 배치', '표의 문단 기준 배치·겹침 방지 속성이 경량 기본값과 다름'))
        if p.get('left') != 0 or p.get('intent') != 0:
            issues.append(('표 배치', '표 앵커에 본문 목록 들여쓰기가 중복됨'))
        margin = re.search(r'<hp:outMargin\b[^>]*/>', table)[0]
        if int(attr(margin, 'top')) != item['top'] or int(attr(margin, 'bottom')) != item['bottom']:
            issues.append(('경계 여백', '표 바깥 위아래 여백이 경계 소유 규칙과 다름'))
        cache = para.rsplit('</hp:tbl>', 1)[1]
        seg = re.search(r'<hp:lineseg\b[^>]*/>', cache)
        h = H.BODY_TEXT_HEIGHT if item['floating'] else item['height']
        spacing = round(H.BODY_TEXT_HEIGHT * (H.BODY_LINE_SPACING - 100) / 100)
        if not seg or int(attr(seg[0], 'vertsize')) != h or int(attr(seg[0], 'spacing')) != spacing:
            issues.append(('표 앵커 줄 배치', '표 높이와 앵커 lineseg가 불일치함 (줄간격을 표 높이의 60%로 계산하면 안 됨)'))
        row_heights = []
        for row in re.findall(r'<hp:tr\b[^>]*>.*?</hp:tr>', table, re.S):
            heights, required = [], []
            for cell in re.findall(r'<hp:tc\b.*?</hp:tc>', row, re.S):
                size = re.search(r'<hp:cellSz\b[^>]*/>', cell)[0]
                margin = re.search(r'<hp:cellMargin\b[^>]*/>', cell)[0]
                heights.append(int(attr(size, 'height')))
                width = int(attr(size, 'width')) - int(attr(margin, 'left')) - int(attr(margin, 'right')) - 2
                segs = re.findall(r'<hp:lineseg\b[^>]*/>', cell)
                if not segs or any(int(attr(s, 'horzsize')) != width for s in segs):
                    issues.append(('표 셀 줄 배치', '최종 셀 폭과 lineseg 줄 폭이 일치하지 않음'))
                required.append(len(segs) * (H.BODY_TEXT_HEIGHT + spacing)
                                + int(attr(margin, 'top')) + int(attr(margin, 'bottom')))
            if heights:
                row_height = max(heights)
                row_heights.append(row_height)
                if len(set(heights)) != 1 or row_height != max(required):
                    issues.append(('표 행 높이', '최종 셀 줄 수와 행 높이가 일치하지 않음'))
                if row_height > page_height:
                    issues.append(('표 행 높이', '한 셀이 한 쪽 높이를 초과해 셀 단위 나눔으로 해결할 수 없음'))
        if sum(row_heights) != item['height']:
            issues.append(('표 행 높이', '행 높이 합과 표 전체 높이가 일치하지 않음'))
    return issues
