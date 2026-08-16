"""Tests for scripts/check_trivy_ignore_expiry.py.

Covers the revisit-date contract enforced on Trivy suppression files:

1. No suppression file at all passes
2. Entry with a valid, in-horizon revisit date passes
3. Entry missing expired_at fails
4. Entry with a past revisit date fails
5. Entry beyond the horizon fails
6. Entry missing statement fails (and passes when the requirement is off)
7. Quoted, unquoted, and timestamp date forms all parse
8. Legacy plain-text .trivyignore fails unless explicitly allowed
9. Malformed documents and unknown keys fail closed
10. Advisory mode (FAIL_ON_VIOLATION off) reports without exiting 1
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

import check_trivy_ignore_expiry as checker

if TYPE_CHECKING:
    from pathlib import Path

TODAY = "2026-08-16"


def write_yaml(tmp_path: Path, content: str, name: str = ".trivyignore.yaml") -> str:
    """Write a suppression file and return its path."""
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def run(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    """Run main() with a fixed clock and the given environment."""
    for key in (
        "TRIVYIGNORE_PATH",
        "LEGACY_TRIVYIGNORE_PATH",
        "MAX_HORIZON_DAYS",
        "WARN_WITHIN_DAYS",
        "REQUIRE_STATEMENT",
        "FAIL_ON_VIOLATION",
        "ALLOW_LEGACY_TRIVYIGNORE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TODAY", TODAY)
    # Point the legacy check at a path that cannot exist unless a test creates
    # one, so an unrelated .trivyignore in the working tree cannot leak in.
    monkeypatch.setenv("LEGACY_TRIVYIGNORE_PATH", os.path.join(env.get("_tmp", ""), ".trivyignore"))
    env.pop("_tmp", None)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    checker.main()


# ---------------------------------------------------------------------------
# 1-2. Baseline: nothing to validate, and a well-formed entry
# ---------------------------------------------------------------------------


def test_missing_file_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run(
        monkeypatch,
        TRIVYIGNORE_PATH=str(tmp_path / ".trivyignore.yaml"),
        _tmp=str(tmp_path),
    )
    assert "no suppressions to validate" in capsys.readouterr().out


def test_valid_entry_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0001
    statement: No upstream fix; base image rebase tracked in #505.
    expired_at: 2026-10-01
""",
    )
    run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "All 1 Trivy suppression(s)" in capsys.readouterr().out


def test_empty_document_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_yaml(tmp_path, "# nothing suppressed yet\n")
    run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))


# ---------------------------------------------------------------------------
# 3-5. The revisit-date contract itself
# ---------------------------------------------------------------------------


def test_missing_expiry_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0002
    statement: Accepted risk.
""",
    )
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "missing `expired_at`" in out
    assert "CVE-2026-0002" in out


def test_past_expiry_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0003
    statement: Accepted risk.
    expired_at: 2026-01-01
""",
    )
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert exc.value.code == 1
    assert "has passed" in capsys.readouterr().out


def test_expiry_today_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A date of exactly today is already due: Trivy stops honouring it."""
    path = write_yaml(
        tmp_path,
        f"""
vulnerabilities:
  - id: CVE-2026-0004
    statement: Accepted risk.
    expired_at: {TODAY}
""",
    )
    with pytest.raises(SystemExit):
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "has passed" in capsys.readouterr().out


def test_beyond_horizon_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0005
    statement: Accepted risk.
    expired_at: 2027-08-16
""",
    )
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "beyond the 90-day horizon" in out
    assert "2026-11-14" in out  # today + 90


def test_horizon_boundary_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """today + horizon is allowed; the check is > horizon, not >=."""
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0006
    statement: Accepted risk.
    expired_at: 2026-11-14
""",
    )
    run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))


def test_custom_horizon_applies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0007
    statement: Accepted risk.
    expired_at: 2026-10-01
""",
    )
    with pytest.raises(SystemExit):
        run(
            monkeypatch,
            TRIVYIGNORE_PATH=path,
            MAX_HORIZON_DAYS="30",
            _tmp=str(tmp_path),
        )
    assert "beyond the 30-day horizon" in capsys.readouterr().out


def test_due_soon_warns_without_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0008
    statement: Accepted risk.
    expired_at: 2026-08-20
""",
    )
    run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    out = capsys.readouterr().out
    assert "::warning::" in out
    assert "revisit due 2026-08-20" in out


# ---------------------------------------------------------------------------
# 6-7. Statement requirement and date forms
# ---------------------------------------------------------------------------


def test_missing_statement_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0009
    expired_at: 2026-10-01
""",
    )
    with pytest.raises(SystemExit):
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "missing `statement`" in capsys.readouterr().out


