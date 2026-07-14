# ADR-003: Snyk AI Code Security Adoption

**Status:** Accepted
**Date:** 2026-06-24
**Deciders:** Byron Williams

---

## TL;DR

Adopt Snyk on the Free plan as a dedicated, opt-in, token-gated `python-snyk.yml`
reusable workflow. Snyk Code (SAST) is the primary added value over Bandit; Snyk
Open Source (SCA) stays advisory because OSV plus Renovate remain the primary SCA
gate; AI-BOM and agent-config scanning are the capabilities that justify adoption
because nothing else in the stack produces them.

---

## Context

The fleet runs 42 active repos, roughly 30 of them Python, maintained by a solo
operator. Software composition analysis (dependency scanning) is already covered
by self-hosted Renovate plus OSV-Scanner through `python-sbom.yml`. Prior internal
analysis (`dependency-tooling-comparison.md`, `fossa-ci-evaluation.md`) concluded
that a SaaS scanner was not justified for SCA at this fleet size. That conclusion
still holds for SCA on its own.

What changed in 2025 and 2026 is that Snyk shipped an AI-code-security layer with
no equivalent in Renovate, OSV, or Bandit:

- An official MCP server that scans code inside an AI coding agent's tool loop.
- AI-BOM (`snyk aibom`), a Python-only CycloneDX 1.6 inventory of AI models,
  agents, tool-calls, and MCP connections; generally available.
- DeepCode AI / Agent Fix autofix.
- MCP-scan / Agent Scan (from the Invariant Labs acquisition) for scanning MCP
  server configs for prompt injection and tool poisoning.

The decision is therefore not about SCA. It is about whether the new AI-security
layer is worth adopting given the fleet's growing AI agent surface.

---

## Decision

### D1: Adopt Snyk on the Free plan

Free scans public repos with unlimited tests; metered limits apply only to private
repos. At this fleet's public-repo majority, marginal cost on Free is near zero.

### D2: Deliver as a dedicated, opt-in, token-gated reusable workflow

Snyk ships as `python-snyk.yml`, following the one-tool-one-file convention. It is
opt-in and token-gated: it no-ops cleanly without `SNYK_TOKEN`, so enrolling a repo
is a deliberate act and an unconfigured repo is never blocked.

### D3: Snyk Code (SAST) is the primary added value; Snyk Open Source (SCA) is advisory

Snyk Code provides cross-file dataflow SAST, an escalation layer over Bandit. Snyk
Open Source (SCA) is advisory, default-off, and `continue-on-error`: OSV plus
Renovate remain the primary SCA gate. The OSS job never fails the build.

### D4: AI-BOM is reachable via the quickstart composite or a direct caller

**Updated 2026-06-27**: the initial restriction (direct caller only) was lifted.

AI-BOM is now available via two paths:

- **Via `python-standard-stack.yml`**: set `enable-aibom: true` alongside
  `run-snyk: true`. The input defaults to `false`, preserving the opt-in intent.
- **Via a direct caller**: call `python-snyk.yml` directly with `run-aibom: true`.

The original decision reserved AI-BOM for direct callers to keep the quickstart
composite minimal. Adding `enable-aibom: false` (default off) achieves the same
intent without requiring a direct caller for LLM/RAG/MCP repos that use the
standard stack.

### D5: One Snyk Organization for both GitHub owners

A CI token reports to its org regardless of repo owner, so one Snyk Organization
suffices on Free for both the ByronWilliamsCPA and williaby owners.

### D6: Store the token mirroring the existing SONAR_TOKEN pattern

Store `SNYK_TOKEN` as an org-level secret for ByronWilliamsCPA and a repo-level
secret for williaby personal repos, mirroring the established `SONAR_TOKEN` pattern.

### D7: Roll out public-first

Roll out across the 24 public code repos first (unlimited Free scanning). Private
repos are PR-triggered only and kept within the Free 5-monitored-project cap.

---

## Pricing reality

The Team plan's listed rate is $25 per contributing developer per month, but the
exact entry cost is unconfirmed and the published figures disagree.

