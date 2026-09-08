#!/usr/bin/env python3
"""Offline acceptance tests for the allowlisted GitHub Pages output."""

import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from build_pages import build, GUIDE_PATH, PUBLIC_FILES

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = '''<!doctype html><html lang="ko"><head><title>합성 안내</title></head>
<body><div class="version">예전 버전</div><h1 id="page-title">한글 안내</h1>
<section id="team-guide">팀원</section><section id="maintainer-guide">배포자</section>
<a href="#team-guide">팀원으로 이동</a><footer>AX1</footer></body></html>'''


class PagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / 'docs').mkdir(parents=True)
        (self.source / 'VERSION').write_text('0.10.0\n', encoding='utf-8')
        self.guide = self.source / GUIDE_PATH
        self.guide.write_text(SYNTHETIC, encoding='utf-8')
        self.output = self.root / 'public'

    def run_build(self, **overrides):
        args = dict(source_root=self.source, output=self.output, tag='v0.10.0',
                    commit='a' * 40, published_at='2026-09-07T06:10:52Z')
        args.update(overrides)
        return build(**args)

    def test_allowlist_excludes_unrelated_documents_and_credentials(self):
        (self.source / 'private').mkdir()
        (self.source / 'private' / 'synthetic-secret.txt').write_text('must not publish')
        (self.source / '.env').write_text('SYNTHETIC=not-a-real-secret')
        result = self.run_build()
        self.assertEqual({p.name for p in self.output.iterdir()}, PUBLIC_FILES)
        self.assertEqual(json.loads((self.output / 'version.json').read_text()), result)

    def test_version_date_provenance_and_original_preserved(self):
        before = self.guide.read_bytes()
        result = self.run_build()
        text = (self.output / 'index.html').read_text(encoding='utf-8')
        self.assertIn('안내 기준 v0.10.0 · 2026-09-07', text)
        self.assertIn('한글 안내', text)
        self.assertIn('/blob/' + 'a' * 40, text)
        self.assertEqual(self.guide.read_bytes(), before)
        self.assertEqual(result['source_sha256'], hashlib.sha256(before).hexdigest())

    def test_mismatched_or_unstable_versions_rejected(self):
        for tag in ('main', 'v0.10.0-rc1', 'v0.9.4'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.run_build(tag=tag)
        self.assertFalse(self.output.exists())

    def test_existing_output_not_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / 'keep.txt'
        sentinel.write_text('keep')
        with self.assertRaises(ValueError):
            self.run_build()
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_unsafe_or_missing_assets_and_anchors_rejected(self):
        for addition in ('<img src="private.png">', '<a href="../README.md">link</a>',
                         '<a href="file:///C:/private">local</a>', '<a href="#missing">bad</a>',
                         '<form action="https://example.com"></form>', '<p>C:/private/report</p>'):
            self.guide.write_text(SYNTHETIC.replace('</body>', addition + '</body>'), encoding='utf-8')
            with self.subTest(addition=addition), self.assertRaises(ValueError):
                self.run_build()

    def test_https_links_and_korean_publication_date(self):
        self.guide.write_text(SYNTHETIC.replace('</body>', '<a href="https://github.com/RealMyeong/ax1-bizplan">저장소</a></body>'), encoding='utf-8')
        self.run_build(published_at='2026-09-07T16:00:00Z')
        self.assertIn('안내 기준 v0.10.0 · 2026-09-08', (self.output / 'index.html').read_text(encoding='utf-8'))

    def test_current_guide_tabs_copy_handlers_and_css_preserved(self):
        original = (ROOT / GUIDE_PATH).read_text(encoding='utf-8')
        self.guide.write_text(original, encoding='utf-8')
        self.run_build()
        text = (self.output / 'index.html').read_text(encoding='utf-8')
        for element in ('script', 'style'):
            pattern = rf'<{element}[^>]*>(.*?)</{element}>'
            self.assertEqual(re.findall(pattern, original, re.S), re.findall(pattern, text, re.S))
        self.assertIn('navigator.clipboard.writeText', text)
        self.assertIn('role="tab"', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
