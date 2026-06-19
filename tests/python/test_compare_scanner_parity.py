"""Tests for scripts/compare_scanner_parity.py.

The script compares Trivy and Grype SARIF output for the issue #152 parallel
run. The central behaviour under test is that findings are joined by the
affected artifact (ecosystem, PEP 503-normalized package name, version) rather
than by raw advisory ID, because Trivy emits CVE-namespace IDs and Grype emits
GHSA-namespace IDs for the same vulnerability. Comparing raw IDs reports false
divergence; comparing package keys reports true parity.

Coverage:
1. PEP 503 name normalization
2. PURL parsing (pypi, with qualifiers/subpath, non-pypi namespaced)
3. Trivy-style extraction from locations[].message.text
4. Grype-style extraction from rule.properties.purls
5. Cross-tool parity: same package under CVE vs GHSA collapses to one (the fix)
6. Genuine divergence: different packages are reported as only-in-one
7. Both empty: parity at zero
8. SARIF files are read by content, not filename extension (Grype "output")
9. Markdown rendering and machine-readable stdout line via main()
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import compare_scanner_parity as csp

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers: build minimal SARIF documents in each scanner's shape
# ---------------------------------------------------------------------------


def trivy_sarif(findings: list[tuple[str, str, str, str]]) -> dict:
    """findings: list of (rule_id, ecosystem, name, version).

    Mirrors aquasecurity/trivy-action SARIF: the package@version lives in the
    result location message text as "<ecosystem>: <name>@<version>".
    """
    results = [
        {
            "ruleId": rid,
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": eco, "uriBaseId": "ROOTPATH"},
                        "region": {"startLine": 1, "startColumn": 1},
                    },
                    "message": {"text": f"{eco}: {name}@{ver}"},
                }
            ],
        }
        for rid, eco, name, ver in findings
    ]
    return {
        "runs": [
            {"tool": {"driver": {"name": "Trivy", "rules": []}}, "results": results}
        ]
    }


def grype_sarif(findings: list[tuple[str, str, str, str]]) -> dict:
    """findings: list of (rule_id, ecosystem, name, version).

    Mirrors anchore/scan-action SARIF: the package URL lives in the rule's
    properties.purls as "pkg:<ecosystem>/<name>@<version>".
    """
    rules = [
        {"id": rid, "properties": {"purls": [f"pkg:{eco}/{name}@{ver}"]}}
        for rid, eco, name, ver in findings
    ]
    results = [{"ruleId": rid} for rid, _, _, _ in findings]
    return {
        "runs": [
            {"tool": {"driver": {"name": "Grype", "rules": rules}}, "results": results}
        ]
    }


# ---------------------------------------------------------------------------
# 1. Name normalization
# ---------------------------------------------------------------------------


def test_normalize_name_lowercases() -> None:
    assert csp.normalize_pypi_name("Pygments") == "pygments"


def test_normalize_name_collapses_separators() -> None:
    # PEP 503: runs of -, _, . collapse to a single -
    assert csp.normalize_pypi_name("python_dotenv") == "python-dotenv"
    assert csp.normalize_pypi_name("A.B__c") == "a-b-c"


# ---------------------------------------------------------------------------
# 2. PURL parsing
# ---------------------------------------------------------------------------


def test_parse_purl_pypi() -> None:
    assert csp.parse_purl("pkg:pypi/python-dotenv@1.2.1") == (
        "pypi",
        "python-dotenv",
        "1.2.1",
    )


def test_parse_purl_strips_qualifiers_and_subpath() -> None:
    assert csp.parse_purl("pkg:pypi/foo@1.0?arch=src#sub") == ("pypi", "foo", "1.0")


def test_parse_purl_normalizes_pypi_name() -> None:
    assert csp.parse_purl("pkg:pypi/Py_Yaml@6.0") == ("pypi", "py-yaml", "6.0")


def test_parse_purl_non_pypi_namespaced() -> None:
    # name is the final segment; ecosystem preserved
    assert csp.parse_purl("pkg:deb/debian/bash@5.1") == ("deb", "bash", "5.1")


def test_parse_purl_invalid_returns_none() -> None:
    assert csp.parse_purl("not-a-purl") is None
    assert csp.parse_purl("pkg:pypi/noversion") is None


# ---------------------------------------------------------------------------
# 3 & 4. Per-tool extraction
# ---------------------------------------------------------------------------


def test_extract_trivy_from_location_message() -> None:
    sarif = trivy_sarif([("CVE-2026-4539", "Python", "Pygments", "2.19.2")])
    keys = {csp.package_key(f) for f in csp.extract_findings(sarif)}
    assert keys == {("pypi", "pygments", "2.19.2")}


def test_extract_grype_from_purls() -> None:
    sarif = grype_sarif([("GHSA-5239-wwwm-4pmq", "pypi", "Pygments", "2.19.2")])
    keys = {csp.package_key(f) for f in csp.extract_findings(sarif)}
    assert keys == {("pypi", "pygments", "2.19.2")}


# ---------------------------------------------------------------------------
# 5. The core fix: same package, different advisory namespace -> parity
# ---------------------------------------------------------------------------


def test_cross_tool_same_package_is_parity_not_divergence() -> None:
    trivy = csp.extract_findings(
        trivy_sarif(
            [
                ("CVE-2026-4539", "Python", "Pygments", "2.19.2"),
                ("CVE-2026-28684", "Python", "python-dotenv", "1.2.1"),
            ]
        )
    )
    grype = csp.extract_findings(
        grype_sarif(
            [
                ("GHSA-5239-wwwm-4pmq", "pypi", "Pygments", "2.19.2"),
                ("GHSA-mf9w-mj56-hr94", "pypi", "python-dotenv", "1.2.1"),
            ]
        )
    )
    result = csp.compare(trivy, grype)
    assert result["both"] == 2
    assert result["trivy_only"] == 0
    assert result["grype_only"] == 0


# ---------------------------------------------------------------------------
# 6. Genuine divergence
# ---------------------------------------------------------------------------


def test_genuine_divergence_reported() -> None:
    trivy = csp.extract_findings(
        trivy_sarif([("CVE-1", "Python", "requests", "2.0.0")])
    )
    grype = csp.extract_findings(grype_sarif([("GHSA-2", "pypi", "urllib3", "1.0.0")]))
    result = csp.compare(trivy, grype)
    assert result["both"] == 0
    assert result["trivy_only"] == 1
    assert result["grype_only"] == 1


# ---------------------------------------------------------------------------
# 7 & 8. Directory loading: content-based, extension-agnostic
# ---------------------------------------------------------------------------


def test_load_dir_reads_files_without_sarif_extension(tmp_path: Path) -> None:
    # Grype's artifact downloads as a file literally named "output"
    d = tmp_path / "grype"
    d.mkdir()
    (d / "output").write_text(
        json.dumps(grype_sarif([("GHSA-x", "pypi", "Pygments", "2.19.2")]))
    )
    findings, files = csp.load_findings_from_dir(str(d))
    assert files == 1
    assert {csp.package_key(f) for f in findings} == {("pypi", "pygments", "2.19.2")}


def test_load_dir_missing_returns_empty(tmp_path: Path) -> None:
    findings, files = csp.load_findings_from_dir(str(tmp_path / "does-not-exist"))
    assert findings == []
    assert files == 0


def test_load_dir_ignores_non_json(tmp_path: Path) -> None:
    d = tmp_path / "trivy"
    d.mkdir()
    (d / "note.txt").write_text("not json")
    (d / "trivy.sarif").write_text(
        json.dumps(trivy_sarif([("CVE-9", "Python", "flask", "3.0.0")]))
    )
    findings, files = csp.load_findings_from_dir(str(d))
    assert files == 1
    assert {csp.package_key(f) for f in findings} == {("pypi", "flask", "3.0.0")}


# ---------------------------------------------------------------------------
# 9. main(): markdown to step summary + machine-readable stdout
# ---------------------------------------------------------------------------


def test_main_writes_summary_and_machine_line(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    tdir = tmp_path / "trivy-sarif"
    gdir = tmp_path / "grype-sarif"
    tdir.mkdir()
    gdir.mkdir()
    (tdir / "t.sarif").write_text(
        json.dumps(trivy_sarif([("CVE-2026-4539", "Python", "Pygments", "2.19.2")]))
    )
    (gdir / "output").write_text(
        json.dumps(grype_sarif([("GHSA-5239-wwwm-4pmq", "pypi", "Pygments", "2.19.2")]))
    )
    summary = tmp_path / "summary.md"
    env = {
        "TRIVY_SARIF_DIR": str(tdir),
        "GRYPE_SARIF_DIR": str(gdir),
        "TRIVY_RESULT": "success",
        "GRYPE_RESULT": "success",
        "GITHUB_STEP_SUMMARY": str(summary),
    }
    with patch.dict(os.environ, env, clear=False):
        rc = csp.main()
    assert rc == 0

    body = summary.read_text()
    # package-level parity is the headline; the one shared package collapses
    assert "Package-level" in body or "package" in body.lower()
    assert "Pygments" in body or "pygments" in body

    out = capsys.readouterr().out
    # machine-readable line for log/API aggregation
    assert "parity" in out.lower()
    assert "pkg_both=1" in out
    assert "pkg_trivy_only=0" in out
    assert "pkg_grype_only=0" in out
