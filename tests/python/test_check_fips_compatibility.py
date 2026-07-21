"""Tests for scripts/check_fips_compatibility.py.

Covers the following scenario groups:

1. FIPS-MD5: hashlib.md5 / hashlib.new("md5") flagged; usedforsecurity=False
   suppresses both.
2. FIPS-SHA1: hashlib.sha1 flagged; usedforsecurity=False suppresses it.
3. FIPS-CIPHER: algorithms.TripleDES(...) and a PyCryptodome-style
   `from Crypto.Cipher import ...` are both flagged.
4. FIPS-CHACHA20 and FIPS-ECB detection.
5. PQC-CLASSICAL-KEX: ec.ECDH(), X25519PrivateKey, X448PrivateKey and
   padding.OAEP(...) each detected, with the inventory algorithm label taken
   from the matched capture group.
6. PQC-CLASSICAL-SIG: ec.ECDSA(), padding.PSS(), padding.PKCS1v15(),
   Ed25519PrivateKey, Ed448PrivateKey, rsa.generate_private_key and
   dsa.generate_private_key each detected.
7. Inline suppression: a bare `# fips: ignore` excludes a line from both the
   issues list and the algorithm inventory; `# fips: ignore[CODE]` suppresses
   only the named code, leaving other codes on the same or other lines
   intact. This exercises the fix where suppression must be checked before
   the inventory append (previously suppressed lines still counted toward
   the CBOM inventory).
8. Dependency scanning: a known-bad dependency (bcrypt, pycryptodome) is
   flagged via DEP_RULES from both pyproject.toml and requirements*.txt; a
   malformed pyproject.toml produces a FIPS-MANIFEST-UNPARSEABLE error
   instead of silently returning zero findings; a tomllib-unavailable
   runtime (Python < 3.11) produces a FIPS-TOML-UNAVAILABLE warning and
   returns no requirements.
9. cryptography_bound_predates_pqc: version-bound heuristic for whether a
   constraint excludes the PQC-capable cryptography release.
10. apply_pqc_mode: off filters PQC issues out entirely; warn leaves
    severity untouched; error escalates PQC warnings (e.g. quantum-vulnerable
    KEX) to error but leaves PQC info findings alone.
11. build_report: summary counts and inventory stats match the underlying
    issues/inventory lists.
12. main()/CLI: clean tree exits 0; a FIPS error exits 1; --json emits the
    documented shape; a nonexistent --root exits 2 with a stderr message;
    --pqc-mode gates PQC findings independently of --strict, which only
    escalates classic (non-PQC) warnings.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import pytest

import check_fips_compatibility
from check_fips_compatibility import InventoryEntry, Issue

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_py(tmp_path: "Path", name: str, source: str) -> tuple["Path", str]:
    """Write a Python source fixture under tmp_path; return (path, rel-name)."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path, name


def scan(
    tmp_path: "Path", source: str
) -> tuple[list[Issue], list[InventoryEntry], bool]:
    """Write `source` as sample.py and run scan_source_file over it."""
    path, rel = write_py(tmp_path, "sample.py", source)
    issues: list[Issue] = []
    inventory: list[InventoryEntry] = []
    pqc_capable = check_fips_compatibility.scan_source_file(
        path, rel, issues, inventory
    )
    return issues, inventory, pqc_capable


def find_issue(issues: list[Issue], code: str) -> Issue | None:
    return next((i for i in issues if i.code == code), None)


def find_entry(
    inventory: list[InventoryEntry], algorithm: str
) -> InventoryEntry | None:
    return next((e for e in inventory if e.algorithm == algorithm), None)


def run_main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    """Patch sys.argv and invoke main(); return its exit code."""
    monkeypatch.setattr(sys, "argv", ["check_fips_compatibility.py", *argv])
    return check_fips_compatibility.main()


# ---------------------------------------------------------------------------
# Section 1: FIPS-MD5
# ---------------------------------------------------------------------------


def test_md5_without_usedforsecurity_flagged(tmp_path: "Path") -> None:
    """hashlib.md5(...) with no usedforsecurity kwarg is flagged as an error."""
    issues, inventory, _ = scan(tmp_path, "import hashlib\nhashlib.md5(data)\n")
    issue = find_issue(issues, "FIPS-MD5")
    assert issue is not None
    assert issue.severity == "error"
    entry = find_entry(inventory, "MD5")
    assert entry is not None
    assert entry.category == "hash"
    assert entry.quantum_vulnerable is False


