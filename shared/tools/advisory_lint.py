#!/usr/bin/env python3
"""Advisory plaintext checks for Korean business-plan drafts.

The script intentionally avoids domain-specific keyword requirements.
Default exit code is always 0. With --strict, only high-confidence unresolved
placeholders and duplicate caption identifiers return exit code 1.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Issue:
    code: str
    severity: str
    line: int
    message: str
    text: str


PLACEHOLDER = re.compile(r"(?:TODO|TBD|FIXME|〈[^〉\n]+〉|_{3,})", re.I)
DEFERRED = re.compile(r"(?:추후|향후|협의\s*(?:후|하여)|검토\s*후|시험\s*(?:전|후)).{0,20}(?:확정|결정|정함|수립)")
VAGUE_EVIDENCE = re.compile(r"(?:공인|시험|검증|성적서).{0,35}(?:가능한\s*경우|필요\s*시|한하여|경우에만)")
TARGET_RANGE = re.compile(r"(?:목표|달성|확보).{0,25}\b\d+(?:\.\d+)?\s*[~～-]\s*\d+(?:\.\d+)?")
CAPTION = re.compile(r"^\s*[\[【]?(그림|표)\s*([0-9]+(?:[-.]\d+)?)[\]】]?", re.I)
VISUAL_MARKER = re.compile(r"^\s*[\[【]?(그림|표)\s*[0-9]+", re.I)


def read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            pass
    raise UnicodeError(f"Unsupported text encoding: {path}")


def scan(lines: list[str], nominal: bool, no_period: bool) -> list[Issue]:
    issues: list[Issue] = []
    captions: dict[tuple[str, str], int] = {}
    visual_lines: list[tuple[int, str]] = []

    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue

        if PLACEHOLDER.search(raw):
            issues.append(Issue("P001", "error", i, "미해결 플레이스홀더 또는 TODO가 남아 있음", raw))
        if DEFERRED.search(raw):
            issues.append(Issue("W001", "warning", i, "핵심 기준을 미래 협의로 유예하는 표현인지 확인 필요", raw))
        if VAGUE_EVIDENCE.search(raw):
            issues.append(Issue("W002", "warning", i, "시험·증빙을 조건부로 회피하는 문장인지 확인 필요", raw))
        if TARGET_RANGE.search(raw):
            issues.append(Issue("W003", "warning", i, "자체 목표가 범위형 수치인지 확인 필요", raw))

        if nominal and re.search(r"(?:한다|이다|된다|있다|없다)\.$", line):
            issues.append(Issue("S001", "style", i, "명사형 종결 프로파일과 다른 완결형 문장", raw))
        if no_period and re.search(r"(?:함|임|필요|예정|수행|추진|구축|확보)\.$", line):
            issues.append(Issue("S002", "style", i, "마침표 미사용 프로파일에서 명사형 종결 뒤 마침표가 있음", raw))

        m = CAPTION.match(raw)
        if m:
            key = (m.group(1), m.group(2))
            if key in captions:
                issues.append(Issue("P002", "error", i, f"중복 캡션 번호: {key[0]} {key[1]} (최초 L{captions[key]})", raw))
            else:
                captions[key] = i

        vm = VISUAL_MARKER.match(raw)
        if vm:
            visual_lines.append((i, vm.group(1)))

    # Same-type visual markers with no substantive text between them.
    for (line_a, kind_a), (line_b, kind_b) in zip(visual_lines, visual_lines[1:]):
        if kind_a != kind_b:
            continue
        between = [x.strip() for x in lines[line_a:line_b-1] if x.strip()]
        substantive = [x for x in between if not CAPTION.match(x) and len(re.sub(r"\s+", "", x)) >= 18]
        if not substantive:
            issues.append(Issue("L001", "layout", line_b, f"{kind_a}-{kind_b} 연속배치 사이에 설명·해석 문단이 없는지 확인 필요", lines[line_b-1]))

    return issues


def render_md(issues: list[Issue], path: Path) -> str:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    out = [f"# Advisory lint: {path.name}", "", "이 결과는 보조 점검이며 제출 가능 여부를 단독 판정하지 않음", ""]
    out.append("- " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) if counts else "- 이슈 없음")
    out.append("")
    for issue in issues:
        out.extend([
            f"## [{issue.severity}] {issue.code} · L{issue.line}",
            "",
            issue.message,
            "",
            f"> {issue.text.strip()}",
            "",
        ])
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("file", type=Path)
    p.add_argument("--nominal-ending", action="store_true")
    p.add_argument("--no-terminal-period", action="store_true")
    p.add_argument("--report", choices=("md", "json"), default="md")
    p.add_argument("--strict", action="store_true", help="return 1 only for high-confidence error issues")
    args = p.parse_args()

    text = read_text(args.file)
    issues = scan(text.replace("\f", "\n").splitlines(), args.nominal_ending, args.no_terminal_period)
    if args.report == "json":
        print(json.dumps([asdict(x) for x in issues], ensure_ascii=False, indent=2))
    else:
        print(render_md(issues, args.file))

    if args.strict and any(x.severity == "error" for x in issues):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
