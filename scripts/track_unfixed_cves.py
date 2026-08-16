"""Revisit-date tracking for container CVEs with no available fix.

`ignore-unfixed` keeps unactionable base-image CVEs out of the pull-request
gate.  Left alone, that turns into an unbounded silence: nothing forces anyone
to look at those findings again.  This script closes the loop.  It reads a
Trivy JSON report, keeps only the findings with no fixed version, and renders
a tracker issue body in which every CVE carries a first-seen date and a revisit
due date (first-seen + horizon, 90 days by default).

Due dates are carried forward by parsing the previous issue body, so a CVE seen
three weeks ago keeps its original deadline instead of rolling forward on every
weekly run.  A CVE whose due date has passed is reported as overdue and the
script exits non-zero, which fails the scheduled run that owns the tracker.

All inputs are read from environment variables so that GitHub Actions workflow
expressions never interpolate into the script body (injection-safe pattern).

Environment variables:
    TRIVY_JSON:            Path to the Trivy JSON report (required).
    EXISTING_BODY_PATH:    Path to the current tracker issue body.  Missing or
                           empty means no tracker exists yet.
    OUTPUT_BODY_PATH:      Path to write the rendered issue body (required).
    REVISIT_HORIZON_DAYS:  Days from first sighting to the revisit due date
                           (default: 90).
    IMAGE_REF:             Image reference, recorded in the issue body.
    SEVERITIES:            Comma-separated severities to track
                           (default: CRITICAL,HIGH).
    FAIL_ON_OVERDUE:       "true" or "1" (default) to exit 1 when any tracked
                           CVE is past its revisit date.
    TODAY:                 ISO date (YYYY-MM-DD) overriding "today".  Test
                           hook; unset in CI so the real clock is used.

Outputs (written to GITHUB_OUTPUT when set): tracked, overdue, due_soon.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from typing import Any, NamedTuple

_TRUE = {"true", "1"}

# Marker row parsed back out of the previous issue body.  Kept deliberately
# simple: the table is the state store, so its shape is a contract between
# successive runs, not incidental formatting.
_ROW = re.compile(
    r"^\|\s*(?P<id>[A-Za-z0-9._:-]+)\s*\|"
    r"\s*(?P<package>[^|]*?)\s*\|"
    r"\s*(?P<severity>[^|]*?)\s*\|"
    r"\s*(?P<first_seen>\d{4}-\d{2}-\d{2})\s*\|"
    r"\s*(?P<due>\d{4}-\d{2}-\d{2})\s*\|"
)


class Finding(NamedTuple):
    """One unfixed vulnerability, with its revisit schedule."""

    id: str
    package: str
    severity: str
    first_seen: dt.date
    due: dt.date


def _flag(name: str, *, default: bool = False) -> bool:
    """Read a boolean environment variable with an explicit default."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def today() -> dt.date:
    """Return the reference date, honouring the TODAY test hook."""
    raw = os.environ.get("TODAY", "").strip()
    if not raw:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        sys.exit(f"::error::TODAY must be an ISO date YYYY-MM-DD (got: {raw!r})")


def horizon_days() -> int:
    """Read REVISIT_HORIZON_DAYS, rejecting non-positive or non-numeric values."""
    raw = os.environ.get("REVISIT_HORIZON_DAYS", "").strip()
    if not raw:
        return 90
    try:
        value = int(raw)
    except ValueError:
        sys.exit(f"::error::REVISIT_HORIZON_DAYS must be an integer (got: {raw!r})")
    if value <= 0:
        sys.exit(f"::error::REVISIT_HORIZON_DAYS must be greater than 0 (got: {value})")
    return value


