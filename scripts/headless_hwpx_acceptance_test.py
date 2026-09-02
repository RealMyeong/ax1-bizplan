#!/usr/bin/env python3
"""Standard-library acceptance test for the AX1 headless HWPX builder."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "bizplan-hwpx"
SCRIPT_DIR = SKILL / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


H = load("headless_hwpx", SCRIPT_DIR / "headless_hwpx.py")
A = load("format_headless_artifact", SCRIPT_DIR / "format_headless_artifact.py")
C = load("check_headless_artifact", SCRIPT_DIR / "check_headless_artifact.py")
B = load("build_headless_artifact", SCRIPT_DIR / "build_headless_artifact.py")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revision_table(section: str) -> tuple[int, int, str]:
    body_start = H.body_start_offset(section)
    spans = H.revision_table_spans(section, body_start)
    if len(spans) != 1:
        raise AssertionError(f"개정 이력표 식별 실패: {len(spans)}개")
    start, end = spans[0]
    return start, end, section[start:end]


def write_revision_variant(source: Path, target: Path, rows: dict[int, tuple[str, str, str, str]]) -> None:
    entries = H.read_hwpx(source)
    section = H.get_text(entries, H.SECTION)
    start, end, table = revision_table(section)
    for row, values in sorted(rows.items()):
        for column, value in enumerate(values):
            if value:
                table = H.set_revision_cell_text(table, row, column, value, require_empty=True)
    H.set_text(entries, H.SECTION, section[:start] + table + section[end:])
    H.write_hwpx(entries, target)


def require_issue(issues: list[dict], rule: str, contains: str) -> None:
    if not any(issue["rule"] == rule and contains in issue["detail"] for issue in issues):
        raise AssertionError(f"예상 위반을 찾지 못함: {rule} / {contains}: {issues!r}")


def top_level_paragraphs(section: str) -> list[dict]:
    """Return generated top-level paragraphs while excluding table-cell paragraphs."""
    spans = H.table_spans(section)
    body_start = H.body_start_offset(section)
    result = []
    for offset, attrs, body in H.paragraphs(section):
        if body_start is None or offset < body_start or H.in_any_span(spans, offset):
            continue
        result.append(
            {
                "offset": offset,
                "attrs": attrs,
                "body": body,
                "text": H.unescape("".join(H.re.findall(r"<hp:t>([^<]*)</hp:t>", body))),
                "table": "<hp:tbl " in body,
            }
        )
    return result


def main() -> int:
    template = H.approved_template(SKILL)
    template_before = digest(template)
    markdown = """# 1. 사업 개요

승인된 AX1 경량 생성기의 수용 테스트 문단입니다.

한글원문보존 가나다라마바사아자차카타파하

## 1.1 구현 방식

### 1.1.1 세부 검증

#### 1.1.1.1 사수준 제목

##### 1.1.1.1.1 본문 목록으로 전환할 항목

- 표준 라이브러리만 사용
- 한컴오피스와 COM 창을 실행하지 않음

## 1.2 목록 뒤 제목

| 구분 | 확인 결과 |
|---|---|
| 선택 상태 | ☑ 완료 / ☐ 미완료 |
| 줄간격 | 본문 160% / 표 셀 160% |
| 한글 표 셀 | 한글표셀검증 |

## 1.3 표 뒤 제목
### 1.3.1 연속 제목

- 매우 긴 한국어 글머리표가 자동으로 두 줄 이상 줄바꿈될 때 둘째 줄 이후의 시작 위치가 첫 줄의 글머리표 다음 본문 시작 위치와 시각적으로 일치하는지 확인하기 위한 합성 검증 문장입니다. 일반 공백과 문단 들여쓰기를 함께 적용해 이중 들여쓰기가 생기면 안 됩니다.