def test_md5_with_usedforsecurity_false_not_flagged(tmp_path: "Path") -> None:
    """hashlib.md5(data, usedforsecurity=False) is excluded from issues and inventory."""
    issues, inventory, _ = scan(tmp_path, "hashlib.md5(data, usedforsecurity=False)\n")
    assert find_issue(issues, "FIPS-MD5") is None
    assert find_entry(inventory, "MD5") is None


def test_md5_new_without_usedforsecurity_flagged(tmp_path: "Path") -> None:
    """hashlib.new('md5') with no usedforsecurity kwarg is flagged as an error."""
    issues, inventory, _ = scan(tmp_path, "hashlib.new('md5')\n")
    issue = find_issue(issues, "FIPS-MD5")
    assert issue is not None
    assert issue.severity == "error"
    assert find_entry(inventory, "MD5") is not None


# ---------------------------------------------------------------------------
# Section 2: FIPS-SHA1
# ---------------------------------------------------------------------------


def test_sha1_without_usedforsecurity_flagged(tmp_path: "Path") -> None:
    """hashlib.sha1(...) with no usedforsecurity kwarg is flagged as a warning."""
    issues, inventory, _ = scan(tmp_path, "hashlib.sha1(data)\n")
    issue = find_issue(issues, "FIPS-SHA1")
    assert issue is not None
    assert issue.severity == "warning"
    entry = find_entry(inventory, "SHA-1")
    assert entry is not None
    assert entry.category == "hash"


def test_sha1_with_usedforsecurity_false_not_flagged(tmp_path: "Path") -> None:
    """hashlib.sha1(data, usedforsecurity=False) is excluded from issues and inventory."""
    issues, inventory, _ = scan(tmp_path, "hashlib.sha1(data, usedforsecurity=False)\n")
    assert find_issue(issues, "FIPS-SHA1") is None
    assert find_entry(inventory, "SHA-1") is None


# ---------------------------------------------------------------------------
# Section 3: FIPS-CIPHER
# ---------------------------------------------------------------------------


def test_triple_des_algorithms_flagged(tmp_path: "Path") -> None:
    """algorithms.TripleDES(key) is a non-FIPS-approved cipher."""
    issues, inventory, _ = scan(
        tmp_path,
        "from cryptography.hazmat.primitives.ciphers import algorithms\n"
        "algorithms.TripleDES(key)\n",
    )
    issue = find_issue(issues, "FIPS-CIPHER")
    assert issue is not None
    assert issue.severity == "error"
    entry = find_entry(inventory, "TripleDES")
    assert entry is not None
    assert entry.category == "symmetric"


def test_pycryptodome_cipher_import_flagged(tmp_path: "Path") -> None:
    """A PyCryptodome-style `from Crypto.Cipher import DES3` is flagged."""
    issues, inventory, _ = scan(tmp_path, "from Crypto.Cipher import DES3\n")
    issue = find_issue(issues, "FIPS-CIPHER")
    assert issue is not None
    entry = find_entry(inventory, "DES3")
    assert entry is not None
    assert entry.category == "symmetric"


# ---------------------------------------------------------------------------
# Section 4: FIPS-CHACHA20 and FIPS-ECB
# ---------------------------------------------------------------------------


def test_chacha20poly1305_flagged(tmp_path: "Path") -> None:
    """ChaCha20Poly1305(key) is not a FIPS-approved cipher."""
    issues, inventory, _ = scan(tmp_path, "ChaCha20Poly1305(key)\n")
    issue = find_issue(issues, "FIPS-CHACHA20")
    assert issue is not None
    assert issue.severity == "warning"
    entry = find_entry(inventory, "ChaCha20")
    assert entry is not None
    assert entry.category == "symmetric"


def test_ecb_mode_flagged(tmp_path: "Path") -> None:
    """modes.ECB(...) is flagged for leaking plaintext structure."""
    issues, inventory, _ = scan(tmp_path, "modes.ECB(iv)\n")
    issue = find_issue(issues, "FIPS-ECB")
    assert issue is not None
    assert issue.severity == "warning"
    entry = find_entry(inventory, "ECB")
    assert entry is not None
    assert entry.category == "symmetric"


# ---------------------------------------------------------------------------
# Section 5: PQC-CLASSICAL-KEX
# ---------------------------------------------------------------------------