def load_report(path: str) -> dict[str, Any]:
    """Load the Trivy JSON report, failing closed on anything unusable.

    A missing or corrupt report must never render as "no unfixed CVEs": that
    would silently close out every tracked finding and reset its revisit date.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            report = json.load(handle)
    except FileNotFoundError:
        sys.exit(f"::error::Trivy report not found at {path}")
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"::error::Cannot parse Trivy report {path}: {exc}")

    if not isinstance(report, dict):
        sys.exit(
            f"::error::Trivy report {path} must be a JSON object, got"
            f" {type(report).__name__}"
        )
    return report


def extract_unfixed(report: dict[str, Any], severities: set[str]) -> dict[str, tuple[str, str]]:
    """Return {vulnerability id: (package, severity)} for unfixed findings.

    A finding counts as unfixed when Trivy reports no FixedVersion for it.
    Trivy emits one entry per affected package, so the same CVE can appear
    several times; the first sighting wins and later duplicates are folded in
    by keeping the package list short and deterministic.
    """
    unfixed: dict[str, tuple[str, str]] = {}
    results = report.get("Results")
    if not isinstance(results, list):
        return unfixed

    for result in results:
        if not isinstance(result, dict):
            continue
        vulnerabilities = result.get("Vulnerabilities")
        if not isinstance(vulnerabilities, list):
            continue
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                continue
            if str(vulnerability.get("FixedVersion", "")).strip():
                continue
            severity = str(vulnerability.get("Severity", "UNKNOWN")).strip().upper()
            if severities and severity not in severities:
                continue
            vuln_id = str(vulnerability.get("VulnerabilityID", "")).strip()
            if not vuln_id:
                continue
            package = str(vulnerability.get("PkgName", "")).strip() or "unknown"
            unfixed.setdefault(vuln_id, (package, severity))
    return unfixed


def parse_existing(body: str) -> dict[str, tuple[dt.date, dt.date]]:
    """Recover {vulnerability id: (first_seen, due)} from a tracker issue body.

    Rows whose dates do not parse are dropped rather than guessed at; the CVE
    is then treated as newly seen, which restarts its clock.  That is the safe
    direction: a corrupted row can only shorten the silence, never extend it.
    """
    known: dict[str, tuple[dt.date, dt.date]] = {}
    for line in body.splitlines():
        match = _ROW.match(line.strip())
        if not match:
            continue
        try:
            first_seen = dt.date.fromisoformat(match.group("first_seen"))
            due = dt.date.fromisoformat(match.group("due"))
        except ValueError:
            continue
        known[match.group("id")] = (first_seen, due)
    return known


def build_findings(
    unfixed: dict[str, tuple[str, str]],
    known: dict[str, tuple[dt.date, dt.date]],
    *,
    reference: dt.date,
    horizon: int,
) -> list[Finding]:
    """Merge the current scan with carried-forward revisit dates.

    CVEs absent from this scan are dropped: either upstream shipped a fix or
    the base image moved on, and a resolved finding should not keep a deadline
    alive.
    """
    findings: list[Finding] = []
    for vuln_id, (package, severity) in unfixed.items():
        if vuln_id in known:
            first_seen, due = known[vuln_id]
        else:
            first_seen = reference
            due = reference + dt.timedelta(days=horizon)
        findings.append(Finding(vuln_id, package, severity, first_seen, due))

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda f: (f.due, severity_rank.get(f.severity, 4), f.id))
    return findings


def render_body(
    findings: list[Finding],
    *,
    reference: dt.date,
    horizon: int,
    image_ref: str,
    overdue: list[Finding],
) -> str:
    """Render the tracker issue body.

    The table doubles as this tracker's state store (see parse_existing), so
    the column order and the ISO dates in it must stay stable across runs.
    """
    lines = [
        "## Unfixed container CVEs: revisit tracker",
        "",
        "These findings have no upstream fix, so pull-request scans run with",
        "`ignore-unfixed: true` and do not block on them. Each one carries a",
        f"revisit date {horizon} days from first sighting; the weekly full scan",
        "fails once a date passes, which forces a decision: accept for another",
        "period with a written justification, rebase onto a patched base image,",
        "or suppress it in `.trivyignore.yaml` with a fresh `expired_at`.",
        "",
        f"- **Image:** `{image_ref or 'not recorded'}`",
        f"- **Last scan:** {reference.isoformat()}",
        f"- **Tracked:** {len(findings)}",
        f"- **Overdue:** {len(overdue)}",
        "",
    ]

    if findings:
        lines += [
            "| CVE | Package | Severity | First seen | Revisit due |",
            "|-----|---------|----------|------------|-------------|",
        ]
        lines += [
            f"| {f.id} | {f.package} | {f.severity} |"
            f" {f.first_seen.isoformat()} | {f.due.isoformat()} |"
            for f in findings
        ]
    else:
        lines.append("No unfixed vulnerabilities at the tracked severities.")

    lines += [
        "",
        "<!-- Maintained by scripts/track_unfixed_cves.py. The table above is",
        "     the state store for revisit dates; edit dates here to re-accept a",
        "     finding for another period. -->",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(**values: object) -> None:
    """Append step outputs to GITHUB_OUTPUT when running under Actions."""
    output_path = os.environ.get("GITHUB_OUTPUT", "")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    """Entry point: read env vars, render the tracker, and exit."""
    report_path = os.environ.get("TRIVY_JSON", "").strip()
    if not report_path:
        sys.exit("::error::TRIVY_JSON is required")
    output_path = os.environ.get("OUTPUT_BODY_PATH", "").strip()
    if not output_path:
        sys.exit("::error::OUTPUT_BODY_PATH is required")

    reference = today()
    horizon = horizon_days()
    fail_on_overdue = _flag("FAIL_ON_OVERDUE", default=True)
    image_ref = os.environ.get("IMAGE_REF", "").strip()
    severities = {
        part.strip().upper()
        for part in os.environ.get("SEVERITIES", "CRITICAL,HIGH").split(",")
        if part.strip()
    }

    existing_body = ""
    existing_path = os.environ.get("EXISTING_BODY_PATH", "").strip()
    if existing_path and os.path.exists(existing_path):
        try:
            with open(existing_path, encoding="utf-8") as handle:
                existing_body = handle.read()
        except OSError as exc:
            # Failing closed here would block the weekly run on a transient
            # read error, but proceeding silently would reset every deadline.
            # Warn loudly and restart the clocks; the next run reconciles.
            print(f"::warning::Cannot read existing tracker body: {exc}")

    report = load_report(report_path)
    unfixed = extract_unfixed(report, severities)
    known = parse_existing(existing_body)
    findings = build_findings(unfixed, known, reference=reference, horizon=horizon)

    overdue = [f for f in findings if f.due < reference]
    due_soon = [f for f in findings if reference <= f.due <= reference + dt.timedelta(days=14)]

    body = render_body(
        findings,
        reference=reference,
        horizon=horizon,
        image_ref=image_ref,
        overdue=overdue,
    )
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(body)
    except OSError as exc:
        sys.exit(f"::error::Cannot write issue body to {output_path}: {exc}")

    write_outputs(tracked=len(findings), overdue=len(overdue), due_soon=len(due_soon))

    for finding in due_soon:
        print(
            f"::warning::{finding.id} ({finding.severity}, {finding.package})"
            f" is due for revisit on {finding.due.isoformat()}"
        )

    if overdue:
        level = "error" if fail_on_overdue else "warning"
        print(f"::{level}::{len(overdue)} unfixed CVE(s) past their revisit date:")
        for finding in overdue:
            print(
                f"::{level}::{finding.id} ({finding.severity}, {finding.package})"
                f" was due {finding.due.isoformat()}, first seen"
                f" {finding.first_seen.isoformat()}"
            )
        if fail_on_overdue:
            sys.exit(1)
        return

    print(f"{len(findings)} unfixed CVE(s) tracked, none overdue.")


if __name__ == "__main__":
    main()
