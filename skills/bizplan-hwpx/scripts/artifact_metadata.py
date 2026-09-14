"""Approved AX1 text slots and revision history; never an arbitrary form editor."""
from pathlib import Path
import json
import re
import headless_hwpx as H

ROLES = ('작성자', '검토자', '사업책임자')
FIELDS = ('소속', '성명', '날짜')


def check_slot_height(table):
    """Do not silently clip long values in protected, fixed-height form cells."""
    for cell in H.cells(table):
        if not H.cell_text(cell):
            continue
        heights = []
        for attrs in re.findall(r'<hp:lineseg ([^>]*)/>', cell.inner):
            numbers = dict(re.findall(r'(\w+)="(-?\d+)"', attrs))
            heights.append(int(numbers.get('vertpos', 0)) + int(numbers.get('vertsize', 0)))
        if heights and max(heights) > cell.height:
            raise H.HeadlessHwpxError('문서 정보·개정 이력 셀 높이 초과: 문구 축약 확인 또는 upstream 표 확장·페이지 검증 필요')


def info_table(section):
    boundary = H.body_start_offset(section)
    matches = [(a,b) for a,b in H.table_spans(section)
               if boundary is not None and a < boundary
               and H.table_header_values(section[a:b]) == H.DOCUMENT_INFO_HEADERS]
    if len(matches) != 1:
        raise H.HeadlessHwpxError('문서 정보표를 정확히 하나로 식별할 수 없음')
    return matches[0]


def validate_people(data):
    if not isinstance(data, dict) or set(data) - set(ROLES):
        raise H.HeadlessHwpxError('문서 정보: 작성자·검토자·사업책임자만 허용')
    for role, fields in data.items():
        if not isinstance(fields, dict) or set(fields) - set(FIELDS):
            raise H.HeadlessHwpxError('문서 정보: 소속·성명·날짜만 입력하며 서명·승인을 자동 생성하지 않음')
        for key, value in fields.items():
            if not isinstance(value, str) or len(value) > 120 or any(ord(c) < 32 for c in value):
                raise H.HeadlessHwpxError('문서 정보 값은 줄바꿈 없는 120자 이하 문자열이어야 함')
            if key == '날짜' and value:
                H.normalize_revision_date(value)
    return data


def prepare(previous, digest, target, version, date, metadata_path):
    records, people = [], {}
    if previous is None:
        if digest:
            raise H.HeadlessHwpxError('기준본 없이 SHA-256만 지정할 수 없음')
        if version != 'v0.1':
            raise H.HeadlessHwpxError('v0.1 이후 개정은 기존 이력 기준본이 필요함; 최초 승인본도 이전 이력을 확인할 것')
    else:
        previous = Path(previous)
        if not digest or not re.fullmatch('[0-9a-fA-F]{64}', digest) or H.sha256_file(previous) != digest.lower():
            raise H.HeadlessHwpxError('기준본 SHA-256 불일치 또는 누락')
        source_match = H.ARTIFACT_FILENAME_RE.fullmatch(previous.stem)
        target_match = H.ARTIFACT_FILENAME_RE.fullmatch(Path(target).stem)
        if not source_match or not target_match or any(source_match[k] != target_match[k] for k in ('project_code','document_type','title')):
            raise H.HeadlessHwpxError('이력 기준본과 출력의 산출물군이 다름; 개명·이관은 별도 확인 필요')
        entries = H.read_hwpx(previous)
        section = H.get_text(entries, H.SECTION)
        boundary = H.body_start_offset(section)
        if not H.ax1_front_matter_signature(section, boundary):
            raise H.HeadlessHwpxError('기준본 AX1 문서 구조가 아님: upstream으로 이력 확인 필요')
        spans = H.revision_table_spans(section, boundary)
        if len(spans) != 1:
            raise H.HeadlessHwpxError('기준본 개정 이력표 누락 또는 복수; 초기화하지 않음')
        a,b = spans[0]
        analysis = H.analyze_revision_table(section[a:b], require_record=True, require_empty_row=False)
        if analysis.issues:
            raise H.HeadlessHwpxError('기준본 개정 이력 오류: ' + '; '.join(analysis.issues))
        records = analysis.records
        issues = H.artifact_filename_issues(previous, records[-1].version, records[-1].date)
        if issues or H.compare_versions(records[-1].version, version) >= 0 or records[-1].date > date:
            raise H.HeadlessHwpxError('기준본 파일명·이력 또는 새 버전·날짜 순서 충돌: ' + '; '.join(issues))
        if any(a.date > b.date for a,b in zip(records, records[1:])):
            raise H.HeadlessHwpxError('기준본 개정 날짜가 역순임')
        a,b = info_table(section)
        cells = H.cells(section[a:b])
        for cell in cells:
            role = H.cell_text(cell)
            if cell.col == 0 and role in ROLES:
                row = {c.col: H.cell_text(c) for c in cells if c.row == cell.row}
                # Assignments may continue; a past review date/signature does not
                # approve the newly revised content.
                people[role] = {'소속': row.get(1,''), '성명': row.get(2,'')}
    if metadata_path is not None:
        supplied = validate_people(json.loads(Path(metadata_path).read_text(encoding='utf-8-sig')))
        for role, fields in supplied.items():
            people.setdefault(role, {}).update(fields)
    return records, validate_people(people)


def fill_people(section, people, relayout):
    if not people:
        return section
    a,b = info_table(section)
    table = section[a:b]
    cells = H.cells(table)
    for role, fields in people.items():
        rows = [cell.row for cell in cells if cell.col == 0 and H.cell_text(cell) == role]
        if len(rows) != 1:
            raise H.HeadlessHwpxError('문서 정보 역할 행 식별 실패: ' + role)
        for col, field in enumerate(FIELDS, 1):
            value = fields.get(field, '')
            if value:
                table = H.set_revision_cell_text(table, rows[0], col, value, paragraph_transform=relayout)
                saved = next(c for c in H.cells(table) if c.row == rows[0] and c.col == col)
                if H.cell_text(saved) != value:
                    raise H.HeadlessHwpxError('문서 정보 readback 불일치')
    check_slot_height(table)
    return section[:a] + table + section[b:]


def fill_history(section, records, version, date, note, author, relayout):
    spans = H.revision_table_spans(section, H.body_start_offset(section))
    if len(spans) != 1:
        raise H.HeadlessHwpxError('개정 이력표를 정확히 하나로 식별할 수 없음')
    a,b = spans[0]
    table = section[a:b]
    analysis = H.analyze_revision_table(table, require_record=False, require_empty_row=True)
    if analysis.issues or analysis.records:
        raise H.HeadlessHwpxError('승인 양식의 빈 개정 이력표가 아님')
    rows = [(r.date,r.version,r.note,r.author,r.confirmer) for r in records]
    rows.append((date,version,note,author,''))
    if len(rows) > len(analysis.empty_rows):
        raise H.HeadlessHwpxError('개정 이력표 용량 초과: 이력을 초기화하지 말고 upstream에서 표 확장·페이지 검증 후 진행')
    for row, values in enumerate(rows, 1):
        for col, value in enumerate(values):
            if value:
                table = H.set_revision_cell_text(table, row, col, value, paragraph_transform=relayout)
    checked = H.analyze_revision_table(table, require_record=True, require_empty_row=False)
    actual = [(r.date,r.version,r.note,r.author,r.confirmer) for r in checked.records]
    if checked.issues or actual != rows:
        raise H.HeadlessHwpxError('누적 개정 이력 readback 불일치')
    return section[:a] + table + section[b:]
