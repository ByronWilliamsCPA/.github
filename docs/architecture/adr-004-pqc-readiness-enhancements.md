# ADR-004: PQC Readiness Enhancements for python-fips-compatibility

**Status:** Accepted
**Date:** 2026-07-14
**Deciders:** Byron Williams

---

## TL;DR

The v8 `python-fips-compatibility.yml` workflow and its org-central checker
established PQC (post-quantum cryptography) readiness scanning: classical-crypto
detection, a three-stage `pqc-mode` ratchet, and a bespoke algorithm inventory.
An impact test across five representative repos (homelab-infra, rag-processor,
llc-manager, xero-crypto, pp-security-master) scored all five at zero
quantum-vulnerable findings, including a cryptocurrency repo. That result is a
measurement artifact, not a clean bill of health: the checker only sees
hand-written `pyca/cryptography` calls, so it misses the surfaces where these
apps' real harvest-now-decrypt-later (HNDL) exposure actually lives, TLS on
every outbound API call and crypto inside dependencies.

This ADR proposes five enhancements to close that gap and turn the workflow from
a per-PR reporter into a fleet-wide migration program:

- **D1** Detect the transport and dependency crypto surface, not just
  hand-written primitives.
- **D2** Emit standard CycloneDX 1.6 CBOM instead of bespoke JSON.
- **D3** Build a fleet aggregator that rolls per-repo CBOMs into one org
  inventory.
- **D4** Add baseline/delta gating so `pqc-mode: error` is adoptable now.
- **D5** Add suppression governance (required reasons, fleet visibility).

All five are accepted; the options considered and the resolved design decisions
are recorded below.

---

## Context

NIST and CISA PQC migration guidance is consistent on sequencing: step one is a
complete **cryptographic inventory** (discovery of every quantum-vulnerable use),
step two is **prioritization** by data sensitivity and lifetime (the HNDL threat:
data encrypted with classical key exchange today can be recorded now and
decrypted once a cryptographically relevant quantum computer exists), and step
three is **migration** to hybrid or PQC algorithms. NIST IR 8547 deprecates
112-bit-strength classical algorithms after 2030 and disallows them after 2035.

The v8 workflow implements a first pass at step one for Python source. Its
limits, confirmed against the current checker (`scripts/check_fips_compatibility.py`),
are:

- **Detection surface.** `SOURCE_RULES` match only `pyca/cryptography` call
  shapes (`ec.ECDH`, `padding.*`, `Ed25519PrivateKey`, `algorithms.*`, etc.) plus
  explicit `ssl.SSLContext` / `ssl.create_default_context`. There is no detection
  of HTTPS clients (`requests`, `httpx`, `urllib3`, `aiohttp`), JWT signing
  algorithms (`PyJWT` RS256/ES256/PS256), or SSH (`paramiko`).
- **Format.** The inventory is a bespoke JSON `inventory` key. The docstring says
  state "can be aggregated across repos", but no aggregator exists and the format
  is not consumable by standard tooling.
- **Gating.** `pqc-mode: error` escalates on absolute findings, which forces a
  boil-the-ocean remediation before it can be turned on.
- **Suppressions.** `# fips: ignore[CODE]` requires no reason and is invisible at
  the fleet level.

```text
#ASSUME: for the sampled repos, near-zero hand-written asymmetric crypto is
#  representative of the fleet's Python code; the dominant quantum exposure is
#  TLS-in-transit and dependency-embedded crypto, not hand-rolled primitives.
#VERIFY: after D1 lands, re-run the impact test on the same five repos and
#  confirm transport/dependency findings appear where the source scan found none.
```

Two pieces of existing infrastructure shape the options below:

- `python-sbom.yml` already produces a CycloneDX SBOM (relevant to D2/D3).
- Fleet-wide iteration already exists (SHA-pin audit scripts, the Renovate
  self-hosted worker with a fleet PAT, and a repo catalog), so cross-repo
  collection in D3 has precedent to reuse rather than invent.

---

## Decision

### D1: Detect the transport and dependency surface

Add detection for the crypto surfaces that carry the real HNDL exposure, framed
as **readiness inventory**, not as code-defect findings.

**Options considered:**

- **(A) Per-call-site source detection** of `requests.get`, `httpx.Client`, etc.
  Rejected as the primary mechanism: every HTTP call in the fleet would flag,
  producing thousands of findings whose signal-to-noise makes the metric useless.
