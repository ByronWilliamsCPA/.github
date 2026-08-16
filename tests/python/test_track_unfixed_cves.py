"""Tests for scripts/track_unfixed_cves.py.

Covers the revisit-tracking contract for container CVEs with no upstream fix:

1. Only unfixed findings at the tracked severities are tracked
2. A new CVE gets first-seen today and due today + horizon
3. An already-tracked CVE keeps its original due date across runs
4. A CVE that disappears from the scan is dropped from the tracker
5. An overdue CVE exits 1 (and only warns when gating is off)
6. Outputs (tracked / overdue / due_soon) reach GITHUB_OUTPUT
7. The rendered body round-trips through parse_existing
8. Missing or corrupt reports fail closed rather than reading as clean
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

import pytest

import track_unfixed_cves as tracker

if TYPE_CHECKING:
    from pathlib import Path

TODAY = "2026-08-16"
REFERENCE = dt.date(2026, 8, 16)


def vuln(
    vuln_id: str,
    *,
    severity: str = "HIGH",
    package: str = "openssl",
    fixed: str = "",
) -> dict[str, str]:
    """Build one Trivy vulnerability entry."""
    return {
        "VulnerabilityID": vuln_id,
        "PkgName": package,
        "Severity": severity,
        "FixedVersion": fixed,
    }


def write_report(tmp_path: Path, *vulnerabilities: dict[str, Any]) -> str:
    """Write a minimal Trivy JSON report and return its path."""
    path = tmp_path / "trivy.json"
    path.write_text(
        json.dumps({"Results": [{"Target": "app", "Vulnerabilities": list(vulnerabilities)}]}),
        encoding="utf-8",
    )
    return str(path)


def run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    report_path: str,
    *,
    existing: str | None = None,
    **env: str,
) -> str:
    """Run main() with a fixed clock; return the rendered body."""
    output = tmp_path / "body.md"
    for key in ("REVISIT_HORIZON_DAYS", "SEVERITIES", "FAIL_ON_OVERDUE", "IMAGE_REF"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TODAY", TODAY)
    monkeypatch.setenv("TRIVY_JSON", report_path)
    monkeypatch.setenv("OUTPUT_BODY_PATH", str(output))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    if existing is None:
        monkeypatch.delenv("EXISTING_BODY_PATH", raising=False)
    else:
        existing_path = tmp_path / "existing.md"
        existing_path.write_text(existing, encoding="utf-8")
        monkeypatch.setenv("EXISTING_BODY_PATH", str(existing_path))

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    tracker.main()
    return output.read_text(encoding="utf-8")


def outputs(tmp_path: Path) -> dict[str, str]:
    """Parse the GITHUB_OUTPUT file written during a run."""
    path = tmp_path / "gh-output"
    if not path.exists():
        return {}
    return dict(
        line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line
    )


# ---------------------------------------------------------------------------
# 1. Selection: unfixed only, tracked severities only
# ---------------------------------------------------------------------------


def test_fixed_findings_are_not_tracked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = write_report(
        tmp_path,
        vuln("CVE-2026-1000", fixed="3.0.14"),
        vuln("CVE-2026-1001"),
    )
    body = run(monkeypatch, tmp_path, report)
    assert "CVE-2026-1001" in body
    assert "CVE-2026-1000" not in body
    assert outputs(tmp_path)["tracked"] == "1"


def test_severity_filter_applies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = write_report(
        tmp_path,
        vuln("CVE-2026-1002", severity="LOW"),
        vuln("CVE-2026-1003", severity="CRITICAL"),
    )
    body = run(monkeypatch, tmp_path, report, SEVERITIES="CRITICAL,HIGH")
    assert "CVE-2026-1003" in body
    assert "CVE-2026-1002" not in body


def test_duplicate_cve_across_results_tracked_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "trivy.json"
    path.write_text(
        json.dumps(
            {
                "Results": [
                    {"Vulnerabilities": [vuln("CVE-2026-1004", package="libssl")]},
                    {"Vulnerabilities": [vuln("CVE-2026-1004", package="libcrypto")]},
                ]
            }
        ),
        encoding="utf-8",
    )
    run(monkeypatch, tmp_path, str(path))
    assert outputs(tmp_path)["tracked"] == "1"


def test_no_findings_renders_empty_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = write_report(tmp_path)
    body = run(monkeypatch, tmp_path, report)
    assert "No unfixed vulnerabilities" in body
    assert outputs(tmp_path)["tracked"] == "0"


# ---------------------------------------------------------------------------
# 2-4. Revisit dates: assignment, carry-forward, and drop-off
# ---------------------------------------------------------------------------


def test_new_cve_gets_horizon_due_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = write_report(tmp_path, vuln("CVE-2026-1005"))
    body = run(monkeypatch, tmp_path, report)
    # today (2026-08-16) + 90 days
    assert "| 2026-08-16 | 2026-11-14 |" in body


def test_custom_horizon_applies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = write_report(tmp_path, vuln("CVE-2026-1006"))
    body = run(monkeypatch, tmp_path, report, REVISIT_HORIZON_DAYS="30")
    assert "| 2026-08-16 | 2026-09-15 |" in body


def test_existing_due_date_is_carried_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = (
        "| CVE | Package | Severity | First seen | Revisit due |\n"
        "|-----|---------|----------|------------|-------------|\n"
        "| CVE-2026-1007 | openssl | HIGH | 2026-07-01 | 2026-09-29 |\n"
    )
    report = write_report(tmp_path, vuln("CVE-2026-1007"))
    body = run(monkeypatch, tmp_path, report, existing=existing)
    assert "| 2026-07-01 | 2026-09-29 |" in body
    assert "2026-11-14" not in body


def test_resolved_cve_is_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = (
        "| CVE-2026-1008 | openssl | HIGH | 2026-07-01 | 2026-09-29 |\n"
        "| CVE-2026-1009 | zlib | HIGH | 2026-07-01 | 2026-09-29 |\n"
    )
    report = write_report(tmp_path, vuln("CVE-2026-1009", package="zlib"))
    body = run(monkeypatch, tmp_path, report, existing=existing)
    assert "CVE-2026-1008" not in body
    assert "CVE-2026-1009" in body


def test_corrupt_existing_row_restarts_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = "| CVE-2026-1010 | openssl | HIGH | not-a-date | 2026-09-29 |\n"
    report = write_report(tmp_path, vuln("CVE-2026-1010"))
    body = run(monkeypatch, tmp_path, report, existing=existing)
    assert "| 2026-08-16 | 2026-11-14 |" in body


def test_missing_existing_body_is_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = write_report(tmp_path, vuln("CVE-2026-1011"))
    body = run(
        monkeypatch,
        tmp_path,
        report,
        EXISTING_BODY_PATH=str(tmp_path / "absent.md"),
    )
    assert "CVE-2026-1011" in body


# ---------------------------------------------------------------------------
# 5-6. Gating and step outputs
# ---------------------------------------------------------------------------


def test_overdue_cve_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    existing = "| CVE-2026-1012 | openssl | HIGH | 2026-01-01 | 2026-04-01 |\n"
    report = write_report(tmp_path, vuln("CVE-2026-1012"))
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, tmp_path, report, existing=existing)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "past their revisit date" in out
    assert "CVE-2026-1012" in out


def test_overdue_still_writes_body_and_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The issue must be updatable even on the run that fails."""
    existing = "| CVE-2026-1013 | openssl | HIGH | 2026-01-01 | 2026-04-01 |\n"
    report = write_report(tmp_path, vuln("CVE-2026-1013"))
    with pytest.raises(SystemExit):
        run(monkeypatch, tmp_path, report, existing=existing)
    assert "CVE-2026-1013" in (tmp_path / "body.md").read_text(encoding="utf-8")
    assert outputs(tmp_path) == {"tracked": "1", "overdue": "1", "due_soon": "0"}


