"""Tests for scripts/check_licenses.py.

Covers the nine cases enumerated in issue #193:
1. Exact SPDX id match (e.g. AGPL-3.0-only)
2. Free-text family mapping (e.g. PyMuPDF "GNU AFFERO GPL 3.0 ..." -> AGPL;
   "GNU Lesser General Public License v3" -> LGPL)
3. Scoped allowlist: certifi:MPL exempts certifi's MPL but not certifi's AGPL
4. Blanket allowlist back-compat: a bare name entry exempts all families
5. <token>-compatible suppression (e.g. GPL-compatible not flagged)
6. PEP 639 coverage via pip-licenses.json (package absent from the SBOM)
7. Both-inventories-missing fails with ::error::
8. Malformed FORBIDDEN_LICENSES / ALLOWED_PACKAGES JSON fails with ::error::
9. Gating mode (fail-on-forbidden-licenses: true) exits 1 on a forbidden license
"""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

# Add scripts/ to sys.path so we can import check_licenses without a package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import check_licenses  # noqa: E402

if TYPE_CHECKING:
    from check_licenses import Sbom

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_FORBIDDEN = [
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "LGPL-2.0-only",
    "LGPL-2.0-or-later",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "MPL-2.0",
]

_DEFAULT_FORBIDDEN_SET = set(_DEFAULT_FORBIDDEN)
_DEFAULT_FORBIDDEN_FAMILIES = {
    fam for fam in (check_licenses.detect_family(x) for x in _DEFAULT_FORBIDDEN) if fam
}


def make_sbom(*components: dict[str, object]) -> "Sbom":
    """Build a minimal CycloneDX-shaped SBOM dict for testing."""
    return {"components": list(components)}  # type: ignore[return-value]


def sbom_component(name: str, licenses: list[dict[str, object]]) -> dict[str, object]:
    """Construct a single CycloneDX component dict."""
    return {"name": name, "licenses": licenses}


def sbom_license_id(spdx_id: str) -> dict[str, object]:
    """License entry using the CycloneDX ``id`` field."""
    return {"license": {"id": spdx_id}}


def sbom_license_name(name: str) -> dict[str, object]:
    """License entry using the CycloneDX ``name`` field (free-text)."""
    return {"license": {"name": name}}


def run_check(
    sbom: "Sbom | None",
    piplic: list[dict[str, object]] | None,
    forbidden: set[str] = _DEFAULT_FORBIDDEN_SET,
    forbidden_families: set[str] = _DEFAULT_FORBIDDEN_FAMILIES,
    allowed: dict[str, set[str] | None] | None = None,
) -> list[str]:
    """Thin wrapper around check_licenses.run_check with sensible defaults."""
    if allowed is None:
        allowed = {}
    return check_licenses.run_check(
        sbom,
        piplic,  # type: ignore[arg-type]
        forbidden,
        forbidden_families,
        allowed,
    )


# ---------------------------------------------------------------------------
# Test 1: Exact SPDX id match
# ---------------------------------------------------------------------------


def test_exact_spdx_id_match_flagged() -> None:
    """A component whose license id is in the forbidden list is reported."""
    sbom = make_sbom(sbom_component("bad-pkg", [sbom_license_id("AGPL-3.0-only")]))
    issues = run_check(sbom, None)
    assert issues == ["bad-pkg: AGPL-3.0-only"]


def test_exact_spdx_id_mit_not_flagged() -> None:
    """A component with MIT license id is not reported."""
    sbom = make_sbom(sbom_component("good-pkg", [sbom_license_id("MIT")]))
    issues = run_check(sbom, None)
    assert issues == []


# ---------------------------------------------------------------------------
# Test 2: Free-text family mapping
# ---------------------------------------------------------------------------


def test_free_text_agpl_mapped_and_flagged() -> None:
    """PyMuPDF-style free-text AGPL string is mapped to AGPL family and flagged."""
    name = "GNU AFFERO GPL 3.0 or Artifex Commercial License"
    sbom = make_sbom(sbom_component("pymupdf", [sbom_license_name(name)]))
    issues = run_check(sbom, None)
    assert issues == [f"pymupdf: {name} [AGPL]"]


