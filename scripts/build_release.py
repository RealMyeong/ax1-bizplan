#!/usr/bin/env python3
"""Synchronize, validate, and package the AX1 Bizplan skill suite."""

from __future__ import annotations

import importlib.util
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
SUITE_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
SKILLS_ROOT = ROOT / "skills"
DIST_ROOT = ROOT / "dist"
PLUGIN_NAME = "ax1-bizplan"
REPOSITORY_URL = "https://github.com/RealMyeong/ax1-bizplan"
FEEDBACK_FORM_URL = "https://forms.gle/GG6GYrgboA4pnkVE6"
FORBIDDEN_ARTIFACT_SUFFIXES = {
    ".hwp",
    ".hwpx",
    ".docx",
    ".pdf",
    ".pptx",
    ".xlsx",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}

GENERAL_SKILLS = (
    "bizplan-draft",
    "bizplan-review",
    "bizplan-revise",
    "bizplan-preflight",
)
ALL_SKILLS = (
    "bizplan-prepare",
    *GENERAL_SKILLS,
    "bizplan-hwpx",
    "bizplan-artifact-format",
    "bizplan-evidence-update",
)

APPROVED_HWPX_ASSET = Path("skills/bizplan-hwpx/assets/templates/ax1-deliverable-cover.hwpx")
HWPX_TEMPLATE_MANIFEST = Path("skills/bizplan-hwpx/assets/templates/template-manifest.json")
CONTRIBUTOR_POLICY_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "docs/pr-operating-policy.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "scripts/validate_pr.py",
)

GENERAL_REFERENCES = {
    "01-core-principles.md": "shared/core/01-core-principles.md",
    "02-format-style-guide.md": "shared/core/02-format-style-guide.md",
    "03-source-and-uncertainty.md": "shared/core/03-source-priority-and-uncertainty.md",
    "04-kpi-framework.md": "shared/core/04-kpi-framework.md",
    "05-project-profile.md": "shared/profiles/pi-lam-manufacturing-physical-ai-2026.md",
    "06-evaluator-lens.md": "shared/core/05-evaluator-lens.md",
    "07-artifact-workflow.md": "shared/core/07-artifact-workflow.md",
    "10-artifact-version-management.md": "shared/core/10-artifact-version-management.md",
    "11-artifact-synchronization.md": "shared/core/11-artifact-synchronization.md",
    "12-user-confirmation-gate.md": "shared/core/12-user-confirmation-gate.md",
}

GENERAL_ASSETS = {
    "artifact-sync-ledger-template.md": "shared/templates/artifact-sync-ledger-template.md",
    "artifact-version-ledger-template.md": "shared/templates/artifact-version-ledger-template.md",
    "change-log-template.md": "shared/templates/change-log-template.md",
    "document-style-profile-template.md": "shared/templates/document-style-profile-template.md",
    "indicator-ledger-template.csv": "shared/templates/indicator-ledger-template.csv",
    "review-report-template.md": "shared/templates/review-report-template.md",
    "review-response-matrix.md": "shared/templates/review-response-matrix.md",
    "source-inventory-template.md": "shared/templates/source-inventory-template.md",
}

EVIDENCE_REFERENCES = {
    "01-update-policy.md": "shared/core/06-evidence-update-policy.md",
    "02-core-principles.md": "shared/core/01-core-principles.md",
    "03-current-evaluator-lens.md": "shared/core/05-evaluator-lens.md",
    "04-current-project-profile.md": "shared/profiles/pi-lam-manufacturing-physical-ai-2026.md",
    "05-profile-template.md": "shared/profiles/profile-template.md",
    "06-user-confirmation-gate.md": "shared/core/12-user-confirmation-gate.md",
}

CONFIRMATION_REFERENCES = {
    "bizplan-prepare": "references/03-user-confirmation-gate.md",
    "bizplan-draft": "references/12-user-confirmation-gate.md",
    "bizplan-review": "references/12-user-confirmation-gate.md",
    "bizplan-revise": "references/12-user-confirmation-gate.md",
    "bizplan-preflight": "references/12-user-confirmation-gate.md",
    "bizplan-hwpx": "references/07-user-confirmation-gate.md",
    "bizplan-artifact-format": "references/05-user-confirmation-gate.md",
    "bizplan-evidence-update": "references/06-user-confirmation-gate.md",
}