def test_overdue_advisory_mode_does_not_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    existing = "| CVE-2026-1014 | openssl | HIGH | 2026-01-01 | 2026-04-01 |\n"
    report = write_report(tmp_path, vuln("CVE-2026-1014"))
    run(monkeypatch, tmp_path, report, existing=existing, FAIL_ON_OVERDUE="false")
    out = capsys.readouterr().out
    assert "::warning::" in out
    assert "::error::" not in out


def test_due_soon_is_counted_and_warned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    existing = "| CVE-2026-1015 | openssl | HIGH | 2026-05-25 | 2026-08-23 |\n"
    report = write_report(tmp_path, vuln("CVE-2026-1015"))
    run(monkeypatch, tmp_path, report, existing=existing)
    assert outputs(tmp_path)["due_soon"] == "1"
    assert "due for revisit on 2026-08-23" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 7. The body is the state store: it must round-trip
# ---------------------------------------------------------------------------


def test_rendered_body_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = write_report(
        tmp_path,
        vuln("CVE-2026-1016", severity="CRITICAL"),
        vuln("CVE-2026-1017", package="zlib"),
    )
    body = run(monkeypatch, tmp_path, report)
    recovered = tracker.parse_existing(body)
    assert set(recovered) == {"CVE-2026-1016", "CVE-2026-1017"}
    assert recovered["CVE-2026-1016"] == (REFERENCE, REFERENCE + dt.timedelta(days=90))


def test_findings_sort_by_due_then_severity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = "| CVE-2026-1018 | openssl | HIGH | 2026-06-01 | 2026-08-30 |\n"
    report = write_report(
        tmp_path,
        vuln("CVE-2026-1019", severity="CRITICAL"),
        vuln("CVE-2026-1018"),
    )
    body = run(monkeypatch, tmp_path, report, existing=existing)
    rows = [line for line in body.splitlines() if line.startswith("| CVE-")]
    assert rows[0].startswith("| CVE-2026-1018")  # earlier due date wins


# ---------------------------------------------------------------------------
# 8. Fail-closed input handling
# ---------------------------------------------------------------------------


def test_missing_report_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, tmp_path, str(tmp_path / "absent.json"))
    assert "Trivy report not found" in str(exc.value)


def test_corrupt_report_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "trivy.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, tmp_path, str(path))
    assert "Cannot parse Trivy report" in str(exc.value)


def test_non_object_report_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "trivy.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, tmp_path, str(path))
    assert "must be a JSON object" in str(exc.value)


def test_report_without_results_is_empty_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "trivy.json"
    path.write_text(json.dumps({"SchemaVersion": 2}), encoding="utf-8")
    body = run(monkeypatch, tmp_path, str(path))
    assert "No unfixed vulnerabilities" in body


@pytest.mark.parametrize("value", ["ninety", "0", "-30"])
def test_invalid_horizon_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    report = write_report(tmp_path, vuln("CVE-2026-1020"))
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, tmp_path, report, REVISIT_HORIZON_DAYS=value)
    assert "REVISIT_HORIZON_DAYS" in str(exc.value)