```text
#CRITICAL: Snyk Team pricing is inconsistent across sources and affects any
#  paid-upgrade decision. Secondary sources report a 5-developer minimum (about
#  $125/month), while the official plans page currently renders "starting at
#  $750/month".
#VERIFY: confirm the actual minimum and per-seat terms at checkout before any
#  Team purchase; do not budget against the secondary-source figure.
```

---

## AI agent surface

The AI-security capabilities target the fleet's AI agent repos. The specific
targets below are planned for the live rollout phase and are not yet exercised.

```text
#ASSUME: these repos are the relevant AI agent surface for AI-BOM and agent-config
#  scanning at rollout time.
#VERIFY in live phase: run AI-BOM on rag-processor, PromptCraft, reference-library,
#  image-generation, and image-preprocessing-detector, confirming aibom.json is
#  non-empty on each. Trial MCP-scan / Agent Scan (preview) against the
#  zen-mcp-server fork and the homelab-infra MCP configs.
```

---

## Consequences

**Positive:**

- SAST coverage stronger than Bandit through cross-file dataflow analysis.
- An AI supply-chain inventory (AI-BOM) that nothing else in the stack produces.
- Agent-loop scanning via the Snyk MCP server inside the coding agent.
- Near-zero marginal cost on Free for the public repos.

**Negative / risks:**

- Snyk SCA cannot parse `uv.lock`. Mitigated: the `snyk-oss` job exports a
  requirements file from the committed lockfile and runs only in the `uv-locked`
  state, so it never triggers a live network resolve.
- The Free plan's 5-monitored-project cap and private test caps bound private-repo
  coverage.
- Preview features (MCP-scan, Agent Scan) may change before general availability.

**Relationship to prior decisions:**

- Complements, does not replace, the OSV/Renovate stack.
- Refines the earlier "not justified" conclusion: that conclusion is still true for
  SCA on its own; the AI-security layer is what justifies adoption.

---

## Revisit Team when

A decision gate roughly 30 days post-rollout. Revisit upgrading to the Team plan
when any of these become true:

1. The Free 5-monitored-project cap becomes binding on private repos.
2. The private SAST test cap (100 per month) becomes binding.
3. A 1-seat Team checkout is confirmed affordable (see Pricing reality).

---

## Future Decisions

### FD1: Snyk MCP Scan / Agent Scan

Snyk MCP Scan (from the Invariant Labs acquisition) scans MCP server configurations
for prompt injection and tool poisoning. As of 2026-06, this capability is pre-GA
(preview). The "AI agent surface" section already targets trial runs against
zen-mcp-server and homelab-infra MCP configs.

**Condition for implementation**: GA announcement in the Snyk changelog. Until GA,
do not implement a `python-snyk-mcp.yml` workflow or automate agent-scan in CI;
the Snyk MCP server inside the coding agent covers interactive use.

---

## Role boundary (added 2026-06-29)

To keep the security stack's responsibilities unambiguous now that a deterministic
provenance workflow exists alongside Snyk:

- **Snyk owns** SAST (Snyk Code), IaC (`python-snyk-iac.yml`), and AIBOM
  (`snyk aibom`). These are the capabilities that justified adoption (D3, D4) and
  have no equivalent elsewhere in the stack.
- **Open Source (SCA) stays advisory.** Snyk OSS remains default-off and
  `continue-on-error` (D3); OSV plus Renovate remain the primary SCA gate. Snyk
  does not own the SCA gate and does not consume hosted test quota in routine CI.
- **Transitive-provenance reporting is handled by the new deterministic
  workflow**, `python-dependency-provenance.yml`, plus a local interpretation
  agent. That workflow is keyless (OSV-Scanner, `uv tree --invert`, `npm why`),
  consumes no Snyk hosted quota and no Anthropic API key, and only produces the
  report; deciding which fix to apply is the local agent's job, run separately on
  the operator's subscription. See
  [docs/workflows/python-dependency-provenance.md](../../workflows/python-dependency-provenance.md)
  and ByronWilliamsCPA/.claude ADR-009 for the interpretation-agent boundary.

This note records the division of labour; it does not change any decision above.
