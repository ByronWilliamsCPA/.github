"""Revisit-date enforcement for Trivy suppression files.

A Trivy suppression with no expiry is a permanent one: the finding disappears
from every scan and nothing ever forces a second look.  This checker requires
that each entry in `.trivyignore.yaml` carries an `expired_at` revisit date,
that the date has not already passed, and that it is no further out than a
configurable horizon (90 days by default).

The legacy plain-text `.trivyignore` format has no expiry field at all, so its
presence is reported as a violation unless explicitly allowed.

All inputs are read from environment variables so that GitHub Actions workflow
expressions never interpolate into the script body (injection-safe pattern).

Environment variables:
    TRIVYIGNORE_PATH:          Path to the YAML suppression file
                               (default: .trivyignore.yaml).
    LEGACY_TRIVYIGNORE_PATH:   Path to the plain-text suppression file
                               (default: .trivyignore).
    ALLOW_LEGACY_TRIVYIGNORE:  "true" or "1" to tolerate the plain-text file
                               even though it cannot carry revisit dates.
    MAX_HORIZON_DAYS:          Furthest an expired_at date may be set from
                               today (default: 90).
    WARN_WITHIN_DAYS:          Emit an advisory warning for entries due within
                               this many days (default: 14).
    REQUIRE_STATEMENT:         "true" or "1" (default) to require a non-empty
                               `statement` explaining each suppression.
    FAIL_ON_VIOLATION:         "true" or "1" (default) to exit 1 on violations;
                               any other value is advisory (warn only).
    TODAY:                     ISO date (YYYY-MM-DD) overriding "today".  Test
                               hook; unset in CI so the real clock is used.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised only without PyYAML
    # Recorded, not raised, at import time: raising here would turn a missing
    # dependency into a collection error for anything that merely imports this
    # module. main() reports it at the call site instead.
    yaml = None  # type: ignore[assignment]

# Trivy's suppression file groups entries by finding kind.  Any other
# top-level key is a typo or a format Trivy does not read, which would make
# the suppression silently ineffective, so it is reported rather than skipped.
ENTRY_KINDS = ("vulnerabilities", "misconfigurations", "secrets", "licenses")

_TRUE = {"true", "1"}


def _flag(name: str, *, default: bool = False) -> bool:
    """Read a boolean environment variable with an explicit default."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def _positive_int(name: str, default: int) -> int:
    """Read a positive integer environment variable, falling back on default.

    A non-numeric or non-positive value is a configuration error rather than
    something to silently coerce: a horizon of 0 or -30 would fail every entry,
    and a horizon of "ninety" would quietly become the default and under-report.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        sys.exit(f"::error::{name} must be an integer (got: {raw!r})")
    if value <= 0:
        sys.exit(f"::error::{name} must be greater than 0 (got: {value})")
    return value


def today() -> dt.date:
    """Return the reference date, honouring the TODAY test hook."""
    raw = os.environ.get("TODAY", "").strip()
    if not raw:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        sys.exit(f"::error::TODAY must be an ISO date YYYY-MM-DD (got: {raw!r})")


def parse_expiry(value: Any) -> dt.date | None:
    """Coerce an `expired_at` value to a date, or None if it is unusable.

    PyYAML resolves an unquoted YYYY-MM-DD to a date and a quoted one to a
    string, and Trivy accepts both, so both are handled here.  A datetime
    (timestamp form) is narrowed to its date.
    """
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def load_document(path: str) -> dict[str, Any] | None:
    """Load the YAML suppression file, or None when it does not exist.

    An unreadable or non-mapping document fails closed: treating a corrupt
    suppression file as "no suppressions" would report a clean revisit state
    for a file that Trivy itself may still be honouring.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        sys.exit(f"::error::Cannot parse {path}: {str(exc).splitlines()[0]}")

    if document is None:
        return {}
    if not isinstance(document, dict):
        sys.exit(
            f"::error::{path} must be a mapping of finding kinds"
            f" ({', '.join(ENTRY_KINDS)}); got {type(document).__name__}."
        )
    return document


def check_entry(
    kind: str,
    index: int,
    entry: Any,
    *,
    reference: dt.date,
    max_horizon_days: int,
    require_statement: bool,
) -> list[str]:
    """Validate one suppression entry and return its violations.

    Entry identity in messages falls back to the list position so a malformed
    entry with no `id` is still locatable.
    """
    violations: list[str] = []
    label = f"{kind}[{index}]"

    if not isinstance(entry, dict):
        return [f"{label}: entry must be a mapping, got {type(entry).__name__}"]

    entry_id = str(entry.get("id", "")).strip()
    label = f"{kind}[{index}] {entry_id}".rstrip()
    if not entry_id:
        violations.append(f"{label}: missing required `id`")

    if require_statement and not str(entry.get("statement", "")).strip():
        violations.append(
            f"{label}: missing `statement`. Record why the finding is"
            " suppressed so the revisit has context."
        )

    if "expired_at" not in entry:
        violations.append(
            f"{label}: missing `expired_at`. Every suppression needs a revisit"
            f" date no more than {max_horizon_days} days out."
        )
        return violations

    expiry = parse_expiry(entry["expired_at"])
    if expiry is None:
        violations.append(
            f"{label}: `expired_at` must be a date YYYY-MM-DD"
            f" (got: {entry['expired_at']!r})"
        )
        return violations

    horizon = reference + dt.timedelta(days=max_horizon_days)
    if expiry <= reference:
        violations.append(
            f"{label}: revisit date {expiry.isoformat()} has passed."
            " Re-justify the suppression with a new date, or remove it and fix"
            " the finding."
        )
    elif expiry > horizon:
        violations.append(
            f"{label}: revisit date {expiry.isoformat()} is beyond the"
            f" {max_horizon_days}-day horizon (latest allowed:"
            f" {horizon.isoformat()})."
        )
    return violations


