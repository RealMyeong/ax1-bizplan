"""Local raster embedding for the approved builder, not an existing-document editor.

PR #7 (gslee, with Claude Code) supplied the picture/caption proposal. This narrow
integration retains the current template, publication, history and layout guards.
No network downloads, image generation, font substitution or implicit renumbering.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib

import headless_hwpx as H

CONTENT = 'Contents/content.hpf'
OPF = 'http://www.idpf.org/2007/opf/'
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_RASTER_BYTES = 64 * 1024 * 1024
FORMATS = {'.png': ('png', 'image/png'), '.jpg': ('jpg', 'image/jpeg'),
           '.jpeg': ('jpg', 'image/jpeg')}
SIZE_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*(?:[xX×]\s*(\d+(?:\.\d+)?))?\s*mm$')


def parse_picture(text: str):
    """One standalone image block; reject ambiguous/inline syntax at the caller."""
    text = text.strip()
    if text.startswith('[[그림:') or text.startswith('[[그림：'):
        if not text.endswith(']]'):
            raise H.HeadlessHwpxError('그림 블록이 ]]로 끝나지 않음')
        fields = re.split(r'\s*\|\s*', re.split('[:：]', text[2:-2], maxsplit=1)[1].strip())
        if len(fields) not in (2, 3) or not fields[0]:
            raise H.HeadlessHwpxError('그림 입력은 [[그림: 경로 | 폭mm | [그림 장-순번] 제목]] 형식')
        size = SIZE_RE.fullmatch(fields[1])
        if not size:
            raise H.HeadlessHwpxError('그림 크기는 양수 폭mm 또는 폭x높이mm 형식')
        width, height = float(size[1]), float(size[2]) if size[2] else None
        path, caption = fields[0], fields[2] if len(fields) == 3 else ''
    else:
        # Angle brackets allow local paths containing spaces; URLs are never fetched.
        match = re.fullmatch(r'!\[(.*)\]\((?:<([^<>]+)>|([^()]+))\)', text)
        if not match:
            return None
        path, caption = (match[2] or match[3]).strip(), match[1].strip()
        width, height = 140.0, None
    if not math.isfinite(width) or width <= 0 or (height is not None and
                                               (not math.isfinite(height) or height <= 0)):
        raise H.HeadlessHwpxError('그림 크기는 유한한 양수여야 함')
    if caption:
        m = H.CAPTION_RE.fullmatch(caption)
        if not m or m[1] != '그림':
            raise H.HeadlessHwpxError('그림 캡션은 [그림 장-순번] 제목 형식')
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', path):
        raise H.HeadlessHwpxError('원격 그림은 자동 다운로드하지 않음; 로컬 PNG/JPEG 필요')
    return dict(path=path, caption=caption, width_mm=width, height_mm=height)


def image_dimensions(data: bytes, fmt: str):
    """Validate PNG chunks/CRC/raster or JPEG marker structure and dimensions.

