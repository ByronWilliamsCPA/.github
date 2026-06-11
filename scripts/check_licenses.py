"""License compliance checker for Python dependency inventories.

Reads CycloneDX SBOM (sbom-runtime.cdx.json) and/or pip-licenses inventory
(pip-licenses.json) from the current working directory, cross-checks them
against a configurable list of forbidden licenses, and reports or fails on
any match.

All inputs are read from environment variables so that GitHub Actions workflow
expressions never interpolate into the script body (injection-safe pattern).

Environment variables:
    FORBIDDEN_LICENSES: JSON array of forbidden license identifiers. SPDX IDs
                        (for example "AGPL-3.0-only") are preferred, but
                        free-text strings are also accepted; every entry is
                        matched both exactly and via the copyleft-family
                        heuristic in detect_family().
    ALLOWED_PACKAGES:   JSON array of allowlist entries.  Each entry is either
                        a bare package name (exempt from every copyleft family)
                        or "name:FAMILY" (exempt only that family).
    FAIL_ON_FORBIDDEN:  "true" or "1" to exit 1 when forbidden licenses are
                        found; any other value is advisory (warn only).
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import TypedDict, cast


class LicenseObj(TypedDict, total=False):
    id: str
    name: str


class LicenseEntry(TypedDict, total=False):
    license: LicenseObj
    expression: str


class SbomComponent(TypedDict, total=False):
    name: str
    licenses: list[LicenseEntry]


class Sbom(TypedDict, total=False):
    components: list[SbomComponent]


class PipLicenseRow(TypedDict, total=False):
    Name: str
    License: str


# Allowlist three-state semantics (see build_allowlist):
#   key absent        -> package not allowlisted; check normally
#   value None        -> blanket exemption (every copyleft family exempt)
#   value set[str]    -> only the named copyleft families are exempt
Allowlist = dict[str, set[str] | None]


def _oneline(exc: BaseException) -> str:
    """Flatten an exception message to one line.

    GitHub Actions ``::error::`` annotations are truncated at the first
    newline; JSONDecodeError messages can embed the offending document.
    """
    return str(exc).replace("\n", " ")


def norm(value: str | None) -> str:
    """Strip and normalise a potentially-None string."""
    return (value or "").strip()


def detect_family(text: str | None) -> str | None:
    """Map an SPDX id or free-text license string to a copyleft family.

    Returns one of "AGPL", "LGPL", "GPL", "MPL", or None for permissive
    licenses.  A "<token>-compatible" phrasing (for example the historic
    "GPL-compatible" classifier) describes a permissive license's compatibility
    with copyleft, not a copyleft grant, so those qualifiers are stripped
    before detection to avoid false positives.
    """
    lowered = (text or "").lower()
    lowered = re.sub(r"\b(?:a?gpl|lgpl|mpl)[- ]compatible\b", " ", lowered)
    if re.search(r"\baffero\b", lowered) or re.search(r"\bagpl", lowered):
        return "AGPL"
    if (
        re.search(r"\blesser\b", lowered)
        or re.search(r"\blgpl", lowered)
        or "library general public" in lowered
    ):
        return "LGPL"
    if re.search(r"\bgpl", lowered) or "gnu general public" in lowered:
        return "GPL"
    if re.search(r"\bmpl\b", lowered) or "mozilla public" in lowered:
        return "MPL"
    return None


def _load_json_file(path: str) -> object | None:
    """Load a JSON file, returning None if absent and exiting loudly otherwise.

    A missing file is a valid state (the caller decides whether at least one
    inventory is required), but a file that exists and cannot be read or
    parsed is always a hard error: silently skipping it would let a corrupt
    artifact produce a false "all licenses compatible" result.
    """
    try:
        with open(path) as handle:
            return cast("object", json.load(handle))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        sys.exit(f"::error::{path} is not valid JSON: {_oneline(exc)}")
    except OSError as exc:
        sys.exit(f"::error::Cannot read {path}: {_oneline(exc)}")


def load_sbom(path: str) -> Sbom | None:
    """Load a CycloneDX SBOM JSON file, returning None if absent.

    Exits with a ``::error::`` annotation if the file exists but is not valid
    JSON, is unreadable, or does not have the expected object shape.
    """
    data = _load_json_file(path)
    if data is None:
        return None
    if not isinstance(data, dict):
        sys.exit(f"::error::{path} must be a JSON object, got {type(data).__name__}")
    components = cast("dict[str, object]", data).get("components", [])
    if not isinstance(components, list):
        sys.exit(
            f"::error::{path}: 'components' must be a list,"
            f" got {type(components).__name__}"
        )
    return cast("Sbom", data)


def load_pip_licenses(path: str) -> list[PipLicenseRow] | None:
    """Load a pip-licenses JSON file, returning None if absent.

    Exits with a ``::error::`` annotation if the file exists but is not valid
    JSON, is unreadable, or is not a JSON array.
    """
    data = _load_json_file(path)
    if data is None:
        return None
    if not isinstance(data, list):
        sys.exit(f"::error::{path} must be a JSON array, got {type(data).__name__}")
    return cast("list[PipLicenseRow]", data)


def load_list(var_name: str) -> list[str]:
    """Parse a JSON-array environment variable, exiting loudly on bad input."""
    raw = os.environ.get(var_name, "[]")
    try:
        parsed = cast("object", json.loads(raw))
    except json.JSONDecodeError as exc:
        sys.exit(f"::error::{var_name} is not valid JSON: {_oneline(exc)}")
    if not isinstance(parsed, list):
        sys.exit(
            f"::error::{var_name} must be a JSON array, got {type(parsed).__name__}"
        )
    return [str(item) for item in cast("list[object]", parsed)]


def build_allowlist(entries: list[str]) -> Allowlist:
    """Build the package allowlist from the ALLOWED_PACKAGES list.

    Returns a dict mapping lowercase package name to either:
      - None: blanket exemption (all copyleft families exempt)
      - set[str]: the specific copyleft families that are exempt

    Note the two distinct meanings of None when reading the result: a stored
    None value means blanket exemption, while dict.get() returning None for an
    absent key means "not allowlisted at all".  Callers must check key
    membership before interpreting a None value (see check_package).
    """
    allowed: Allowlist = {}
    for entry in entries:
        name, _, family = entry.partition(":")
        name = name.strip().lower()
        family = family.strip().upper()
        if not family:
            allowed[name] = None
        else:
            existing = allowed.get(name)
            if existing is None and name in allowed:
                # Key already stored as None (blanket-exempt); a family-scoped
                # entry cannot downgrade a blanket exemption.
                pass
            elif existing is None:
                allowed[name] = {family}
            else:
                existing.add(family)
    return allowed


def check_package(
    pkg_name: str,
    strings: list[str | None],
    forbidden: set[str],
    forbidden_families: set[str],
    allowed: Allowlist,
) -> list[str]:
    """Return a list of issue strings for a single package.

    An empty list means the package is either clean (no forbidden licenses)
    or explicitly allowlisted; the two cases are indistinguishable here.
    """
    key = pkg_name.lower()
    if key in allowed and allowed[key] is None:
        return []  # blanket allowlist entry: skip every family

    # None here means "not allowlisted" (the blanket case returned above).
    exempt_families = allowed.get(key)

    flagged: set[str] = set()
    for raw in strings:
        text = norm(raw)
        if not text:
            continue
        family = detect_family(text)
        exact = text in forbidden
        heuristic = family is not None and family in forbidden_families
        if not exact and not heuristic:
            continue
        if exempt_families is not None and family in exempt_families:
            continue  # family-scoped exemption (for example certifi:MPL)
        flagged.add(text if exact else f"{text} [{family}]")

    return [f"{pkg_name}: {item}" for item in sorted(flagged)]


def run_check(
    sbom: Sbom | None,
    piplic: list[PipLicenseRow] | None,
    forbidden: set[str],
    forbidden_families: set[str],
    allowed: Allowlist,
) -> list[str]:
    """Return sorted, deduplicated issues across both inventory sources."""
    issues: list[str] = []

    if sbom:
        for component in sbom.get("components", []):
            name = component.get("name", "")
            if not name:
                print(
                    "::warning::SBOM component with empty or missing name;"
                    " its license entries are attributed to ''."
                )
            strings: list[str | None] = []
            for lic in component.get("licenses", []):
                license_obj = lic.get("license", {})
                strings.append(license_obj.get("id"))
                strings.append(license_obj.get("name"))
                strings.append(lic.get("expression"))
            issues.extend(
                check_package(name, strings, forbidden, forbidden_families, allowed)
            )

    if piplic:
        for row in piplic:
            issues.extend(
                check_package(
                    row.get("Name", ""),
                    [row.get("License")],
                    forbidden,
                    forbidden_families,
                    allowed,
                )
            )

    return sorted(set(issues))


def main() -> None:
    """Entry point: read env vars, load inventories, run check, and exit."""
    forbidden = set(load_list("FORBIDDEN_LICENSES"))
    fail_on = os.environ.get("FAIL_ON_FORBIDDEN", "false").strip().lower() in {
        "true",
        "1",
    }
    forbidden_families = {fam for fam in (detect_family(x) for x in forbidden) if fam}
    allowed = build_allowlist(load_list("ALLOWED_PACKAGES"))

    sbom = load_sbom("sbom-runtime.cdx.json")
    piplic = load_pip_licenses("pip-licenses.json")

    if sbom is None and piplic is None:
        msg = (
            "::error::No license inventory found (neither"
            " sbom-runtime.cdx.json nor pip-licenses.json). Cannot verify"
            " dependency licenses; failing rather than reporting clean."
        )
        sys.exit(msg)

    try:
        issues = run_check(sbom, piplic, forbidden, forbidden_families, allowed)
    except (AttributeError, TypeError) as exc:
        # Root shapes are validated at load time, but deeper malformations
        # (for example a string where CycloneDX requires a license object)
        # surface here.  Exit loudly: a mid-scan crash must never read as a
        # partial "clean" result.
        sys.exit(f"::error::Malformed license inventory structure: {_oneline(exc)}")

    if issues:
        # ::warning:: / ::error:: prefixes surface each finding as a GitHub
        # Actions annotation; bare print() output is hidden inside the
        # collapsed step log, which made advisory-mode findings invisible.
        level = "error" if fail_on else "warning"
        print(f"::{level}::Found forbidden or copyleft licenses:")
        for issue in issues:
            print(f"::{level}::{issue}")
        if fail_on:
            sys.exit(1)
    else:
        print("All licenses compatible")


if __name__ == "__main__":
    main()
