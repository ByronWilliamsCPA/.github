#!/usr/bin/env python3
"""Org-central FIPS 140-2/140-3 and PQC-readiness checker for Python projects.

This is the canonical checker consumed by the reusable workflow
`.github/workflows/python-fips-compatibility.yml`. Downstream repositories get
it automatically (the workflow fetches it from ByronWilliamsCPA/.github when
the repo has no local checker); a repo may still ship its own script at
`scripts/check_fips_compatibility.py` to override it, provided the script
honors the same CLI and JSON contract documented in
`docs/workflows/python-fips-compatibility.md`.

Two rule families are enforced:

1. Classic FIPS rules (codes `FIPS-*`): non-approved algorithms such as MD5
   without `usedforsecurity=False`, DES/RC4/Blowfish ciphers, and
   non-validated crypto dependencies. These gate exactly as before: errors
   fail the build; warnings fail it only under `--strict`.

2. PQC readiness rules (codes `PQC-*`): classical-only key establishment and
   signatures that are quantum-vulnerable, plus dependency-capability checks.
   NIST finalized FIPS 203 (ML-KEM), FIPS 204 (ML-DSA) and FIPS 205 (SLH-DSA)
   in August 2024, and NIST IR 8547 schedules deprecation of 112-bit-strength
   classical algorithms after 2030 (disallowed after 2035). Hybrid key
   establishment that combines ML-KEM with a classical exchange is permitted
   under SP 800-56C Rev. 2. The `--pqc-mode` flag is the migration ratchet:

   - `off`:   PQC rules are skipped (inventory is still collected).
   - `warn`:  PQC findings are reported but NEVER fail the build; they are
              also exempt from `--strict` escalation so the classic FIPS
              ratchet and the PQC ratchet move independently.
   - `error`: warning-level PQC findings (quantum-vulnerable key
              establishment, non-validated PQC dependencies) are escalated to
              errors and gate the build.

Every crypto touchpoint found is also recorded in a CBOM-style algorithm
inventory (JSON `inventory` key) so compliance state can be aggregated across
the fleet; that inventory is the migration progress metric.

Exit codes: 0 = compliant (per mode); 1 = errors found, or classic warnings
found under --strict; 2 = usage error (e.g. --root is not a directory).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None  # type: ignore[assignment]

# Directories never scanned. `.`-prefixed directories are skipped separately;
# `.fips-central-checker` (the workflow's fallback checkout of this repo) is
# covered by that rule.
SKIP_DIRS = {
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
    "venv",
}

# Self-exclusion: a downstream copy of this checker contains the rule patterns
# below as string literals; scanning it would report the ruleset itself.
SELF_NAMES = {"check_fips_compatibility.py"}

MAX_FILE_BYTES = 2_000_000

SUPPRESS_RE = re.compile(r"#\s*fips:\s*ignore(?:\[(?P<codes>[A-Z0-9-,\s]+)\])?", re.I)

# #VERIFY pyca/cryptography grew ML-KEM/ML-DSA support in release 46 when
# built against OpenSSL 3.5+. Revisit this threshold when bumping the checker.
CRYPTOGRAPHY_PQC_MIN_MAJOR = 46

PQC_CAPABLE_DEPS = {"liboqs-python", "pqcrypto", "oqs", "quantcrypt"}


@dataclass
class Issue:
    file: str
    line: int
    severity: str  # error | warning | info
    code: str
    message: str
    fix_hint: str = ""
    pqc: bool = False

    def as_dict(self) -> dict:
        d = {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "pqc": self.pqc,
        }
        if self.fix_hint:
            d["fix_hint"] = self.fix_hint
        return d


@dataclass
class InventoryEntry:
    algorithm: str
    category: str  # hash | symmetric | key-establishment | signature | tls | pqc | kdf
    file: str
    line: int
    quantum_vulnerable: bool

    def as_dict(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "quantum_vulnerable": self.quantum_vulnerable,
        }


@dataclass
class SourceRule:
    code: str
    severity: str
    pattern: re.Pattern
    message: str
    fix_hint: str = ""
    pqc: bool = False
    # usedforsecurity=False on the same call suppresses the finding
    honors_usedforsecurity: bool = False
    # inventory metadata; algorithm may use a capture-group template like {1}
    algorithm: str = ""
    category: str = ""
    quantum_vulnerable: bool = False


SOURCE_RULES: list[SourceRule] = [
    # ------------------------------------------------------------------
    # Classic FIPS rules
    # ------------------------------------------------------------------
    SourceRule(
        code="FIPS-MD5",
        severity="error",
        pattern=re.compile(r"hashlib\.md5\s*\("),
        message="MD5 usage without usedforsecurity=False fails in FIPS mode.",
        fix_hint=(
            "Add usedforsecurity=False for non-security use (checksums, cache "
            "keys), or switch to hashlib.sha256 for security contexts."
        ),
        honors_usedforsecurity=True,
        algorithm="MD5",
        category="hash",
    ),
    SourceRule(
        code="FIPS-MD5",
        severity="error",
        pattern=re.compile(r"hashlib\.new\s*\(\s*['\"]md5['\"]"),
        message="hashlib.new('md5') without usedforsecurity=False fails in FIPS mode.",
        fix_hint="Add usedforsecurity=False, or use a SHA-2/SHA-3 digest.",
        honors_usedforsecurity=True,
        algorithm="MD5",
        category="hash",
    ),
    SourceRule(
        code="FIPS-SHA1",
        severity="warning",
        pattern=re.compile(r"hashlib\.sha1\s*\("),
        message=(
            "SHA-1 is disallowed for digital signatures and being phased out; "
            "verify this usage is non-security."
        ),
        fix_hint=(
            "Prefer SHA-256, or add usedforsecurity=False for non-security use."
        ),
        honors_usedforsecurity=True,
        algorithm="SHA-1",
        category="hash",
    ),
    SourceRule(
        code="FIPS-CIPHER",
        severity="error",
        pattern=re.compile(r"algorithms\.(TripleDES|Blowfish|ARC4|IDEA|CAST5|SEED)\s*\("),
        message="Cipher is not FIPS-approved.",
        fix_hint="Use algorithms.AES; AES-128/192/256 are FIPS-approved.",
        algorithm="{1}",
        category="symmetric",
    ),
    SourceRule(
        code="FIPS-CIPHER",
        severity="error",
        pattern=re.compile(
            r"from\s+Crypto(?:dome)?\.Cipher\s+import\s+\w*(DES3?|ARC[24]|Blowfish|CAST|Salsa20)"
        ),
        message="Cipher import is not FIPS-approved.",
        fix_hint="Use AES via pyca/cryptography built against a validated OpenSSL.",
        algorithm="{1}",
        category="symmetric",
    ),
    SourceRule(
        code="FIPS-CHACHA20",
        severity="warning",
        pattern=re.compile(r"\bChaCha20(?:Poly1305)?\s*\("),
        message="ChaCha20/ChaCha20-Poly1305 is not a FIPS-approved cipher.",
        fix_hint="Use AES-GCM (AESGCM) in FIPS environments.",
        algorithm="ChaCha20",
        category="symmetric",
    ),
    SourceRule(
        code="FIPS-ECB",
        severity="warning",
        pattern=re.compile(r"modes\.ECB\s*\("),
        message="ECB mode leaks plaintext structure and is unsafe for data at rest or in transit.",
        fix_hint="Use an authenticated mode such as GCM.",
        algorithm="ECB",
        category="symmetric",
    ),
    # ------------------------------------------------------------------
    # PQC readiness rules (quantum-vulnerable primitives; Shor's algorithm)
    # ------------------------------------------------------------------
    SourceRule(
        code="PQC-CLASSICAL-KEX",
        severity="warning",
        pattern=re.compile(r"ec\.(ECDH)\s*\(|\b(X25519|X448)PrivateKey\b"),
        message=(
            "Classical-only key establishment is quantum-vulnerable "
            "(harvest-now-decrypt-later risk)."
        ),
        fix_hint=(
            "Plan hybrid key establishment: combine ML-KEM (FIPS 203) with the "
            "classical exchange per NIST SP 800-56C Rev. 2."
        ),
        pqc=True,
        algorithm="{1}",
        category="key-establishment",
        quantum_vulnerable=True,
    ),
    SourceRule(
        code="PQC-CLASSICAL-KEX",
        severity="warning",
        pattern=re.compile(r"padding\.OAEP\s*\("),
        message=(
            "RSA key transport (OAEP) is quantum-vulnerable "
            "(harvest-now-decrypt-later risk)."
        ),
        fix_hint=(
            "Plan migration to ML-KEM (FIPS 203) based key establishment, or a "
            "hybrid scheme per NIST SP 800-56C Rev. 2."
        ),
        pqc=True,
        algorithm="RSA-OAEP",
        category="key-establishment",
        quantum_vulnerable=True,
    ),
    SourceRule(
        code="PQC-CLASSICAL-SIG",
        severity="info",
        pattern=re.compile(
            r"ec\.(ECDSA)\s*\(|padding\.(PSS|PKCS1v15)\s*\("
            r"|\b(Ed25519|Ed448)PrivateKey\b|\b(dsa|rsa)\.generate_private_key\b"
        ),
        message=(
            "Classical-only public-key primitive (signature or RSA keygen); "
            "quantum-vulnerable in the NIST IR 8547 transition timeline "
            "(deprecated after 2030)."
        ),
        fix_hint=(
            "Plan migration to ML-DSA (FIPS 204) or SLH-DSA (FIPS 205), or a "
            "hybrid signature scheme."
        ),
        pqc=True,
        algorithm="{1}",
        category="signature",
        quantum_vulnerable=True,
    ),
    SourceRule(
        code="PQC-TLS-CONTEXT",
        severity="info",
        pattern=re.compile(r"ssl\.SSLContext\s*\(|ssl\.create_default_context\s*\("),
        message=(
            "TLS group negotiation is delegated to the linked OpenSSL; hybrid "
            "key exchange (e.g. X25519MLKEM768) requires OpenSSL 3.5+ at runtime."
        ),
        fix_hint=(
            "Track the runtime OpenSSL version; the workflow's pqc-probe "
            "runtime leg reports hybrid capability of the environment."
        ),
        pqc=True,
        algorithm="TLS",
        category="tls",
        quantum_vulnerable=True,
    ),
]

# Inventory-only patterns: recorded in the CBOM, never raise an issue.
INVENTORY_PATTERNS: list[tuple[re.Pattern, str, str, bool]] = [
    (re.compile(r"hashlib\.(sha256|sha384|sha512|sha3_\d{3}|blake2[bs])\s*\("), "{1}", "hash", False),
    (re.compile(r"algorithms\.AES\s*\(|\bAESGCM\s*\("), "AES", "symmetric", False),
    (re.compile(r"\bpbkdf2_hmac\s*\(|\bPBKDF2HMAC\s*\("), "PBKDF2-HMAC", "kdf", False),
    (re.compile(r"\bhmac\.(new|digest)\s*\("), "HMAC", "hash", False),
]

# Presence of these identifiers marks the code as already PQC-aware.
PQC_CAPABLE_CODE_RE = re.compile(
    r"\b(ml_kem|MLKEM|ml_dsa|MLDSA|slh_dsa|SLHDSA|kyber|dilithium|sphincs)\b"
)

# Dependency denylist: name -> (code, severity, pqc, message, fix_hint)
DEP_RULES: dict[str, tuple[str, str, bool, str, str]] = {
    "bcrypt": (
        "FIPS-DEP",
        "warning",
        False,
        "bcrypt uses Blowfish-based hashing, which is not FIPS-approved.",
        "Use PBKDF2-HMAC-SHA256 (NIST SP 800-132), e.g. passlib or hashlib.pbkdf2_hmac.",
    ),
    "pycrypto": (
        "FIPS-DEP",
        "error",
        False,
        "pycrypto is unmaintained and not FIPS-validated.",
        "Migrate to pyca/cryptography built against a validated OpenSSL.",
    ),
    "pycryptodome": (
        "FIPS-DEP",
        "warning",
        False,
        "pycryptodome is not FIPS 140-3 validated.",
        "Prefer pyca/cryptography built against a validated OpenSSL.",
    ),
    "pycryptodomex": (
        "FIPS-DEP",
        "warning",
        False,
        "pycryptodomex is not FIPS 140-3 validated.",
        "Prefer pyca/cryptography built against a validated OpenSSL.",
    ),
    "argon2-cffi": (
        "FIPS-DEP",
        "warning",
        False,
        "Argon2 is not a NIST-approved KDF.",
        "Use PBKDF2-HMAC-SHA256 (NIST SP 800-132) in FIPS environments.",
    ),
    "pynacl": (
        "FIPS-DEP",
        "warning",
        False,
        "PyNaCl (libsodium) primitives are not FIPS-validated.",
        "Prefer pyca/cryptography built against a validated OpenSSL.",
    ),
    "liboqs-python": (
        "PQC-DEP-NONVALIDATED",
        "warning",
        True,
        "liboqs is not FIPS 140-3 validated; a hybrid deployment must keep the "
        "FIPS-approved component inside a validated module boundary.",
        "Treat liboqs output as the non-approved share of a hybrid scheme per SP 800-56C Rev. 2.",
    ),
    "pqcrypto": (
        "PQC-DEP-NONVALIDATED",
        "warning",
        True,
        "pqcrypto is not FIPS 140-3 validated; a hybrid deployment must keep "
        "the FIPS-approved component inside a validated module boundary.",
        "Treat pqcrypto output as the non-approved share of a hybrid scheme per SP 800-56C Rev. 2.",
    ),
}


def is_test_path(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & {"tests", "test"}:
        return True
    name = rel.name
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def iter_python_files(root: Path, include_tests: bool) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if rel.name in SELF_NAMES:
            continue
        if not include_tests and is_test_path(rel):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def line_of(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def line_text(lines: list[str], line_no: int) -> str:
    return lines[line_no - 1] if 0 < line_no <= len(lines) else ""


def is_suppressed(lines: list[str], line_no: int, code: str) -> bool:
    m = SUPPRESS_RE.search(line_text(lines, line_no))
    if not m:
        return False
    codes = m.group("codes")
    if not codes:
        return True
    return code in {c.strip().upper() for c in codes.split(",")}


def call_has_usedforsecurity_false(content: str, start: int) -> bool:
    """Check the call starting at `start` for usedforsecurity=False.

    Scans forward from the opening parenthesis, tracking nesting depth, over a
    bounded window. #EDGE calls longer than the window are treated as lacking
    the parameter, which fails safe (a finding is raised).
    """
    open_idx = content.find("(", start)
    if open_idx == -1:
        return False
    depth = 0
    end = min(len(content), open_idx + 500)
    for i in range(open_idx, end):
        ch = content[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                segment = content[open_idx : i + 1]
                return re.search(r"usedforsecurity\s*=\s*False", segment) is not None
    return False


def scan_source_file(path: Path, rel: str, issues: list[Issue], inventory: list[InventoryEntry]) -> bool:
    """Scan one file; returns True if PQC-capable identifiers were seen."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    lines = content.splitlines()

    for rule in SOURCE_RULES:
        for match in rule.pattern.finditer(content):
            line_no = line_of(content, match.start())
            # Suppressed and usedforsecurity=False touchpoints are excluded from
            # BOTH findings and the inventory, so the CBOM migration metric and
            # the PQC-NO-CAPABILITY heuristic count only actionable crypto.
            if rule.honors_usedforsecurity and call_has_usedforsecurity_false(content, match.start()):
                continue
            if is_suppressed(lines, line_no, rule.code):
                continue
            # algorithm="{1}" resolves to whichever alternation group matched
            # (match.lastindex), so mixed patterns label the actual primitive
            # (X25519 vs ECDH, ECDSA vs RSA) instead of a static string.
            algorithm = rule.algorithm
            if algorithm == "{1}":
                algorithm = match.group(match.lastindex) if match.lastindex else ""
            if algorithm:
                inventory.append(
                    InventoryEntry(algorithm, rule.category, rel, line_no, rule.quantum_vulnerable)
                )
            issues.append(
                Issue(rel, line_no, rule.severity, rule.code, rule.message, rule.fix_hint, rule.pqc)
            )

    for pattern, algo_tpl, category, qv in INVENTORY_PATTERNS:
        for match in pattern.finditer(content):
            algorithm = algo_tpl
            if "{1}" in algo_tpl and match.lastindex:
                algorithm = match.group(1).upper().replace("_", "-")
            inventory.append(
                InventoryEntry(algorithm, category, rel, line_of(content, match.start()), qv)
            )

    pqc_match = PQC_CAPABLE_CODE_RE.search(content)
    if pqc_match:
        inventory.append(
            InventoryEntry(
                pqc_match.group(1), "pqc", rel, line_of(content, pqc_match.start()), False
            )
        )
    return pqc_match is not None