def test_free_text_lgpl_mapped_and_flagged() -> None:
    """GNU Lesser General Public License v3 is mapped to LGPL and flagged."""
    name = "GNU Lesser General Public License v3"
    sbom = make_sbom(sbom_component("lgpl-pkg", [sbom_license_name(name)]))
    issues = run_check(sbom, None)
    assert issues == [f"lgpl-pkg: {name} [LGPL]"]


# ---------------------------------------------------------------------------
# Test 3: Scoped allowlist (certifi:MPL)
# ---------------------------------------------------------------------------


def test_scoped_allowlist_mpl_exempts_certifi_mpl() -> None:
    """certifi:MPL exempts certifi from MPL but not from other families."""
    allowed = check_licenses.build_allowlist(["certifi:MPL"])
    sbom = make_sbom(sbom_component("certifi", [sbom_license_id("MPL-2.0")]))
    issues = run_check(sbom, None, allowed=allowed)
    assert issues == []


def test_scoped_allowlist_does_not_exempt_certifi_agpl() -> None:
    """certifi:MPL does NOT exempt certifi if it were to declare AGPL."""
    allowed = check_licenses.build_allowlist(["certifi:MPL"])
    sbom = make_sbom(sbom_component("certifi", [sbom_license_id("AGPL-3.0-only")]))
    issues = run_check(sbom, None, allowed=allowed)
    assert issues == ["certifi: AGPL-3.0-only"]


# ---------------------------------------------------------------------------
# Test 4: Blanket allowlist back-compat
# ---------------------------------------------------------------------------


def test_blanket_allowlist_exempts_all_families() -> None:
    """A bare package name in the allowlist skips every copyleft family."""
    allowed = check_licenses.build_allowlist(["somepkg"])
    sbom = make_sbom(sbom_component("somepkg", [sbom_license_id("GPL-3.0-only")]))
    issues = run_check(sbom, None, allowed=allowed)
    assert issues == []


# ---------------------------------------------------------------------------
# Test 5: <token>-compatible suppression
# ---------------------------------------------------------------------------


def test_gpl_compatible_classifier_not_flagged() -> None:
    """A 'GPL-compatible' string describes a permissive license; it is NOT flagged."""
    name = "GPL-compatible Open Source License"
    sbom = make_sbom(sbom_component("compat-pkg", [sbom_license_name(name)]))
    issues = run_check(sbom, None)
    assert issues == []


def test_agpl_compatible_not_flagged() -> None:
    """An 'AGPL-compatible' phrase is not a copyleft grant and must not be flagged."""
    name = "AGPL-compatible permissive license"
    sbom = make_sbom(sbom_component("permissive-pkg", [sbom_license_name(name)]))
    issues = run_check(sbom, None)
    assert issues == []


# ---------------------------------------------------------------------------
# Test 6: PEP 639 coverage via pip-licenses.json
# ---------------------------------------------------------------------------


def test_pip_licenses_catches_pep639_package() -> None:
    """A package absent from the SBOM but present in pip-licenses.json is flagged."""
    piplic = [{"Name": "hypothesis", "License": "AGPL-3.0-only"}]
    # Pass None for sbom to simulate the package being absent from the SBOM.
    issues = run_check(None, piplic)  # type: ignore[arg-type]
    assert issues == ["hypothesis: AGPL-3.0-only"]


def test_pip_licenses_permissive_not_flagged() -> None:
    """A package in pip-licenses.json with a permissive license is not flagged."""
    piplic = [{"Name": "requests", "License": "Apache-2.0"}]
    issues = run_check(None, piplic)  # type: ignore[arg-type]
    assert issues == []


# ---------------------------------------------------------------------------
# Test 7: Both inventories missing
# ---------------------------------------------------------------------------


