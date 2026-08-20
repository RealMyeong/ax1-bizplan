#!/usr/bin/env python3
"""Run the AX1 HWPX acceptance path through an installed MCP plugin.

The script creates only synthetic documents in a new/empty output directory.
It never edits a user document and does not claim manual Hancom review.  On
Windows, the mixed-form commit receipt is the bounded structural verifier;
the separate render verifier is intentionally left for an isolated optional
check because the pinned upstream stack can block while probing a render
oracle that is not configured.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


READ_TIMEOUT_SECONDS = 180.0
REQUIRED_TOOLS = {
    "mcp_server_health",
    "create_document",
    "get_document_map",
    "get_document_node",
    "query_document_nodes",
    "add_heading",
    "add_paragraph",
    "add_table",
    "add_form_field",
    "list_form_fields",
    "copy_document",
    "search_and_replace",
    "apply_document_commands",
    "analyze_form_fill",
    "apply_form_fill",
    "verify_form_fill",
    "get_document_text",
    "get_table_text",
    "render_preview",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def structured(result: Any) -> dict[str, Any]:
    if bool(getattr(result, "isError", False)):
        raise RuntimeError(f"MCP tool returned an error: {result}")
    payload = getattr(result, "structuredContent", None)
    if isinstance(payload, dict):
        return payload
    for item in getattr(result, "content", ()):
        text = getattr(item, "text", None)
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError(f"MCP tool returned no structured object: {result}")


def find_dict(value: Any, key: str) -> dict[str, Any] | None:
    if isinstance(value, dict):
        candidate = value.get(key)
        if isinstance(candidate, dict):
            return candidate
        for child in value.values():
            found = find_dict(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_dict(child, key)
            if found is not None:
                return found
    return None


def require_open_safety(receipt: dict[str, Any], label: str) -> None:
    open_safety = find_dict(receipt, "openSafety")
    if not open_safety or open_safety.get("ok") is not True:
        raise RuntimeError(f"{label} lacks passing openSafety evidence: {receipt}")


def require_dry_run(receipt: dict[str, Any], label: str) -> None:
    if receipt.get("dryRun") is not True and receipt.get("dry_run") is not True:
        raise RuntimeError(f"{label} did not report dry-run mode: {receipt}")
    if not isinstance(receipt.get("semanticDiff"), dict):
        raise RuntimeError(f"{label} lacks semanticDiff: {receipt}")
    require_open_safety(receipt, label)


def resolve_command(command: str) -> str:
    if Path(command).is_file() or shutil.which(command):
        return command
    if os.name == "nt" and command.lower() in {"uv", "uvx"}:
        candidate = Path.home() / ".local" / "bin" / f"{command}.exe"
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(f"MCP command is not available: {command}")


def detect_chrome() -> str | None:
    configured = os.environ.get("HWPX_AUTOMATION_CHROME_PATH") or os.environ.get(
        "HWPX_MCP_CHROME_PATH"
    )
    candidates = [
        configured,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    return next(
        (str(Path(item)) for item in candidates if item and Path(item).is_file()),
        None,
    )


async def call(
    session: ClientSession, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    return structured(
        await session.call_tool(
            name,
            arguments,
            read_timeout_seconds=READ_TIMEOUT_SECONDS,
        )
    )


async def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"output directory must be new or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    config = json.loads(args.mcp_config.read_text(encoding="utf-8"))
    server = config.get("mcpServers", {}).get("hwpx")
    if not isinstance(server, dict):
        raise RuntimeError(f"MCP config has no 'hwpx' server: {args.mcp_config}")

    command = resolve_command(str(server.get("command", "")))
    command_args = server.get("args") or []
    if not isinstance(command_args, list) or not all(
        isinstance(item, str) for item in command_args
    ):
        raise RuntimeError("MCP command args must be a string list")

    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(name, None)
    environment.update(
        {
            key: str(value)
            for key, value in (server.get("env") or {}).items()
        }
    )
    chrome_path = detect_chrome()
    if chrome_path:
        environment["HWPX_AUTOMATION_CHROME_PATH"] = chrome_path
    environment.update(
        {
            "HWPX_AUTOMATION_WORKSPACE_ROOTS": json.dumps(
                [str(output_dir)], ensure_ascii=False
            ),
            "HWPX_AUTOMATION_WORKFLOW_STORE": str(output_dir / "workflow.sqlite3"),
            "LOG_LEVEL": "ERROR",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )

    source = output_dir / "ax1-hwpx-smoke-source.hwpx"
    edited = output_dir / "ax1-hwpx-smoke-edited.hwpx"
    batch_output = output_dir / "ax1-hwpx-smoke-batch.hwpx"
    form_output = output_dir / "ax1-hwpx-smoke-form-filled.hwpx"
    preview_dir = output_dir / "preview"

    params = StdioServerParameters(
        command=command,
        args=command_args,
        env=environment,
        cwd=output_dir,
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = {item.name for item in (await session.list_tools()).tools}
            missing = sorted(REQUIRED_TOOLS - tools)
            if missing:
                raise RuntimeError(f"required HWPX tools are missing: {missing}")

            health = await call(session, "mcp_server_health", {})
            surface = health.get("toolSurface") or {}
            if surface.get("status") != "ok" or surface.get("missingKeyTools"):
                raise RuntimeError(f"HWPX tool surface is unhealthy: {health}")
            observed = {
                "automation": health.get("version"),
                "core": health.get("pythonHwpxVersion"),
                "plugin": health.get("skillBundleVersion"),
            }
            expected = {
                "automation": args.expected_automation,
                "core": args.expected_core,
                "plugin": args.expected_plugin,
            }
            if observed != expected:
                raise RuntimeError(
                    f"HWPX stack mismatch: expected={expected}, observed={observed}"
                )

            created = await call(
                session,
                "create_document",
                {
                    "filename": str(source),
                    "title": "AX1 HWPX 기능 검증",
                    "author": "AX1 Team",
                },
            )
            require_open_safety(created, "create_document")

            async def dry_then_commit(
                tool: str, base: dict[str, Any], token: str
            ) -> tuple[dict[str, Any], dict[str, Any]]:
                document_map = await call(
                    session,
                    "get_document_map",
                    {"filename": str(source), "detail": "summary"},
                )
                revision = document_map.get("document_revision")
                if not isinstance(revision, str):
                    raise RuntimeError(f"document revision is missing: {document_map}")
                before_hash = sha256(source)
                preview = await call(
                    session,
                    tool,
                    {
                        **base,
                        "filename": str(source),
                        "dry_run": True,
                        "expected_revision": revision,
                        "idempotency_key": f"{token}-dry",
                    },
                )
                require_dry_run(preview, f"{tool} dry-run")
                if sha256(source) != before_hash:
                    raise RuntimeError(f"{tool} dry-run changed the source file")
                committed = await call(
                    session,
                    tool,
                    {
                        **base,
                        "filename": str(source),
                        "dry_run": False,
                        "expected_revision": revision,
                        "idempotency_key": f"{token}-commit",
                    },
                )
                require_open_safety(committed, f"{tool} commit")
                return preview, committed

            heading_dry, heading_commit = await dry_then_commit(
                "add_heading",
                {"text": "AX1 HWPX 기능 검증", "level": 1},
                "heading",
            )
            paragraph_dry, paragraph_commit = await dry_then_commit(
                "add_paragraph",
                {"text": "검증 대상 문구: 초안"},
                "paragraph",
            )
            owner_dry, owner_commit = await dry_then_commit(
                "add_paragraph",
                {"text": "담당자: {{담당자}}"},
                "owner-anchor",
            )
            goal_dry, goal_commit = await dry_then_commit(
                "add_paragraph",
                {"text": "사업목표: 미정"},
                "goal",
            )
            table_dry, table_commit = await dry_then_commit(
                "add_table",
                {
                    "rows": 2,
                    "cols": 2,
                    "data": [["항목", "내용"], ["상태", "초안"]],
                },
                "table",
            )
            form_table_dry, form_table_commit = await dry_then_commit(
                "add_table",
                {
                    "rows": 2,
                    "cols": 2,
                    "data": [["사업명", ""], ["담당 부서", ""]],
                },
                "form-table",
            )

            field_map = await call(
                session,
                "get_document_map",
                {"filename": str(source), "detail": "summary"},
            )
            field_revision = field_map.get("document_revision")
            if not isinstance(field_revision, str):
                raise RuntimeError(f"form-field revision is missing: {field_map}")
            before_field_hash = sha256(source)
            field_dry = await call(
                session,
                "add_form_field",
                {
                    "filename": str(source),
                    "name": "사업명",
                    "prompt": "사업명을 입력하세요",
                    "table_index": 1,
                    "row": 0,
                    "col": 1,
                    "dry_run": True,
                    "expected_revision": field_revision,
                },
            )
            require_dry_run(field_dry, "add_form_field dry-run")
            if sha256(source) != before_field_hash:
                raise RuntimeError("add_form_field dry-run changed the source file")
            field_commit = await call(
                session,
                "add_form_field",
                {
                    "filename": str(source),
                    "name": "사업명",
                    "prompt": "사업명을 입력하세요",
                    "table_index": 1,
                    "row": 0,
                    "col": 1,
                    "dry_run": False,
                    "expected_revision": field_revision,
                },
            )
            require_open_safety(field_commit, "add_form_field commit")
            fields_before = await call(
                session,
                "list_form_fields",
                {"filename": str(source)},
            )
            if "사업명" not in json.dumps(fields_before, ensure_ascii=False):
                raise RuntimeError("the synthetic native form field was not created")

            source_hash = sha256(source)
            copied = await call(
                session,
                "copy_document",
                {
                    "source_filename": str(source),
                    "destination_filename": str(edited),
                },
            )
            require_open_safety(copied, "copy_document")
            if not edited.is_file() or sha256(source) != source_hash:
                raise RuntimeError("copy_document did not preserve the source")

            edited_map = await call(
                session,
                "get_document_map",
                {"filename": str(edited), "detail": "summary"},
            )
            edited_revision = edited_map.get("document_revision")
            if not isinstance(edited_revision, str):
                raise RuntimeError(f"edited document revision is missing: {edited_map}")
            edited_before = sha256(edited)
            replace_dry = await call(
                session,
                "search_and_replace",
                {
                    "filename": str(edited),
                    "find_text": "초안",
                    "replace_text": "확정",
                    "dry_run": True,
                    "expected_revision": edited_revision,
                    "idempotency_key": "replace-dry",
                },
            )
            require_dry_run(replace_dry, "search_and_replace dry-run")
            if sha256(edited) != edited_before:
                raise RuntimeError("search_and_replace dry-run changed the output file")

            replace_commit = await call(
                session,
                "search_and_replace",
                {
                    "filename": str(edited),
                    "find_text": "초안",
                    "replace_text": "확정",
                    "dry_run": False,
                    "expected_revision": edited_revision,
                    "idempotency_key": "replace-commit",
                },
            )
            require_open_safety(replace_commit, "search_and_replace commit")

            edited_hash = sha256(edited)
            goal_query = await call(
                session,
                "query_document_nodes",
                {
                    "filename": str(edited),
                    "selector": 'paragraph:contains("사업목표")',
                    "limit": 5,
                    "node_depth": 0,
                    "child_limit": 5,
                },
            )
            goal_nodes = goal_query.get("nodes") or []
            if len(goal_nodes) != 1 or not isinstance(goal_nodes[0].get("path"), str):
                raise RuntimeError(f"goal canonical path is not unique: {goal_query}")
            batch_revision = goal_query.get("revision")
            if not isinstance(batch_revision, str):
                raise RuntimeError(f"batch revision is missing: {goal_query}")
            batch_commands = [
                {
                    "commandId": "setGoal",
                    "op": "set",
                    "path": goal_nodes[0]["path"],
                    "properties": {
                        "text": "사업목표: 실현 가능한 HWPX 자동화 검증"
                    },
                }
            ]
            batch_arguments = {
                "filename": str(edited),
                "output": str(batch_output),
                "commands": batch_commands,
                "expected_revision": batch_revision,
                "quality": "transparent",
                "verification_requirements": [
                    "package",
                    "reopen",
                    "openSafety",
                    "semanticDiff",
                    "bytePreservation",
                ],
                "overwrite": False,
            }
            batch_dry = await call(
                session,
                "apply_document_commands",
                {
                    **batch_arguments,
                    "dry_run": True,
                    "idempotency_key": "batch-dry",
                },
            )
            require_dry_run(batch_dry, "apply_document_commands dry-run")
            if batch_output.exists() or sha256(edited) != edited_hash:
                raise RuntimeError("apply_document_commands dry-run wrote output or changed input")
            batch_commit = await call(
                session,
                "apply_document_commands",
                {
                    **batch_arguments,
                    "dry_run": False,
                    "idempotency_key": "batch-commit",
                },
            )
            if batch_commit.get("ok") is not True or batch_commit.get("rolledBack") is True:
                raise RuntimeError(f"apply_document_commands commit failed: {batch_commit}")
            require_open_safety(batch_commit, "apply_document_commands commit")
            if not batch_output.is_file() or sha256(edited) != edited_hash:
                raise RuntimeError("apply_document_commands did not preserve its input")

            batch_hash = sha256(batch_output)
            form_anchor_query = await call(
                session,
                "query_document_nodes",
                {
                    "filename": str(batch_output),
                    "selector": 'paragraph:contains("검증 대상 문구")',
                    "limit": 5,
                    "node_depth": 0,
                    "child_limit": 5,
                },
            )
            anchor_nodes = form_anchor_query.get("nodes") or []
            if len(anchor_nodes) != 1 or not isinstance(anchor_nodes[0].get("path"), str):
                raise RuntimeError(f"form canonical path is not unique: {form_anchor_query}")
            form_revision = form_anchor_query.get("revision")
            if not isinstance(form_revision, str):
                raise RuntimeError(f"form revision is missing: {form_anchor_query}")

            form_operations = [
                {
                    "operationId": "native-project-name",
                    "target": {"kind": "nativeField", "name": "사업명"},
                    "value": "AX1 HWPX 검증 사업",
                },
                {
                    "operationId": "label-department",
                    "target": {
                        "kind": "labelCell",
                        "sectionPath": "/section[1]",
                        "tableIndex": 1,
                        "cellAnchor": {
                            "label": "담당 부서",
                            "direction": "right",
                        },
                    },
                    "value": "AX1팀",
                },
                {
                    "operationId": "canonical-status",
                    "target": {
                        "kind": "canonicalPath",
                        "path": anchor_nodes[0]["path"],
                    },
                    "value": "검증 대상 문구: 최종",
                },
                {
                    "operationId": "body-owner",
                    "target": {
                        "kind": "bodyAnchor",
                        "sectionPath": "/section[1]",
                        "anchor": "{{담당자}}",
                        "expectedCount": 1,
                    },
                    "value": "AX1 담당자",
                },
            ]

            def form_plan(*, dry_run: bool, idempotency_key: str) -> dict[str, Any]:
                return {
                    "schemaVersion": "hwpx.mixed-form-plan/v1",
                    "source": str(batch_output),
                    "output": str(form_output),
                    "expectedRevision": form_revision,
                    "idempotencyKey": idempotency_key,
                    "dryRun": dry_run,
                    "overwrite": False,
                    "quality": "transparent",
                    "verificationRequirements": [
                        "package",
                        "reopen",
                        "bytePreservation",
                        "openSafety",
                    ],
                    "operations": form_operations,
                }

            form_analysis_dry = await call(
                session,
                "analyze_form_fill",
                {"plan": form_plan(dry_run=True, idempotency_key="form-dry")},
            )
            if form_analysis_dry.get("mutated") is not False or form_output.exists():
                raise RuntimeError(f"analyze_form_fill mutated files: {form_analysis_dry}")
            compiled_dry = form_analysis_dry.get("compiledPlan")
            if not isinstance(compiled_dry, dict):
                raise RuntimeError(f"analyze_form_fill lacks compiledPlan: {form_analysis_dry}")
            form_dry = await call(
                session,
                "apply_form_fill",
                {"plan": compiled_dry},
            )
            require_dry_run(form_dry, "apply_form_fill dry-run")
            if form_output.exists() or sha256(batch_output) != batch_hash:
                raise RuntimeError("apply_form_fill dry-run wrote output or changed input")

            form_analysis_commit = await call(
                session,
                "analyze_form_fill",
                {"plan": form_plan(dry_run=False, idempotency_key="form-commit")},
            )
            compiled_commit = form_analysis_commit.get("compiledPlan")
            if not isinstance(compiled_commit, dict):
                raise RuntimeError(f"commit analysis lacks compiledPlan: {form_analysis_commit}")
            target_kinds = [
                item.get("locatorKind")
                for item in (form_analysis_commit.get("resolutions") or [])
            ]
            if target_kinds != [
                "nativeField",
                "labelCell",
                "canonicalPath",
                "bodyAnchor",
            ]:
                raise RuntimeError(f"mixed-form targets did not all resolve: {target_kinds}")
            form_commit = await call(
                session,
                "apply_form_fill",
                {"plan": compiled_commit},
            )
            if form_commit.get("ok") is not True or form_commit.get("rolledBack") is True:
                raise RuntimeError(f"apply_form_fill commit failed: {form_commit}")
            require_open_safety(form_commit, "apply_form_fill commit")
            committed_form_revision = form_commit.get("documentRevision")
            if not isinstance(committed_form_revision, str) or not form_output.is_file():
                raise RuntimeError(f"form output revision or file is missing: {form_commit}")
            if sha256(batch_output) != batch_hash:
                raise RuntimeError("apply_form_fill changed its source file")
            form_verify = form_commit.get("verificationReceipt")
            if not isinstance(form_verify, dict):
                raise RuntimeError(
                    f"apply_form_fill lacks its verification receipt: {form_commit}"
                )
            if (
                form_verify.get("schemaVersion")
                != "hwpx.form-verification-receipt/v1"
                or form_verify.get("phase") != "apply"
                or form_verify.get("status") != "committed"
                or form_verify.get("ok") is not True
                or form_verify.get("committed") is not True
                or form_verify.get("rolledBack") is not False
            ):
                raise RuntimeError(
                    f"mixed-form verification receipt did not pass: {form_verify}"
                )
            value_verification = form_verify.get("valueVerification")
            source_preservation = form_verify.get("sourcePreservation")
            if not isinstance(value_verification, dict):
                raise RuntimeError(
                    f"mixed-form value verification state is missing: {form_verify}"
                )
            if value_verification.get("status") == "checked":
                if (
                    value_verification.get("ok") is not True
                    or value_verification.get("matchedCount")
                    != value_verification.get("checkCount")
                    or not value_verification.get("checkCount")
                ):
                    raise RuntimeError(
                        f"mixed-form values were not fully verified: {form_verify}"
                    )
            elif not (
                value_verification.get("status") == "deferred"
                and value_verification.get("ok") is None
                and value_verification.get("matchedCount") == 0
                and value_verification.get("checkCount") == 0
            ):
                raise RuntimeError(
                    f"mixed-form value verification has an unsafe state: {form_verify}"
                )
            if (
                not isinstance(source_preservation, dict)
                or source_preservation.get("preserved") is not True
            ):
                raise RuntimeError(
                    f"mixed-form source preservation did not pass: {form_verify}"
                )

            text_receipt = await call(
                session,
                "get_document_text",
                {"filename": str(form_output), "mask": True},
            )
            table_receipt = await call(
                session,
                "get_table_text",
                {"filename": str(form_output), "table_index": 0},
            )
            form_table_receipt = await call(
                session,
                "get_table_text",
                {"filename": str(form_output), "table_index": 1},
            )
            fields_after = await call(
                session,
                "list_form_fields",
                {"filename": str(form_output)},
            )
            text_value = json.dumps(text_receipt, ensure_ascii=False)
            table_value = json.dumps(table_receipt, ensure_ascii=False)
            form_table_value = json.dumps(form_table_receipt, ensure_ascii=False)
            fields_value = json.dumps(fields_after, ensure_ascii=False)
            expected_readback = (
                "검증 대상 문구: 최종",
                "사업목표: 실현 가능한 HWPX 자동화 검증",
                "담당자: AX1 담당자",
            )
            if not all(value in text_value for value in expected_readback):
                raise RuntimeError("document readback lacks batch or form-fill values")
            if "확정" not in table_value:
                raise RuntimeError("table readback lacks the committed replacement")
            if "AX1팀" not in form_table_value or "AX1 HWPX 검증 사업" not in fields_value:
                raise RuntimeError("mixed-form readback lacks label-cell or native-field values")
            if "초안" in text_value + table_value + form_table_value + fields_value:
                raise RuntimeError("readback still contains the replaced marker")
            if "{{담당자}}" in text_value:
                raise RuntimeError("body anchor residue remains after form fill")
            if sha256(source) != source_hash:
                raise RuntimeError("editing the copy changed the source file")

            preview = await call(
                session,
                "render_preview",
                {
                    "filename": str(form_output),
                    "output_dir": str(preview_dir),
                    "mode": "pages",
                    "screenshot": "auto",
                    "embed_images": False,
                    "viewer": True,
                },
            )
            if preview.get("status") == "blocked" or not preview.get("pageCount"):
                raise RuntimeError(f"render_preview did not produce pages: {preview}")
            for key in ("htmlPath", "manifestPath", "visualReviewPath"):
                artifact = Path(str(preview.get(key, "")))
                if not artifact.is_absolute():
                    artifact = output_dir / artifact
                if not artifact.is_file():
                    raise RuntimeError(f"render_preview artifact is missing: {key}")

            return {
                "schemaVersion": "ax1.hwpx-acceptance.v1",
                "ok": True,
                "versions": observed,
                "toolCount": len(tools),
                "source": {
                    "path": str(source),
                    "sha256": source_hash,
                    "preservedAfterAllOperations": sha256(source) == source_hash,
                },
                "intermediates": {
                    "searchReplace": {
                        "path": str(edited),
                        "sha256": edited_hash,
                    },
                    "canonicalBatch": {
                        "path": str(batch_output),
                        "sha256": batch_hash,
                    },
                },
                "output": {
                    "path": str(form_output),
                    "sha256": sha256(form_output),
                    "distinctFromSource": form_output.resolve() != source.resolve(),
                },
                "dryRuns": {
                    "heading": heading_dry.get("semanticDiff"),
                    "paragraph": paragraph_dry.get("semanticDiff"),
                    "ownerAnchor": owner_dry.get("semanticDiff"),
                    "goal": goal_dry.get("semanticDiff"),
                    "table": table_dry.get("semanticDiff"),
                    "formTable": form_table_dry.get("semanticDiff"),
                    "formField": field_dry.get("semanticDiff"),
                    "replace": replace_dry.get("semanticDiff"),
                    "canonicalBatch": batch_dry.get("semanticDiff"),
                    "mixedForm": form_dry.get("semanticDiff"),
                },
                "commits": {
                    "heading": find_dict(heading_commit, "openSafety"),
                    "paragraph": find_dict(paragraph_commit, "openSafety"),
                    "ownerAnchor": find_dict(owner_commit, "openSafety"),
                    "goal": find_dict(goal_commit, "openSafety"),
                    "table": find_dict(table_commit, "openSafety"),
                    "formTable": find_dict(form_table_commit, "openSafety"),
                    "formField": find_dict(field_commit, "openSafety"),
                    "replace": find_dict(replace_commit, "openSafety"),
                    "canonicalBatch": find_dict(batch_commit, "openSafety"),
                    "mixedForm": find_dict(form_commit, "openSafety"),
                },
                "mixedForm": {
                    "targetKinds": target_kinds,
                    "planHash": form_analysis_commit.get("planHash"),
                    "requestHash": form_analysis_commit.get("requestHash"),
                    "receiptStatus": form_verify.get("status"),
                    "receiptOk": form_verify.get("ok"),
                    "receiptValueVerification": form_verify.get(
                        "valueVerification"
                    ),
                    "valueVerificationCompletedByReadback": (
                        value_verification.get("status") == "deferred"
                    ),
                    "sourcePreservation": form_verify.get("sourcePreservation"),
                    "separateVerifyTool": {
                        "available": "verify_form_fill" in tools,
                        "invoked": False,
                        "status": "not-invoked-in-main-acceptance",
                        "reason": (
                            "The pinned Windows stack can block while probing an "
                            "unconfigured render oracle. Use the committed apply receipt, "
                            "readback, preview, and observed Hancom evidence as release gates; "
                            "exercise verify_form_fill only in an isolated bounded check."
                        ),
                    },
                },
                "readback": {
                    "confirmedSearchReplace": "확정" in table_value,
                    "confirmedCanonicalBatch": expected_readback[1] in text_value,
                    "confirmedNativeField": "AX1 HWPX 검증 사업" in fields_value,
                    "confirmedLabelCell": "AX1팀" in form_table_value,
                    "confirmedCanonicalFormTarget": expected_readback[0] in text_value,
                    "confirmedBodyAnchor": expected_readback[2] in text_value,
                    "draftMarkerAbsent": "초안" not in (
                        text_value + table_value + form_table_value + fields_value
                    ),
                    "bodyAnchorResidueAbsent": "{{담당자}}" not in text_value,
                },
                "preview": {
                    "status": preview.get("status"),
                    "pageCount": preview.get("pageCount"),
                    "htmlPath": preview.get("htmlPath"),
                    "manifestPath": preview.get("manifestPath"),
                    "visualReviewPath": preview.get("visualReviewPath"),
                    "screenshots": preview.get("screenshots"),
                    "screenshotEngine": preview.get("screenshotEngine"),
                    "chromePath": chrome_path,
                    "fidelityTier": (preview.get("viewer") or {}).get(
                        "fidelityTier"
                    ),
                },
                "manualHancomReview": {
                    "required": True,
                    "status": "pending",
                    "reason": "Open every page in Hancom and record visual evidence.",
                },
            }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--expected-core", default="6.2.1")
    parser.add_argument("--expected-automation", default="7.0.2")
    parser.add_argument("--expected-plugin", default="2.0.1")
    args = parser.parse_args()
    if not args.mcp_config.is_file():
        parser.error(f"MCP config not found: {args.mcp_config}")

    report = anyio.run(run, args)
    report_path = args.report or (args.output_dir / "acceptance-report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