- **(B) Dependency-level detection** (recommended). Classify at the manifest
  layer: a repo that depends on `requests`/`httpx`/`urllib3`/`aiohttp` uses TLS,
  therefore classical key exchange in transit until its runtime can negotiate a
  hybrid group. One finding per dependency, not per call. Curated capability map:
  TLS clients, JWT libraries, SSH libraries, and `pyOpenSSL`.
- **(C) Runtime endpoint probing** (what TLS groups the deployed service actually
  negotiates). Most accurate for real exposure, but belongs to the existing
  `pqc-probe` runtime leg, not the static checker. Deferred.

**Recommended:** (B) as the core, with a narrow (A)-style pass only for JWT
signing algorithms (the algorithm string, e.g. `RS256`, is the actionable detail
and is cheap to grep in `jwt.encode(..., algorithm=...)` calls). Introduce a new
category (proposed: `transport`) and, critically, keep these findings
**inventory/info-level only**; they never gate.

```text
#CRITICAL: D1 transport/dependency findings must NOT feed pqc-mode: error at
#  introduction. They are ecosystem-wide and unfixable by the caller until the
#  runtime (OpenSSL 3.5+ / cryptography hybrid bindings) can negotiate hybrid
#  groups. Gating on "uses requests" would break every repo on day one.
#VERIFY: the escalation path (apply_pqc_mode) leaves category == transport at
#  info regardless of mode until a future ADR flips them once hybrid is
#  deployable fleet-wide.
```

### D2: Emit CycloneDX 1.6 CBOM

Replace the bespoke inventory with standard CycloneDX 1.6, emitted **alongside**
the existing report (not replacing it).

**Options considered:**

- **(A) Keep bespoke JSON, add an external converter.** Extra moving part; the
  canonical artifact stays non-standard. Rejected.
- **(B) Emit CycloneDX natively as an additional `fips-cbom.json` artifact**
  (recommended). The existing `fips-report.json` (`summary`, `issues`,
  `inventory`) stays byte-compatible so the PR-comment, step summary, gate, and
  the just-shipped v8 contract keep working. CBOM is additive.
- **(C) Replace `fips-report.json` with CycloneDX.** Breaks the v8 report
  contract shipped days ago and the PR-comment/summary parsing. Rejected.

**Recommended:** (B). CycloneDX 1.6 models this domain directly via
`cryptoProperties`:

- `assetType: algorithm` for primitives, with `algorithmProperties` (primitive,
  parameterSetIdentifier / curve, `nistQuantumSecurityLevel`, mode, padding).
  `quantum_vulnerable` maps to `nistQuantumSecurityLevel: 0`.
- `assetType: protocol` with `protocolProperties` (type `tls`, version, cipher
  suites) for the D1 transport surface. This is why D2 is sequenced before D1:
  CycloneDX gives transport crypto a first-class representation.
- `evidence.occurrences` carries `file:line`, replacing the flat inventory
  fields.

```text
#ASSUME: CycloneDX 1.6 cryptoProperties (assetType algorithm/protocol/certificate)
#  is stable and is the schema to target; the CycloneDX Python lib or hand-built
#  JSON both satisfy it (stdlib-only is a checker constraint, so hand-built JSON
#  is the default to avoid a runtime dependency).
#VERIFY: validate emitted CBOM against the CycloneDX 1.6 JSON schema in CI.
```

**Open detail:** whether crypto assets live in a standalone `fips-cbom.json` or
are injected into the `python-sbom.yml` SBOM as components. Recommendation:
standalone first (keeps checker ownership clean and stdlib-only), with a
documented path to link CBOM crypto-assets to SBOM dependency `bom-ref`s later,
which is where D1 + D2 become powerful (a `requests` component `dependsOn` an
X25519 protocol asset).

### D3: Fleet aggregator

Add a companion job in `.github` that rolls every repo's CBOM into one fleet
inventory plus a dashboard. This is what makes `quantum_vulnerable` an
organization-level migration metric rather than a per-PR number.

**Options considered:**

- **(A) Scheduled workflow downloads the latest CBOM artifact from each repo via
  the GH API.** No per-repo commits, but artifacts expire (retention window) and
  cross-repo artifact reads need a fleet token.
- **(B) Each repo commits `fips-cbom.json` to a known path; aggregator checks out
  or reads via API.** Durable and version-controlled; costs one tracked file per
  repo.
- **(C) Push CBOMs into a central store (Dependency-Track).** Dependency-Track
  ingests CycloneDX natively and provides a UI, metrics, and policy. Best
  long-term; requires hosting.

