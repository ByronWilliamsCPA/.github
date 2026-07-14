# Handoff: Snyk Developer Experience (.claude repo)

**Repo:** ~/dev/.github (this is the global ~/.claude/ config, symlinked)
**Branch:** claude/snyk-developer-experience-0 (new branch, off main)
**Session date:** 2026-06-25

> **SCOPE NOTE:** All work items below target the `~/.claude/` global config
> repository (symlinked from `~/dev/.github`), NOT the ByronWilliamsCPA/.github
> org repo. Files created or edited are under `~/.claude/rules/`,
> `~/.claude/standards/`, and `~/.claude/settings.json`. This PR lives in the
> `.github` repo only because `~/.claude/` is symlinked there; the actual
> changes will land in that global config repo's working tree.

---

## Context

The CI/CD layer (handled in the parallel `claude/snyk-iac-aibom-1` branch in
the same repo) covers scanning code after it is pushed to GitHub. This work
package covers scanning during authoring: inside the Claude Code session and at
pre-commit time. These are the two vectors where Snyk can block problems before
they enter the repo at all.

The capabilities being wired in:
- **MCP Server** (`ai-mcp-server`): rated HIGH. Snyk MCP Server lets Claude
  Code invoke `snyk test` or `snyk code test` inline while writing code, before
  any commit exists.
- **Secrets CI gate** (`sast-secrets-ci-gate`): rated MEDIUM. Snyk Code's
  secrets detection can be added as a pre-commit hook to close the bypass window
  that `--no-verify` opens for local trufflehog/detect-secrets hooks.
- **MCP Scan** (`ai-mcp-scan`): rated HIGH but pre-GA as of 2026-06. Document
  the gap; implement the hook stub when GA.

Evaluation summary: Snyk was selected over Cycode, Checkmarx One, and Endor Labs
based on breadth of coverage (SAST + SCA + IaC + secrets), GitHub Actions native
integration, MCP Server availability (Invariant Labs acquisition), and a free tier
matching the org's use pattern. See `../archive/handoff-snyk-cicd.md` for full
selection rationale.

---

## Existing files to be aware of

These files exist in `~/.claude/` and must not be duplicated or contradicted:

- `rules/mcp-strategy.md` -- tiered MCP loading strategy; Snyk MCP Server
  will be added here as a Tier 2 (on-demand) server.
- `rules/pre-commit.md` -- pre-commit checklist; add a Snyk item to the
  Security section.
- `standards/mcp-minimal-bloat.md` -- guidance on keeping MCP tool surface
  small; reference this when specifying which Snyk MCP tools to expose.

The global `~/.claude/settings.json` controls Claude Code hooks. Check its
current content before writing any hook additions.

---

## Work items

### 1. Snyk MCP Server setup standard (HIGH priority)

**Create** `~/.claude/standards/snyk-mcp-setup.md`.

Content to cover:

**One-time setup (per workstation):**
```bash
# Install Snyk CLI globally
npm install -g snyk          # pin to a specific version; e.g. snyk@1.1293.1
                             # check latest: https://github.com/snyk/cli/releases
                             # or: brew install snyk (brew manages versions separately)

# Authenticate (browser opens; use GitHub SSO or personal token)
snyk auth

# Configure MCP Server for Claude Code
npx -y snyk@latest mcp configure --tool=claude-cli
# This writes an MCP server entry to ~/.claude/settings.json automatically
```

**Verify the MCP entry** was written by checking `~/.claude/settings.json` for
a `snyk-mcp` entry after running the configure command.

**Which Snyk MCP tools to expose**: Snyk MCP Server exposes multiple tools.
Per the minimal-bloat standard, document which tools are active in Claude Code
sessions and why. The high-value tools are:
- `snyk_test`: runs `snyk test` on the current project (SCA check)
- `snyk_code_test`: runs `snyk code test` on specified paths (SAST check)
- `snyk_monitor`: pushes a snapshot to the Snyk dashboard (use sparingly;
  this creates a project entry in the Snyk org)

**When to invoke in a Claude Code session** (rules for the agent):
- Before adding a new dependency to pyproject.toml: invoke `snyk_test` after
  the uv add command to check the new dep against the Snyk advisory database.
- Before committing a new authentication or data-handling module: invoke
  `snyk_code_test` on the changed files to surface SAST findings.
- When reviewing a PR that adds new MCP tool dependencies: invoke `snyk_test`.

Document that `snyk_monitor` should NOT be called automatically because it
creates persistent project entries in the Snyk org dashboard that require
manual cleanup.

**Add** a MEMORY.md entry pointing to this file:
```
- [Snyk MCP setup](standards/snyk-mcp-setup.md): workstation setup for Snyk MCP Server; which tools to call and when
```

### 2. Rules file for Snyk MCP usage (HIGH priority)

**Create** `~/.claude/rules/snyk-mcp.md`.

This is a path-scoped rule that should activate when editing Python package
files (pyproject.toml, requirements*.txt, uv.lock). Content structure:

```markdown
---
path: "**/{pyproject.toml,requirements*.txt,uv.lock}"
---
# Snyk MCP: Dependency Review Rule

When a dependency is added or upgraded in a file this rule matches:

1. After the change is written, invoke the snyk_test MCP tool on the project root.
2. If snyk_test returns HIGH or CRITICAL findings on the newly added package,
   surface the finding to the user before proceeding.
3. Do NOT invoke snyk_monitor automatically.
4. Do NOT block the edit based solely on snyk_test output; report findings and
   let the user decide.

When snyk_test is not available (SNYK_TOKEN not set or MCP server not configured),
note the gap and continue without blocking.
```