JPEG entropy decoding and actual Hancom rendering remain separate visual checks.
Interlaced PNG and uncommon JPEG coding modes require the upstream image path.
"""
    def fail():
        raise H.HeadlessHwpxError('지원하지 않거나 손상된 그림 데이터')
    if not data or len(data) > MAX_IMAGE_BYTES:
        fail()
    if fmt == 'png':
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            fail()
        offset, chunks, seen, pixels, scan_bytes = 8, [], set(), None, 0
        row_bytes = 0
        while offset + 12 <= len(data):
            length = struct.unpack_from('>I', data, offset)[0]
            tag = data[offset + 4:offset + 8]
            end = offset + 12 + length
            if end > len(data):
                fail()
            body = data[offset + 8:end - 4]
            crc = struct.unpack_from('>I', data, end - 4)[0]
            if zlib.crc32(tag + body) & 0xffffffff != crc:
                fail()
            if pixels is None and tag != b'IHDR':
                fail()
            if tag == b'IHDR':
                if pixels is not None or length != 13:
                    fail()
                w, h, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', body)
                depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
                if not w or not h or depth not in depths.get(color, ()) or compression or filtering or interlace:
                    fail()
                channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
                row_bytes = (w * depth * channels + 7) // 8
                scan_bytes = (row_bytes + 1) * h
                if scan_bytes > MAX_RASTER_BYTES:
                    fail()
                pixels = (w, h)
            elif tag == b'IDAT':
                chunks.append(body)
            elif tag == b'IEND':
                if length or end != len(data) or not chunks or (color == 3 and b'PLTE' not in seen):
                    fail()
                try:
                    decoder = zlib.decompressobj()
                    raster = decoder.decompress(b''.join(chunks), scan_bytes + 1)
                except zlib.error:
                    fail()
                if len(raster) != scan_bytes or not decoder.eof or decoder.unused_data:
                    fail()
                if any(raster[i] > 4 for i in range(0, scan_bytes, row_bytes + 1)):
                    fail()
                return pixels
            elif tag[:1].isupper() and tag != b'PLTE':
                fail()  # Unknown critical chunk: cannot claim a supported image.
            seen.add(tag)
            offset = end
        fail()
    if fmt == 'jpg':
        if data[:2] != b'\xff\xd8' or not data.endswith(b'\xff\xd9'):
            fail()
        offset, pixels, saw_scan = 2, None, False
        while offset < len(data) - 2:
            if data[offset] != 0xff:
                fail()
            while offset < len(data) and data[offset] == 0xff:
                offset += 1
            marker = data[offset]
            offset += 1
            if marker in (0, 0xd8, 0xd9) or 0xd0 <= marker <= 0xd7:
                fail()
            if offset + 2 > len(data):
                fail()
            length = struct.unpack_from('>H', data, offset)[0]
            end = offset + length
            if length < 2 or end > len(data):
                fail()
            if marker in (0xc0, 0xc2):
                if length < 11 or pixels is not None:
                    fail()
                precision, h, w, components = struct.unpack_from('>BHHB', data, offset + 2)
                if precision != 8 or not w or not h or components not in (1, 3) or length != 8 + 3 * components:
                    fail()
                if w * h * components > MAX_RASTER_BYTES:
                    fail()
                pixels = (w, h)
            if marker == 0xda:
                if pixels is None or length < 8:
                    fail()
                saw_scan = True
                # Find a non-stuffed/non-restart marker terminating the entropy scan.
                offset = end
                while offset < len(data) - 2:
                    if data[offset] == 0xff:
                        following = data[offset + 1]
                        if following not in (0, 0xff) and not 0xd0 <= following <= 0xd7:
                            break
                        offset += 2
                    else:
                        offset += 1
                if offset == len(data) - 2:
                    return pixels if saw_scan else fail()
            else:
                offset = end
        fail()
    fail()


def prepare(spec: dict, entries: list, base: Path, max_width: int, max_height: int):
    path = Path(spec['path'])
    if not path.is_absolute():
        path = base / path
    fmt = FORMATS.get(path.suffix.lower())
    if not fmt or not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
        raise H.HeadlessHwpxError('읽을 수 있는 20MiB 이하 로컬 PNG/JPEG 그림 필요')
    data = path.read_bytes()
    pixels = image_dimensions(data, fmt[0])
    width = round(spec['width_mm'] * 7200 / 25.4)
    height = round(spec['height_mm'] * 7200 / 25.4) if spec['height_mm'] else round(width * pixels[1] / pixels[0])
    if width <= 0 or height <= 0:
        raise H.HeadlessHwpxError('그림 표시 크기가 0 이하임')
    if width > max_width:
        height = round(height * max_width / width)
        width = max_width
    if height <= 0 or height + H.CAPTION_TOP_SPACING + H.BODY_TEXT_HEIGHT * 1.6 > max_height:
        raise H.HeadlessHwpxError('그림과 캡션이 한 쪽에 들어가지 않음; 크기 축소 또는 upstream 편집 필요')
    content = H.get_text(entries, CONTENT)
    if '</opf:manifest>' not in content:
        raise H.HeadlessHwpxError('그림 등록용 opf:manifest 누락')
    ids = {item.get('id') for item in ET.fromstring(content).iter(f'{{{OPF}}}item')}
    names = {entry.name.casefold() for entry in entries}
    n = 1
    while f'ax1image{n}' in ids or f'bindata/ax1image{n}.{fmt[0]}' in names:
        n += 1
    item_id = f'ax1image{n}'
    href = f'BinData/{item_id}.{fmt[0]}'
    entries.append(H.Entry(name=href, data=data, compress_type=zipfile.ZIP_STORED))
    item = f'<opf:item id="{item_id}" href="{href}" media-type="{fmt[1]}" isEmbeded="1"/>'
    H.set_text(entries, CONTENT, content.replace('</opf:manifest>', item + '</opf:manifest>', 1))
    spec.update(item_id=item_id, width=width, height=height, pixels=pixels)


def check_resources(entries: list, section: str):
    issues = []
    manifest = ET.fromstring(H.get_text(entries, CONTENT))
    items = {}
    for item in manifest.iter(f'{{{OPF}}}item'):
        items.setdefault(item.get('id'), []).append(item)
    data = {entry.name: entry.data for entry in entries}
    boundary = H.body_start_offset(section)
    # Approved logo resources are not rewritten or subjected to a new raster profile.
    for ref in re.findall(r'<hc:img\b[^>]*binaryItemIDRef="([^"]+)"', section[boundary or 0:]):
        candidates = items.get(ref, [])
        if len(candidates) != 1:
            issues.append(('그림 리소스', f'{ref}: 그림 매니페스트가 하나가 아님'))
            continue
        item = candidates[0]
        href = item.get('href', '')
        fmt = FORMATS.get(Path(href).suffix.lower())
        if not re.fullmatch(r'BinData/[A-Za-z0-9_-]+\.(?:png|jpg|jpeg)', href) or href not in data:
            issues.append(('그림 리소스', f'{ref}: 실제 로컬 BinData 파일 누락 또는 잘못된 경로'))
        elif not fmt or item.get('media-type') != fmt[1] or item.get('isEmbeded') != '1':
            issues.append(('그림 리소스', f'{ref}: 그림 형식·매체 유형·임베드 지정 불일치'))
        else:
            try:
                image_dimensions(data[href], fmt[0])
            except H.HeadlessHwpxError as exc:
                issues.append(('그림 리소스', f'{ref}: {exc}'))
    return issues
