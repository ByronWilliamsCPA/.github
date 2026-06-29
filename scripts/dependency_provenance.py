#!/usr/bin/env python3
"""Assemble a dependency-provenance report from OSV-Scanner output.

Deterministic, keyless transitive-provenance reporter. Reads an OSV-Scanner
JSON results file plus a provenance map (introducing direct dependency per
vulnerable package, gathered by the workflow from ``uv tree --invert`` for
Python and ``npm why`` for the frontend), and emits a structured Markdown
report.

The report makes Open-Source vulnerability findings actionable by showing
which DIRECT dependency pulls in each insecure TRANSITIVE package, plus a
suggested action category (remove / upgrade / replace / gate). The
interpretation layer (deciding which action to take) runs locally on the
operator's subscription, separately from CI; this script only does the
deterministic assembly.

All inputs arrive via environment variables and files (injection-safe). No
network calls, no API tokens, no hosted-scanner quota consumed.

Environment variables:
  OSV_RESULTS         Path to the OSV-Scanner JSON results file (may be absent
                      or empty on a clean run).
  PROVENANCE_MAP      Path to a JSON object mapping package name -> provenance
                      record. Each record: {"direct": str, "extra": str,
                      "path": str, "ecosystem": str}. Missing entries are
                      tolerated and reported as "unknown".
  REPORT_OUT          Path to write the Markdown report (default:
                      dependency-provenance-report.md).
  REPO_SLUG           "owner/repo" for the report header (optional).
  ECOSYSTEMS          Comma-separated list of ecosystems scanned
                      (e.g. "python,frontend") for the header (optional).

Exit status is always 0: this is a reporting tool, not a gate. The OSV
scanner job upstream is the place to gate if a gate is ever wanted.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

MARKER = "<!-- dependency-provenance -->"

# Severity ranking for deterministic sorting (highest first).
_SEVERITY_RANK = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "MODERATE": 2,
    "LOW": 1,
    "UNKNOWN": 0,
    "": 0,
}


def _read_json(path_str: str) -> Any:
    """Read a JSON file, returning None when the path is absent or empty."""
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


def _normalize_severity(raw: Any) -> str:
    """Map an OSV severity record to a single upper-case severity word."""
    if isinstance(raw, str):
        return raw.strip().upper() or "UNKNOWN"
    if isinstance(raw, list):
        # OSV severity arrays carry CVSS vectors, not a human label; the
        # database-specific severity usually lives elsewhere. Treat as unknown
        # and let the human-readable ecosystem severity (below) win when set.
        return "UNKNOWN"
    return "UNKNOWN"


def _extract_severity(vuln: dict[str, Any], group_max: str) -> str:
    """Pick the most informative severity available for a vulnerability."""
    # OSV-Scanner's grouped output often carries a "max_severity" per group;
    # prefer that when present, else fall back to the ecosystem_specific field.
    ecosystem = vuln.get("database_specific", {})
    if isinstance(ecosystem, dict):
        label = ecosystem.get("severity")
        if isinstance(label, str) and label.strip():
            return label.strip().upper()
    return group_max or "UNKNOWN"


def _suggested_action(direct: str, vuln_pkg: str, extra: str) -> str:
    """Derive a deterministic suggested-action category.

    The categories are advisory hints for the local interpretation agent, not
    decisions:
      - remove:  introduced only through an optional/dev extra or group -> the
                 cheapest fix is often dropping that extra.
      - upgrade: introduced by a runtime direct dependency -> bumping the
                 direct dep (or the transitive pin) usually clears it.
      - replace: the vulnerable package IS the direct dependency -> no
                 transitive indirection to bump through.
      - gate:    provenance is unknown -> needs manual investigation before any
                 action.
    """
    if not direct or direct == "unknown":
        return "gate"
    if direct == vuln_pkg:
        return "replace"
    if extra and extra not in {"", "unknown", "(runtime)"}:
        return "remove"
    return "upgrade"


def _iter_findings(
    osv: dict[str, Any] | None,
    provenance: dict[str, Any],
) -> list[dict[str, str]]:
    """Flatten OSV-Scanner results into one row per (vuln id, package)."""
    findings: list[dict[str, str]] = []
    if not isinstance(osv, dict):
        return findings

    for result in osv.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        for package_block in result.get("packages", []) or []:
            if not isinstance(package_block, dict):
                continue
            pkg_info = package_block.get("package", {}) or {}
            pkg_name = str(pkg_info.get("name", "")).strip()
            pkg_eco = str(pkg_info.get("ecosystem", "")).strip()

            # Group-level max severity (OSV-Scanner >= 1.4 emits "groups").
            group_max = "UNKNOWN"
            for group in package_block.get("groups", []) or []:
                if isinstance(group, dict):
                    candidate = str(group.get("max_severity", "")).strip()
                    if candidate:
                        group_max = candidate.upper()

            prov = provenance.get(pkg_name, {}) if isinstance(provenance, dict) else {}
            direct = str(prov.get("direct", "unknown")) or "unknown"
            extra = str(prov.get("extra", "")) or ""
            path = str(prov.get("path", "")) or ""

            for vuln in package_block.get("vulnerabilities", []) or []:
                if not isinstance(vuln, dict):
                    continue
                vuln_id = str(vuln.get("id", "")).strip() or "UNKNOWN"
                aliases = vuln.get("aliases", []) or []
                cve = next(
                    (a for a in aliases if isinstance(a, str) and a.startswith("CVE-")),
                    "",
                )
                severity = _extract_severity(vuln, group_max)
                action = _suggested_action(direct, pkg_name, extra)
                findings.append(
                    {
                        "id": vuln_id,
                        "cve": cve,
                        "severity": severity,
                        "package": pkg_name,
                        "ecosystem": pkg_eco,
                        "direct": direct,
                        "extra": extra or "(runtime)",
                        "path": path,
                        "action": action,
                    }
                )

    # Deterministic order: severity desc, then package, then vuln id.
    findings.sort(
        key=lambda row: (
            -_SEVERITY_RANK.get(row["severity"], 0),
            row["package"],
            row["id"],
        )
    )
    return findings


def _preamble(repo_slug: str, ecosystems: str, count: int) -> str:
    """Build the 'how to act' preamble shown above the table."""
    lines = [
        MARKER,
        "",
        "# Dependency Provenance Report",
        "",
    ]
    meta = []
    if repo_slug:
        meta.append(f"**Repository:** `{repo_slug}`")
    if ecosystems:
        meta.append(f"**Ecosystems scanned:** {ecosystems}")
    meta.append(f"**Actionable transitive vulnerabilities:** {count}")
    lines.append("  \n".join(meta))
    lines += [
        "",
        "This is a deterministic, keyless report: OSV-Scanner finds the",
        "vulnerable packages, and `uv tree --invert` (Python) / `npm why`",
        "(frontend) trace each one back to the DIRECT dependency that pulls it",
        "in. No hosted scanner quota is consumed and no Anthropic API key is",
        "used. Interpretation (which fix to apply) is done separately by a",
        "local agent on the operator's subscription.",
        "",
        "## How to act",
        "",
        "Read the **Introducing direct dep** column, not the vulnerable",
        "package: you fix the thing you actually depend on. The **Suggested",
        "action** column is an advisory category, not a decision:",
        "",
        "- **remove** -- the vulnerable package arrives only through an",
        "  optional/dev extra or group. Dropping that extra is often the",
        "  cheapest fix.",
        "- **upgrade** -- a runtime direct dependency pulls it in. Bump the",
        "  direct dependency (or its transitive pin) to a fixed version.",
        "- **replace** -- the vulnerable package IS a direct dependency. There",
        "  is no transitive layer to bump through; upgrade it directly or swap",
        "  it out.",
        "- **gate** -- provenance could not be determined. Investigate",
        "  manually before acting.",
        "",
    ]
    return "\n".join(lines)


def _table(findings: list[dict[str, str]]) -> str:
    """Render the findings table."""
    header = (
        "| Vulnerability | Severity | Vulnerable package | "
        "Introducing direct dep | Extra/group | Suggested action |\n"
        "| --- | --- | --- | --- | --- | --- |"
    )
    rows = []
    for row in findings:
        vuln_label = row["id"]
        if row["cve"] and row["cve"] != row["id"]:
            vuln_label = f"{row['id']} ({row['cve']})"
        rows.append(
            "| {vuln} | {sev} | `{pkg}` | `{direct}` | {extra} | {action} |".format(
                vuln=vuln_label,
                sev=row["severity"],
                pkg=row["package"],
                direct=row["direct"],
                extra=row["extra"],
                action=row["action"],
            )
        )
    return header + "\n" + "\n".join(rows)


def _clean_report(repo_slug: str, ecosystems: str) -> str:
    """Report body for a zero-vulnerability run."""
    lines = [
        MARKER,
        "",
        "# Dependency Provenance Report",
        "",
    ]
    meta = []
    if repo_slug:
        meta.append(f"**Repository:** `{repo_slug}`")
    if ecosystems:
        meta.append(f"**Ecosystems scanned:** {ecosystems}")
    meta.append("**Actionable transitive vulnerabilities:** 0")
    lines.append("  \n".join(meta))
    lines += [
        "",
        "No actionable transitive vulnerabilities were found this week. "
        "OSV-Scanner reported no vulnerable packages in the scanned "
        "ecosystems.",
        "",
        "This issue is kept open as a sticky marker and will be updated on the "
        "next run. A clean result here does not replace the gating "
        "OSV-Scanner job in `python-sbom.yml`; it only confirms there is "
        "nothing to trace this cycle.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    """Assemble the report and write it to REPORT_OUT."""
    osv = _read_json(os.environ.get("OSV_RESULTS", ""))
    provenance_raw = _read_json(os.environ.get("PROVENANCE_MAP", ""))
    provenance: dict[str, Any] = (
        provenance_raw if isinstance(provenance_raw, dict) else {}
    )
    report_out = os.environ.get("REPORT_OUT", "dependency-provenance-report.md")
    repo_slug = os.environ.get("REPO_SLUG", "").strip()
    ecosystems = os.environ.get("ECOSYSTEMS", "").strip()

    findings = _iter_findings(osv, provenance)

    if findings:
        body = (
            _preamble(repo_slug, ecosystems, len(findings))
            + "\n"
            + _table(findings)
            + "\n"
        )
        has_findings = "true"
    else:
        body = _clean_report(repo_slug, ecosystems)
        has_findings = "false"

    Path(report_out).write_text(body, encoding="utf-8")
    print(f"Wrote {report_out} ({len(findings)} finding(s))")

    # Surface a machine-readable count to the workflow via GITHUB_OUTPUT.
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as handle:
            handle.write(f"finding-count={len(findings)}\n")
            handle.write(f"has-findings={has_findings}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