def test_ecdh_flagged_with_ecdh_label(tmp_path: "Path") -> None:
    """ec.ECDH() is quantum-vulnerable key establishment; inventory label is 'ECDH'."""
    issues, inventory, _ = scan(tmp_path, "ec.ECDH()\n")
    issue = find_issue(issues, "PQC-CLASSICAL-KEX")
    assert issue is not None
    assert issue.severity == "warning"
    assert issue.pqc is True
    entry = find_entry(inventory, "ECDH")
    assert entry is not None
    assert entry.category == "key-establishment"
    assert entry.quantum_vulnerable is True


def test_x25519_flagged_with_x25519_label(tmp_path: "Path") -> None:
    """X25519PrivateKey is flagged; inventory label is the captured 'X25519'."""
    issues, inventory, _ = scan(tmp_path, "X25519PrivateKey.generate()\n")
    assert find_issue(issues, "PQC-CLASSICAL-KEX") is not None
    entry = find_entry(inventory, "X25519")
    assert entry is not None
    assert entry.category == "key-establishment"
    assert entry.quantum_vulnerable is True


def test_x448_flagged_with_x448_label(tmp_path: "Path") -> None:
    """X448PrivateKey is flagged; inventory label is the captured 'X448'."""
    issues, inventory, _ = scan(tmp_path, "X448PrivateKey.generate()\n")
    assert find_issue(issues, "PQC-CLASSICAL-KEX") is not None
    entry = find_entry(inventory, "X448")
    assert entry is not None
    assert entry.category == "key-establishment"
    assert entry.quantum_vulnerable is True


def test_rsa_oaep_flagged(tmp_path: "Path") -> None:
    """padding.OAEP(...) is RSA key transport, quantum-vulnerable."""
    issues, inventory, _ = scan(
        tmp_path, "padding.OAEP(mgf=None, algorithm=None, label=None)\n"
    )
    issue = find_issue(issues, "PQC-CLASSICAL-KEX")
    assert issue is not None
    entry = find_entry(inventory, "RSA-OAEP")
    assert entry is not None
    assert entry.category == "key-establishment"
    assert entry.quantum_vulnerable is True


# ---------------------------------------------------------------------------
# Section 6: PQC-CLASSICAL-SIG
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "label"),
    [
        ("ec.ECDSA(hashes.SHA256())\n", "ECDSA"),
        ("padding.PSS(mgf=None, salt_length=32)\n", "PSS"),
        ("padding.PKCS1v15()\n", "PKCS1v15"),
        ("Ed25519PrivateKey.generate()\n", "Ed25519"),
        ("Ed448PrivateKey.generate()\n", "Ed448"),
        ("rsa.generate_private_key(public_exponent=65537, key_size=2048)\n", "rsa"),
        ("dsa.generate_private_key(key_size=2048)\n", "dsa"),
    ],
)
def test_classical_signature_primitives_flagged(
    tmp_path: "Path", source: str, label: str
) -> None:
    """Each classical-only signature/RSA-keygen primitive is detected and labeled."""
    issues, inventory, _ = scan(tmp_path, source)
    issue = find_issue(issues, "PQC-CLASSICAL-SIG")
    assert issue is not None
    assert issue.severity == "info"
    assert issue.pqc is True
    entry = find_entry(inventory, label)
    assert entry is not None
    assert entry.category == "signature"
    assert entry.quantum_vulnerable is True


# ---------------------------------------------------------------------------
# Section 7: Inline suppression
# ---------------------------------------------------------------------------


def test_bare_suppression_excludes_issue_and_inventory(tmp_path: "Path") -> None:
    """A bare `# fips: ignore` removes the line from BOTH issues and inventory.

    This is the ordering-sensitive regression: suppression must be checked
    before the inventory append, otherwise a suppressed line still counts
    toward the CBOM migration metric even though no issue is raised.
    """
    issues, inventory, _ = scan(tmp_path, "hashlib.md5(data)  # fips: ignore\n")
    assert find_issue(issues, "FIPS-MD5") is None
    assert find_entry(inventory, "MD5") is None
    assert issues == []
    assert inventory == []


def test_scoped_suppression_suppresses_only_matching_code(tmp_path: "Path") -> None:
    """`# fips: ignore[PQC-CLASSICAL-KEX]` suppresses only that code on the line."""
    issues, inventory, _ = scan(
        tmp_path, "ec.ECDH()  # fips: ignore[PQC-CLASSICAL-KEX]\n"
    )
    assert find_issue(issues, "PQC-CLASSICAL-KEX") is None
    assert find_entry(inventory, "ECDH") is None