**Recommended:** the aggregator and dashboard live in **homelab-infra**, not in
`.github`. Each fleet repo's `python-fips-compatibility.yml` run produces a
per-repo CBOM artifact (D2); a scheduled job in homelab-infra collects them,
merges them into a fleet CBOM, and renders the dashboard. Near term the render
target is a committed markdown/HTML page; end state is a Dependency-Track
instance in homelab-infra (it already hosts Renovate and other services and
ingests CycloneDX natively). Collection reuses the existing fleet-catalog and
token pattern.

```text
#CRITICAL: the D4 merge gate must NOT depend on the homelab-infra dashboard or
#  aggregator being reachable. The gate runs self-contained inside each repo's
#  workflow; the aggregator is a strictly read-only, downstream consumer of the
#  CBOM artifacts. Coupling merge success to an external service means a
#  homelab-infra outage blocks every PR in the fleet.
#VERIFY: the gate logic reads only local scan output, never the fleet dashboard.
```

**Resolved (2026-07-14):** dashboard host is homelab-infra; interim collection is
artifact download via the GH API (fleet token scope: read-only, contents +
`actions:read`), with the default 90-day artifact retention ample for a scheduled
aggregator.

### D4: Baseline / delta gating

Gate on **net-new** quantum-vulnerable findings in a PR rather than on absolute
count, so `error` mode can be enabled fleet-wide immediately to stop regressions
while existing debt is burned down on a schedule.

**Options considered:**

- **(A) Committed `.fips-baseline.json` per repo**, compared against the current
  scan. Explicit and visible; requires regenerating the baseline on intentional
  changes.
- **(B) Merge-base diff**: scan the PR base ref and the head, and fail only on
  findings present in head but not base (recommended default). No file to
  maintain; naturally answers "did this PR add exposure". Costs a second scan
  (acceptable: the checker runs in seconds) and needs base-ref checkout.
- **(C) Baseline stored as an artifact from the last main run.** Fragile
  (retention).

**Resolved (2026-07-14): (B), merge-base diff.** Option A (committed baseline) is
dropped. Its one advantage over B was an in-repo burn-down ledger, but with the
D3 dashboard now hosted in homelab-infra, the aggregator owns trend tracking, so
A's advantage disappears and only its costs (regen maintenance, merge conflicts,
staleness) remain. The gate is exposed via a new additive input (proposed:
`fail-on: new | all`, default preserving current absolute behavior):

- On `pull_request`, `fail-on: new` scans the merge-base and the head and gates
  only on net-new findings.
- On `push` and `schedule` there is no base to diff against, so those events fall
  back to absolute mode (`fail-on: all`).

```text
#CRITICAL: finding identity must be stable across unrelated edits. file:line is
#  NOT stable (an added import shifts every line below it, producing false "new"
#  findings). Fingerprint on (normalized path, rule code, matched token/snippet),
#  not line number.
#VERIFY: unit test that inserting a blank line above an existing finding does not
#  register it as new under fail-on: new.
```

**Open detail (implementation, not blocking Accepted):** the exact fingerprint
algorithm (token-plus-enclosing-function anchor vs. normalized snippet hash).

### D5: Suppression governance

Make suppressions auditable: a suppressed classical KEX is still HNDL-exposed, so
accepted risk must be visible and justified.

**Options considered / recommended combination:**

- **(A) Require a reason**: `# fips: ignore[CODE]: <reason/ticket>`. A bare
  reasonless ignore is itself reported. Introduce at **warning** first so existing
  bare suppressions are not an instant failure, then ratchet.
- **(B) Optional expiry**: `# fips: ignore[CODE] until=YYYY-MM-DD`; expired
  suppressions reactivate. Useful for HNDL (forces periodic revisit). Nice to
  have.
- **(C) Surface a suppression inventory** (count and list) in the report and CBOM
  so the D3 aggregator can track accepted risk fleet-wide. Adopt with A.

**Recommended:** A + C now, B as a follow-up.

