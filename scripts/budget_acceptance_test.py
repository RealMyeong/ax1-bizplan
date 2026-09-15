#!/usr/bin/env python3
"""Blank-template corruption and isolated package regressions (stdlib only)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/ax1-budget"
spec = importlib.util.spec_from_file_location("budget_template", SKILL / "scripts/check_budget_template.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ax1-budget-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "ax1-budget"
        shutil.copytree(SKILL, self.root)
        self.asset = self.root / "assets/templates/ax1-budget-ledger.xlsx"

    def rewrite(self, transform):
        with ZipFile(self.asset) as z:
            parts = {n: z.read(n) for n in z.namelist()}
        transform(parts)
        with ZipFile(self.asset, "w", ZIP_DEFLATED) as z:
            for name, data in parts.items():
                z.writestr(name, data)
        path = self.asset.with_name("template-manifest.json")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["sha256"] = hashlib.sha256(self.asset.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    def test_template_is_blank_and_complete(self):
        result = checker.check(self.root)
        self.assertEqual(result["formulas"], 2032)
        self.assertEqual(result["sheets"], 4)

    def test_hash_mismatch_rejected(self):
        with self.asset.open("ab") as stream:
            stream.write(b"unexpected edit")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            checker.check(self.root)

    def test_filled_input_rejected_even_with_new_hash(self):
        def fill(parts):
            path = "xl/worksheets/sheet2.xml"
            tree = ET.fromstring(parts[path])
            row = tree.find("s:sheetData/s:row[@r='7']", checker.NS)
            cell = row.find("s:c[@r='A7']", checker.NS)
            if cell is None:
                cell = ET.SubElement(row, f"{{{checker.NS['s']}}}c", {"r": "A7"})
            cell.set("t", "n")
            ET.SubElement(cell, f"{{{checker.NS['s']}}}v").text = "123"
            parts[path] = ET.tostring(tree, encoding="utf-8")
        self.rewrite(fill)
        with self.assertRaisesRegex(ValueError, "filled transaction"):
            checker.check(self.root)

    def test_external_relationship_rejected_even_with_new_hash(self):
        def external(parts):
            name = "_rels/.rels"
            root = ET.fromstring(parts[name])
            ET.SubElement(root, "Relationship", {"Id": "rExternal", "Type": "hyperlink",
                                                 "Target": "https://example.invalid", "TargetMode": "External"})
            parts[name] = ET.tostring(root, encoding="utf-8")
        self.rewrite(external)
        with self.assertRaisesRegex(ValueError, "external relationship"):
            checker.check(self.root)

    def test_missing_chart_rejected_even_with_new_hash(self):
        self.rewrite(lambda parts: parts.pop("xl/drawings/charts/chart1.xml"))
        with self.assertRaisesRegex(ValueError, "chart missing"):
            checker.check(self.root)

    def test_isolated_template_checker(self):
        result = subprocess.run([sys.executable, "-X", "utf8", str(self.root / "scripts/check_budget_template.py")],
                                cwd=self.root.parent, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def packages():
    suite = (ROOT / "VERSION").read_text().strip()
    version = re.search(r'\bversion:\s*"([0-9.]+)"', (SKILL / "SKILL.md").read_text(encoding="utf-8")).group(1)
    paths = [(ROOT / f"dist/ax1-bizplan-v{suite}.zip", "ax1-bizplan/skills/ax1-budget"),
             (ROOT / f"dist/skills/ax1-budget-v{version}.zip", "ax1-budget")]
    for archive_path, relative in paths:
        with tempfile.TemporaryDirectory(prefix="ax1-budget-package-") as folder:
            with ZipFile(archive_path) as archive:
                archive.extractall(folder)
            root = Path(folder) / relative
            for source in SKILL.rglob("*"):
                if source.is_file() and "__pycache__" not in source.parts:
                    target = root / source.relative_to(SKILL)
                    if not target.is_file() or target.read_bytes() != source.read_bytes():
                        raise AssertionError(f"package omitted or changed {source.relative_to(SKILL)}")
            result = subprocess.run([sys.executable, "-X", "utf8", str(root / "scripts/check_budget_template.py")],
                                    cwd=folder, capture_output=True, text=True, encoding="utf-8")
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
    print("PASS: integrated and individual ZIP isolated budget template checks")


if __name__ == "__main__":
    if "--packages" in sys.argv:
        packages()
    else:
        unittest.main()
