#!/usr/bin/env python3
"""Trace transitive vulnerability provenance for the dependency-provenance workflow.

Three deterministic subcommands, selected by argv[1]:

  python    Read OSV-Scanner Python results, run ``uv tree --invert --package
            <pkg>`` for each vulnerable package, and write a provenance map.
  frontend  Run ``npm audit --json`` and ``npm why <pkg>`` in the frontend
            directory, writing an OSV-shaped results file plus a provenance map.
  merge     Merge the per-ecosystem OSV results and provenance maps into single
            files for the report assembler.

All inputs and outputs arrive via environment variables (injection-safe). No
Anthropic API key and no hosted-scanner quota are used: OSV-Scanner runs
keyless upstream, ``uv`` and ``npm`` run locally on the committed lockfiles.

The provenance record shape (one per vulnerable package name) is::

    {"direct": str, "extra": str, "path": str, "ecosystem": str}

``direct`` is the introducing direct dependency, ``extra`` is the
introducing extra/group when one is tagged (e.g. ``uv tree`` prints
``extra: dev``), ``path`` is a readable dependency path, and ``ecosystem`` is
``PyPI`` or ``npm``.

Exit status is always 0: this is a reporting helper, not a gate.
"""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404 - invoking uv/npm with fixed argv, no shell.
import sys
from pathlib import Path
from typing import Any

_TIMEOUT_SECONDS = 120


def _load_json(path_str: str) -> Any:
    """Read a JSON file, returning None when absent, empty, or invalid."""
    if not path_str:
        return None
    path = Path(path_str)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"::warning::Could not parse {path_str}: {exc}", file=sys.stderr)
        return None


def _write_json(path_str: str, data: Any) -> None:
    """Write a JSON file with deterministic key ordering."""
    Path(path_str).write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _osv_package_names(osv: Any) -> list[str]:
    """Collect the distinct vulnerable package names from OSV-Scanner output."""
    names: set[str] = set()
    if not isinstance(osv, dict):
        return []
    for result in osv.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        for block in result.get("packages", []) or []:
            if not isinstance(block, dict):
                continue
            name = str((block.get("package", {}) or {}).get("name", "")).strip()
            if name:
                names.add(name)
    return sorted(names)


def _run(argv: list[str], cwd: str | None = None) -> str:
    """Run a command with a fixed argv (no shell) and return stdout."""
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, untrusted data not in argv[0].
            argv,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            cwd=cwd,
            check=False,
        )
        return proc.stdout or ""
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"::warning::command {argv!r} failed: {exc}", file=sys.stderr)
        return ""


def _parse_uv_tree(tree: str) -> dict[str, str]:
    """Parse ``uv tree --invert`` output into a provenance record.

    The inverted tree lists the vulnerable package first, then the dependents
    that pull it in, indented by tree-drawing characters. The deepest entry is
    the top-level (direct) dependent. ``extra:`` / ``group:`` tags, when
    present, identify the introducing optional extra or dependency group.
    """
    lines = [ln.rstrip() for ln in tree.splitlines() if ln.strip()]
    direct = "unknown"
    extra = ""
    path_parts: list[str] = []
    for line in lines:
        token = line.lstrip("│├└─- ").split(" ")[0].strip()
        if token:
            path_parts.append(token)
        lowered = line.lower()
        if "extra:" in lowered:
            extra = line.split("extra:", 1)[1].strip().rstrip(")").strip()
        elif "group:" in lowered:
            extra = line.split("group:", 1)[1].strip().rstrip(")").strip()
    if len(path_parts) >= 2:
        direct = path_parts[-1]
    elif path_parts:
        direct = path_parts[0]
    return {
        "direct": direct,
        "extra": extra,
        "path": " -> ".join(reversed(path_parts)) if path_parts else "",
        "ecosystem": "PyPI",
    }


def cmd_python() -> int:
    """Build the Python provenance map via ``uv tree --invert``."""
    osv = _load_json(os.environ.get("OSV_PYTHON", "osv-python.json"))
    out_path = os.environ.get("PROVENANCE_PYTHON_OUT", "provenance-python.json")
    provenance: dict[str, Any] = {}
    for name in _osv_package_names(osv):
        tree = _run(["uv", "tree", "--invert", "--package", name])
        provenance[name] = _parse_uv_tree(tree)
    _write_json(out_path, provenance)
    print(f"Traced provenance for {len(provenance)} Python package(s).")
    return 0


