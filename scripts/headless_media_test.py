"""Synthetic-only picture/caption integration and failure-boundary tests."""
from pathlib import Path
import base64
import re
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/bizplan-hwpx/scripts'))
import headless_hwpx as H
import artifact_media as P
import build_headless_artifact as B
import format_headless_artifact as A
import check_headless_artifact as C
import layout_headless_artifact as L

NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
      'hc': 'http://www.hancom.co.kr/hwpml/2011/core'}
COVER = dict(agency='합성 기관', program='합성 사업', project_number='SYNTHETIC',
             project='합성 과제', title='그림캡션검증', document_type='시험')


def synthetic_png():
    def chunk(tag, body):
        return struct.pack('>I', len(body)) + tag + body + struct.pack('>I', zlib.crc32(tag + body) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\x00\x80\xff\x80\x00\xff')) + chunk(b'IEND', b''))


# Self-created two-pixel image, not a customer file or approval template.
JPEG = base64.b64decode(
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/'
    '2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAIDASIAAhEBAxEB/'
    '8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/'
    '8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/'
    '9oADAMBAAIRAxEAPwDHooor9MPz0//Z')


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ax1-media-')
        self.directory = Path(self.temp.name)
        (self.directory / '합성 그림.png').write_bytes(synthetic_png())
        (self.directory / '합성 그림.jpg').write_bytes(JPEG)
        self.template = B.default_template()
        self.digest = H.sha256_file(self.template)

    def tearDown(self):
        self.assertEqual(H.sha256_file(self.template), self.digest)
        self.temp.cleanup()

    def build(self, text, version='v0.1', **kwargs):
        source = self.directory / 'synthetic.md'
        source.write_text(text, encoding='utf-8')
        target = self.directory / f'DXS-AX-TST-그림캡션검증-20261001-{version}.hwpx'
        B.build(self.template, source, target, COVER, artifact_version=version,
                revision_date='2026-10-01', **kwargs)
        return target

    def sample(self):
        return self.build('# 1. 합성 문서\n\n☐ 미선택 ☑ 선택 ☒ 취소 ✓ 확인 ✔ 완료\n\n'
                          '[표 1-1] 합성 표\n\n| 구분 | 설명 |\n| --- | --- |\n| 시험 | 합성 자료 |\n\n'
                          '![ [그림 1-1] 합성 첫 그림 ](<합성 그림.png>)\n\n'
                          '[[그림: 합성 그림.jpg | 80mm | [그림 1-2] 합성 둘째 그림]]\n\n'
                          '## 1.1 확인\n\n[그림 1-1]과 [그림 1-2]를 확인합니다.\n')

    def assert_rejected(self, text, reason):
        with self.assertRaisesRegex(H.HeadlessHwpxError, reason):
            self.build(text)
        self.assertFalse(list(self.directory.glob('*.hwpx')))
        self.assertFalse(list(self.directory.glob('.ax1-headless-build-*')))

    def test_two_picture_forms_embed_png_jpeg_and_readback(self):
        target = self.sample()
        entries = H.read_hwpx(target)
        section = H.get_text(entries, H.SECTION)
        self.assertEqual(C.check(target), [])
        pics = [pic for pic in ET.fromstring(section).findall('hp:p/hp:run/hp:pic', NS)
                if pic.find('hc:img', NS).get('binaryItemIDRef', '').startswith('ax1image')]
        self.assertEqual(len(pics), 2)
        self.assertEqual([e.data for e in entries if e.name.startswith('BinData/ax1image')],
                         [synthetic_png(), JPEG])
        for symbol in ('☐', '☑', '☒', '✓', '✔'):
            self.assertIn(symbol, section)

    def test_captions_below_objects_and_team_spacing(self):
        entries = H.read_hwpx(self.sample())
        section, header = H.get_text(entries, H.SECTION), H.get_text(entries, H.HEADER)
        props = H.parse_para_prs(header)
        plan = L.layout_plan(section, header)
        captions = [i for i in range(len(plan)) if plan[i]['kind'] == 'caption']
        self.assertEqual(len(captions), 3)
        for i in captions:
            previous = plan[i - 1]
            self.assertIn(previous['kind'], ('table', 'picture'))
            paragraph = plan[i]['xml']
            self.assertEqual(props[L.attr(paragraph, 'paraPrIDRef')]['align'], 'CENTER')
            self.assertEqual(plan[i]['prev'], 1200 if previous['kind'] == 'table' else 300)
        heading = next(item for item in plan if item['level'] == 2)
        self.assertEqual(heading['prev'], 1200)
        self.assertFalse(any(not H.unescape(''.join(re.findall(r'<hp:t>([^<]*)</hp:t>', i['xml']))).strip()
                             and i['kind'] not in ('table', 'picture') for i in plan))

    def test_reformat_preserves_picture_bytes_and_front_matter(self):
        source = self.sample()
        target = self.directory / 'DXS-AX-TST-재서식-20261001-v0.1.hwpx'
        A.apply(source, target)
        before, after = H.read_hwpx(source), H.read_hwpx(target)
        self.assertEqual([(e.name, e.data) for e in before], [(e.name, e.data) for e in after])
        self.assertEqual(C.check(target), [])

    def test_regeneration_keeps_prior_history_with_pictures(self):
        source = self.sample()
        old_digest = H.sha256_file(source)
        target = self.build('# 1. 개정 문서\n\n[[그림: 합성 그림.png | 80mm | [그림 1-1] 개정 그림]]',
                            version='v0.2', previous_artifact=source, previous_sha256=old_digest,
                            revision_note='그림 보완')
        section = H.get_text(H.read_hwpx(target), H.SECTION)
        a, b = H.revision_table_spans(section, H.body_start_offset(section))[0]
        history = H.analyze_revision_table(section[a:b], require_record=True, require_empty_row=False)
        self.assertEqual([r.version for r in history.records], ['v0.1', 'v0.2'])
        self.assertEqual(H.sha256_file(source), old_digest)

    def test_existing_output_is_not_overwritten(self):
        target = self.sample()
        digest = H.sha256_file(target)
        with self.assertRaises(H.HeadlessHwpxError):
            self.build('# 1. 새 내용\n\n바뀐 본문')
        self.assertEqual(H.sha256_file(target), digest)

    def test_invalid_image_rejected_even_with_explicit_size(self):
        (self.directory / 'invalid.png').write_bytes(b'not an image')
        self.assert_rejected('# 1. 합성\n\n[[그림: invalid.png | 80x20mm]]', '손상된 그림')

    def test_truncated_png_and_crc_failure(self):
        for data in (synthetic_png()[:-1], synthetic_png().replace(b'IHDR', b'IHDS')):
            with self.assertRaises(H.HeadlessHwpxError):
                P.image_dimensions(data, 'png')

    def test_truncated_jpeg_rejected(self):
        with self.assertRaises(H.HeadlessHwpxError):
            P.image_dimensions(JPEG[:-2], 'jpg')

    def test_inline_picture_is_not_silently_deleted(self):
        self.assert_rejected('# 1. 합성\n\n앞 문장 ![제목](그림.png) 뒷 문장', '독립된 문단')

    def test_missing_remote_and_oversized_pictures_stop(self):
        cases = [('[[그림: missing.png | 80mm]]', '로컬 PNG/JPEG'),
                 ('![](<https://example.com/a.png>)', '원격 그림'),
                 ('[[그림: 합성 그림.png | 0mm]]', '양수'),
                 ('[[그림: 합성 그림.png | 80x999mm]]', '한 쪽')]
        for block, reason in cases:
            self.assert_rejected('# 1. 합성\n\n' + block, reason)

    def test_duplicate_or_detached_captions_stop(self):
        self.assert_rejected('# 1. 합성\n\n[그림 1-1] 대상 없음', '캡션 위치')
        self.assert_rejected('# 1. 합성\n\n[[그림: 합성 그림.png | 80mm | [그림 1-1] 합성]]\n\n'
                             '[[그림: 합성 그림.png | 80mm | [그림 1-1] 중복]]', '캡션 번호')

    def test_undefined_caption_reference_stops(self):
        self.assert_rejected('# 1. 합성\n\n문장은 [그림 1-2]를 참조합니다.', '캡션 참조')

    def test_checker_detects_missing_corrupt_and_unembedded_resources(self):
        original = self.sample()
        for variant in ('missing', 'corrupt', 'embed', 'missingref'):
            entries = H.read_hwpx(original)
            if variant == 'missing':
                entries = [e for e in entries if e.name != 'BinData/ax1image1.png']
            elif variant == 'corrupt':
                next(e for e in entries if e.name == 'BinData/ax1image1.png').data = b'invalid'
            elif variant == 'embed':
                hpf = H.get_text(entries, P.CONTENT)
                hpf = hpf.replace('media-type="image/png" isEmbeded="1"', 'media-type="image/png" isEmbeded="0"')
                H.set_text(entries, P.CONTENT, hpf)
            else:
                section = H.get_text(entries, H.SECTION)
                section = re.sub(r'<hc:img binaryItemIDRef="ax1image1"[^>]*/>', '', section, count=1)
                H.set_text(entries, H.SECTION, section)
            target = self.directory / f'DXS-AX-TST-{variant}-20261001-v0.1.hwpx'
            H.write_hwpx(entries, target)
            self.assertIn('그림 리소스', [issue['rule'] for issue in C.check(target)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
