"""Synthetic regression tests for cover, metadata, history and publication."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/bizplan-hwpx/scripts'))
sys.dont_write_bytecode = True
import build_headless_artifact as B
import headless_hwpx as H
import check_headless_artifact as C


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.content = self.root / 'synthetic.md'
        self.content.write_text('# 1. 목적\n\n합성 자료의 데이터 항목을 정의한다.\n', encoding='utf-8')
        self.cover = dict(agency='합성기관', program='합성사업', project_number='TEST-0000',
                          project='합성과제', title='현재 수집 데이터 정의서', document_type='데이터 정의서')

    def build(self, version='v0.1', **kwargs):
        path = self.root / f'DXS-AX-DAT-합성정의서-20260910-{version}.hwpx'
        B.build(B.default_template(), self.content, path, self.cover,
                artifact_version=version, revision_date='2026-09-10',
                revision_note='합성 개정', revision_author='합성 작성자', **kwargs)
        self.assertEqual(C.check(path), [])
        return path

    def records(self, path):
        section = H.get_text(H.read_hwpx(path), H.SECTION)
        a, b = H.revision_table_spans(section, H.body_start_offset(section))[0]
        return H.analyze_revision_table(section[a:b], require_record=True, require_empty_row=False).records

    def test_cover_type_not_repeated(self):
        path = self.build()
        section = H.get_text(H.read_hwpx(path), H.SECTION)
        texts = [H.unescape(x) for x in H.re.findall(r'<hp:t>([^<]*)</hp:t>', section)]
        self.assertIn(self.cover['title'], texts)
        self.assertNotIn(self.cover['document_type'], texts)

    def test_people_slots_and_no_approval_inference(self):
        metadata = self.root / 'info.json'
        metadata.write_text(json.dumps({'작성자': {'소속': '합성팀', '성명': '합성 작성자'},
                                       '검토자': {'성명': '합성 검토자'}}, ensure_ascii=False), encoding='utf-8')
        path = self.build(document_info=metadata)
        section = H.get_text(H.read_hwpx(path), H.SECTION)
        table = next(section[a:b] for a,b in H.table_spans(section)
                     if H.table_header_values(section[a:b]) == H.DOCUMENT_INFO_HEADERS)
        self.assertIn('합성 검토자', table)
        self.assertIn('합성팀', table)
        self.assertEqual(self.records(path)[-1].confirmer, '')

    def test_history_append_and_source_unchanged(self):
        old = self.build()
        before = old.read_bytes()
        new = self.build('v0.2', previous_artifact=old, previous_sha256=H.sha256_file(old))
        self.assertEqual([r.version for r in self.records(new)], ['v0.1', 'v0.2'])
        self.assertEqual(self.records(new)[0], self.records(old)[0])
        self.assertEqual(old.read_bytes(), before)

    def test_missing_history_not_silently_reset(self):
        with self.assertRaisesRegex(H.HeadlessHwpxError, '기준본'):
            self.build('v0.2')
        self.assertFalse(list(self.root.glob('*.hwpx')))

    def test_stale_hash_and_wrong_family_rejected(self):
        old = self.build()
        with self.assertRaisesRegex(H.HeadlessHwpxError, 'SHA-256'):
            self.build('v0.2', previous_artifact=old, previous_sha256='0'*64)
        different = self.root / 'DXS-AX-REQ-다른문서-20260910-v0.1.hwpx'
        different.write_bytes(old.read_bytes())
        with self.assertRaisesRegex(H.HeadlessHwpxError, '산출물군'):
            self.build('v0.2', previous_artifact=different, previous_sha256=H.sha256_file(different))

    def test_four_history_rows_and_capacity_stop(self):
        old = self.build()
        for version in ('v0.2', 'v0.3', 'v0.4'):
            old = self.build(version, previous_artifact=old, previous_sha256=H.sha256_file(old))
        self.assertEqual(len(self.records(old)), 4)
        before = old.read_bytes()
        with self.assertRaisesRegex(H.HeadlessHwpxError, '용량|빈 행|upstream'):
            self.build('v0.5', previous_artifact=old, previous_sha256=H.sha256_file(old))
        self.assertEqual(old.read_bytes(), before)
        self.assertFalse((self.root / 'DXS-AX-DAT-합성정의서-20260910-v0.5.hwpx').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows inherited-ACL publication')
    def test_windows_publication_does_not_hardlink(self):
        source = B.default_template()
        target = self.root / 'copy.hwpx'
        with patch.object(H.os, 'link', side_effect=AssertionError('must not retain temporary ACL')):
            H.publish_new_file(source, target)
        self.assertEqual(source.read_bytes(), target.read_bytes())
        self.assertNotEqual(source.stat().st_ino, target.stat().st_ino)
        with self.assertRaises(H.HeadlessHwpxError):
            H.publish_new_file(source, target)

    def test_invalid_metadata_does_not_emit_document(self):
        path = self.root / 'bad.json'
        path.write_text('{"검토자":{"서명":"자동 승인"}}', encoding='utf-8')
        with self.assertRaises(H.HeadlessHwpxError):
            self.build(document_info=path)
        self.assertFalse(list(self.root.glob('*.hwpx')))

    def test_long_metadata_does_not_silently_clip(self):
        path = self.root / 'long.json'
        path.write_text(json.dumps({'작성자': {'소속': '긴합성소속명' * 20}}, ensure_ascii=False), encoding='utf-8')
        with self.assertRaisesRegex(H.HeadlessHwpxError, '높이 초과'):
            self.build(document_info=path)
        self.assertFalse(list(self.root.glob('*.hwpx')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