def test_statement_requirement_can_be_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0010
    expired_at: 2026-10-01
""",
    )
    run(
        monkeypatch,
        TRIVYIGNORE_PATH=path,
        REQUIRE_STATEMENT="false",
        _tmp=str(tmp_path),
    )


@pytest.mark.parametrize(
    "raw",
    ["2026-10-01", "'2026-10-01'", "2026-10-01T00:00:00Z"],
    ids=["unquoted-date", "quoted-string", "timestamp"],
)
def test_date_forms_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    path = write_yaml(
        tmp_path,
        f"""
vulnerabilities:
  - id: CVE-2026-0011
    statement: Accepted risk.
    expired_at: {raw}
""",
    )
    run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))


def test_unparseable_date_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0012
    statement: Accepted risk.
    expired_at: 'next quarter'
""",
    )
    with pytest.raises(SystemExit):
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "must be a date YYYY-MM-DD" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 8. Legacy plain-text .trivyignore
# ---------------------------------------------------------------------------


def test_legacy_trivyignore_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    legacy = tmp_path / ".trivyignore"
    legacy.write_text("CVE-2026-0013\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run(
            monkeypatch,
            TRIVYIGNORE_PATH=str(tmp_path / ".trivyignore.yaml"),
            _tmp=str(tmp_path),
        )
    assert exc.value.code == 1
    assert "never expire" in capsys.readouterr().out


def test_legacy_trivyignore_allowed_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    legacy = tmp_path / ".trivyignore"
    legacy.write_text("CVE-2026-0014\n", encoding="utf-8")
    run(
        monkeypatch,
        TRIVYIGNORE_PATH=str(tmp_path / ".trivyignore.yaml"),
        ALLOW_LEGACY_TRIVYIGNORE="true",
        _tmp=str(tmp_path),
    )
    assert "::warning::" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 9-10. Fail-closed parsing and advisory mode
# ---------------------------------------------------------------------------


def test_unknown_top_level_key_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilties:
  - id: CVE-2026-0015
    statement: Typo in the key above; Trivy would ignore this entry.
    expired_at: 2026-10-01
""",
    )
    with pytest.raises(SystemExit):
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "unknown top-level key" in capsys.readouterr().out


def test_non_mapping_document_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_yaml(tmp_path, "- CVE-2026-0016\n")
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "must be a mapping" in str(exc.value)


def test_invalid_yaml_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_yaml(tmp_path, "vulnerabilities: [unclosed\n")
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "Cannot parse" in str(exc.value)


def test_entry_list_wrong_shape_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(tmp_path, "vulnerabilities:\n  CVE-2026-0017: accepted\n")
    with pytest.raises(SystemExit):
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "must be a list of entries" in capsys.readouterr().out


def test_scalar_entry_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(tmp_path, "vulnerabilities:\n  - CVE-2026-0018\n")
    with pytest.raises(SystemExit):
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    assert "entry must be a mapping" in capsys.readouterr().out


def test_advisory_mode_does_not_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
vulnerabilities:
  - id: CVE-2026-0019
    statement: Accepted risk.
""",
    )
    run(
        monkeypatch,
        TRIVYIGNORE_PATH=path,
        FAIL_ON_VIOLATION="false",
        _tmp=str(tmp_path),
    )
    out = capsys.readouterr().out
    assert "::warning::" in out
    assert "::error::" not in out


def test_all_entry_kinds_are_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(
        tmp_path,
        """
misconfigurations:
  - id: AVD-DS-0001
    statement: Accepted.
secrets:
  - id: aws-access-key-id
    statement: Test fixture.
licenses:
  - id: GPL-3.0
    statement: Vendored doc tooling only.
""",
    )
    with pytest.raises(SystemExit):
        run(monkeypatch, TRIVYIGNORE_PATH=path, _tmp=str(tmp_path))
    out = capsys.readouterr().out
    assert "AVD-DS-0001" in out
    assert "aws-access-key-id" in out
    assert "GPL-3.0" in out


@pytest.mark.parametrize("value", ["ninety", "0", "-30"])
def test_invalid_horizon_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    path = write_yaml(tmp_path, "vulnerabilities: []\n")
    with pytest.raises(SystemExit) as exc:
        run(
            monkeypatch,
            TRIVYIGNORE_PATH=path,
            MAX_HORIZON_DAYS=value,
            _tmp=str(tmp_path),
        )
    assert "MAX_HORIZON_DAYS" in str(exc.value)