Note: path-scoped rules in `~/.claude/rules/` use the `path:` frontmatter field.
Check existing rule files for the exact frontmatter format before writing.

### 3. Pre-commit hook: Snyk secrets gate (MEDIUM priority)

Snyk Code includes secrets detection. Adding it as a pre-commit hook closes
the bypass window that `--no-verify` opens for the local trufflehog or
detect-secrets hooks already in place.

The challenge: `snyk code test` is too slow (10-30 seconds) for a synchronous
pre-commit hook that runs on every commit. The right approach is a faster,
targeted secrets-only check.

**Option to implement**: Use Snyk CLI's `--detection-type=secrets` flag (if
available in the installed version) to run only the secrets scanner, which is
fast. Alternatively, this belongs in a `pre-push` hook rather than `pre-commit`.

**Document** in `~/.claude/rules/pre-commit.md` under the Security section:

Add to the checklist:
```
- [ ] **Snyk Secrets Gate**: If SNYK_TOKEN is set, run `snyk code test
  --detection-type=secrets <changed-dirs>` on staged Python files before push.
  This closes the --no-verify bypass vector for the local trufflehog hook.
```

**Do NOT add** a slow `snyk code test` full SAST scan as a pre-commit hook.
The CI job covers that. Pre-commit must remain fast.

**Future**: When Snyk MCP Scan (MCP server config prompt-injection scanning)
reaches GA, add a pre-push hook that runs `snyk mcp-scan` on `.claude/settings.json`
and any project-local MCP configuration files.

### 4. Claude Code hook: dependency change notification (MEDIUM priority)

Claude Code hooks (configured in `~/.claude/settings.json` or
`.claude/settings.json`) can fire on tool events. A `PostToolUse` hook on Edit
or Write targeting pyproject.toml can remind the session to run a Snyk check.

**Read** `~/.claude/settings.json` before making changes (check the current
hook configuration to avoid duplicates).

**Add** a `PostToolUse` hook that fires when Write or Edit modifies
`pyproject.toml` or `requirements*.txt`:

<!-- #ASSUME: `"condition": "match_files(...)"` is valid PostToolUse hook schema. -->
<!-- #VERIFY: Read `~/.claude/rules/settings-and-permissions.md` and inspect -->
<!-- the live `~/.claude/settings.json` schema before pasting. The `condition` -->
<!-- field may be silently inert or absent from older Claude Code hook schemas. -->
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Dependency file modified. If SNYK_TOKEN is set, consider invoking snyk_test via the Snyk MCP Server before committing.'",
            "condition": "match_files('**/pyproject.toml', '**/requirements*.txt')"
          }
        ]
      }
    ]
  }
}
```

Check the existing settings.json hook format before writing; the exact schema
may differ from the example above. Reference `~/.claude/rules/settings-and-permissions.md`
for the correct format.

### 5. CLAUDE.md update for the .github project-local scope (LOW priority)

The project-local `.claude/CLAUDE.md` in `~/dev/.github` documents project-specific
Claude instructions. Add a Developer Setup section that references:
- Snyk CLI auth requirement (`snyk auth` before first use)
- Snyk MCP Server config step (`npx snyk mcp configure --tool=claude-cli`)
- Link to `~/.claude/standards/snyk-mcp-setup.md` for full setup instructions

---

## Implementation order

1. Create branch: `git checkout -b claude/snyk-developer-experience-0 main`
2. Read `~/.claude/settings.json` (understand current hook structure before touching it)
3. Read `~/.claude/rules/mcp-strategy.md` (understand Tier 1/2/3 structure before adding Snyk)
4. Create `~/.claude/standards/snyk-mcp-setup.md`
5. Create `~/.claude/rules/snyk-mcp.md` (check frontmatter format against existing rules)
6. Update `~/.claude/rules/pre-commit.md` (add Snyk secrets gate checkbox)
7. Update `~/.claude/rules/mcp-strategy.md` (add Snyk as Tier 2 on-demand server)
8. Add PostToolUse hook to `~/.claude/settings.json` (or project-local `.claude/settings.json`)
9. Update `.claude/CLAUDE.md` (project-local developer setup section)
10. Update `MEMORY.md` (add snyk-mcp-setup pointer)
11. Run `pre-commit run --all-files`
12. Commit with signed commit, conventional commit format

---

## Key constraints

- **No em-dashes** in any file content (pre-commit hook will block the commit).
- **Signed commits**: `git commit -S` on every commit.
- **mcp-minimal-bloat standard**: Only document tools that earn their token cost.
  `snyk_monitor` does not belong in the on-by-default set.
- **Path-scoped rules**: Rules in `~/.claude/rules/` with a `path:` frontmatter
  field only activate when Claude is editing files matching that path. Verify the
  exact frontmatter syntax by reading an existing path-scoped rule first.
- **settings.json hook schema**: The hook format has changed across Claude Code
  versions. Read the current file and the settings-and-permissions rule before
  writing any hook additions to avoid syntax errors.
- **Branch naming**: `claude/<description>-<id>` format.
- **MCP Scan is pre-GA**: Document the gap; do not implement MCP Scan hooks yet.
  Add a TODO in the pre-commit rules file noting the condition for implementation.