def copy_file(source: str, target: Path) -> None:
    source_path = ROOT / source
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)


def sync_shared_resources() -> None:
    for skill_name in GENERAL_SKILLS:
        skill = SKILLS_ROOT / skill_name
        for target_name, source in GENERAL_REFERENCES.items():
            copy_file(source, skill / "references" / target_name)
        for target_name, source in GENERAL_ASSETS.items():
            copy_file(source, skill / "assets" / target_name)

    evidence = SKILLS_ROOT / "bizplan-evidence-update"
    for target_name, source in EVIDENCE_REFERENCES.items():
        copy_file(source, evidence / "references" / target_name)

    for skill_name in ("bizplan-review", "bizplan-preflight"):
        copy_file("shared/tools/advisory_lint.py", SKILLS_ROOT / skill_name / "scripts" / "advisory_lint.py")

    copy_file(
        "shared/core/10-artifact-version-management.md",
        SKILLS_ROOT / "bizplan-prepare" / "references" / "01-artifact-version-management.md",
    )
    copy_file(
        "shared/templates/artifact-version-ledger-template.md",
        SKILLS_ROOT / "bizplan-prepare" / "assets" / "artifact-version-ledger-template.md",
    )
    copy_file(
        "shared/core/11-artifact-synchronization.md",
        SKILLS_ROOT / "bizplan-prepare" / "references" / "02-artifact-synchronization.md",
    )
    copy_file(
        "shared/core/12-user-confirmation-gate.md",
        SKILLS_ROOT / "bizplan-prepare" / "references" / "03-user-confirmation-gate.md",
    )
    copy_file(
        "shared/templates/artifact-sync-ledger-template.md",
        SKILLS_ROOT / "bizplan-prepare" / "assets" / "artifact-sync-ledger-template.md",
    )
    copy_file(
        "shared/core/10-artifact-version-management.md",
        SKILLS_ROOT / "bizplan-hwpx" / "references" / "05-artifact-version-management.md",
    )
    copy_file(
        "shared/templates/artifact-version-ledger-template.md",
        SKILLS_ROOT / "bizplan-hwpx" / "assets" / "artifact-version-ledger-template.md",
    )
    copy_file(
        "shared/core/11-artifact-synchronization.md",
        SKILLS_ROOT / "bizplan-hwpx" / "references" / "06-artifact-synchronization.md",
    )
    copy_file(
        "shared/core/12-user-confirmation-gate.md",
        SKILLS_ROOT / "bizplan-hwpx" / "references" / "07-user-confirmation-gate.md",
    )
    copy_file(
        "shared/templates/artifact-sync-ledger-template.md",
        SKILLS_ROOT / "bizplan-hwpx" / "assets" / "artifact-sync-ledger-template.md",
    )


def validate_frontmatter(skill: Path) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"{skill.name}: invalid SKILL.md frontmatter")
    frontmatter = match.group(1)
    name_match = re.search(r"^name:\s*([^\n]+)$", frontmatter, flags=re.MULTILINE)
    if not name_match or name_match.group(1).strip().strip('"\'') != skill.name:
        raise ValueError(f"{skill.name}: frontmatter name does not match folder")
    if not re.search(r"^description:\s*\S", frontmatter, flags=re.MULTILINE):
        raise ValueError(f"{skill.name}: description is missing")
    if re.search(r"^compatibility:", frontmatter, flags=re.MULTILINE):
        raise ValueError(f"{skill.name}: unsupported compatibility frontmatter key")
    version_match = re.search(
        r"^\s+version:\s*[\"']?(\d+\.\d+\.\d+)[\"']?\s*$",
        frontmatter,
        flags=re.MULTILINE,
    )
    if not version_match:
        raise ValueError(f"{skill.name}: metadata version must use semantic versioning")
    return version_match.group(1)


def validate_openai_yaml(skill: Path) -> None:
    path = skill / "agents" / "openai.yaml"
    text = path.read_text(encoding="utf-8")
    required = ("interface:", "display_name:", "short_description:", "default_prompt:", "policy:")
    if any(token not in text for token in required):
        raise ValueError(f"{skill.name}: incomplete agents/openai.yaml")
    if f"${skill.name}" not in text:
        raise ValueError(f"{skill.name}: default_prompt must mention ${skill.name}")
    if not re.search(r"allow_implicit_invocation:\s*true\s*$", text, flags=re.MULTILINE):
        raise ValueError(f"{skill.name}: implicit invocation is not enabled")