def run_check(
    document: dict[str, Any],
    *,
    reference: dt.date,
    max_horizon_days: int,
    warn_within_days: int,
    require_statement: bool,
) -> tuple[list[str], list[str], int]:
    """Validate every entry in the document.

    Returns (violations, warnings, entry_count).
    """
    violations: list[str] = []
    warnings: list[str] = []
    entry_count = 0

    unknown = sorted(set(document) - set(ENTRY_KINDS))
    for key in unknown:
        violations.append(
            f"unknown top-level key `{key}`. Trivy reads only"
            f" {', '.join(ENTRY_KINDS)}; entries under any other key are"
            " silently ignored by the scanner."
        )

    warn_edge = reference + dt.timedelta(days=warn_within_days)
    for kind in ENTRY_KINDS:
        entries = document.get(kind)
        if entries is None:
            continue
        if not isinstance(entries, list):
            violations.append(
                f"{kind}: must be a list of entries, got {type(entries).__name__}"
            )
            continue
        for index, entry in enumerate(entries):
            entry_count += 1
            entry_violations = check_entry(
                kind,
                index,
                entry,
                reference=reference,
                max_horizon_days=max_horizon_days,
                require_statement=require_statement,
            )
            violations.extend(entry_violations)

            # Only entries that passed validation earn a due-soon warning; an
            # entry already reported as a violation does not need a second,
            # quieter line about the same date.
            if entry_violations or not isinstance(entry, dict):
                continue
            expiry = parse_expiry(entry.get("expired_at"))
            if expiry is not None and expiry <= warn_edge:
                entry_id = str(entry.get("id", "")).strip()
                warnings.append(
                    f"{kind} {entry_id}: revisit due {expiry.isoformat()}"
                    f" (within {warn_within_days} days)"
                )

    return violations, warnings, entry_count


def main() -> None:
    """Entry point: read env vars, validate suppressions, and exit."""
    if yaml is None:
        sys.exit(
            "::error::PyYAML is required to validate .trivyignore.yaml. Install"
            " it (pip install 'pyyaml==6.0.2') before running this checker."
        )

    path = os.environ.get("TRIVYIGNORE_PATH", ".trivyignore.yaml").strip()
    legacy_path = os.environ.get("LEGACY_TRIVYIGNORE_PATH", ".trivyignore").strip()
    max_horizon_days = _positive_int("MAX_HORIZON_DAYS", 90)
    warn_within_days = _positive_int("WARN_WITHIN_DAYS", 14)
    require_statement = _flag("REQUIRE_STATEMENT", default=True)
    fail_on_violation = _flag("FAIL_ON_VIOLATION", default=True)
    allow_legacy = _flag("ALLOW_LEGACY_TRIVYIGNORE")
    reference = today()

    violations: list[str] = []
    warnings: list[str] = []

    if legacy_path and os.path.exists(legacy_path):
        message = (
            f"{legacy_path}: the plain-text format has no `expired_at` field, so"
            " its suppressions never expire. Migrate the entries to"
            f" {path} with a revisit date on each one."
        )
        if allow_legacy:
            warnings.append(message)
        else:
            violations.append(message)

    document = load_document(path)
    entry_count = 0
    if document is None:
        print(f"No {path} found; no suppressions to validate.")
    else:
        doc_violations, doc_warnings, entry_count = run_check(
            document,
            reference=reference,
            max_horizon_days=max_horizon_days,
            warn_within_days=warn_within_days,
            require_statement=require_statement,
        )
        violations.extend(doc_violations)
        warnings.extend(doc_warnings)

    for warning in warnings:
        print(f"::warning::{warning}")

    if violations:
        # ::error:: / ::warning:: prefixes surface each finding as a GitHub
        # Actions annotation; bare print() output stays hidden inside the
        # collapsed step log.
        level = "error" if fail_on_violation else "warning"
        print(f"::{level}::Trivy suppression revisit-date violations:")
        for violation in violations:
            print(f"::{level}::{violation}")
        if fail_on_violation:
            sys.exit(1)
        return

    if entry_count:
        print(
            f"All {entry_count} Trivy suppression(s) carry a revisit date within"
            f" {max_horizon_days} days."
        )


if __name__ == "__main__":
    main()
