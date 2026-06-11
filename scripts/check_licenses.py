"""License compliance checker for Python dependency inventories.

Reads CycloneDX SBOM (sbom-runtime.cdx.json) and/or pip-licenses inventory
(pip-licenses.json) from the current working directory, cross-checks them
against a configurable list of forbidden SPDX license IDs, and reports or
fails on any match.

All inputs are read from environment variables so that GitHub Actions workflow
expressions never interpolate into the script body (injection-safe pattern).

Environment variables:
    FORBIDDEN_LICENSES: JSON array of forbidden SPDX license IDs.
    ALLOWED_PACKAGES:   JSON array of allowlist entries.  Each entry is either
                        a bare package name (exempt from every copyleft family)
                        or "name:FAMILY" (exempt only that family).
    FAIL_ON_FORBIDDEN:  "true" to exit 1 when forbidden licenses are found;
                        any other value is advisory (warn only).
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


def load_sbom(path: str) -> Sbom | None:
    """Load a CycloneDX SBOM JSON file, returning None if absent."""
    try:
        with open(path) as handle:
            return cast("Sbom", json.load(handle))
    except FileNotFoundError:
        return None


def load_pip_licenses(path: str) -> list[PipLicenseRow] | None:
    """Load a pip-licenses JSON file, returning None if absent."""
    try:
        with open(path) as handle:
            return cast("list[PipLicenseRow]", json.load(handle))
    except FileNotFoundError:
        return None


def load_list(var_name: str) -> list[str]:
    """Parse a JSON-array environment variable, exiting loudly on bad input."""
    raw = os.environ.get(var_name, "[]")
    try:
        parsed = cast("object", json.loads(raw))
    except json.JSONDecodeError as exc:
        sys.exit(f"::error::{var_name} is not valid JSON: {exc}")
    if not isinstance(parsed, list):
        sys.exit(
            f"::error::{var_name} must be a JSON array, got {type(parsed).__name__}"
        )
    return [str(item) for item in cast("list[object]", parsed)]


def build_allowlist(entries: list[str]) -> dict[str, set[str] | None]:
    """Build the package allowlist from the ALLOWED_PACKAGES list.

    Returns a dict mapping lowercase package name to either:
      - None: blanket exemption (all copyleft families exempt)
      - set[str]: the specific copyleft families that are exempt
    """
    allowed: dict[str, set[str] | None] = {}
    for entry in entries:
        name, _, family = entry.partition(":")
        name = name.strip().lower()
        family = family.strip().upper()
        if not family:
            allowed[name] = None
        else:
            existing = allowed.get(name)
            if existing is None and name in allowed:
                # Already blanket-exempt; keep it
                pass
            elif existing is None:
                allowed[name] = {family}
            else:
                existing.add(family)
    return allowed


_UNSET: object = object()


def check_package(
    pkg_name: str,
    strings: list[str | None],
    forbidden: set[str],
    forbidden_families: set[str],
    allowed: dict[str, set[str] | None],
) -> list[str]:
    """Return a list of issue strings for a single package.

    An empty list means the package is compatible.
    """
    exempt = allowed.get(pkg_name.lower(), _UNSET)
    if exempt is None:
        return []  # blanket allowlist entry: skip every family

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
        if exempt is not _UNSET and isinstance(exempt, set) and family in exempt:
            continue  # family-scoped exemption (for example certifi:MPL)
        flagged.add(text if exact else f"{text} [{family}]")

    return [f"{pkg_name}: {item}" for item in sorted(flagged)]


def run_check(
    sbom: Sbom | None,
    piplic: list[PipLicenseRow] | None,
    forbidden: set[str],
    forbidden_families: set[str],
    allowed: dict[str, set[str] | None],
) -> list[str]:
    """Return sorted, deduplicated issues across both inventory sources."""
    issues: list[str] = []

    if sbom:
        for component in sbom.get("components", []):
            name = component.get("name", "")
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
    fail_on = os.environ.get("FAIL_ON_FORBIDDEN", "false").lower() == "true"
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

    issues = run_check(sbom, piplic, forbidden, forbidden_families, allowed)

    if issues:
        print("WARNING: Found forbidden or copyleft licenses:")
        for issue in issues:
            print(f"  - {issue}")
        if fail_on:
            sys.exit(1)
    else:
        print("All licenses compatible")


if __name__ == "__main__":
    main()