def test_both_inventories_missing_exits_with_error(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """When both sbom and pip-licenses are absent, main() exits non-zero with ::error::."""
    env = {
        "FORBIDDEN_LICENSES": json.dumps(_DEFAULT_FORBIDDEN),
        "ALLOWED_PACKAGES": "[]",
        "FAIL_ON_FORBIDDEN": "false",
    }
    with patch.dict(os.environ, env, clear=False):
        import os as _os

        original_cwd = _os.getcwd()
        _os.chdir(tmp_path)  # type: ignore[arg-type]
        try:
            with pytest.raises(SystemExit) as exc_info:
                check_licenses.main()
        finally:
            _os.chdir(original_cwd)

    assert exc_info.value.code != 0
    assert "::error::" in str(exc_info.value.code)


# ---------------------------------------------------------------------------
# Test 8: Malformed JSON input
# ---------------------------------------------------------------------------


def test_malformed_forbidden_licenses_exits_with_error() -> None:
    """A non-JSON FORBIDDEN_LICENSES value causes sys.exit with ::error::."""
    with patch.dict(os.environ, {"FORBIDDEN_LICENSES": "not-json"}):
        with pytest.raises(SystemExit) as exc_info:
            check_licenses.load_list("FORBIDDEN_LICENSES")
    assert "::error::FORBIDDEN_LICENSES" in str(exc_info.value.code)


def test_forbidden_licenses_not_array_exits_with_error() -> None:
    """FORBIDDEN_LICENSES set to a JSON object (not array) causes sys.exit."""
    with patch.dict(os.environ, {"FORBIDDEN_LICENSES": '{"key": "value"}'}):
        with pytest.raises(SystemExit) as exc_info:
            check_licenses.load_list("FORBIDDEN_LICENSES")
    assert "::error::FORBIDDEN_LICENSES" in str(exc_info.value.code)


def test_malformed_allowed_packages_exits_with_error() -> None:
    """A non-JSON ALLOWED_PACKAGES value causes sys.exit with ::error::."""
    with patch.dict(os.environ, {"ALLOWED_PACKAGES": "bad[json"}):
        with pytest.raises(SystemExit) as exc_info:
            check_licenses.load_list("ALLOWED_PACKAGES")
    assert "::error::ALLOWED_PACKAGES" in str(exc_info.value.code)


# ---------------------------------------------------------------------------
# Test 9: Gating mode exits 1
# ---------------------------------------------------------------------------


def test_gating_mode_exits_1_on_forbidden(tmp_path: pytest.TempPathFactory) -> None:
    """With FAIL_ON_FORBIDDEN=true, a forbidden license causes sys.exit(1)."""
    sbom_data: dict[str, object] = {
        "components": [
            {"name": "evil-pkg", "licenses": [{"license": {"id": "GPL-3.0-only"}}]}
        ]
    }
    sbom_path = tmp_path / "sbom-runtime.cdx.json"  # type: ignore[operator]
    sbom_path.write_text(json.dumps(sbom_data))  # type: ignore[union-attr]

    env = {
        "FORBIDDEN_LICENSES": json.dumps(_DEFAULT_FORBIDDEN),
        "ALLOWED_PACKAGES": "[]",
        "FAIL_ON_FORBIDDEN": "true",
    }
    with patch.dict(os.environ, env, clear=False):
        import os as _os

        original_cwd = _os.getcwd()
        _os.chdir(tmp_path)  # type: ignore[arg-type]
        try:
            with pytest.raises(SystemExit) as exc_info:
                check_licenses.main()
        finally:
            _os.chdir(original_cwd)

    assert exc_info.value.code == 1


def test_advisory_mode_does_not_exit_on_forbidden(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """With FAIL_ON_FORBIDDEN=false, a forbidden license warns but does not exit 1."""
    sbom_data: dict[str, object] = {
        "components": [
            {"name": "evil-pkg", "licenses": [{"license": {"id": "GPL-3.0-only"}}]}
        ]
    }
    sbom_path = tmp_path / "sbom-runtime.cdx.json"  # type: ignore[operator]
    sbom_path.write_text(json.dumps(sbom_data))  # type: ignore[union-attr]

    env = {
        "FORBIDDEN_LICENSES": json.dumps(_DEFAULT_FORBIDDEN),
        "ALLOWED_PACKAGES": "[]",
        "FAIL_ON_FORBIDDEN": "false",
    }
    with patch.dict(os.environ, env, clear=False):
        import os as _os

        original_cwd = _os.getcwd()
        _os.chdir(tmp_path)  # type: ignore[arg-type]
        try:
            # Should NOT raise; advisory mode just prints the warning.
            check_licenses.main()
        finally:
            _os.chdir(original_cwd)