def validate_references(skill: Path) -> None:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    paths = set(re.findall(r"\]\(((?:references|assets|scripts)/[^)]+)\)", text))
    paths.update(re.findall(r"`((?:references|assets|scripts)/[^`\s]+)`", text))
    missing = [path for path in sorted(paths) if not (skill / Path(path)).is_file()]
    if missing:
        raise ValueError(f"{skill.name}: missing referenced files: {', '.join(missing)}")


def validate_lint_examples() -> None:
    module_path = ROOT / "shared" / "tools" / "advisory_lint.py"
    spec = importlib.util.spec_from_file_location("advisory_lint", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load advisory_lint.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    generic = (ROOT / "examples" / "generic-non-ai-plan.txt").read_text(encoding="utf-8-sig").splitlines()
    layout = (ROOT / "examples" / "layout-warning-plan.txt").read_text(encoding="utf-8-sig").splitlines()
    generic_codes = {item.code for item in module.scan(generic, nominal=True, no_period=True)}
    layout_codes = {item.code for item in module.scan(layout, nominal=True, no_period=True)}
    if "P001" not in generic_codes:
        raise ValueError("lint example: placeholder was not detected")
    if not {"P002", "L001", "S002"}.issubset(layout_codes):
        raise ValueError("lint example: expected layout/style issues were not detected")


def validate_plugin() -> None:
    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "name": PLUGIN_NAME,
        "version": SUITE_VERSION,
        "skills": "./skills/",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"plugin.json: {key} must be {value!r}")


def validate_no_private_artifacts() -> None:
    forbidden = [
        path.relative_to(ROOT).as_posix()
        for path in SKILLS_ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in FORBIDDEN_ARTIFACT_SUFFIXES
        and path.relative_to(ROOT) != APPROVED_HWPX_ASSET
    ]
    if forbidden:
        raise ValueError(
            "skills contain forbidden document or credential artifacts: "
            + ", ".join(sorted(forbidden))
        )


def validate_confirmation_gate() -> None:
    if set(CONFIRMATION_REFERENCES) != set(ALL_SKILLS):
        missing = sorted(set(ALL_SKILLS) - set(CONFIRMATION_REFERENCES))
        extra = sorted(set(CONFIRMATION_REFERENCES) - set(ALL_SKILLS))
        raise ValueError(
            "confirmation gate map must exactly match ALL_SKILLS; "
            f"missing={missing}, extra={extra}"
        )
    canonical = (ROOT / "shared" / "core" / "12-user-confirmation-gate.md").read_bytes()
    for skill_name, reference in CONFIRMATION_REFERENCES.items():
        skill = SKILLS_ROOT / skill_name
        skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
        reference_path = skill / reference
        if not reference_path.is_file() or reference_path.read_bytes() != canonical:
            raise ValueError(f"{skill_name}: confirmation gate reference is missing or stale")
        if "# 작업 시작 전 사용자 이해 확인" not in skill_text:
            raise ValueError(f"{skill_name}: confirmation gate heading is missing")
        if f"]({reference})" not in skill_text:
            raise ValueError(f"{skill_name}: confirmation gate reference is not linked")
        if "별도 메시지" not in skill_text or "동의" not in skill_text:
            raise ValueError(f"{skill_name}: explicit subsequent-turn confirmation is missing")


def validate_contributor_policy() -> None:
    for relative in CONTRIBUTOR_POLICY_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    pr_template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    for token in ("VERSION", ".changes/", "confirmation gate", "HWPX"):
        if token not in agents:
            raise ValueError(f"AGENTS.md: required contributor rule missing: {token}")
    for token in ("VERSION", ".changes/", "개인정보", "배포자"):
        if token not in contributing:
            raise ValueError(f"CONTRIBUTING.md: required policy missing: {token}")
    for token in ("본문과 표 셀 줄간격 160%", ".changes/<주제>.md", "한컴 시각 검증"):
        if token not in pr_template:
            raise ValueError(f"PR template: required checklist missing: {token}")


def validate_headless_scripts_are_stdlib_only() -> None:
    script_root = SKILLS_ROOT / "bizplan-hwpx" / "scripts"
    paths = [
        script_root / "headless_hwpx.py",
        script_root / "format_headless_artifact.py",
        script_root / "check_headless_artifact.py",
        script_root / "build_headless_artifact.py",
    ]
    local_modules = {path.stem for path in paths}
    allowed = set(sys.stdlib_module_names) | local_modules
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        external = sorted(imported - allowed)
        if external:
            raise ValueError(f"{path.relative_to(ROOT)} imports non-stdlib modules: {external}")


