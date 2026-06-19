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
10. Ecosystem alias (Python -> pypi) pinned directly so cross-tool parity
    cannot pass vacuously
11. Data-loss observability: empty-version drop, no-artifact drop, failed-file
    and non-SARIF-JSON counts
12. Verdict branches: parity-at-zero, inconclusive-on-parse-warning,
    inconclusive-when-scanner-absent, divergence via render_markdown
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
    findings, dropped = csp.extract_findings(sarif)
    assert {csp.package_key(f) for f in findings} == {("pypi", "pygments", "2.19.2")}
    assert dropped == 0


def test_extract_grype_from_purls() -> None:
    sarif = grype_sarif([("GHSA-5239-wwwm-4pmq", "pypi", "Pygments", "2.19.2")])
    findings, dropped = csp.extract_findings(sarif)
    assert {csp.package_key(f) for f in findings} == {("pypi", "pygments", "2.19.2")}
    assert dropped == 0


# ---------------------------------------------------------------------------
# 5. The core fix: same package, different advisory namespace -> parity
# ---------------------------------------------------------------------------


def test_cross_tool_same_package_is_parity_not_divergence() -> None:
    trivy, _ = csp.extract_findings(
        trivy_sarif(
            [
                ("CVE-2026-4539", "Python", "Pygments", "2.19.2"),
                ("CVE-2026-28684", "Python", "python-dotenv", "1.2.1"),
            ]
        )
    )
    grype, _ = csp.extract_findings(
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


def test_ecosystem_alias_maps_python_to_pypi() -> None:
    # The core fix depends on this alias: Trivy spells the ecosystem "Python"
    # while Grype emits the PURL type "pypi". Without the alias the same package
    # would land in two different keys and read as divergence. Pinning the alias
    # directly means the cross-tool parity test above cannot pass vacuously.
    assert csp._normalize_ecosystem("Python") == "pypi"
    assert csp._normalize_ecosystem("pypi") == "pypi"


# ---------------------------------------------------------------------------
# 6. Genuine divergence
# ---------------------------------------------------------------------------


def test_genuine_divergence_reported() -> None:
    trivy, _ = csp.extract_findings(
        trivy_sarif([("CVE-1", "Python", "requests", "2.0.0")])
    )
    grype, _ = csp.extract_findings(
        grype_sarif([("GHSA-2", "pypi", "urllib3", "1.0.0")])
    )
    result = csp.compare(trivy, grype)
    assert result["both"] == 0
    assert result["trivy_only"] == 1
    assert result["grype_only"] == 1


def test_extract_empty_version_location_is_dropped_not_phantom() -> None:
    # A Trivy location with an empty version ("Python: requests@   ") must not
    # become a phantom finding with version="" that inflates the trivy-only
    # bucket; it is dropped and counted instead.
    sarif = {
        "runs": [
            {
                "tool": {"driver": {"name": "Trivy", "rules": []}},
                "results": [
                    {
                        "ruleId": "CVE-EMPTY",
                        "locations": [{"message": {"text": "Python: requests@   "}}],
                    }
                ],
            }
        ]
    }
    assert csp._parse_trivy_location("Python: requests@   ") is None
    findings, dropped = csp.extract_findings(sarif)
    assert findings == []
    assert dropped == 1


def test_extract_counts_results_with_no_parseable_artifact() -> None:
    # A result carrying a ruleId but neither a PURL nor a parseable location is
    # the signature of a scanner output-format change. It is dropped and the
    # drop is counted so a silent under-count is visible downstream.
    sarif = {
        "runs": [
            {
                "tool": {"driver": {"name": "Grype", "rules": []}},
                "results": [{"ruleId": "GHSA-shape-change", "properties": {}}],
            }
        ]
    }
    findings, dropped = csp.extract_findings(sarif)
    assert findings == []
    assert dropped == 1


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
    result = csp.load_findings_from_dir(str(d))
    assert result["files_parsed"] == 1
    assert result["files_failed"] == 0
    assert {csp.package_key(f) for f in result["findings"]} == {
        ("pypi", "pygments", "2.19.2")
    }


def test_load_dir_missing_returns_empty(tmp_path: Path) -> None:
    result = csp.load_findings_from_dir(str(tmp_path / "does-not-exist"))
    assert result["findings"] == []
    assert result["files_parsed"] == 0
    assert result["files_failed"] == 0


def test_load_dir_reads_valid_sarif_and_counts_unparseable_sibling(
    tmp_path: Path,
) -> None:
    # A non-JSON sibling does not pollute findings or corrupt the valid SARIF
    # read, but it is counted as files_failed rather than silently ignored, so
    # a corrupted/truncated artifact cannot vanish without a trace.
    d = tmp_path / "trivy"
    d.mkdir()
    (d / "note.txt").write_text("not json")
    (d / "trivy.sarif").write_text(
        json.dumps(trivy_sarif([("CVE-9", "Python", "flask", "3.0.0")]))
    )
    result = csp.load_findings_from_dir(str(d))
    assert result["files_parsed"] == 1
    assert result["files_failed"] == 1
    assert {csp.package_key(f) for f in result["findings"]} == {
        ("pypi", "flask", "3.0.0")
    }


def test_load_dir_counts_non_sarif_json(tmp_path: Path) -> None:
    # Valid JSON that lacks a "runs" key (e.g. a future enveloped SARIF shape)
    # is counted separately so the divergence between "no SARIF" and
    # "unrecognized SARIF" is visible.
    d = tmp_path / "grype"
    d.mkdir()
    (d / "enveloped.json").write_text(json.dumps({"schema": "x", "sarif": {}}))
    result = csp.load_findings_from_dir(str(d))
    assert result["files_parsed"] == 0
    assert result["non_sarif_json"] == 1
    assert result["findings"] == []


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
    # Assert the exact verdict, not just the presence of the word "package"
    # (which also appears in the table headers): a broken verdict must fail.
    assert "**Package-level parity confirmed.**" in body
    assert "pygments" in body.lower()
    # A clean run records no parse warnings.
    assert "**Warning:**" not in body

    out = capsys.readouterr().out
    # machine-readable line for log/API aggregation
    assert "parity" in out.lower()
    assert "pkg_both=1" in out
    assert "pkg_trivy_only=0" in out
    assert "pkg_grype_only=0" in out
    assert "trivy_files_failed=0" in out
    assert "grype_files_failed=0" in out


# ---------------------------------------------------------------------------
# 10. Verdict branches and parse-warning gating
# ---------------------------------------------------------------------------


def _load_result(
    findings: list[csp.Finding],
    *,
    files_parsed: int = 1,
    files_failed: int = 0,
    non_sarif_json: int = 0,
    dropped_results: int = 0,
) -> csp.LoadResult:
    return csp.LoadResult(
        findings=findings,
        files_parsed=files_parsed,
        files_failed=files_failed,
        non_sarif_json=non_sarif_json,
        dropped_results=dropped_results,
    )


def test_verdict_parity_at_zero_when_clean() -> None:
    empty = _load_result([], files_parsed=1)
    comparison = csp.compare([], [])
    verdict = csp._verdict(comparison, empty, empty, "success", "success")
    assert "Parity at zero" in verdict


def test_verdict_inconclusive_on_parse_warning_despite_success() -> None:
    # Both scanners "succeeded" and report zero packages, but a SARIF failed to
    # parse. The zero must NOT be reported as parity at zero: this is the
    # false-green case the observability counters exist to prevent.
    clean = _load_result([], files_parsed=1)
    lossy = _load_result([], files_parsed=0, files_failed=1)
    comparison = csp.compare([], [])
    verdict = csp._verdict(comparison, lossy, clean, "success", "success")
    assert "inconclusive" in verdict.lower()
    assert "Parity at zero" not in verdict


def test_verdict_inconclusive_when_scanner_did_not_run() -> None:
    empty = _load_result([], files_parsed=0)
    comparison = csp.compare([], [])
    verdict = csp._verdict(comparison, empty, empty, "failure", "success")
    assert "inconclusive" in verdict.lower()


def test_render_markdown_reports_divergence_and_warning() -> None:
    trivy_findings, _ = csp.extract_findings(
        trivy_sarif([("CVE-1", "Python", "requests", "2.0.0")])
    )
    grype_findings, _ = csp.extract_findings(
        grype_sarif([("GHSA-2", "pypi", "urllib3", "1.0.0")])
    )
    comparison = csp.compare(trivy_findings, grype_findings)
    trivy = _load_result(trivy_findings, files_parsed=1, dropped_results=2)
    grype = _load_result(grype_findings, files_parsed=1)
    report = csp.render_markdown(comparison, trivy, grype, "success", "success")
    assert "**Package-level divergence detected.**" in report
    # The dropped results surface as a visible warning block.
    assert "**Warning:**" in report
    assert "2 result(s) produced no parseable artifact" in report