def test_scoped_suppression_does_not_suppress_other_codes(tmp_path: "Path") -> None:
    """A scoped ignore for FIPS-MD5 does not suppress an unrelated FIPS-SHA1 line."""
    issues, inventory, _ = scan(
        tmp_path, "hashlib.sha1(data)  # fips: ignore[FIPS-MD5]\n"
    )
    issue = find_issue(issues, "FIPS-SHA1")
    assert issue is not None
    assert find_entry(inventory, "SHA-1") is not None


# ---------------------------------------------------------------------------
# Section 8: Dependency scanning
# ---------------------------------------------------------------------------


def test_pyproject_known_bad_dep_flagged(tmp_path: "Path") -> None:
    """A pyproject.toml dependency present in DEP_RULES (bcrypt) is flagged."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\ndependencies = ["bcrypt>=4.0"]\n',
        encoding="utf-8",
    )
    issues: list[Issue] = []
    inventory: list[InventoryEntry] = []
    check_fips_compatibility.scan_dependencies(tmp_path, issues, inventory)
    issue = find_issue(issues, "FIPS-DEP")
    assert issue is not None
    assert issue.severity == "warning"
    assert "bcrypt" in issue.message


def test_requirements_txt_known_bad_dep_flagged(tmp_path: "Path") -> None:
    """A requirements.txt entry present in DEP_RULES (pycryptodome) is flagged."""
    (tmp_path / "requirements.txt").write_text("pycryptodome==3.9\n", encoding="utf-8")
    issues: list[Issue] = []
    inventory: list[InventoryEntry] = []
    check_fips_compatibility.scan_dependencies(tmp_path, issues, inventory)
    issue = find_issue(issues, "FIPS-DEP")
    assert issue is not None
    assert "pycryptodome" in issue.message


def test_malformed_pyproject_toml_raises_manifest_unparseable_error(
    tmp_path: "Path",
) -> None:
    """An unparseable pyproject.toml produces a FIPS-MANIFEST-UNPARSEABLE error.

    This is the single most important regression test: the previous
    implementation swallowed TOMLDecodeError and returned zero findings,
    which is a silent false-green on a broken manifest.
    """
    (tmp_path / "pyproject.toml").write_text(
        "[project\nname = broken\n", encoding="utf-8"
    )
    found, manifest_issues = check_fips_compatibility.collect_requirements(tmp_path)
    assert found == []
    assert len(manifest_issues) == 1
    issue = manifest_issues[0]
    assert issue.code == "FIPS-MANIFEST-UNPARSEABLE"
    assert issue.severity == "error"


def test_scan_dependencies_surfaces_malformed_manifest_issue(tmp_path: "Path") -> None:
    """scan_dependencies must surface the manifest_issues from collect_requirements."""
    (tmp_path / "pyproject.toml").write_text(
        "[project\nname = broken\n", encoding="utf-8"
    )
    issues: list[Issue] = []
    inventory: list[InventoryEntry] = []
    check_fips_compatibility.scan_dependencies(tmp_path, issues, inventory)
    issue = find_issue(issues, "FIPS-MANIFEST-UNPARSEABLE")
    assert issue is not None
    assert issue.severity == "error"


def test_tomllib_unavailable_warns_and_returns_empty(
    tmp_path: "Path", monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a runtime without tomllib (Python < 3.11), a FIPS-TOML-UNAVAILABLE

    warning is raised and no requirements are collected, instead of crashing.
    Simulated by patching the module's `tomllib` reference to None, matching
    the guard at the top of collect_requirements().
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["bcrypt"]\n', encoding="utf-8"
    )
    monkeypatch.setattr(check_fips_compatibility, "tomllib", None)
    found, manifest_issues = check_fips_compatibility.collect_requirements(tmp_path)
    assert found == []
    assert len(manifest_issues) == 1
    issue = manifest_issues[0]
    assert issue.code == "FIPS-TOML-UNAVAILABLE"
    assert issue.severity == "warning"


def test_cryptography_dependency_recorded_in_inventory(tmp_path: "Path") -> None:
    """A `cryptography` dependency declaration is recorded in the inventory."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["cryptography>=42.0"]\n',
        encoding="utf-8",
    )
    issues: list[Issue] = []
    inventory: list[InventoryEntry] = []
    check_fips_compatibility.scan_dependencies(tmp_path, issues, inventory)
    entry = find_entry(inventory, "cryptography")
    assert entry is not None
    assert entry.category == "library"


