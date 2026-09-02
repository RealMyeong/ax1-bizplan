#!/usr/bin/env python3
"""Validate contributor PR boundaries before the suite build runs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTECTED = {"VERSION", ".codex-plugin/plugin.json", "CHANGELOG.md"}
FORBIDDEN_DOCUMENT_SUFFIXES = {".hwp", ".hwpx", ".docx", ".pdf", ".pptx", ".xlsx"}
APPROVED_HWPX_ASSET = "skills/bizplan-hwpx/assets/templates/ax1-deliverable-cover.hwpx"
HWPX_TEMPLATE_MANIFEST = "skills/bizplan-hwpx/assets/templates/template-manifest.json"
MEANINGFUL_PREFIXES = ("skills/", "shared/", "scripts/", ".github/", "docs/")
REQUIRED_FRAGMENT_LABELS = (
    "사용자 효과:",
    "변경 범위:",
    "제외 범위:",
    "검증:",
    "호환성:",
    "기여자:",
)


def changed_files(base: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="PR base commit SHA")
    args = parser.parse_args()
    files = changed_files(args.base)
    errors: list[str] = []

    protected = sorted(PROTECTED & set(files))
    if protected:
        errors.append("기여 PR은 배포자 전용 파일을 수정할 수 없음: " + ", ".join(protected))

    forbidden_documents = sorted(
        path
        for path in files
        if Path(path).suffix.lower() in FORBIDDEN_DOCUMENT_SUFFIXES
        and path != APPROVED_HWPX_ASSET
    )
    if forbidden_documents:
        errors.append(
            "승인 경로 밖의 문서 바이너리는 PR에 포함할 수 없음: "
            + ", ".join(forbidden_documents)
        )
    if APPROVED_HWPX_ASSET in files and HWPX_TEMPLATE_MANIFEST not in files:
        errors.append("승인 HWPX 템플릿 변경에는 template-manifest.json 동시 변경이 필요함")

    meaningful = any(path.startswith(MEANINGFUL_PREFIXES) for path in files)
    fragments = [
        path
        for path in files
        if path.startswith(".changes/") and path.endswith(".md") and path != ".changes/README.md"
    ]
    if meaningful and not fragments:
        errors.append("사용자 영향 변경에는 .changes/<주제>.md 변경 조각이 필요함")
    for fragment in fragments:
        path = ROOT / fragment
        if not path.is_file():
            errors.append(f"변경 조각 파일을 읽을 수 없음: {fragment}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [label for label in REQUIRED_FRAGMENT_LABELS if label not in text]
        if missing:
            errors.append(f"{fragment}: 필수 항목 누락: {', '.join(missing)}")

    if errors:
        print("AX1 PR 정책 검사 실패")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"AX1 PR 정책 검사 통과: 변경 파일 {len(files)}개, 변경 조각 {len(fragments)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