```text
#ASSUME: introducing "reason required" as a warning first avoids breaking repos
#  that already use bare `# fips: ignore`.
#VERIFY: grep the fleet for existing bare suppressions before flipping the
#  reason requirement from warning to error.
```

---

## Sequencing

The dependencies between the five drive the order:

1. **D2 (CBOM format)** first: it defines the data contract D1 and D3 build on,
   and CycloneDX `protocol` assets are the representation D1 needs.
2. **D1 (transport/dependency detection)** next, emitting into the CBOM shape.
3. **D3 (fleet aggregator)** consumes the CBOMs D1/D2 produce.
4. **D4 (delta gating)** and **D5 (suppression governance)** are independent of
   the above and can proceed in parallel at any point.

---

## Consequences

**Positive:**

- The readiness metric measures real HNDL exposure (transport + dependencies),
  not just the small hand-written-primitive surface.
- A standard, tool-consumable CBOM that merges with the existing SBOM stack and
  feeds standard inventory tooling (Dependency-Track).
- A genuine organization-wide cryptographic inventory (NIST step one), with a
  progress metric that aggregates.
- `pqc-mode: error` becomes adoptable fleet-wide immediately via delta gating.
- Accepted quantum risk (suppressions) becomes auditable.

**Negative / risks:**

- D1 will make the currently "clean" repos show real numbers. This is the intent,
  but it changes the rollout narrative and must be communicated: the number going
  up is the inventory working, not a regression.
- More moving parts (aggregator, CBOM emitter, baseline diff) raise maintenance
  surface for a solo operator. Mitigation: keep the checker stdlib-only and the
  aggregator reuse existing fleet-iteration patterns.
- D4 doubles the per-PR scan (base + head). Acceptable given checker runtime.

**Relationship to prior decisions:**

- Additive to the v8 contract (ADR text in `CHANGELOG.md` [Unreleased]). The
  `fips-report.json` shape, PR-comment, and artifact names are unchanged; CBOM,
  new inputs, and new categories are all additive.
- Complements `python-sbom.yml` (D2/D3) rather than replacing it.

---

## Scope boundary

This ADR is Python-only (ring 1: Python source plus the transport and dependency
surface). Deferral of the outer rings is safe because **D2 and D3 are the
integration contract**: CycloneDX is language-agnostic and the homelab-infra
aggregator is a generic CBOM consumer, so every future ring is a new producer
clipping onto a fixed consumer, not a rewrite. The two outer rings are not equal
and are handled differently:

- **Ring 2, Certificates / PKI, is the immediate next ADR (ADR-005 candidate).**
  Committed certs (`*.pem`, `*.crt`, `*.key`) and cert-generating code carry
  RSA/ECDSA signature algorithms; PKI is the hardest, highest-stakes part of PQC
  migration (long-lived roots, signatures baked into trust chains) and is entirely
  uncovered today. The surface is small and bounded (glob, parse, read the sig
  alg), but it needs an ASN.1/x509 parser, not source regex, so it is a new engine
  rather than a rule addition. Tracked as GitHub issue #280.
- **Ring 3, Polyglot coverage, is a downstream program, not a single ADR.** The
  org is polyglot, so this is the largest raw-exposure gap, but also the largest
  lift (one detector per ecosystem) with the least reuse from the Python tool. It
  is sequenced as per-ecosystem detectors emitting into the shared CBOM and
  dashboard this ADR establishes. Tracked as GitHub issue #281.

---

## Resolved decisions (2026-07-14)

- **D1 severity:** transport/dependency findings are inventory/info only and never
  gate, until hybrid TLS is deployable fleet-wide (a future ADR flips them).
- **D2 placement:** a standalone `fips-cbom.json` artifact, not injected into the
  `python-sbom.yml` output; the checker stays stdlib-only, with a documented path
  to link CBOM crypto-assets to SBOM `bom-ref`s later.
- **D3 hosting:** aggregator and dashboard live in homelab-infra; Dependency-Track
  is the end state. The merge gate stays self-contained and never depends on it.
- **D3 collection transport:** artifact download via the GH API (`actions:read`);
  the default 90-day retention is ample for a scheduled aggregator, and it avoids
  a per-repo bot commit on every run.
- **D4 mechanism:** merge-base diff (B) on `pull_request`, absolute fallback on
  `push`/`schedule`. Committed baseline (A) dropped.
- **D5 enforcement:** warn-then-ratchet, require `# fips: ignore[CODE]: <reason>`
  as a warning first, sweep the fleet for existing bare suppressions, then flip to
  error; expiry adopted later.
- **Scope:** Python-only (ring 1) for this ADR. Certs/PKI is the next ADR (ADR-005
  candidate, issue #280); polyglot is a downstream program (issue #281).

## Implementation details (non-blocking)

Settled in principle, left to the implementation PR:

- The D4 finding-fingerprint algorithm (token-plus-enclosing-function anchor vs.
  normalized snippet hash), excluding line number.
- The eventual linkage of CBOM crypto-assets to `python-sbom.yml` dependency
  `bom-ref`s (D2 follow-on).
