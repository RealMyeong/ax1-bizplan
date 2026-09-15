#!/usr/bin/env python3
"""Validate the distributed blank template, not a filled project workbook."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SHEETS = ["00_통합현황", "01_구매비용원장", "02_승인예산", "03_코드_안내"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check(skill_root: Path | None = None) -> dict:
    root = skill_root or Path(__file__).resolve().parents[1]
    folder = root / "assets" / "templates"
    manifest = json.loads((folder / "template-manifest.json").read_text(encoding="utf-8"))
    require(manifest.get("schemaVersion") == "ax1.xlsx-template/v1", "invalid manifest schema")
    require(manifest.get("file") == "ax1-budget-ledger.xlsx", "unexpected template path")
    require(manifest.get("sanitized") is True and bool(manifest.get("approvedBy")), "approval missing")
    require(bool(manifest.get("sourceSha256")) and bool(manifest.get("sanitization")), "provenance missing")
    asset = folder / manifest["file"]
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    require(digest == manifest.get("sha256"), "template SHA-256 mismatch")
    with ZipFile(asset) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), "duplicate ZIP parts")
        require(z.testzip() is None, "ZIP CRC failure")
        roots = {}
        for name in names:
            require(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
                    and "\\" not in name, "unsafe ZIP path")
            require(name.lower().endswith((".xml", ".rels")), "unexpected binary or embedded part")
            require(not any(token in name.lower() for token in
                            ("externallink", "connection", "vba", "activex", "embedding", "comment", "person")),
                    "external, executable or personal part")
            data = z.read(name)
            require(b"<!DOCTYPE" not in data and b"<!ENTITY" not in data, "unsafe XML declaration")
            tree = ET.fromstring(data)
            roots[name] = tree
            if name.endswith(".rels"):
                require(not any(r.get("TargetMode") == "External" for r in tree), "external relationship")
            visible = " ".join(tree.itertext())
            require(not re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b01[016789]-?\d{3,4}-?\d{4}\b", visible),
                    "personal contact information")
        wb = roots["xl/workbook.xml"]
        require([s.get("name") for s in wb.findall("s:sheets/s:sheet", NS)] == SHEETS, "sheet topology changed")
        require(all(s.get("state", "visible") == "visible" for s in wb.findall("s:sheets/s:sheet", NS)),
                "hidden worksheet")
        strings = ["".join(t.itertext()) for t in roots["xl/sharedStrings.xml"].findall("s:si", NS)]

        def text(cell: ET.Element) -> str:
            v = cell.find("s:v", NS)
            if cell.get("t") == "s":
                return strings[int(v.text)]
            if cell.get("t") == "inlineStr":
                return "".join(cell.find("s:is", NS).itertext())
            return "" if v is None else v.text or ""

        counts, cells = [], []
        for i in range(1, 5):
            sheet = roots[f"xl/worksheets/sheet{i}.xml"]
            rowcells = {c.get("r"): c for c in sheet.findall(".//s:sheetData/s:row/s:c", NS)}
            cells.append(rowcells)
            counts.append(sum(c.find("s:f", NS) is not None for c in rowcells.values()))
            require(not any(c.get("t") == "e" for c in rowcells.values()), "cached formula error")
            if i in (2, 3):
                for address, c in rowcells.items():
                    if int(re.search(r"\d+$", address).group()) >= 7 and c.find("s:f", NS) is None:
                        require(not text(c), "template contains filled transaction or budget input")
        require(counts == [82, 1350, 600, 0] == manifest.get("formulaCounts"), "formula topology changed")
        require(manifest.get("sheets") == SHEETS, "manifest sheet list changed")
        table_refs = sorted(t.get("ref") for name, t in roots.items() if name.startswith("xl/tables/"))
        require(table_refs == ["A6:AQ156", "A6:S66"] == manifest.get("tables"), "table ranges changed")
        require(sum("/charts/" in n and n.endswith(".xml") for n in names) == 1, "chart missing")
        require([text(cells[3][f"F{r}"]) for r in (5, 6, 7)] == ["주관기관", "참여기관 1", "참여기관 2"],
                "organization placeholders changed")
        validations = roots["xl/worksheets/sheet2.xml"].findall("s:dataValidations/s:dataValidation", NS)
        require(len(validations) == 14, "ledger data validation missing")
        org = [v for v in validations if v.get("sqref") == "AJ7:AJ156"]
        require(len(org) == 1 and org[0].find("s:formula1", NS).text == '"주관기관,참여기관 1,참여기관 2"',
                "organization dropdown does not match placeholders")
    return {"status": "PASS", "sha256": digest, "sheets": len(SHEETS),
            "formulas": sum(counts), "tables": len(table_refs), "charts": 1,
            "scope": "blank template integrity only; not financial or native Excel approval"}


if __name__ == "__main__":
    try:
        print(json.dumps(check(), ensure_ascii=False))
    except (ValueError, KeyError, OSError, ET.ParseError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
