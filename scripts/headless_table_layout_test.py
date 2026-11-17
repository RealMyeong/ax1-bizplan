"""Synthetic-only regression tests for table flow, spacing and numbered lists."""
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/bizplan-hwpx/scripts'))
import headless_hwpx as H
import build_headless_artifact as B
import format_headless_artifact as A
import check_headless_artifact as C
import layout_headless_artifact as L

NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
SMALL = '| 구분 | 설명 |\n| --- | --- |\n| 시험 | 합성 내용 |\n'
LONG_TEXT = '긴 한국어 목록의 후속 줄이 첫 줄 본문 시작 위치와 일치하는지 확인합니다. ' * 5
MARKDOWN = ('# 1. 합성 시험\n\n첫 본문입니다.\n\n둘째 본문입니다.\n\n'
            '## 1.1 본문 다음 제목\n\n### 1.1.1 연속 제목\n\n'
            '- 첫 목록\n- 둘째 목록\n\n## 1.2 목록 다음 제목\n\n'
            '표 앞 본문입니다.\n\n' + SMALL + '\n표 뒤 본문입니다.\n\n'
            + SMALL + '\n## 1.3 표 다음 제목\n\n'
            + SMALL + '\n- ' + LONG_TEXT + '\n\n'
            '1. ' + LONG_TEXT + '\n10. ' + LONG_TEXT + '\n\n'
            '## 1.4 긴 표\n\n| 구분 | 설명 |\n| --- | --- |\n'
            + ''.join(f'| 항목 {i} | 합성 검증 자료 |\n' for i in range(65))
            + '\n긴 표 뒤 본문입니다.\n\n# 2. 새 페이지\n\n' + SMALL)


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ax1-table-regression-')
        cls.directory = Path(cls.temp.name)
        cls.source = cls.directory / 'synthetic.md'
        cls.source.write_text(MARKDOWN, encoding='utf-8')
        cls.output = cls.directory / 'DXS-AX-TST-표흐름검증-20260907-v0.1.hwpx'
        cls.template = B.default_template()
        cls.digest = H.sha256_file(cls.template)
        B.build(cls.template, cls.source, cls.output,
                dict(agency='합성 기관', program='합성 사업', project_number='SYNTHETIC',
                     project='합성 과제', title='표흐름검증', document_type='시험'),
                revision_date='2026-09-07')
        cls.entries = H.read_hwpx(cls.output)
        cls.header = H.get_text(cls.entries, H.HEADER)
        cls.section = H.get_text(cls.entries, H.SECTION)
        cls.props = H.parse_para_prs(cls.header)
        root = ET.fromstring(cls.section)
        cls.paras = []
        active = False
        for p in root:
            text = ''.join(p.itertext())
            if text == '1. 합성 시험' and p.get('pageBreak') == '1':
                active = True
            if active:
                cls.paras.append(p)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_short_tables_are_inline(self):
        tables = [p.find('hp:run/hp:tbl', NS) for p in self.paras]
        tables = [t for t in tables if t is not None]
        self.assertEqual(len(tables), 5)
        for table in tables:
            long = int(table.get('rowCnt')) > 50
            self.assertEqual(table.find('hp:pos', NS).get('treatAsChar'), '0' if long else '1')
            self.assertEqual(table.get('pageBreak'), 'CELL')

    def test_long_tables_repeat_every_first_row_cell_only(self):
        tables = [p.find('hp:run/hp:tbl', NS) for p in self.paras]
        long = next(t for t in tables if t is not None and int(t.get('rowCnt')) > 50)
        self.assertEqual(long.get('repeatHeader'), '1')
        for cell in long.findall('hp:tr/hp:tc', NS):
            row = cell.find('hp:cellAddr', NS).get('rowAddr')
            self.assertEqual(cell.get('header'), '1' if row == '0' else '0')

    def modify_long_table(self, section, transform):
        start, end = next((s, e) for s, e in H.table_spans(section)
                          if s >= H.body_start_offset(section)
                          and int(L.attr(section[s:e], 'rowCnt')) > 50)
        return section[:start] + transform(section[start:end]) + section[end:]

    def test_checker_rejects_missing_long_table_repeat(self):
        self.assert_corruption(lambda s: self.modify_long_table(s, lambda t:
                               L.set_attr(t, 'repeatHeader', 0)), '표 제목행 반복')

    def test_checker_rejects_missing_first_row_title_cell(self):
        self.assert_corruption(lambda s: self.modify_long_table(s, lambda t:
                               t.replace('header="1"', 'header="0"', 1)), '표 제목행 반복')

    def test_table_to_body_and_body_to_table_gap(self):
        previous = None
        for p in self.paras:
            table = p.find('hp:run/hp:tbl', NS)
            prev_table = previous.find('hp:run/hp:tbl', NS) if previous is not None else None
            if p.get('pageBreak') != '1' and previous is not None and (table is not None or prev_table is not None):
                # Floating-table boundaries are owned by the object margin;
                # inline boundaries are owned by the following paragraph.
                prev = self.props[p.get('paraPrIDRef')]['prev']
                bottom = int(prev_table.find('hp:outMargin', NS).get('bottom')) if prev_table is not None else 0
                top = int(table.find('hp:outMargin', NS).get('top')) if table is not None else 0
                self.assertEqual(prev + bottom + top, 1200, ''.join(p.itertext())[:40])
            previous = p

    def test_numbered_list_hanging_indent(self):
        count = 0
        for p in self.paras:
            text = ''.join(p.itertext())
            if not re.match(r'^(1|10)\. 긴 한국어', text):
                continue
            count += 1
            props = self.props[p.get('paraPrIDRef')]
            self.assertGreater(props['left'], 3200)
            self.assertEqual(props['left'] + props['intent'], 3200)
            segs = p.findall('hp:linesegarray/hp:lineseg', NS)
            self.assertGreater(len(segs), 1)
            self.assertEqual(int(segs[0].get('horzpos')), 3200)
            for seg in segs[1:]:
                self.assertEqual(int(seg.get('horzpos')), props['left'])
        self.assertEqual(count, 2)

    def test_readback_and_template_preserved(self):
        self.assertEqual(C.check(self.output), [])
        self.assertEqual(H.sha256_file(self.template), self.digest)
        self.assertIn(LONG_TEXT.strip(), self.section)
        self.assertNotIn('################', self.section)
        self.assertTrue(all(p.find('hp:run/hp:tbl', NS) is not None or ''.join(p.itertext()).strip() for p in self.paras))

    def assert_corruption(self, transform, rule):
        entries = H.read_hwpx(self.output)
        section = H.get_text(entries, H.SECTION)
        changed = transform(section)
        self.assertTrue(changed != section, '변형이 원본을 변경하지 않음')
        H.set_text(entries, H.SECTION, changed)
        target = self.directory / 'DXS-AX-TST-오류검증-20260907-v0.1.hwpx'
        H.write_hwpx(entries, target)
        self.assertIn(rule, [i['rule'] for i in C.check(target)])

    def modify_first_table(self, section, transform):
        start, end = next((s, e) for s, e in H.table_spans(section) if s >= H.body_start_offset(section))
        return section[:start] + transform(section[start:end]) + section[end:]

    def test_checker_rejects_floating_short_table(self):
        self.assert_corruption(lambda s: self.modify_first_table(s, lambda t: t.replace('treatAsChar="1"', 'treatAsChar="0"')), '표 배치')

    def test_checker_rejects_duplicate_gap(self):
        self.assert_corruption(lambda s: self.modify_first_table(s, lambda t: re.sub(
            r'<hp:outMargin\b[^>]*/>', lambda m: L.set_attr(m[0], 'bottom', 1200), t)), '경계 여백')

    def test_checker_rejects_stale_width(self):
        self.assert_corruption(lambda s: self.modify_first_table(s, lambda t: re.sub(
            r'<hp:cellSz\b[^>]*/>', lambda m: L.set_attr(m[0], 'width', int(L.attr(m[0], 'width')) + 1000), t, count=1)), '표 셀 줄 배치')

    def test_checker_rejects_stale_anchor_cache(self):
        def corrupt(section):
            start, end, para = next((s, e, p) for s, e, p in L.top_paragraphs(section)
                                   if s >= H.body_start_offset(section) and '<hp:tbl ' in p)
            head, tail = para.rsplit('</hp:tbl>', 1)
            tail = re.sub(r'vertsize="\d+"', 'vertsize="1000"', tail, count=1)
            return section[:start] + head + '</hp:tbl>' + tail + section[end:]
        self.assert_corruption(corrupt, '표 앵커 줄 배치')

    def test_repeat_format_is_idempotent(self):
        target = self.directory / 'DXS-AX-TST-재서식검증-20260907-v0.1.hwpx'
        A.apply(self.output, target)
        entries = H.read_hwpx(target)
        self.assertEqual(H.get_text(entries, H.SECTION), self.section)
        self.assertEqual(H.get_text(entries, H.HEADER), self.header)
        self.assertEqual(C.check(target), [])

    def test_no_extra_spacing_between_headings_or_on_explicit_new_page(self):
        for p in self.paras:
            text = ''.join(p.itertext()).strip()
            if text == '1.1.1 연속 제목' or p.get('pageBreak') == '1':
                self.assertEqual(self.props[p.get('paraPrIDRef')]['prev'], 0)

    def test_reflow_changes_cache_and_height_after_column_resize(self):
        table = next(i['table'] for i in L.layout_plan(self.section, self.header) if i['table'])
        table = table.replace('합성 내용', '긴 셀 줄바꿈 검증 문구 ' * 10)
        table = re.sub(r'<hp:cellSz\b[^>]*/>', lambda m: L.set_attr(m[0], 'width', 6000), table)
        regular, bold = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)
        after = L.reflow_table(table, H.parse_char_prs(self.header), regular, bold)
        self.assertGreater(int(L.attr(re.search(r'<hp:sz\b[^>]*/>', after)[0], 'height')),
                           int(L.attr(re.search(r'<hp:sz\b[^>]*/>', table)[0], 'height')))
        for cell in re.findall(r'<hp:tc\b.*?</hp:tc>', after, re.S):
            self.assertTrue(all(int(L.attr(s, 'horzsize')) == 4978 for s in re.findall(r'<hp:lineseg\b[^>]*/>', cell)))

    def test_tall_single_cell_stops_without_publishing(self):
        source = self.directory / 'tall-cell.md'
        source.write_text('# 1. 합성\n\n| 내용 |\n| --- |\n| ' + '가나다라마바사 ' * 600 + ' |\n', encoding='utf-8')
        target = self.directory / 'DXS-AX-TST-과대셀검증-20260907-v0.1.hwpx'
        with self.assertRaisesRegex(H.HeadlessHwpxError, '한 셀이 한 쪽'):
            B.build(self.template, source, target,
                    dict(agency='합성', program='합성', project_number='SYNTHETIC',
                         project='합성', title='합성', document_type='시험'), revision_date='2026-09-07')
        self.assertFalse(target.exists())

    def test_previous_content_does_not_make_fitting_table_float(self):
        # The mode is based on a FULL page, not the remaining height after text.
        first = next(i for i in L.layout_plan(self.section, self.header) if i['table'])
        body = next(p for _, _, p in L.top_paragraphs(self.section)
                    if '표 앞 본문입니다.' in p and '<hp:tbl ' not in p)
        sample = self.section[:first['start']] + body * 70 + self.section[first['start']:]
        table = next(i for i in L.layout_plan(sample, self.header) if i['table'])
        self.assertFalse(table['floating'])

    def test_hancom_body_height_excludes_header_and_footer(self):
        # Independent fixed arithmetic for the approved page geometry, not Word margins.
        self.assertEqual(L.page_body_height(self.section), 84186 - 5668 - 4252 - 4252 - 4252)
        first = next(i for i in L.layout_plan(self.section, self.header) if i['table'])
        # This table fits only if header/footer space is incorrectly counted as body.
        table = re.sub(r'<hp:sz\b[^>]*/>', lambda m: L.set_attr(m[0], 'height', 68000), first['table'], count=1)
        sample = self.section.replace(first['table'], table, 1)
        self.assertTrue(next(i for i in L.layout_plan(sample, self.header) if i['table'])['floating'])

    def test_example_allowlist_requires_exact_approved_bytes(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import build_release as release
        release.validate_no_private_artifacts()
        with patch.object(Path, 'read_bytes', return_value=b'unapproved replacement'):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                release.validate_no_private_artifacts()
        # Removing this one approval must restore the default document prohibition.
        with patch.object(release, 'APPROVED_HWPX_EXAMPLES', {}):
            with self.assertRaisesRegex(ValueError, 'forbidden document'):
                release.validate_no_private_artifacts()


CELL_LIST_TABLE = (
    '| 절차 ID | 요구사항 ID | 시험절차 | 합격 조건 | 증빙 / 비고 |\n'
    '| --- | --- | --- | --- | --- |\n'
    '| AB-01 | SR-AB-01.02, 01.03 | 합성 신호 발생 / 합성 이벤트 확인 | 이벤트 번호·생성시각·설비·공정 기록 / 합성 화면에 이벤트 표시 | 화면 캡처, 로그 |\n'
    '| AB-02 | SR-AB-02.01 | 1) 기준 시간 확인 2) 안내 등록 3) 수신 상태 확인 | 단일 합격 조건 문장입니다 | 합성 화면 캡처 |\n'
    '| AB-03 / AB-04 | SR-AB-03.01 | 첫 줄<br>둘째 줄 | - 줄 나눔 항목<br>- 두 번째 항목 | 로그 |\n'
)


class CellListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ax1-cell-list-')
        cls.directory = Path(cls.temp.name)
        source = cls.directory / 'cell-list.md'
        source.write_text('# 1. 칸 나열 합성\n\n본문입니다.\n\n' + CELL_LIST_TABLE, encoding='utf-8')
        cls.output = cls.directory / 'DXS-AX-TST-칸나열검증-20260907-v0.1.hwpx'
        cls.template = B.default_template()
        B.build(cls.template, source, cls.output,
                dict(agency='합성 기관', program='합성 사업', project_number='SYNTHETIC',
                     project='합성 과제', title='칸나열검증', document_type='시험'),
                revision_date='2026-09-07')
        entries = H.read_hwpx(cls.output)
        cls.header = H.get_text(entries, H.HEADER)
        cls.section = H.get_text(entries, H.SECTION)
        cls.props = H.parse_para_prs(cls.header)
        table = next(i['table'] for i in L.layout_plan(cls.section, cls.header) if i['table'])
        cls.cells = {}
        for cell in re.findall(r'<hp:tc\b.*?</hp:tc>', table, re.S):
            address = re.search(r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"/>', cell)
            paras = [p for _, _, p in L.top_paragraphs(cell)]
            cls.cells[(int(address[2]), int(address[1]))] = paras

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @staticmethod
    def text(para):
        return H.unescape(''.join(re.findall(r'<hp:t>([^<]*)</hp:t>', para)))

    def test_cell_items_split_rules(self):
        self.assertEqual(B.cell_items('A / B'), ['• A', '• B'])
        self.assertEqual(B.cell_items('1) 가 2) 나 3) 다'), ['1) 가', '2) 나', '3) 다'])
        self.assertEqual(B.cell_items('가<br>나'), ['• 가', '• 나'])
        self.assertEqual(B.cell_items('1) 가<br>2) 나'), ['1) 가', '2) 나'])
        self.assertEqual(B.cell_items('단일 문장 (1) 포함'), ['단일 문장 (1) 포함'])
        self.assertEqual(B.cell_items('2) 가 3) 나'), ['2) 가 3) 나'])  # 1부터가 아니면 나누지 않음
        self.assertEqual(B.cell_items('SR-AB-01 ~ 05'), ['SR-AB-01 ~ 05'])

    def test_slash_list_becomes_bullet_paragraphs_with_hanging_indent(self):
        paras = self.cells[(1, 3)]
        self.assertEqual([self.text(p) for p in paras],
                         ['• 이벤트 번호·생성시각·설비·공정 기록', '• 합성 화면에 이벤트 표시'])
        regular, bold = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)
        hang = L.cell_item_hang('• ', regular, bold)
        for para in paras:
            props = self.props[L.attr(para, 'paraPrIDRef')]
            self.assertEqual((props['left'], props['intent'], props['align']), (hang, -hang, 'LEFT'))

    def test_numbered_list_and_br_lines(self):
        self.assertEqual([self.text(p) for p in self.cells[(2, 2)]],
                         ['1) 기준 시간 확인', '2) 안내 등록', '3) 수신 상태 확인'])
        self.assertEqual([self.text(p) for p in self.cells[(3, 2)]], ['• 첫 줄', '• 둘째 줄'])
        self.assertEqual([self.text(p) for p in self.cells[(3, 3)]], ['• 줄 나눔 항목', '• 두 번째 항목'])

    def test_single_item_header_and_axis_cells_are_not_split(self):
        self.assertEqual([self.text(p) for p in self.cells[(2, 3)]], ['단일 합격 조건 문장입니다'])
        self.assertEqual([self.text(p) for p in self.cells[(0, 4)]], ['증빙 / 비고'])
        self.assertEqual([self.text(p) for p in self.cells[(3, 0)]], ['AB-03 / AB-04'])

    def test_short_id_column_stays_on_one_line(self):
        for row in (1, 2, 3):
            segs = re.findall(r'<hp:lineseg\b[^>]*/>', self.cells[(row, 0)][0])
            self.assertEqual(len(segs), 1)

    def test_no_line_starts_with_space(self):
        for paras in self.cells.values():
            for para in paras:
                text = self.text(para)
                for pos in re.findall(r'<hp:lineseg [^>]*textpos="(\d+)"', para)[1:]:
                    self.assertNotEqual(text[int(pos)], ' ', text)

    def test_checker_passes_and_reformat_is_idempotent(self):
        self.assertEqual(C.check(self.output), [])
        target = self.directory / 'DXS-AX-TST-칸나열재서식-20260907-v0.1.hwpx'
        A.apply(self.output, target)
        self.assertEqual(H.get_text(H.read_hwpx(target), H.SECTION), self.section)

    def test_column_widths_avoid_mid_word_breaks_when_possible(self):
        regular, bold = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)
        rows = [['번호', '내용', '비고'],
                ['1', '스마트글라스·현장 대시보드 화면 캡처', '짧은 비고'],
                ['2', '정지시간·무작업률 산출 / 종료시각 저장', '비고']]
        items = [[[c] if (r == 0 or i == 0) else B.cell_items(c) for i, c in enumerate(row)] for r, row in enumerate(rows)]
        total = 30000
        widths = B.column_widths(items, total, 1020, regular, bold)
        self.assertEqual(sum(widths), total)
        for r in range(1, 3):
            for c in range(3):
                _, forced = B.cell_layout(items[r][c], False, widths[c] - 1022, regular, bold)
                self.assertEqual(forced, 0, (r, c, widths))


if __name__ == '__main__':
    unittest.main(verbosity=2)
