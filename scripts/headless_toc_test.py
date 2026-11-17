"""Synthetic-only regression tests for the Hancom TOC structure and body page numbers."""
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/bizplan-hwpx/scripts'))
import headless_hwpx as H
import build_headless_artifact as B
import check_headless_artifact as C
import layout_headless_artifact as L
import toc_pages_hwp as T

TABLE = '| 구분 | 설명 |\n| --- | --- |\n| 시험 | 합성 내용 |\n'
MARKDOWN = ('# 1. 합성 개요\n\n첫 본문입니다.\n\n## 1.1 목적\n\n목적 본문입니다.\n\n'
            '### 1.1.1 세부 항목\n\n세부 본문입니다.\n\n## 1.2 범위\n\n' + TABLE
            + '\n## 1.3 긴 표\n\n| 구분 | 설명 |\n| --- | --- |\n'
            + ''.join(f'| 항목 {i} | 합성 검증 자료 |\n' for i in range(65))
            + '\n# 2. 합성 결과\n\n결과 본문입니다.\n\n## 2.1 요약\n\n요약 본문입니다.\n')
COVER = dict(agency='합성 기관', program='합성 사업', project_number='SYNTHETIC',
             project='합성 과제', title='목차검증', document_type='시험')


def build(directory: Path, name: str, make_toc=True) -> Path:
    source = directory / f'{name}.md'
    source.write_text(MARKDOWN, encoding='utf-8')
    output = directory / name / 'DXS-AX-TST-목차검증-20260907-v0.1.hwpx'
    output.parent.mkdir()
    B.build(B.default_template(), source, output, COVER, make_toc, revision_date='2026-09-07')
    return output


def rewrite(source: Path, target: Path, change) -> Path:
    entries = H.read_hwpx(source)
    H.set_text(entries, H.SECTION, change(H.get_text(entries, H.SECTION)))
    target.parent.mkdir(exist_ok=True)
    H.write_hwpx(entries, target)
    return target


class TocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ax1-toc-regression-')
        cls.directory = Path(cls.temp.name)
        cls.output = build(cls.directory, 'toc')
        entries = H.read_hwpx(cls.output)
        cls.header = H.get_text(entries, H.HEADER)
        cls.section = H.get_text(entries, H.SECTION)
        cls.body_start = H.body_start_offset(cls.section)
        cls.headings = C.body_headings(cls.section, cls.header, cls.body_start)
        cls.toc = H.toc_entries(cls.section)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_generated_artifact_passes_checker(self):
        self.assertEqual(C.check(self.output), [])

    def test_toc_lists_chapters_and_sections_linked_to_heading_ids(self):
        expected = [(pid, text) for level, text, pid, _ in self.headings if level in H.TOC_LEVELS]
        self.assertEqual([(target, title) for target, title, _, _ in self.toc], expected)
        self.assertEqual([title for _, title, _, _ in self.toc],
                         ['1. 합성 개요', '1.1 목적', '1.2 범위', '1.3 긴 표', '2. 합성 결과', '2.1 요약'])
        ids = [pid for _, _, pid, _ in self.headings]
        self.assertEqual(len(ids), len(set(ids)))

    def test_toc_is_wrapped_in_hancom_toc_field_after_template_boundary(self):
        start, end = H.toc_region(self.section)
        first_heading = self.section.find(self.headings[0][3])
        self.assertTrue(self.body_start <= start < end < first_heading)
        self.assertEqual(self.section.count('type="TABLEOFCONTENTS"'), 1)
        region = self.section[start:end]
        self.assertEqual(region.count('type="HYPERLINK"'), len(self.toc))
        self.assertEqual(region.count(f'leader="{H.TOC_LEADER}" type="2"'), len(self.toc))

    def test_toc_character_sizes_and_right_dot_tab(self):
        chars = H.parse_char_prs(self.header)
        levels = {pid: level for level, _, pid, _ in self.headings}
        for target, _, _, cid in self.toc:
            self.assertEqual(chars[cid].height, H.TOC_HEIGHT[levels[target]])
            self.assertEqual(chars[cid].bold, levels[target] == 1)
        self.assertIn('type="RIGHT" leader="DOT"', self.header)

    def test_toc_pages_are_estimated_and_ordered(self):
        pages = [int(page) for _, _, page, _ in self.toc]
        self.assertEqual(pages[0], 1)
        self.assertEqual(pages, sorted(pages))
        long_table, chapter_two = pages[3], pages[4]
        self.assertGreaterEqual(chapter_two, long_table + 2)

    def test_page_number_starts_at_first_chapter_only(self):
        self.assertEqual(self.section.count('<hp:pageNum '), 1)
        self.assertNotIn('<hp:pageNum ', self.section[:self.body_start])
        first = self.headings[0][3]
        self.assertIn('pos="BOTTOM_CENTER"', first)
        self.assertIn('<hp:newNum num="1" numType="PAGE"/>', first)
        text = ''.join(re.findall(r'<hp:t>([^<]*)</hp:t>', first))
        self.assertEqual(text, '1. 합성 개요')

    def test_checker_rejects_plain_toc_and_bad_page(self):
        missing_field = rewrite(self.output, self.directory / 'nofield' / self.output.name,
                                lambda s: s.replace('type="TABLEOFCONTENTS"', 'type="UNKNOWN"'))
        self.assertTrue(any(i['rule'] == '목차' for i in C.check(missing_field)))
        target = self.toc[0][0]

        def zero_page(section):
            span = H.toc_region(section)
            region = H.TOC_ENTRY_RE.sub(lambda m: m.group(0).replace(
                f'type="2"/>{m.group(6)}</hp:t>', 'type="2"/>0</hp:t>') if m.group(2) == target else m.group(0),
                section[span[0]:span[1]])
            return section[:span[0]] + region + section[span[1]:]
        zero = rewrite(self.output, self.directory / 'zero' / self.output.name, zero_page)
        self.assertTrue(any('쪽 번호가 비었거나' in i['detail'] for i in C.check(zero)))

    def test_checker_rejects_missing_body_page_number(self):
        stripped = rewrite(self.output, self.directory / 'nopage' / self.output.name,
                           lambda s: s.replace(H.PAGE_NUM_CTRL, ''))
        self.assertTrue(any(i['rule'] == '쪽 번호' for i in C.check(stripped)))

    def test_no_toc_option_still_numbers_body(self):
        output = build(self.directory, 'notoc', make_toc=False)
        section = H.get_text(H.read_hwpx(output), H.SECTION)
        self.assertIsNone(H.toc_region(section))
        self.assertEqual(section.count('<hp:pageNum '), 1)
        self.assertEqual(C.check(output), [])

    def test_estimate_starts_at_first_heading(self):
        pages = L.estimate_pages(self.section, self.header, self.headings[0][2])
        self.assertEqual(pages[self.headings[0][2]], 1)
        self.assertEqual({pages[t] for t, _, _, _ in self.toc},
                         {int(p) for _, _, p, _ in self.toc})


class OptionalHancomToolTests(unittest.TestCase):
    """The Hancom PDF tool is optional and never executed by CI; test its pure logic only."""

    def test_heading_pages_skip_toc_page_and_keep_order(self):
        texts = ['표지', '목 차\n1. 합성 개요 ········ 1\n2. 합성 결과 ········ 2',
                 '- 1 -\n1. 합성 개요\n본문', '- 2 -\n표', '- 3 -\n2. 합성 결과']
        self.assertEqual(T.heading_pages(texts, ['1. 합성 개요', '2. 합성 결과']), [2, 4])

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'DXS-AX-TST-목차검증-20260907-v0.1.hwpx'
            path.write_bytes(b'x')
            with self.assertRaises(H.HeadlessHwpxError):
                T.correct(path, path)


if __name__ == '__main__':
    unittest.main()
