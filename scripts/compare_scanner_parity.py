"""Trivy vs Grype SARIF parity comparison for the issue #152 parallel run.

Compares the findings of two vulnerability scanners that ingest the same
CycloneDX SBOM. The comparison joins findings by the affected artifact
(ecosystem, PEP 503-normalized package name, version), NOT by advisory ID.

Why the join key matters: Trivy emits CVE-namespace rule IDs and Grype emits
GHSA-namespace rule IDs for the same underlying vulnerability. A naive set-diff
of raw rule IDs therefore reports total divergence even when both scanners flag
the identical package at the identical version. The stable join key is the
affected artifact, so that is what this script compares. Advisory-ID divergence
between the two namespaces is expected and is not a parity failure.

Findings are extracted defensively from each scanner's SARIF shape:
    - Grype (anchore/scan-action): package URLs in rule.properties.purls
      (or result.properties.purls), e.g. "pkg:pypi/python-dotenv@1.2.1".
    - Trivy (aquasecurity/trivy-action): "<ecosystem>: <name>@<version>" in
      each result's location message text, e.g. "Python: Pygments@2.19.2".

SARIF files are located by content (any file in the directory that parses as
JSON with a "runs" key), not by extension, because the Grype artifact downloads
as a file with no .sarif suffix.

All inputs are read from environment variables so GitHub Actions workflow
expressions never interpolate into the script body (injection-safe pattern).

Environment variables:
    TRIVY_SARIF_DIR: directory holding the Trivy SARIF (default "trivy-sarif").
    GRYPE_SARIF_DIR: directory holding the Grype SARIF (default "grype-sarif").
    TRIVY_RESULT:    Trivy scan job result for status reporting (default
                     "unknown").
    GRYPE_RESULT:    Grype scan job result for status reporting (default
                     "unknown").
    GITHUB_STEP_SUMMARY: if set, the markdown report is appended to this file;
                     the report is also printed to stdout for log durability.

The comparison is advisory: the script always exits 0. It never gates a build.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import TypedDict

# Ecosystems some scanners spell differently from the PURL "type". Map to the
# PURL type so the two scanners' findings join.
_ECOSYSTEM_ALIASES = {"python": "pypi"}

# PEP 503: a name is normalized by lowercasing and collapsing runs of -, _, .
# into a single -.
_PEP503_SEPARATORS = re.compile(r"[-_.]+")

# Trivy location message: "<ecosystem>: <name>@<version>".
_TRIVY_LOCATION = re.compile(r"^\s*(?P<eco>[^:]+):\s*(?P<name>.+)@(?P<ver>[^@]+?)\s*$")


class Finding(TypedDict):
    """A single scanner finding reduced to its affected artifact."""

    ecosystem: str
    name: str
    version: str
    advisory_id: str


def normalize_pypi_name(name: str) -> str:
    """Normalize a PyPI distribution name per PEP 503."""
    return _PEP503_SEPARATORS.sub("-", name.strip().lower()).strip("-")


def _normalize_ecosystem(ecosystem: str) -> str:
    eco = ecosystem.strip().lower()
    return _ECOSYSTEM_ALIASES.get(eco, eco)


def _normalize_artifact(
    ecosystem: str, name: str, version: str
) -> tuple[str, str, str]:
    eco = _normalize_ecosystem(ecosystem)
    norm_name = normalize_pypi_name(name) if eco == "pypi" else name.strip().lower()
    return eco, norm_name, version.strip()


def parse_purl(purl: str) -> tuple[str, str, str] | None:
    """Parse a package URL into a normalized (ecosystem, name, version) tuple.

    Returns None if the string is not a versioned PURL.
    """
    if not purl.startswith("pkg:"):
        return None
    body = purl[len("pkg:") :].split("#", 1)[0].split("?", 1)[0]
    if "@" not in body:
        return None
    coordinates, version = body.rsplit("@", 1)
    if not version.strip():
        return None
    segments = [seg for seg in coordinates.split("/") if seg]
    if len(segments) < 2:
        return None
    ecosystem, name = segments[0], segments[-1]
    if not ecosystem or not name:
        return None
    return _normalize_artifact(ecosystem, name, version)


def _parse_trivy_location(text: str) -> tuple[str, str, str] | None:
    match = _TRIVY_LOCATION.match(text)
    if match is None:
        return None
    artifact = _normalize_artifact(match["eco"], match["name"], match["ver"])
    # Guard against an empty version (e.g. "Python: requests@   "), mirroring
    # parse_purl. A version of "" can never join against a real scanner finding
    # and would otherwise inflate the trivy-only bucket with a phantom entry.
    if not artifact[2]:
        return None
    return artifact


def _purls_for_result(result: dict, rule: dict) -> list[str]:
    purls = (result.get("properties") or {}).get("purls")
    if not purls:
        purls = (rule.get("properties") or {}).get("purls")
    return list(purls or [])


def _artifacts_for_result(result: dict, rule: dict) -> list[tuple[str, str, str]]:
    """Resolve one result's affected artifacts.

    PURLs (Grype) take precedence; the Trivy location-message text is the
    fallback. Returns an empty list when neither shape yields a parseable
    artifact, which the caller treats as a dropped result.
    """
    artifacts = [
        parsed
        for purl in _purls_for_result(result, rule)
        if (parsed := parse_purl(purl)) is not None
    ]
    if artifacts:
        return artifacts
    return [
        parsed
        for location in result.get("locations", [])
        if (
            parsed := _parse_trivy_location(
                (location.get("message") or {}).get("text", "")
            )
        )
        is not None
    ]


def extract_findings(sarif: dict) -> tuple[list[Finding], int]:
    """Extract artifact-level findings from one SARIF document.

    Returns the findings and the count of results that carried a ruleId but
    yielded no parseable artifact (neither a PURL nor a Trivy location matched).
    A nonzero drop count on an otherwise well-formed SARIF is the signature of a
    scanner output-format change; it is surfaced as a parity warning so a silent
    under-count cannot masquerade as a clean result.
    """
    findings: list[Finding] = []
    dropped = 0
    for run in sarif.get("runs", []):
        rules = {
            rule.get("id"): rule
            for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
            if isinstance(rule, dict)
        }
        for result in run.get("results", []):
            advisory = str(result.get("ruleId", ""))
            artifacts = _artifacts_for_result(result, rules.get(advisory, {}))
            if not artifacts:
                dropped += 1
                continue
            findings.extend(
                Finding(
                    ecosystem=ecosystem,
                    name=name,
                    version=version,
                    advisory_id=advisory,
                )
                for ecosystem, name, version in artifacts
            )
    return findings, dropped


class LoadResult(TypedDict):
    """Findings plus the data-loss signals gathered while loading a directory.

    The counters exist so a silently lost SARIF cannot be reported as a clean
    zero. files_failed and non_sarif_json distinguish "no SARIF present" from
    "SARIF present but unreadable/unrecognized"; dropped_results flags a
    well-formed SARIF whose results no longer match the expected purl/location
    shape (a scanner output-format change).
    """

    findings: list[Finding]
    files_parsed: int  # valid SARIF documents (a dict with a "runs" key)
    files_failed: int  # files that did not parse as JSON (corrupt/truncated)
    non_sarif_json: int  # valid JSON lacking a "runs" key (unexpected shape)
    dropped_results: int  # results yielding no parseable artifact


def load_findings_from_dir(path: str) -> LoadResult:
    """Load findings from every SARIF document under a directory.

    A SARIF document is any file that parses as JSON with a "runs" key,
    regardless of extension. Alongside the findings, returns counters that make
    data loss observable: files_parsed (0 distinguishes "directory missing or no
    SARIF" from "SARIF present but empty"), files_failed, non_sarif_json, and
    dropped_results.
    """
    findings: list[Finding] = []
    files_parsed = files_failed = non_sarif_json = dropped_results = 0
    if os.path.isdir(path):
        for root, _dirs, names in os.walk(path):
            for name in sorted(names):
                file_path = os.path.join(root, name)
                try:
                    with open(file_path, encoding="utf-8") as handle:
                        data = json.load(handle)
                except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                    files_failed += 1
                    continue
                if not isinstance(data, dict) or "runs" not in data:
                    non_sarif_json += 1
                    continue
                files_parsed += 1
                file_findings, dropped = extract_findings(data)
                findings.extend(file_findings)
                dropped_results += dropped
    return LoadResult(
        findings=findings,
        files_parsed=files_parsed,
        files_failed=files_failed,
        non_sarif_json=non_sarif_json,
        dropped_results=dropped_results,
    )


def package_key(finding: Finding) -> tuple[str, str, str]:
    """The artifact join key: (ecosystem, normalized name, version)."""
    return finding["ecosystem"], finding["name"], finding["version"]


class Comparison(TypedDict):
    both: int
    trivy_only: int
    grype_only: int
    both_keys: list[tuple[str, str, str]]
    trivy_only_keys: list[tuple[str, str, str]]
    grype_only_keys: list[tuple[str, str, str]]
    trivy_pkgs: int
    grype_pkgs: int


def compare(trivy: list[Finding], grype: list[Finding]) -> Comparison:
    """Compare two finding lists by artifact key."""
    trivy_keys = {package_key(f) for f in trivy}
    grype_keys = {package_key(f) for f in grype}
    both = trivy_keys & grype_keys
    trivy_only = trivy_keys - grype_keys
    grype_only = grype_keys - trivy_keys
    return Comparison(
        both=len(both),
        trivy_only=len(trivy_only),
        grype_only=len(grype_only),
        both_keys=sorted(both),
        trivy_only_keys=sorted(trivy_only),
        grype_only_keys=sorted(grype_only),
        trivy_pkgs=len(trivy_keys),
        grype_pkgs=len(grype_keys),
    )


def _format_key(key: tuple[str, str, str]) -> str:
    ecosystem, name, version = key
    return f"{ecosystem}/{name}@{version}"


def _details_block(title: str, keys: list[tuple[str, str, str]]) -> list[str]:
    if not keys:
        return []
    lines = ["", f"<details><summary>{title} ({len(keys)})</summary>", "", "```"]
    lines.extend(_format_key(k) for k in keys[:50])
    if len(keys) > 50:
        lines.append(f"... ({len(keys) - 50} more)")
    lines.extend(["```", "</details>"])
    return lines


def _parse_warning_count(trivy: LoadResult, grype: LoadResult) -> int:
    """Total data-loss signals across both scanners (parse/shape/drop)."""
    return sum(
        side[key]
        for side in (trivy, grype)
        for key in ("files_failed", "non_sarif_json", "dropped_results")
    )


def _verdict(
    comparison: Comparison,
    trivy: LoadResult,
    grype: LoadResult,
    trivy_result: str,
    grype_result: str,
) -> str:
    if comparison["trivy_pkgs"] == 0 and comparison["grype_pkgs"] == 0:
        # A zero-zero result is only trustworthy when nothing was lost in
        # loading. Parse failures, unrecognized JSON, or dropped results mean
        # the zero may be data loss, not a true empty scan, so do not declare
        # parity at zero on the strength of the scan job result alone.
        if _parse_warning_count(trivy, grype):
            return (
                "**Parity inconclusive:** both scanners reported zero packages, but "
                "parse warnings were recorded (see the warning above). The zero counts "
                "may reflect lost or unrecognized SARIF data rather than a true empty "
                "result. Review the scan job logs before drawing conclusions."
            )
        if trivy_result == "success" and grype_result == "success":
            return "Both scanners reported zero package-level findings. Parity at zero."
        return (
            "**Parity inconclusive:** at least one scanner did not produce SARIF. "
            "Review the scan job logs before drawing conclusions."
        )
    if comparison["trivy_only"] == 0 and comparison["grype_only"] == 0:
        return (
            f"**Package-level parity confirmed.** All {comparison['both']} affected "
            "package-versions were detected by both scanners."
        )
    return (
        "**Package-level divergence detected.** The scanners disagree on the set of "
        "affected package-versions; review the buckets below."
    )


def _warning_line(trivy: LoadResult, grype: LoadResult) -> list[str]:
    """A visible warning block when any SARIF data was lost during loading."""
    if not _parse_warning_count(trivy, grype):
        return []
    failed = trivy["files_failed"] + grype["files_failed"]
    non_sarif = trivy["non_sarif_json"] + grype["non_sarif_json"]
    dropped = trivy["dropped_results"] + grype["dropped_results"]
    return [
        "",
        f"> **Warning:** {failed} file(s) failed to parse, {non_sarif} JSON file(s) "
        f"lacked a SARIF `runs` key, and {dropped} result(s) produced no parseable "
        "artifact. These were excluded, so the counts above may understate true "
        "findings. A corrupted artifact or a scanner output-format change is the "
        "most likely cause; review the scan job logs.",
    ]


def render_markdown(
    comparison: Comparison,
    trivy: LoadResult,
    grype: LoadResult,
    trivy_result: str,
    grype_result: str,
) -> str:
    """Render the parity report as GitHub-flavored markdown."""
    lines = [
        "### Trivy vs Grype Parity (issue #152)",
        "",
        "Package-level comparison: findings are joined by (ecosystem, package, "
        "version), not by advisory ID. Trivy reports CVE IDs and Grype reports "
        "GHSA IDs for the same vulnerability, so comparing raw IDs reports false "
        "divergence. Advisory-ID differences between the two namespaces are "
        "expected and are not a parity failure.",
        "",
        "| Scanner | Job result | SARIF files | Packages flagged |",
        "|---------|------------|-------------|------------------|",
        f"| Trivy (gating) | {trivy_result} | {trivy['files_parsed']} | {comparison['trivy_pkgs']} |",
        f"| Grype (advisory) | {grype_result} | {grype['files_parsed']} | {comparison['grype_pkgs']} |",
        "",
        "| Bucket | Count |",
        "|--------|-------|",
        f"| Detected by both | {comparison['both']} |",
        f"| Trivy only (missed by Grype) | {comparison['trivy_only']} |",
        f"| Grype only (missed by Trivy) | {comparison['grype_only']} |",
        *_warning_line(trivy, grype),
        "",
        _verdict(comparison, trivy, grype, trivy_result, grype_result),
    ]
    lines.extend(_details_block("Detected by both", comparison["both_keys"]))
    lines.extend(
        _details_block("Trivy only (missed by Grype)", comparison["trivy_only_keys"])
    )
    lines.extend(
        _details_block("Grype only (missed by Trivy)", comparison["grype_only_keys"])
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    """Entry point: compare, write the report, emit a machine-readable line."""
    trivy_dir = os.environ.get("TRIVY_SARIF_DIR", "trivy-sarif")
    grype_dir = os.environ.get("GRYPE_SARIF_DIR", "grype-sarif")
    trivy_result = os.environ.get("TRIVY_RESULT", "unknown")
    grype_result = os.environ.get("GRYPE_RESULT", "unknown")

    trivy = load_findings_from_dir(trivy_dir)
    grype = load_findings_from_dir(grype_dir)
    comparison = compare(trivy["findings"], grype["findings"])

    report = render_markdown(comparison, trivy, grype, trivy_result, grype_result)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        # Guard the summary write: a failure here must not crash the advisory
        # tool (it always exits 0) or skip the stdout fallback below.
        try:
            with open(summary_path, "a", encoding="utf-8") as handle:
                handle.write(report)
        except OSError as exc:
            print(
                f"Warning: could not write GITHUB_STEP_SUMMARY ({exc}); "
                "report is in the step log only.",
                file=sys.stderr,
            )
    # Always print the report for log durability; the step summary is not
    # retrievable via the API for later aggregation.
    print(report)

    # Single machine-readable line for log scraping and cross-PR aggregation.
    # The *_files_failed and *_dropped fields let an aggregator detect data
    # loss without parsing the markdown report.
    print(
        "parity "
        f"pkg_both={comparison['both']} "
        f"pkg_trivy_only={comparison['trivy_only']} "
        f"pkg_grype_only={comparison['grype_only']} "
        f"trivy_pkgs={comparison['trivy_pkgs']} "
        f"grype_pkgs={comparison['grype_pkgs']} "
        f"trivy_files={trivy['files_parsed']} "
        f"grype_files={grype['files_parsed']} "
        f"trivy_files_failed={trivy['files_failed']} "
        f"grype_files_failed={grype['files_failed']} "
        f"trivy_dropped={trivy['dropped_results']} "
        f"grype_dropped={grype['dropped_results']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
