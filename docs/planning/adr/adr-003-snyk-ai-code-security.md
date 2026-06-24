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

### D4: AI-BOM is reachable only through a direct caller, not the quickstart composite

AI-BOM is available by calling `python-snyk.yml` directly with `run-aibom: true`.
It is intentionally NOT wired through the `python-standard-stack` quickstart
composite, keeping that composite minimal and consistent with how it constrains
the other layers.

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