# ---------------------------------------------------------------------------
# Section 9: cryptography_bound_predates_pqc
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec",
    ["==45.0.0", "<46", "<46.0", "~=44.0"],
)
def test_bound_predates_pqc_true_cases(spec: str) -> None:
    """A version bound that excludes the PQC-capable release returns True."""
    assert check_fips_compatibility.cryptography_bound_predates_pqc(spec) is True


@pytest.mark.parametrize(
    "spec",
    [">=46.0", "~=46.0", "<46.1"],
)
def test_bound_predates_pqc_false_cases(spec: str) -> None:
    """A version bound that allows the PQC-capable release returns False."""
    assert check_fips_compatibility.cryptography_bound_predates_pqc(spec) is False


# ---------------------------------------------------------------------------
# Section 10: apply_pqc_mode
# ---------------------------------------------------------------------------


def _sample_issues() -> list[Issue]:
    return [
        Issue("a.py", 1, "error", "FIPS-MD5", "md5", pqc=False),
        Issue("a.py", 2, "warning", "PQC-CLASSICAL-KEX", "kex", pqc=True),
        Issue("a.py", 3, "info", "PQC-CLASSICAL-SIG", "sig", pqc=True),
    ]


def test_apply_pqc_mode_off_filters_pqc_issues() -> None:
    """pqc-mode off drops every issue with pqc=True but keeps classic ones."""
    issues = check_fips_compatibility.apply_pqc_mode(_sample_issues(), "off")
    assert [i.code for i in issues] == ["FIPS-MD5"]


def test_apply_pqc_mode_warn_leaves_severity_unchanged() -> None:
    """pqc-mode warn keeps all issues and does not change any severity."""
    original = _sample_issues()
    issues = check_fips_compatibility.apply_pqc_mode(original, "warn")
    assert [(i.code, i.severity) for i in issues] == [
        ("FIPS-MD5", "error"),
        ("PQC-CLASSICAL-KEX", "warning"),
        ("PQC-CLASSICAL-SIG", "info"),
    ]


def test_apply_pqc_mode_error_escalates_pqc_warning_to_error() -> None:
    """pqc-mode error escalates a PQC warning (quantum-vulnerable KEX) to error."""
    issues = check_fips_compatibility.apply_pqc_mode(_sample_issues(), "error")
    kex = find_issue(issues, "PQC-CLASSICAL-KEX")
    assert kex is not None
    assert kex.severity == "error"


def test_apply_pqc_mode_error_does_not_escalate_pqc_info() -> None:
    """pqc-mode error leaves PQC info findings (e.g. PQC-CLASSICAL-SIG) untouched."""
    issues = check_fips_compatibility.apply_pqc_mode(_sample_issues(), "error")
    sig = find_issue(issues, "PQC-CLASSICAL-SIG")
    assert sig is not None
    assert sig.severity == "info"


# ---------------------------------------------------------------------------
# Section 11: build_report
# ---------------------------------------------------------------------------


def test_build_report_summary_counts_match_issues() -> None:
    """summary.{errors,warnings,info,pqc_findings} match the issues list."""
    issues = _sample_issues()
    report = check_fips_compatibility.build_report(issues, [], "warn")
    assert report["summary"] == {
        "errors": 1,
        "warnings": 1,
        "info": 1,
        "pqc_findings": 2,
    }
    assert report["pqc_mode"] == "warn"
    assert report["issues"] == [i.as_dict() for i in issues]


def test_build_report_inventory_stats_correct() -> None:
    """inventory.stats.total, quantum_vulnerable and by_category are correct."""
    inventory = [
        InventoryEntry("MD5", "hash", "a.py", 1, False),
        InventoryEntry("ECDH", "key-establishment", "a.py", 2, True),
        InventoryEntry("AES", "symmetric", "a.py", 3, False),
    ]
    report = check_fips_compatibility.build_report([], inventory, "off")
    stats = report["inventory"]["stats"]
    assert stats["total"] == 3
    assert stats["quantum_vulnerable"] == 1
    assert stats["by_category"] == {"hash": 1, "key-establishment": 1, "symmetric": 1}
    assert report["inventory"]["algorithms"] == [e.as_dict() for e in inventory]


# ---------------------------------------------------------------------------
# Section 12: main() / CLI
# ---------------------------------------------------------------------------