def dep_name(requirement: str) -> str:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    return m.group(1).lower().replace("_", "-") if m else ""


def cryptography_bound_predates_pqc(spec: str) -> bool:
    """Best-effort: does the version constraint exclude PQC-capable releases?

    #EDGE only ==, ~=, <= and < bounds are inspected; complex markers are
    ignored. A `<46.x` bound with x > 0 still allows 46.0 features, so only
    exact `<46` / `<46.0` style bounds count as excluding the threshold.
    """
    excluded = False
    for op, version in re.findall(r"(==|~=|<=|<)\s*([0-9][0-9.]*)", spec):
        parts = version.split(".")
        try:
            major = int(parts[0])
        except ValueError:
            continue
        rest_is_zero = all(p in ("", "0") for p in parts[1:])
        if op in ("==", "~=", "<="):
            if major < CRYPTOGRAPHY_PQC_MIN_MAJOR:
                excluded = True
        elif op == "<":
            if major < CRYPTOGRAPHY_PQC_MIN_MAJOR or (
                major == CRYPTOGRAPHY_PQC_MIN_MAJOR and rest_is_zero
            ):
                excluded = True
    return excluded


def collect_requirements(root: Path) -> tuple[list[tuple[str, str, int]], list[Issue]]:
    """Return (requirements, manifest_issues).

    requirements are (requirement, source_file, line) tuples from pyproject and
    requirements files. manifest_issues surfaces conditions that would otherwise
    SILENTLY disable dependency scanning: an unparseable pyproject.toml (raised
    as an error so the gate fails loudly instead of passing green), or a
    pyproject.toml present on a runtime whose stdlib lacks tomllib (Python < 3.11).
    """
    found: list[tuple[str, str, int]] = []
    manifest_issues: list[Issue] = []

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        if tomllib is None:
            manifest_issues.append(
                Issue(
                    "pyproject.toml",
                    1,
                    "warning",
                    "FIPS-TOML-UNAVAILABLE",
                    "pyproject.toml is present but tomllib is unavailable "
                    "(Python < 3.11); its declared dependencies were NOT scanned.",
                    "Run the checker on Python 3.11+ so pyproject dependencies are scanned.",
                )
            )
            return found, manifest_issues

        try:
            raw = pyproject.read_text(encoding="utf-8", errors="replace")
            data = tomllib.loads(raw)
        except OSError:
            raw, data = "", {}
        except tomllib.TOMLDecodeError as exc:
            raw, data = "", {}
            manifest_issues.append(
                Issue(
                    "pyproject.toml",
                    1,
                    "error",
                    "FIPS-MANIFEST-UNPARSEABLE",
                    f"pyproject.toml could not be parsed ({exc}); dependency "
                    "scanning was skipped and may hide non-FIPS packages.",
                    "Fix the pyproject.toml syntax so declared dependencies are scanned.",
                )
            )
        raw_lines = raw.splitlines()

        def locate(req: str) -> int:
            needle = req.split(";")[0].strip().strip("'\"")
            for i, text in enumerate(raw_lines, start=1):
                if needle and needle in text:
                    return i
            return 1

        reqs: list[str] = list(data.get("project", {}).get("dependencies", []) or [])
        for group in (data.get("project", {}).get("optional-dependencies", {}) or {}).values():
            reqs.extend(group or [])
        for group in (data.get("dependency-groups", {}) or {}).values():
            reqs.extend(r for r in (group or []) if isinstance(r, str))
        for req in reqs:
            found.append((req, "pyproject.toml", locate(req)))

    for req_file in sorted(root.glob("requirements*.txt")):
        try:
            for i, text in enumerate(req_file.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                text = text.strip()
                if text and not text.startswith(("#", "-")):
                    found.append((text, req_file.name, i))
        except OSError:
            continue

    return found, manifest_issues


def scan_dependencies(root: Path, issues: list[Issue], inventory: list[InventoryEntry]) -> bool:
    """Scan dependency declarations; returns True if a PQC-capable dep is present."""
    pqc_capable = False
    requirements, manifest_issues = collect_requirements(root)
    issues.extend(manifest_issues)
    for requirement, source, line_no in requirements:
        name = dep_name(requirement)
        if not name:
            continue
        if name in PQC_CAPABLE_DEPS:
            pqc_capable = True
            inventory.append(InventoryEntry(name, "pqc", source, line_no, False))
        if name in DEP_RULES:
            code, severity, pqc, message, fix_hint = DEP_RULES[name]
            issues.append(Issue(source, line_no, severity, code, f"{name}: {message}", fix_hint, pqc))
        if name == "cryptography":
            inventory.append(InventoryEntry("cryptography", "library", source, line_no, False))
            # An explicit >=46 floor guarantees a PQC-capable release resolves.
            if any(
                int(v.split(".")[0]) >= CRYPTOGRAPHY_PQC_MIN_MAJOR
                for v in re.findall(r">=\s*([0-9][0-9.]*)", requirement)
            ):
                pqc_capable = True
            if cryptography_bound_predates_pqc(requirement):
                issues.append(
                    Issue(
                        source,
                        line_no,
                        "info",
                        "PQC-DEP-CAPABILITY",
                        "cryptography version constraint may exclude ML-KEM/ML-DSA "
                        f"support (available from release {CRYPTOGRAPHY_PQC_MIN_MAJOR} "
                        "when built against OpenSSL 3.5+).",
                        "Relax the upper bound once the project can adopt a PQC-capable release.",
                        True,
                    )
                )
    return pqc_capable


def apply_pqc_mode(issues: list[Issue], mode: str) -> list[Issue]:
    if mode == "off":
        return [i for i in issues if not i.pqc]
    if mode == "error":
        for issue in issues:
            if issue.pqc and issue.severity == "warning":
                issue.severity = "error"
    return issues


def build_report(issues: list[Issue], inventory: list[InventoryEntry], mode: str) -> dict:
    by_category: dict[str, int] = {}
    for entry in inventory:
        by_category[entry.category] = by_category.get(entry.category, 0) + 1
    return {
        "summary": {
            "errors": sum(1 for i in issues if i.severity == "error"),
            "warnings": sum(1 for i in issues if i.severity == "warning"),
            "info": sum(1 for i in issues if i.severity == "info"),
            "pqc_findings": sum(1 for i in issues if i.pqc),
        },
        "pqc_mode": mode,
        "issues": [i.as_dict() for i in issues],
        "inventory": {
            "generated_by": "check_fips_compatibility.py",
            "algorithms": [e.as_dict() for e in inventory],
            "stats": {
                "total": len(inventory),
                "quantum_vulnerable": sum(1 for e in inventory if e.quantum_vulnerable),
                "by_category": by_category,
            },
        },
    }


def print_text_report(report: dict, issues: list[Issue], fix_hints: bool) -> None:
    for issue in issues:
        tag = " [PQC]" if issue.pqc else ""
        print(f"{issue.file}:{issue.line} [{issue.severity}]{tag} {issue.code}: {issue.message}")
        if fix_hints and issue.fix_hint:
            print(f"  Fix: {issue.fix_hint}")
    summary = report["summary"]
    stats = report["inventory"]["stats"]
    print()
    print("FIPS/PQC compatibility check")
    print(f"  Errors:       {summary['errors']}")
    print(f"  Warnings:     {summary['warnings']}")
    print(f"  Info:         {summary['info']}")
    print(f"  PQC findings: {summary['pqc_findings']} (mode: {report['pqc_mode']})")
    print(
        f"  Inventory:    {stats['total']} crypto touchpoints, "
        f"{stats['quantum_vulnerable']} quantum-vulnerable"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "FIPS/PQC compatibility checker").splitlines()[0]
    )
    parser.add_argument("--strict", action="store_true", help="classic FIPS warnings fail the build")
    parser.add_argument("--fix-hints", action="store_true", help="show fix hints in text output")
    parser.add_argument("--include-tests", action="store_true", help="also scan test files")
    parser.add_argument("--json", action="store_true", help="emit the JSON report on stdout")
    parser.add_argument(
        "--pqc-mode",
        choices=("off", "warn", "error"),
        default="warn",
        help="PQC readiness ratchet: off, warn (report only, default), error (gate)",
    )
    parser.add_argument("--root", default=".", help="project root to scan")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(
            f"error: --root is not an existing directory: {args.root}",
            file=sys.stderr,
        )
        return 2
    issues: list[Issue] = []
    inventory: list[InventoryEntry] = []

    pqc_capable = False
    for path in iter_python_files(root, args.include_tests):
        rel = str(path.relative_to(root))
        pqc_capable = scan_source_file(path, rel, issues, inventory) or pqc_capable
    pqc_capable = scan_dependencies(root, issues, inventory) or pqc_capable

    if (
        args.pqc_mode != "off"
        and not pqc_capable
        and any(e.quantum_vulnerable for e in inventory)
    ):
        issues.append(
            Issue(
                "pyproject.toml" if (root / "pyproject.toml").is_file() else ".",
                1,
                "info",
                "PQC-NO-CAPABILITY",
                "Quantum-vulnerable cryptography detected but no PQC-capable "
                "dependency or code path is present; the project cannot express "
                "hybrid key establishment yet.",
                "Add a PQC-capable dependency (e.g. cryptography "
                f">= {CRYPTOGRAPHY_PQC_MIN_MAJOR} on OpenSSL 3.5+) when the stack allows.",
                True,
            )
        )

    issues = apply_pqc_mode(issues, args.pqc_mode)
    issues.sort(key=lambda i: (i.file, i.line, i.code))
    report = build_report(issues, inventory, args.pqc_mode)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report, issues, args.fix_hints)

    errors = report["summary"]["errors"]
    classic_warnings = sum(1 for i in issues if i.severity == "warning" and not i.pqc)
    if errors > 0:
        return 1
    if args.strict and classic_warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