def validate_approved_hwpx_asset() -> None:
    asset = ROOT / APPROVED_HWPX_ASSET
    manifest_path = ROOT / HWPX_TEMPLATE_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "schemaVersion": "ax1.hwpx-template/v1",
        "file": asset.name,
        "sections": 1,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"template manifest: {key} must be {value!r}")
    actual_sha = hashlib.sha256(asset.read_bytes()).hexdigest()
    if manifest.get("sha256") != actual_sha:
        raise ValueError("approved HWPX template SHA-256 mismatch")
    placeholders = set(manifest.get("placeholders", []))
    expected_placeholders = {
        "[발주기관]",
        "[사업명]",
        "[과제번호]",
        "[세부 사업명]",
        "[산출물 제목]",
        "[문서 유형]",
    }
    if placeholders != expected_placeholders:
        raise ValueError("template manifest placeholders are incomplete")

    with zipfile.ZipFile(asset) as archive:
        infos = archive.infolist()
        if archive.testzip() is not None:
            raise ValueError("approved HWPX template CRC check failed")
        if not infos or infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
            raise ValueError("approved HWPX template mimetype must be first and stored")
        if archive.read("mimetype").strip() != b"application/hwp+zip":
            raise ValueError("approved HWPX template mimetype is invalid")
        section_names = sorted(
            info.filename
            for info in infos
            if re.fullmatch(r"Contents/section\d+\.xml", info.filename)
        )
        if section_names != ["Contents/section0.xml"]:
            raise ValueError("approved HWPX template must contain one section0.xml")
        text_parts = []
        for info in infos:
            if (info.filename == "mimetype" or info.filename.startswith("BinData/")) and info.compress_type != zipfile.ZIP_STORED:
                raise ValueError(f"approved HWPX template part must be stored: {info.filename}")
            if info.filename.lower().endswith((".xml", ".hpf")):
                data = archive.read(info.filename)
                ET.fromstring(data)
                text_parts.append(data.decode("utf-8"))
            elif info.filename == "Preview/PrvText.txt":
                text_parts.append(archive.read(info.filename).decode("utf-8"))
        text = "\n".join(text_parts)
    for placeholder in expected_placeholders:
        if placeholder not in text:
            raise ValueError(f"approved HWPX template placeholder missing: {placeholder}")
    # 특정 PR 표본값을 검사 코드에 다시 저장하지 않는다. 실제 과제번호 형식과
    # 개인 작성자 메타데이터를 일반 규칙으로 차단한다.
    if re.search(r"\b[A-Z]{2,10}-\d{4}-\d{6,12}\b", text):
        raise ValueError("approved HWPX template contains a filled project number")
    author_values = re.findall(
        r'<opf:meta name="(?:creator|lastsaveby)" content="([^"]*)"',
        text,
    )
    if not author_values or any(value != "AX1" for value in author_values):
        raise ValueError("approved HWPX template author metadata must be AX1")
    date_values = re.findall(
        r'<opf:meta name="(?:CreatedDate|ModifiedDate|date)" content="([^"]*)"',
        text,
    )
    if any(value for value in date_values):
        raise ValueError("approved HWPX template must not retain document dates")
    pii_patterns = (
        r"\b\d{6}-[1-4]\d{6}\b",
        r"\b01[016789]-?\d{3,4}-?\d{4}\b",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    )
    if any(re.search(pattern, text) for pattern in pii_patterns):
        raise ValueError("approved HWPX template contains high-confidence personal information")


def validate_headless_acceptance() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "headless_hwpx_acceptance_test.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise ValueError(
            "headless HWPX acceptance test failed:\n"
            + result.stdout
            + result.stderr
        )


def validate_skills() -> dict[str, str]:
    validate_no_private_artifacts()
    versions: dict[str, str] = {}
    for skill_name in ALL_SKILLS:
        skill = SKILLS_ROOT / skill_name
        if not (skill / "SKILL.md").is_file():
            raise FileNotFoundError(skill / "SKILL.md")
        versions[skill_name] = validate_frontmatter(skill)
        validate_openai_yaml(skill)
        validate_references(skill)
    validate_confirmation_gate()
    validate_contributor_policy()
    validate_headless_scripts_are_stdlib_only()
    validate_approved_hwpx_asset()
    validate_headless_acceptance()
    validate_lint_examples()
    validate_plugin()
    return versions