def _parse_npm_why(why: str) -> str:
    """Extract the introducing direct dependency from ``npm why`` output."""
    lines = [ln.strip() for ln in why.splitlines() if ln.strip()]
    if not lines:
        return "unknown"
    # The first line names the top of the dependency path, e.g. "lodash@4.17.0"
    # or "lodash@4.17.0 dev". Strip the version and any trailing annotation.
    first = lines[0].split("@")[0].split(" ")[0].strip()
    return first or "unknown"


def cmd_frontend() -> int:
    """Build the frontend OSV-shaped results and provenance map via npm."""
    frontend_state = os.environ.get("FRONTEND_STATE", "skip")
    frontend_dir = os.environ.get("FRONTEND_DIR", "frontend")
    root_dir = os.environ.get("ROOT_DIR", ".")
    osv_out = os.environ.get("OSV_FRONTEND_OUT", "osv-frontend.json")
    prov_out = os.environ.get("PROVENANCE_FRONTEND_OUT", "provenance-frontend.json")

    work_dir = frontend_dir if frontend_state == "npm" else "."

    # npm audit exits non-zero when vulnerabilities exist; capture stdout anyway.
    audit_json = _run(["npm", "audit", "--json"], cwd=work_dir)
    audit_path = Path(root_dir) / "npm-audit.json"
    audit_path.write_text(audit_json, encoding="utf-8")

    osv: dict[str, Any] = {"results": [{"packages": []}]}
    provenance: dict[str, Any] = {}

    try:
        data = json.loads(audit_json) if audit_json.strip() else {}
    except json.JSONDecodeError:
        data = {}

    # npm v7+ audit schema: top-level "vulnerabilities" keyed by package name.
    vulnerabilities = data.get("vulnerabilities", {}) or {}
    for name, info in sorted(vulnerabilities.items()):
        if not isinstance(info, dict):
            continue
        severity = str(info.get("severity", "")).upper()
        ids: list[dict[str, str]] = []
        for via in info.get("via", []) or []:
            if isinstance(via, dict):
                identifier = via.get("source") or via.get("name") or via.get("url")
                ids.append(
                    {"id": str(identifier or name), "url": str(via.get("url", ""))}
                )
        if not ids:
            ids = [{"id": name, "url": ""}]

        osv["results"][0]["packages"].append(
            {
                "package": {"name": name, "ecosystem": "npm"},
                "groups": [{"max_severity": severity}],
                "vulnerabilities": [
                    {"id": entry["id"], "aliases": []} for entry in ids
                ],
            }
        )

        why = _run(["npm", "why", name], cwd=work_dir)
        why_lines = [ln.strip() for ln in why.splitlines() if ln.strip()]
        provenance[name] = {
            "direct": _parse_npm_why(why),
            "extra": "",
            "path": " -> ".join(ln.split(" ")[0] for ln in why_lines[:4]),
            "ecosystem": "npm",
        }

    _write_json(osv_out, osv)
    _write_json(prov_out, provenance)
    print(f"Frontend: {len(provenance)} vulnerable package(s) traced.")
    return 0


def cmd_merge() -> int:
    """Merge per-ecosystem OSV results and provenance maps into single files."""
    osv_out = os.environ.get("OSV_MERGED_OUT", "osv-merged.json")
    prov_out = os.environ.get("PROVENANCE_MERGED_OUT", "provenance-merged.json")

    merged_osv: dict[str, Any] = {"results": []}
    for source in ("osv-python.json", "osv-frontend.json"):
        data = _load_json(source)
        if isinstance(data, dict):
            merged_osv["results"].extend(data.get("results", []) or [])

    merged_prov: dict[str, Any] = {}
    for source in ("provenance-python.json", "provenance-frontend.json"):
        data = _load_json(source)
        if isinstance(data, dict):
            merged_prov.update(data)

    # Preserve OSV result ordering (no key sort) but keep provenance sorted.
    Path(osv_out).write_text(json.dumps(merged_osv, indent=2), encoding="utf-8")
    _write_json(prov_out, merged_prov)
    print("Merged OSV + provenance inputs.")
    return 0


_COMMANDS = {
    "python": cmd_python,
    "frontend": cmd_frontend,
    "merge": cmd_merge,
}


def main(argv: list[str]) -> int:
    """Dispatch to the requested subcommand."""
    if len(argv) < 2 or argv[1] not in _COMMANDS:
        print(
            f"usage: {argv[0]} {{python|frontend|merge}}",
            file=sys.stderr,
        )
        return 2
    return _COMMANDS[argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
