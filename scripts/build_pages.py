#!/usr/bin/env python3
"""Publish only the existing self-contained guide from a stable release checkout."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

SITE_URL = 'https://realmyeong.github.io/ax1-bizplan/'
REPO_URL = 'https://github.com/RealMyeong/ax1-bizplan'
GUIDE_PATH = Path('docs/ax1-bizplan-guide.html')
PUBLIC_FILES = {'index.html', '.nojekyll', 'version.json'}
VERSION_BADGE = re.compile(r'(<div class="version">)[^<]*(</div>)')


class GuideValidator(HTMLParser):
    """Fail closed when the single-file guide acquires unbundled dependencies."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.fragments = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {'base', 'iframe', 'object', 'embed', 'form'}:
            raise ValueError(f'Unsupported public guide element: {tag}')
        if 'id' in attributes:
            if attributes['id'] in self.ids:
                raise ValueError('Duplicate HTML id')
            self.ids.add(attributes['id'])
        for name, value in attrs:
            if name in {'src', 'srcset', 'poster'}:
                raise ValueError('Guide must remain self-contained; review new assets first')
            if name == 'href' and value:
                if value.startswith('#'):
                    self.fragments.append(value[1:])
                elif urlsplit(value).scheme != 'https' or not urlsplit(value).netloc:
                    raise ValueError(f'Broken or unsafe public link: {value}')

    def validate(self, text):
        self.feed(text)
        self.close()
        if any(fragment not in self.ids for fragment in self.fragments):
            raise ValueError('Broken guide anchor')
        if re.search(r'file://|(?<![A-Za-z0-9])[A-Za-z]:[\\/]|url\s*\(', text, re.I):
            raise ValueError('Local paths or unreviewed CSS assets in public guide')
        if not {'team-guide', 'maintainer-guide', 'page-title'} <= self.ids:
            raise ValueError('Required guide sections missing')


def build(source_root: Path, output: Path, tag: str, commit: str, published_at: str):
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError('Stable release tag required')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Full source commit required')
    published = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
    if published.tzinfo is None:
        raise ValueError('Publication timestamp must include timezone')
    release_date = published.astimezone(timezone(timedelta(hours=9))).date().isoformat()
    for relative in (Path('VERSION'), GUIDE_PATH):
        source = source_root / relative
        if not source.is_file() or source.is_symlink():
            raise ValueError(f'Released file missing or linked: {relative}')
    if (source_root / 'VERSION').read_text(encoding='utf-8-sig').strip() != tag[1:]:
        raise ValueError('Release tag and VERSION disagree')
    original = (source_root / GUIDE_PATH).read_bytes()
    document = original.decode('utf-8-sig')
    GuideValidator().validate(document)
    document, count = VERSION_BADGE.subn(
        lambda match: f'{match[1]}안내 기준 {tag} · {release_date}{match[2]}', document,
    )
    if count != 1:
        raise ValueError('Exactly one version badge is required')
    if document.count('</head>') != 1:
        raise ValueError('Invalid guide head')
    document = document.replace('</head>', f'  <link rel="canonical" href="{SITE_URL}">\n</head>')
    if document.count('<footer>') != 1:
        raise ValueError('Exactly one guide footer is required')
    source_url = f'{REPO_URL}/blob/{commit}/{GUIDE_PATH.as_posix()}'
    provenance = (
        f'<p>안내 기준: <a href="{REPO_URL}/releases/tag/{tag}">{escape(tag)}</a>'
        f' · <a href="{source_url}">릴리즈 원문</a></p>'
    )
    document = document.replace('<footer>', '<footer>\n      ' + provenance)
    GuideValidator().validate(document)
    # Never delete or publish an entire pre-existing directory.
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Public output must be a new or empty directory')
    if output.is_symlink():
        raise ValueError('Public output must not be a link')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(document, encoding='utf-8', newline='\n')
    (output / '.nojekyll').write_bytes(b'')
    manifest = {
        'tag': tag, 'commit': commit, 'published_at': published_at,
        'source_path': GUIDE_PATH.as_posix(),
        'source_sha256': hashlib.sha256(original).hexdigest(),
        'index_sha256': hashlib.sha256((output / 'index.html').read_bytes()).hexdigest(),
    }
    (output / 'version.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if {path.name for path in output.iterdir()} != PUBLIC_FILES:
        raise ValueError('Unexpected public file')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--published-at', required=True)
    args = parser.parse_args()
    result = build(args.source_root, args.output, args.tag, args.commit, args.published_at)
    print(f"Built public guide: {result['tag']} ({result['commit']}) — {len(PUBLIC_FILES)} files")


if __name__ == '__main__':
    main()
