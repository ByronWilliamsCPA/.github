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
    return _normalize_artifact(match["eco"], match["name"], match["ver"])


def _purls_for_result(result: dict, rule: dict) -> list[str]:
    purls = (result.get("properties") or {}).get("purls")
    if not purls:
        purls = (rule.get("properties") or {}).get("purls")
    return list(purls or [])


def extract_findings(sarif: dict) -> list[Finding]:
    """Extract artifact-level findings from one SARIF document."""
    findings: list[Finding] = []
    for run in sarif.get("runs", []):
        rules = {
            rule.get("id"): rule
            for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
            if isinstance(rule, dict)
        }
        for result in run.get("results", []):
            advisory = str(result.get("ruleId", ""))
            rule = rules.get(advisory, {})
            artifacts = [
                parsed
                for purl in _purls_for_result(result, rule)
                if (parsed := parse_purl(purl)) is not None
            ]
            if not artifacts:
                for location in result.get("locations", []):
                    text = (location.get("message") or {}).get("text", "")
                    parsed = _parse_trivy_location(text)
                    if parsed is not None:
                        artifacts.append(parsed)
            for ecosystem, name, version in artifacts:
                findings.append(
                    Finding(
                        ecosystem=ecosystem,
                        name=name,
                        version=version,
                        advisory_id=advisory,
                    )
                )
    return findings


def load_findings_from_dir(path: str) -> tuple[list[Finding], int]:
    """Load findings from every SARIF document under a directory.

    A SARIF document is any file that parses as JSON with a "runs" key,
    regardless of extension. Returns the findings and the count of SARIF
    documents parsed (0 distinguishes "directory missing or no SARIF" from
    "SARIF present but empty").
    """
    if not os.path.isdir(path):
        return [], 0
    findings: list[Finding] = []
    files_parsed = 0
    for root, _dirs, names in os.walk(path):
        for name in sorted(names):
            file_path = os.path.join(root, name)
            try:
                with open(file_path, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                continue
            if not isinstance(data, dict) or "runs" not in data:
                continue
            files_parsed += 1
            findings.extend(extract_findings(data))
    return findings, files_parsed


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


def _verdict(comparison: Comparison, trivy_result: str, grype_result: str) -> str:
    if comparison["trivy_pkgs"] == 0 and comparison["grype_pkgs"] == 0:
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


def render_markdown(
    comparison: Comparison,
    trivy_files: int,
    grype_files: int,
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
        f"| Trivy (gating) | {trivy_result} | {trivy_files} | {comparison['trivy_pkgs']} |",
        f"| Grype (advisory) | {grype_result} | {grype_files} | {comparison['grype_pkgs']} |",
        "",
        "| Bucket | Count |",
        "|--------|-------|",
        f"| Detected by both | {comparison['both']} |",
        f"| Trivy only (missed by Grype) | {comparison['trivy_only']} |",
        f"| Grype only (missed by Trivy) | {comparison['grype_only']} |",
        "",
        _verdict(comparison, trivy_result, grype_result),
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

    trivy_findings, trivy_files = load_findings_from_dir(trivy_dir)
    grype_findings, grype_files = load_findings_from_dir(grype_dir)
    comparison = compare(trivy_findings, grype_findings)

    report = render_markdown(
        comparison, trivy_files, grype_files, trivy_result, grype_result
    )

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(report)
    # Always print the report for log durability; the step summary is not
    # retrievable via the API for later aggregation.
    print(report)

    # Single machine-readable line for log scraping and cross-PR aggregation.
    print(
        "parity "
        f"pkg_both={comparison['both']} "
        f"pkg_trivy_only={comparison['trivy_only']} "
        f"pkg_grype_only={comparison['grype_only']} "
        f"trivy_pkgs={comparison['trivy_pkgs']} "
        f"grype_pkgs={comparison['grype_pkgs']} "
        f"trivy_files={trivy_files} "
        f"grype_files={grype_files}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