def test_main_clean_dir_exits_zero(
    tmp_path: "Path", monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory with no FIPS/PQC findings exits 0."""
    write_py(tmp_path, "app.py", "print('hello world')\n")
    assert run_main(monkeypatch, ["--root", str(tmp_path)]) == 0


def test_main_fips_error_exits_one(
    tmp_path: "Path", monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory containing a classic FIPS error exits 1."""
    write_py(tmp_path, "app.py", "import hashlib\nhashlib.md5(data)\n")
    assert run_main(monkeypatch, ["--root", str(tmp_path)]) == 1


def test_main_json_output_has_expected_keys(
    tmp_path: "Path",
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--json emits valid JSON with the documented top-level shape."""
    write_py(tmp_path, "app.py", "import hashlib\nhashlib.md5(data)\nec.ECDH()\n")
    exit_code = run_main(monkeypatch, ["--root", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    report = json.loads(out)
    assert set(report["summary"]) == {"errors", "warnings", "info", "pqc_findings"}
    assert report["summary"]["errors"] >= 1
    assert report["summary"]["pqc_findings"] >= 1
    assert "pqc_mode" in report
    assert isinstance(report["issues"], list)
    assert set(report["inventory"]) >= {"algorithms", "stats"}
    assert exit_code == 1


def test_main_root_nonexistent_exits_two_with_stderr_message(
    tmp_path: "Path",
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A --root pointing at a nonexistent path exits 2 with an error: message."""
    missing = tmp_path / "does-not-exist"
    exit_code = run_main(monkeypatch, ["--root", str(missing)])
    err = capsys.readouterr().err
    assert exit_code == 2
    assert "error:" in err


def test_main_pqc_mode_off_skips_pqc_issues_but_keeps_inventory(
    tmp_path: "Path",
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """pqc-mode off: PQC issues are skipped but the inventory is still collected."""
    write_py(tmp_path, "app.py", "ec.ECDH()\n")
    exit_code = run_main(
        monkeypatch, ["--root", str(tmp_path), "--json", "--pqc-mode", "off"]
    )
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert all(not i["pqc"] for i in report["issues"])
    algorithms = [e["algorithm"] for e in report["inventory"]["algorithms"]]
    assert "ECDH" in algorithms


def test_main_pqc_mode_warn_reports_without_failing(
    tmp_path: "Path",
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """pqc-mode warn: PQC findings are present but do not affect the exit code."""
    write_py(tmp_path, "app.py", "ec.ECDH()\n")
    exit_code = run_main(
        monkeypatch, ["--root", str(tmp_path), "--json", "--pqc-mode", "warn"]
    )
    report = json.loads(capsys.readouterr().out)
    kex = next(i for i in report["issues"] if i["code"] == "PQC-CLASSICAL-KEX")
    assert kex["severity"] == "warning"
    assert exit_code == 0


def test_main_pqc_mode_error_escalates_kex_and_fails(
    tmp_path: "Path",
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """pqc-mode error: quantum-vulnerable KEX escalates to error and exit code is 1."""
    write_py(tmp_path, "app.py", "ec.ECDH()\n")
    exit_code = run_main(
        monkeypatch, ["--root", str(tmp_path), "--json", "--pqc-mode", "error"]
    )
    report = json.loads(capsys.readouterr().out)
    kex = next(i for i in report["issues"] if i["code"] == "PQC-CLASSICAL-KEX")
    assert kex["severity"] == "error"
    assert exit_code == 1


def test_main_strict_escalates_classic_warning_to_failure(
    tmp_path: "Path", monkeypatch: pytest.MonkeyPatch
) -> None:
    """--strict fails the build on a classic FIPS warning (e.g. SHA-1)."""
    write_py(tmp_path, "app.py", "hashlib.sha1(data)\n")
    assert run_main(monkeypatch, ["--root", str(tmp_path)]) == 0
    assert run_main(monkeypatch, ["--root", str(tmp_path), "--strict"]) == 1


def test_main_strict_does_not_escalate_pqc_warning(
    tmp_path: "Path", monkeypatch: pytest.MonkeyPatch
) -> None:
    """--strict does not escalate a PQC warning; PQC is governed by --pqc-mode only."""
    write_py(tmp_path, "app.py", "ec.ECDH()\n")
    exit_code = run_main(
        monkeypatch, ["--root", str(tmp_path), "--strict", "--pqc-mode", "warn"]
    )
    assert exit_code == 0
