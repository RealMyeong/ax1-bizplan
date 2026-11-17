"""Synthetic-only regression tests for the explicit page-break marker (<!-- 쪽나눔 -->)."""
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/bizplan-hwpx/scripts'))
import headless_hwpx as H
import build_headless_artifact as B
import check_headless_artifact as C
import layout_headless_artifact as L

TABLE = '| 구분 | 설명 |\n| --- | --- |\n| 시험 | 합성 내용 |\n'
MARKDOWN = (
    '# 1. 쪽 나눔 시험\n\n'
    '## 1.1 첫 절\n\n첫 절 본문입니다.\n\n'
    '<!-- 쪽나눔 -->\n\n'
    '## 1.2 새 쪽 절\n\n새 쪽 절 본문입니다.\n\n'
    '표 앞 본문입니다.\n\n'
    '<!--쪽 나눔-->\n'
    + TABLE +
    '\n표 뒤 본문입니다.\n\n'
    '<!-- 쪽나눔 -->\n\n'
    '새 쪽 문단입니다.\n\n'
    '<!-- 쪽나눔 -->\n\n'
    '<!-- 쪽나눔 -->\n\n'
    '- 연속 표시 뒤 목록\n\n'
    '<!-- 쪽나눔 -->\n\n'
    '# 2. 이미 새 쪽인 장\n\n장 본문입니다.\n\n'
    '<!-- 쪽나눔 -->\n'
)
COVER = dict(agency='합성 기관', program='합성 사업', project_number='SYNTHETIC',
             project='합성 과제', title='쪽나눔검증', document_type='시험')


def text_of(p) -> str:
    return ''.join(p.itertext()).strip()


class PageBreakMarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ax1-page-break-')
        directory = Path(cls.temp.name)
        source = directory / 'synthetic.md'
        source.write_text(MARKDOWN, encoding='utf-8')
        cls.output = directory / 'DXS-AX-TST-쪽나눔검증-20260907-v0.1.hwpx'
        B.build(B.default_template(), source, cls.output, COVER, revision_date='2026-09-07')
        entries = H.read_hwpx(cls.output)
        cls.header = H.get_text(entries, H.HEADER)
        cls.section = H.get_text(entries, H.SECTION)
        cls.props = H.parse_para_prs(cls.header)
        cls.paras, active = [], False
        for p in ET.fromstring(cls.section):
            if text_of(p) == '1. 쪽 나눔 시험' and p.get('pageBreak') == '1':
                active = True
            if active:
                cls.paras.append(p)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def para(self, needle: str):
        return next(p for p in self.paras if needle in text_of(p))

    def table_anchor(self):
        return next(p for p in self.paras if p.find('.//{*}tbl') is not None)

    def test_marker_is_parsed_as_block_and_not_emitted_as_text(self):
        blocks = B.parse_markdown(MARKDOWN)
        self.assertEqual(sum(1 for b in blocks if b[0] == 'pb'), 5)  # 연속 표시는 하나, 끝 표시는 버림
        self.assertNotEqual(blocks[-1][0], 'pb')
        self.assertNotIn('&lt;!--', self.section)

    def test_next_heading_paragraph_and_list_start_new_page(self):
        for needle in ('1.2 새 쪽 절', '새 쪽 문단입니다.', '• 연속 표시 뒤 목록'):
            p = self.para(needle)
            self.assertEqual(p.get('pageBreak'), '1', needle)
            self.assertEqual(self.props[p.get('paraPrIDRef')]['prev'], 0, needle)

    def test_table_anchor_starts_new_page_without_boundary_gap(self):
        anchor = self.table_anchor()
        self.assertEqual(anchor.get('pageBreak'), '1')
        self.assertEqual(self.props[anchor.get('paraPrIDRef')]['prev'], 0)
        # The table that follows text still keeps its normal 12pt edge after it.
        after = self.para('표 뒤 본문입니다.')
        self.assertEqual(after.get('pageBreak'), '0')
        self.assertEqual(self.props[after.get('paraPrIDRef')]['prev'], H.TABLE_BOUNDARY_SPACING)

    def test_other_paragraphs_do_not_gain_page_breaks(self):
        breaks = ['[표]' if p.find('.//{*}tbl') is not None else text_of(p)
                  for p in self.paras if p.get('pageBreak') == '1']
        self.assertEqual(breaks, ['1. 쪽 나눔 시험', '1.2 새 쪽 절', '[표]', '새 쪽 문단입니다.',
                                  '• 연속 표시 뒤 목록', '2. 이미 새 쪽인 장'])
        self.assertEqual(self.props[self.para('표 앞 본문입니다.').get('paraPrIDRef')]['prev'], 0)

    def test_checker_and_layout_accept_marker_output(self):
        self.assertEqual(C.check(self.output), [])
        self.assertEqual(L.check_layout(self.section, self.header), [])

    def test_inline_comment_text_is_not_a_marker(self):
        blocks = B.parse_markdown('# 1. 합성\n\n본문 <!-- 쪽나눔 --> 안의 표시는 글자입니다.\n')
        self.assertFalse(any(b[0] == 'pb' for b in blocks))


if __name__ == '__main__':
    unittest.main()