def add_tree(archive: zipfile.ZipFile, source_root: Path, archive_root: Path) -> None:
    for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
        if "__pycache__" in path.parts:
            continue
        archive.write(path, archive_root / path.relative_to(source_root))


def build_zips(versions: dict[str, str]) -> None:
    if DIST_ROOT.exists():
        shutil.rmtree(DIST_ROOT)
    skill_zip_root = DIST_ROOT / "skills"
    skill_zip_root.mkdir(parents=True)

    for skill_name in ALL_SKILLS:
        skill = SKILLS_ROOT / skill_name
        output = skill_zip_root / f"{skill_name}-v{versions[skill_name]}.zip"
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            add_tree(archive, skill, Path(skill_name))

    plugin_output = DIST_ROOT / f"{PLUGIN_NAME}-v{SUITE_VERSION}.zip"
    with zipfile.ZipFile(plugin_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        add_tree(archive, ROOT / ".codex-plugin", Path(PLUGIN_NAME) / ".codex-plugin")
        add_tree(archive, SKILLS_ROOT, Path(PLUGIN_NAME) / "skills")


def write_checksums() -> None:
    paths = sorted(DIST_ROOT.rglob("*.zip"))
    lines = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(DIST_ROOT).as_posix()}")
    (DIST_ROOT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def changelog_section(version: str) -> str:
    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    headings = list(re.finditer(
        rf"^##\s+v{re.escape(version)}(?=\s|$).*?$",
        text,
        flags=re.MULTILINE,
    ))
    if not headings:
        raise ValueError(f"CHANGELOG.md: missing section for v{version}")
    if len(headings) > 1:
        raise ValueError(f"CHANGELOG.md: duplicate sections for v{version}")
    heading = headings[0]
    if re.fullmatch(
        rf"## v{re.escape(version)}(?:\s+-\s+[^\n]+)?\s*",
        heading.group(0),
    ) is None:
        raise ValueError(f"CHANGELOG.md: invalid heading for v{version}")
    remainder = text[heading.end() :]
    next_heading = re.search(r"^##\s+", remainder, flags=re.MULTILINE)
    body = remainder[: next_heading.start()] if next_heading else remainder
    body = body.strip()
    if not body or not any(line.startswith("- ") for line in body.splitlines()):
        raise ValueError(f"CHANGELOG.md: v{version} must contain release bullets")
    return body


def write_release_notes(versions: dict[str, str]) -> None:
    highlights = changelog_section(SUITE_VERSION)
    lines = [
        f"# AX1 Bizplan v{SUITE_VERSION}",
        "",
        "## 주요 변경사항",
        "",
        highlights,
        "",
        "## 설치·업데이트",
        "",
        f"- 전체 묶음: `{PLUGIN_NAME}-v{SUITE_VERSION}.zip`",
        "- 필요한 스킬만 설치할 때: Release의 개별 스킬 ZIP",
        "- 다운로드 후 `SHA256SUMS.txt`로 파일 무결성 확인",
        "- 업데이트 전 기존 사용자 스킬을 백업한 뒤 새 버전 설치",
        "",
        "## 포함 스킬",
        "",
        "| 스킬 | 버전 |",
        "|---|---:|",
    ]
    lines.extend(f"| `{name}` | `{version}` |" for name, version in versions.items())
    lines.extend(
        [
            "",
            "## 안내",
            "",
            f"- [전체 변경이력]({REPOSITORY_URL}/blob/v{SUITE_VERSION}/CHANGELOG.md)",
            f"- [팀원 설치·활용 안내]({REPOSITORY_URL}/blob/v{SUITE_VERSION}/docs/team-guide.md)",
            f"- [개선 요청 Form]({FEEDBACK_FORM_URL})",
            "",
        ]
    )
    (DIST_ROOT / "RELEASE_NOTES.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    sync_shared_resources()
    versions = validate_skills()
    build_zips(versions)
    write_release_notes(versions)
    write_checksums()
    version_summary = ", ".join(f"{name}=v{version}" for name, version in versions.items())
    print(f"Built {PLUGIN_NAME} v{SUITE_VERSION}: {version_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