# 2. 새 쪽 제목
"""
    cover = {
        "agency": "테스트 발주기관",
        "program": "테스트 사업",
        "project_number": "TEST-0000",
        "project": "테스트 세부사업",
        "title": "한글표지보존 AX1 경량 HWPX 수용 테스트",
        "document_type": "검증 문서",
    }

    with tempfile.TemporaryDirectory(prefix="ax1-headless-test-") as temp_dir:
        temp = Path(temp_dir)
        content = temp / "content.md"
        output = temp / "DXS-AX-TST-AX1_경량_HWPX_수용테스트-20260902-v0.1.hwpx"
        output2 = temp / "DXS-AX-TST-AX1_경량_HWPX_재적용-20260902-v0.1.hwpx"
        unsupported = temp / "unsupported.hwpx"
        escaped_hangul = temp / "DXS-AX-TST-한글_코드표기_결함-20260902-v0.1.hwpx"
        bad_outline = temp / "DXS-AX-TST-잘못된_개요_들여쓰기-20260902-v0.1.hwpx"
        bad_outline_h4 = temp / "DXS-AX-TST-잘못된_사수준_들여쓰기-20260902-v0.1.hwpx"
        bad_heading_gap = temp / "DXS-AX-TST-잘못된_제목위간격-20260902-v0.1.hwpx"
        bad_list_indent = temp / "DXS-AX-TST-잘못된_목록들여쓰기-20260902-v0.1.hwpx"
        bad_list_lineseg = temp / "DXS-AX-TST-잘못된_목록줄배치-20260902-v0.1.hwpx"
        content.write_text(markdown, encoding="utf-8")
        revision_note = "한글 개정내역: C:\\검증\\원본\\1"
        revision_author = "테스트 작성자"
        revision_date = "2026-09-02"
        B.build(
            template,
            content,
            output,
            cover,
            artifact_version="v0.1",
            revision_note=revision_note,
            revision_author=revision_author,
            revision_date=revision_date,
        )
        issues = C.check(output)
        if issues:
            raise AssertionError(issues)
        section = H.get_text(H.read_hwpx(output), H.SECTION)
        for token in (
            "☑ 완료",
            "☐ 미완료",
            "본문 160%",
            "표 셀 160%",
            "한글표지보존",
            "한글원문보존",
            "가나다라마바사아자차카타파하",
            "한글표셀검증",
            "검증 문서",
            "사수준 제목",
            revision_note,
            revision_author,
        ):
            if token not in section:
                raise AssertionError(f"의미·본문 보존 실패: {token}")
        if "□ 완료" in section or "□ 미완료" in section:
            raise AssertionError("체크 상태 기호가 빈 네모로 바뀜")
        if H.encoded_hangul_references(section):
            raise AssertionError("한글이 코드 표기로 기록됨")
        if H.missing_hangul_runs(["한글표셀검증"], "hangeul-table-cell") != ["한글표셀검증"]:
            raise AssertionError("한글 ASCII 대체를 원문 불일치로 탐지하지 못함")

        for invalid_version in (
            "v1",
            "v01.1",
            "v0." + "9" * 10,
            "v0." + ".".join("1" for _ in range(40)),
        ):
            try:
                H.validate_artifact_version(invalid_version)
            except H.HeadlessHwpxError:
                pass
            else:
                raise AssertionError(f"비정상 또는 과도한 버전을 허용함: {invalid_version!r}")

        _, _, recorded_table = revision_table(section)
        revision = H.analyze_revision_table(
            recorded_table,
            require_record=True,
            require_empty_row=True,
        )
        if revision.issues or len(revision.records) != 1:
            raise AssertionError(f"최초 개정 이력 검사 실패: {revision!r}")
        record = revision.records[0]
        if (record.row, record.date, record.version, record.note, record.author, record.confirmer) != (
            1,
            revision_date,
            "v0.1",
            revision_note,
            revision_author,
            "",
        ):
            raise AssertionError(f"개정 이력 readback 불일치: {record!r}")

        paragraph_texts = []
        header = H.get_text(H.read_hwpx(output), H.HEADER)
        para_prs = H.parse_para_prs(header)
        heading_styles = H.style_ids_by_name(header)
        expected_heading_styles = {
            "1. 사업 개요": heading_styles["개요 1"],
            "   1.1 구현 방식": heading_styles["개요 2"],
            "     1.1.1 세부 검증": heading_styles["개요 3"],
            "       1.1.1.1 사수준 제목": heading_styles["개요 4"],
            "   1.2 목록 뒤 제목": heading_styles["개요 2"],
            "   1.3 표 뒤 제목": heading_styles["개요 2"],
            "     1.3.1 연속 제목": heading_styles["개요 3"],
            "2. 새 쪽 제목": heading_styles["개요 1"],
        }
        observed_heading_styles = set()
        for _, attrs, body in H.paragraphs(section):
            text = H.unescape("".join(H.re.findall(r"<hp:t>([^<]*)</hp:t>", body)))
            if text:
                paragraph_texts.append(text)
            if text in {
                "1. 사업 개요",
                "   1.1 구현 방식",
                "     1.1.1 세부 검증",
                "       1.1.1.1 사수준 제목",
                "   1.2 목록 뒤 제목",
                "   1.3 표 뒤 제목",
                "     1.3.1 연속 제목",
                "2. 새 쪽 제목",
            }:
                pid = H.re.search(r'paraPrIDRef="(\d+)"', attrs)
                if not pid or para_prs[pid.group(1)]["left"] != 0 or para_prs[pid.group(1)]["intent"] != 0:
                    raise AssertionError(f"개요 문단 왼쪽 들여쓰기 중복: {text!r}")
            if text in expected_heading_styles:
                style = H.re.search(r'styleIDRef="(\d+)"', attrs)
                if style and style.group(1) == expected_heading_styles[text]:
                    observed_heading_styles.add(text)
        missing_heading_styles = set(expected_heading_styles) - observed_heading_styles
        if missing_heading_styles:
            raise AssertionError(f"개요 스타일 태그 불일치: {sorted(missing_heading_styles)!r}")
        for expected in (
            "1. 사업 개요",
            "   1.1 구현 방식",
            "     1.1.1 세부 검증",
            "       1.1.1.1 사수준 제목",
            "   1.2 목록 뒤 제목",
            "   1.3 표 뒤 제목",
            "     1.3.1 연속 제목",
            "2. 새 쪽 제목",
            "• 본문 목록으로 전환할 항목",
            "• 표준 라이브러리만 사용",
        ):
            if expected not in paragraph_texts:
                raise AssertionError(f"개요 수준 앞 공백 보존 실패: {expected!r}")
        if any("1.1.1.1.1" in text for text in paragraph_texts):
            raise AssertionError("5단계 숫자 제목이 본문 목록으로 전환되지 않음")

        top_level = top_level_paragraphs(section)
        by_text = {paragraph["text"]: paragraph for paragraph in top_level if paragraph["text"]}
        expected_spacing = {
            "   1.1 구현 방식": H.HEADING_TOP_SPACING,
            "   1.2 목록 뒤 제목": H.HEADING_TOP_SPACING,
            "   1.3 표 뒤 제목": H.HEADING_TOP_SPACING,
            "     1.3.1 연속 제목": 0,
        }
        for text, expected_prev in expected_spacing.items():
            paragraph = by_text[text]
            pid = H.re.search(r'paraPrIDRef="(\d+)"', paragraph["attrs"]).group(1)
            if para_prs[pid]["prev"] != expected_prev:
                raise AssertionError(
                    f"제목 위 간격 불일치: {text!r} / {para_prs[pid]['prev']} != {expected_prev}"
                )

        new_page = by_text["2. 새 쪽 제목"]
        new_page_pid = H.re.search(r'paraPrIDRef="(\d+)"', new_page["attrs"]).group(1)
        if 'pageBreak="1"' not in new_page["attrs"] or para_prs[new_page_pid]["prev"] != 0:
            raise AssertionError("수준 1 새 쪽 시작 동작 또는 위 간격이 변경됨")

        list_paragraphs = [paragraph for paragraph in top_level if paragraph["text"].startswith("• ")]
        if len(list_paragraphs) < 4:
            raise AssertionError("합성 목록 문단을 모두 찾지 못함")
        for paragraph in list_paragraphs:
            pid = H.re.search(r'paraPrIDRef="(\d+)"', paragraph["attrs"]).group(1)
            props = para_prs[pid]
            if props["left"] != H.BODY_LIST_LEFT_INDENT or props["intent"] != H.BODY_LIST_FIRST_LINE_INDENT:
                raise AssertionError(f"본문 목록 hanging indent 불일치: {paragraph['text'][:34]!r} / {props!r}")
            if paragraph["text"] != paragraph["text"].lstrip(" "):
                raise AssertionError(f"본문 목록에 앞 공백과 문단 들여쓰기가 중복됨: {paragraph['text'][:34]!r}")

        long_item = next(paragraph for paragraph in list_paragraphs if "매우 긴 한국어" in paragraph["text"])
        line_positions = [
            (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            for match in H.re.finditer(
                r'<hp:lineseg [^>]*textpos="(\d+)"[^>]*horzpos="(-?\d+)"[^>]*horzsize="(\d+)"',
                long_item["body"],
            )
        ]
        if len(line_positions) < 2:
            raise AssertionError("긴 한국어 글머리표가 두 줄 이상으로 배치되지 않음")
        if line_positions[0][1] != H.BODY_LIST_BULLET_POSITION:
            raise AssertionError(f"글머리표 첫 줄 위치 불일치: {line_positions!r}")
        if any(position[1] != H.BODY_LIST_LEFT_INDENT for position in line_positions[1:]):
            raise AssertionError(f"글머리표 후속 줄이 본문 시작 위치에 맞지 않음: {line_positions!r}")
        if "##############################" in section:
            raise AssertionError("사용자 검토 마커가 생성 결과에 남음")

        front_para_ids = set(
            H.re.findall(r'paraPrIDRef="(\d+)"', section[: H.body_start_offset(section)])
        )
        generated_para_ids = {
            H.re.search(r'paraPrIDRef="(\d+)"', paragraph["attrs"]).group(1)
            for paragraph in list_paragraphs
        }
        generated_para_ids.update(
            H.re.search(r'paraPrIDRef="(\d+)"', by_text[text]["attrs"]).group(1)
            for text in expected_spacing
            if expected_spacing[text]
        )
        if front_para_ids & generated_para_ids:
            raise AssertionError("새 제목 간격·목록 들여쓰기 문단모양이 표지~목차에 연결됨")

        gap_entries = H.read_hwpx(output)
        gap_section = H.get_text(gap_entries, H.SECTION)
        gap_paragraph = by_text["   1.2 목록 뒤 제목"]
        gap_open = f'<hp:p {gap_paragraph["attrs"]}>'
        gap_open_bad = H.re.sub(r'paraPrIDRef="\d+"', 'paraPrIDRef="0"', gap_open, count=1)
        gap_section = gap_section.replace(gap_open, gap_open_bad, 1)
        H.set_text(gap_entries, H.SECTION, gap_section)
        H.write_hwpx(gap_entries, bad_heading_gap)
        require_issue(C.check(bad_heading_gap), "제목 위 간격", "규칙")

        list_entries = H.read_hwpx(output)
        list_section = H.get_text(list_entries, H.SECTION).replace(
            "• 표준 라이브러리만 사용",
            "         • 표준 라이브러리만 사용",
            1,
        )
        H.set_text(list_entries, H.SECTION, list_section)
        H.write_hwpx(list_entries, bad_list_indent)
        require_issue(C.check(bad_list_indent), "본문 목록 들여쓰기", "중복")

        lineseg_entries = H.read_hwpx(output)
        lineseg_section = H.get_text(lineseg_entries, H.SECTION)
        bad_long_body = long_item["body"].replace(
            f'horzpos="{H.BODY_LIST_LEFT_INDENT}"',
            'horzpos="0"',
            1,
        )
        if bad_long_body == long_item["body"]:
            raise AssertionError("긴 목록의 후속 lineseg 변형에 실패함")
        lineseg_section = lineseg_section.replace(long_item["body"], bad_long_body, 1)
        H.set_text(lineseg_entries, H.SECTION, lineseg_section)
        H.write_hwpx(lineseg_entries, bad_list_lineseg)
        require_issue(C.check(bad_list_lineseg), "본문 목록 줄 배치", "규칙")

        bad_entries = H.read_hwpx(output)
        bad_section = H.get_text(bad_entries, H.SECTION).replace(
            "   1.1 구현 방식",
            "  1.1 구현 방식",
            1,
        )
        H.set_text(bad_entries, H.SECTION, bad_section)
        H.write_hwpx(bad_entries, bad_outline)
        bad_outline_issues = C.check(bad_outline)
        if not any(issue["rule"] == "개요 수준 들여쓰기" for issue in bad_outline_issues):
            raise AssertionError("잘못된 제목 앞 공백을 검사기가 탐지하지 못함")

        bad_h4_entries = H.read_hwpx(output)
        bad_h4_section = H.get_text(bad_h4_entries, H.SECTION).replace(
            "       1.1.1.1 사수준 제목",
            "      1.1.1.1 사수준 제목",
            1,
        )
        H.set_text(bad_h4_entries, H.SECTION, bad_h4_section)
        H.write_hwpx(bad_h4_entries, bad_outline_h4)
        bad_h4_issues = C.check(bad_outline_h4)
        if not any(issue["rule"] == "개요 수준 들여쓰기" for issue in bad_h4_issues):
            raise AssertionError("잘못된 4수준 제목 앞 공백을 검사기가 탐지하지 못함")

        encoded_entries = H.read_hwpx(output)
        encoded_section = H.get_text(encoded_entries, H.SECTION).replace(
            "한글표셀검증",
            "&#xD55C;&#xAE00;&#xD45C;&#xC140;&#xAC80;&#xC99D;",
            1,
        )
        H.set_text(encoded_entries, H.SECTION, encoded_section)
        H.write_hwpx(encoded_entries, escaped_hangul)
        escaped_issues = C.check(escaped_hangul)
        if not any(issue["rule"] == "한글 원문 보존" for issue in escaped_issues):
            raise AssertionError("한글 숫자 문자참조를 검사기가 탐지하지 못함")

        # 개정표와 파일명 버전 검사: 불일치와 복수 토큰은 각각 실패해야 한다.
        filename_mismatch = temp / "DXS-AX-TST-파일명_버전불일치-20260902-v0.2.hwpx"
        write_revision_variant(output, filename_mismatch, {})
        require_issue(C.check(filename_mismatch), "파일명 규칙", "다름")

        multiple_versions = temp / "DXS-AX-TST-복수_v0.1_버전-20260902-v0.1.hwpx"
        write_revision_variant(output, multiple_versions, {})
        require_issue(C.check(multiple_versions), "파일명 규칙", "단일하지 않음")

        random_like_name = temp / "DXS-AX-TST-ax1_fmt_v1_abc-20260902-v0.1.hwpx"
        write_revision_variant(output, random_like_name, {})
        if H.artifact_filename_versions(random_like_name) != ["v0.1"]:
            raise AssertionError("임시 파일명 난수 일부를 버전 토큰으로 오인함")
        if C.check(random_like_name):
            raise AssertionError("유효한 끝 버전 앞의 일반 문자열을 잘못 거부함")

        invalid_document_code = temp / "DXS-AX-XYZ-미승인_문서코드-20260902-v0.1.hwpx"
        write_revision_variant(output, invalid_document_code, {})
        require_issue(C.check(invalid_document_code), "파일명 규칙", "승인되지 않은 문서유형")

        invalid_date = temp / "DXS-AX-TST-잘못된_날짜-20260230-v0.1.hwpx"
        write_revision_variant(output, invalid_date, {})
        require_issue(C.check(invalid_date), "파일명 규칙", "유효한 YYYYMMDD")

        mismatched_date = temp / "DXS-AX-TST-개정일자_불일치-20260903-v0.1.hwpx"
        write_revision_variant(output, mismatched_date, {})
        require_issue(C.check(mismatched_date), "파일명 규칙", "개정 이력 일자")

        state_word = temp / "DXS-AX-TST-요구사항_final2-20260902-v0.1.hwpx"
        write_revision_variant(output, state_word, {})
        require_issue(C.check(state_word), "파일명 규칙", "상태어")

        legacy_name = temp / "output_v0.1.hwpx"
        write_revision_variant(output, legacy_name, {})
        require_issue(C.check(legacy_name), "파일명 규칙", "DXS-[사업코드]")

        # 부분 기록, 중복·역순 버전, 빈 행 소진을 서로 독립적으로 탐지한다.
        partial = temp / "DXS-AX-TST-부분_개정기록-20260903-v0.1.hwpx"
        write_revision_variant(output, partial, {2: ("2026-09-03", "", "", "")})
        require_issue(C.check(partial), "개정 이력", "빈 필드")

        duplicate = temp / "DXS-AX-TST-중복_개정기록-20260903-v0.1.hwpx"
        write_revision_variant(output, duplicate, {2: ("2026-09-03", "v0.1", "중복", "")})
        require_issue(C.check(duplicate), "개정 이력", "중복 버전")

        descending = temp / "DXS-AX-TST-역순_개정기록-20260904-v0.2.hwpx"
        write_revision_variant(
            output,
            descending,
            {
                2: ("2026-09-03", "v0.3", "앞선 기록", ""),
                3: ("2026-09-04", "v0.2", "역순 기록", ""),
            },
        )
        require_issue(C.check(descending), "개정 이력", "커지지 않음")

        saturated = temp / "DXS-AX-TST-포화_개정기록-20260905-v0.4.hwpx"
        write_revision_variant(
            output,
            saturated,
            {
                2: ("2026-09-03", "v0.2", "두 번째", ""),
                3: ("2026-09-04", "v0.3", "세 번째", ""),
                4: ("2026-09-05", "v0.4", "네 번째", ""),
            },
        )
        require_issue(C.check(saturated), "개정 이력", "빈 행이 없어")

        missing_revision = temp / "DXS-AX-TST-개정표_누락-20260902-v0.1.hwpx"
        missing_entries = H.read_hwpx(output)
        missing_section = H.get_text(missing_entries, H.SECTION).replace("개정일자", "개정 일자", 1)
        H.set_text(missing_entries, H.SECTION, missing_section)
        H.write_hwpx(missing_entries, missing_revision)
        require_issue(C.check(missing_revision), "개정 이력", "1개가 아님")

        bad_signature = temp / "DXS-AX-TST-표지_시그니처_오류-20260902-v0.1.hwpx"
        signature_entries = H.read_hwpx(output)
        signature_section = (
            H.get_text(signature_entries, H.SECTION)
            .replace("문서정보", "문서안내")
            .replace("문서 정보", "문서 안내")
        )
        H.set_text(signature_entries, H.SECTION, signature_section)
        H.write_hwpx(signature_entries, bad_signature)
        require_issue(C.check(bad_signature), "승인 템플릿 경계", "시그니처")

        row_overflow = temp / "DXS-AX-TST-개정표_행범위_오류-20260902-v0.1.hwpx"
        overflow_entries = H.read_hwpx(output)
        overflow_section = H.get_text(overflow_entries, H.SECTION)
        overflow_start, overflow_end, overflow_table = revision_table(overflow_section)
        table_rows = re.findall(r"<hp:tr(?:\s[^>]*)?>.*?</hp:tr>", overflow_table, re.S)
        if not table_rows:
            raise AssertionError("개정 이력표의 실제 행을 찾지 못함")
        hidden_row = table_rows[-1].replace('rowAddr="4"', 'rowAddr="5"')
        if hidden_row == table_rows[-1]:
            raise AssertionError("개정 이력표 범위 밖 행 변형에 실패함")
        overflow_table = overflow_table.replace("</hp:tbl>", hidden_row + "</hp:tbl>", 1)
        H.set_text(
            overflow_entries,
            H.SECTION,
            overflow_section[:overflow_start] + overflow_table + overflow_section[overflow_end:],
        )
        H.write_hwpx(overflow_entries, row_overflow)
        require_issue(C.check(row_overflow), "개정 이력", "rowCnt")

        oversized_count = recorded_table.replace('rowCnt="5"', 'rowCnt="' + "9" * 5000 + '"', 1)
        oversized_analysis = H.analyze_revision_table(
            oversized_count,
            require_record=True,
            require_empty_row=True,
        )
        if not any("rowCnt" in detail for detail in oversized_analysis.issues):
            raise AssertionError("과도한 rowCnt를 안전하게 거부하지 못함")

        # 잘못된 경로와 기존 대상은 본문이나 기존 파일을 전혀 건드리지 않고 거부한다.
        wrong_version = temp / "DXS-AX-TST-요청_버전불일치-20260902-v0.2.hwpx"
        try:
            B.build(
                template,
                content,
                wrong_version,
                cover,
                artifact_version="v0.1",
                revision_date=revision_date,
            )
        except H.HeadlessHwpxError:
            pass
        else:
            raise AssertionError("요청 버전과 다른 출력 파일명을 거부하지 않음")
        if wrong_version.exists():
            raise AssertionError("파일명 검증 실패 뒤 출력 파일이 남음")

        multiple_target = temp / "DXS-AX-TST-요청_v0.1_복수버전-20260902-v0.1.hwpx"
        try:
            B.build(
                template,
                content,
                multiple_target,
                cover,
                artifact_version="v0.1",
                revision_date=revision_date,
            )
        except H.HeadlessHwpxError:
            pass
        else:
            raise AssertionError("복수 버전 토큰 출력 파일명을 거부하지 않음")
        if multiple_target.exists():
            raise AssertionError("복수 버전 토큰 검증 실패 뒤 출력 파일이 남음")

        existing = temp / "DXS-AX-TST-기존_출력-20260902-v0.1.hwpx"
        sentinel = b"existing-user-file"
        existing.write_bytes(sentinel)
        try:
            B.build(
                template,
                content,
                existing,
                cover,
                revision_date=revision_date,
            )
        except H.HeadlessHwpxError:
            pass
        else:
            raise AssertionError("기존 출력 대상을 거부하지 않음")
        if existing.read_bytes() != sentinel:
            raise AssertionError("실패 처리에서 기존 사용자 파일을 변경하거나 삭제함")
        cli = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "build_headless_artifact.py"),
                "--content", str(content),
                "-o", str(existing),
                "--agency", cover["agency"],
                "--program", cover["program"],
                "--project-number", cover["project_number"],
                "--project", cover["project"],
                "--title", cover["title"],
                "--document-type", cover["document_type"],
                "--revision-date", revision_date,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        )
        if cli.returncode != 2 or existing.read_bytes() != sentinel:
            raise AssertionError(
                "CLI 실패 처리에서 기존 사용자 파일을 보존하지 못함: "
                + cli.stdout
                + cli.stderr
            )

        A.apply(output, output2)
        if C.check(output2):
            raise AssertionError("두 번째 적용 후 검사 실패")
        if digest(output) != digest(output2):
            raise AssertionError("경량 서식 적용이 멱등하지 않음")

        entries = H.read_hwpx(output)
        section0 = next(entry for entry in entries if entry.name == H.SECTION)
        entries.append(
            H.Entry(
                name="Contents/section1.xml",
                data=section0.data,
                compress_type=section0.compress_type,
            )
        )
        try:
            H.write_hwpx(entries, unsupported)
        except H.HeadlessHwpxError:
            pass
        else:
            raise AssertionError("다중 섹션 문서를 거부하지 않음")
        if unsupported.exists():
            raise AssertionError("지원하지 않는 문서의 출력이 남음")

    if digest(template) != template_before:
        raise AssertionError("승인 템플릿이 수정됨")
    print("AX1 headless HWPX acceptance test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
