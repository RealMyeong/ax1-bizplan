#!/usr/bin/env python3
"""Standard-library acceptance test for the AX1 headless HWPX builder."""

from __future__ import annotations

import hashlib
import importlib.util
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


def main() -> int:
    template = H.approved_template(SKILL)
    template_before = digest(template)
    markdown = """# 1. 사업 개요

승인된 AX1 경량 생성기의 수용 테스트 문단입니다.

## 1.1 구현 방식

- 표준 라이브러리만 사용
- 한컴오피스와 COM 창을 실행하지 않음

| 구분 | 확인 결과 |
|---|---|
| 선택 상태 | ☑ 완료 / ☐ 미완료 |
| 줄간격 | 본문 160% / 표 셀 160% |
"""
    cover = {
        "agency": "테스트 발주기관",
        "program": "테스트 사업",
        "project_number": "TEST-0000",
        "project": "테스트 세부사업",
        "title": "AX1 경량 HWPX 수용 테스트",
        "document_type": "검증 문서",
    }

    with tempfile.TemporaryDirectory(prefix="ax1-headless-test-") as temp_dir:
        temp = Path(temp_dir)
        content = temp / "content.md"
        output = temp / "output.hwpx"
        output2 = temp / "output-second.hwpx"
        unsupported = temp / "unsupported.hwpx"
        content.write_text(markdown, encoding="utf-8")
        B.build(template, content, output, cover)
        issues = C.check(output)
        if issues:
            raise AssertionError(issues)
        section = H.get_text(H.read_hwpx(output), H.SECTION)
        for token in ("☑ 완료", "☐ 미완료", "본문 160%", "표 셀 160%"):
            if token not in section:
                raise AssertionError(f"의미·본문 보존 실패: {token}")
        if "□ 완료" in section or "□ 미완료" in section:
            raise AssertionError("체크 상태 기호가 빈 네모로 바뀜")

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
