#!/usr/bin/env python3
"""Synchronize, validate, and package the AX1 Bizplan skill suite."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path


sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
SUITE_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
SKILLS_ROOT = ROOT / "skills"
DIST_ROOT = ROOT / "dist"
PLUGIN_NAME = "ax1-bizplan"
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
    "bizplan-evidence-update",
)

GENERAL_REFERENCES = {
    "01-core-principles.md": "shared/core/01-core-principles.md",
    "02-format-style-guide.md": "shared/core/02-format-style-guide.md",
    "03-source-and-uncertainty.md": "shared/core/03-source-priority-and-uncertainty.md",
    "04-kpi-framework.md": "shared/core/04-kpi-framework.md",
    "05-project-profile.md": "shared/profiles/pi-lam-manufacturing-physical-ai-2026.md",
    "06-evaluator-lens.md": "shared/core/05-evaluator-lens.md",
    "07-artifact-workflow.md": "shared/core/07-artifact-workflow.md",
}

GENERAL_ASSETS = {
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
        if path.is_file() and path.suffix.lower() in FORBIDDEN_ARTIFACT_SUFFIXES
    ]
    if forbidden:
        raise ValueError(
            "skills contain forbidden document or credential artifacts: "
            + ", ".join(sorted(forbidden))
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


def main() -> int:
    sync_shared_resources()
    versions = validate_skills()
    build_zips(versions)
    write_checksums()
    version_summary = ", ".join(f"{name}=v{version}" for name, version in versions.items())
    print(f"Built {PLUGIN_NAME} v{SUITE_VERSION}: {version_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
