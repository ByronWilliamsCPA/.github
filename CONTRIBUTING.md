# Contributing

Thanks for taking the time to contribute. This file applies to all
repositories in the ByronWilliamsCPA org that do not provide their own
`CONTRIBUTING.md`.

## Before You Start

1. Read the [Code of Conduct](CODE_OF_CONDUCT.md).
2. Search existing issues and pull requests so you don't duplicate work.
3. For non-trivial changes, open an issue first and agree on the approach
   before writing code.

## Local Development Setup

Setup is per-repository. Always read the target repo's `README.md` and CI
workflows (`.github/workflows/`) for the authoritative install and test
commands. The org spans Python projects, shell/bats projects, and pure
docs repos, so there is no single setup recipe.

What is consistent across the org:

```bash
# 1. Fork the repository on GitHub first (https://github.com/ByronWilliamsCPA/<repo>)
git clone https://github.com/<your-username>/<repo>.git
cd <repo>

# 2. Point "upstream" at the org repo so you can pull updates.
git remote add upstream https://github.com/ByronWilliamsCPA/<repo>.git

# 3. Install pre-commit hooks (required).
pre-commit install       # installs commit and commit-msg hooks
```

Maintainers with push access to the org repository can clone the org URL
directly and skip the fork step.

`pre-commit` hooks must pass before a commit lands. Run
`pre-commit run --all-files` if you touch many files at once.

**Example: Python repos** (those with a `pyproject.toml`):

```bash
python3 -m venv .venv
source .venv/bin/activate
uv sync                  # or: pip install -e ".[dev]"
pytest                   # run the test suite
```

**Example: shell/workflow repos** (those with `tests/*.bats`):

```bash
git submodule update --init --recursive   # bats helper libraries
bats tests/                                # run the test suite
```

## Branch Naming

Branch from `main` using one of these prefixes:

| Prefix      | Use for                                          |
|-------------|--------------------------------------------------|
| `feature/`  | New functionality                                |
| `fix/`      | Bug fixes                                        |
| `chore/`    | Tooling, build, dependency, and CI changes       |
| `docs/`     | Documentation only                               |
| `claude/`   | Reserved for automated agent commits             |

Examples: `feature/retry-handler`, `fix/timeout-on-empty-payload`,
`chore/bump-actions-checkout`, `docs/contributing-clarify-gpg`,
`claude/review-security-policy-aasG1`.

`claude/` is reserved for branches pushed by Claude Code agents working
on this repository; human contributors should pick one of the other four
prefixes.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/). The format
is:

```text
<type>(<scope>): <subject>

<optional body>

<optional footer(s)>
```

`<type>` is one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
`build`, `ci`, `chore`, `revert`. `<scope>` is optional and identifies the
area touched (for example `api`, `workflows`, `deps`).

Example:

```text
feat(api): add retry logic to request handler

Retries idempotent requests up to three times with exponential backoff.
Closes #123.
```

Keep the subject under 72 characters and in the imperative mood.

## GPG-Signed Commits Required

Every commit on every PR must be GPG-signed (or SSH-signed) and show as
**Verified** on GitHub. Branch protection on `main` enforces this at merge
time; unsigned commits pushed to a feature branch are not rejected at push,
but they cannot be merged.

To set this up once:

```bash
gpg --full-generate-key                       # or use an existing key
git config --global user.signingkey <KEY_ID>
git config --global commit.gpgsign true
git config --global tag.gpgsign true
```

Then add the public key to your GitHub account under
**Settings, SSH and GPG keys**. GitHub's docs cover SSH signing if you prefer
that path. DCO `Signed-off-by` lines are not a substitute for a cryptographic
signature.

## Pull Request Checklist

Before requesting review, confirm each item:

- [ ] Branch follows the naming convention above.
- [ ] All commits are GPG-signed and show as Verified on the PR.
- [ ] Commit messages follow Conventional Commits.
- [ ] `pre-commit run --all-files` passes locally.
- [ ] Tests pass (`pytest`, or the project's equivalent).
- [ ] New behavior has tests; bug fixes have regression tests.
- [ ] Public APIs and CLI changes are documented.
- [ ] The PR description links the issue (`Closes #N`) when one exists.
- [ ] The PR is scoped to one logical change; unrelated cleanup goes in a
      separate PR.

## Code Review Expectations

What contributors can expect:

- A first response within five business days. If the PR is small and CI is
  green, often sooner.
- Review comments will be specific and actionable. If something is a
  preference rather than a requirement, the reviewer will label it as
  `nit:`.
- The maintainer may push small fixups (typos, lint) directly rather than
  block on round trips. Anything larger will be requested as a change.

What reviewers expect from contributors:

- Respond to comments, even if the response is "I disagree, here's why."
- Resolve threads only after the comment has been addressed.
- Rebase on `main` rather than merging `main` into the branch when
  conflicts arise.
- Squash fixup commits before merge unless the history is intentionally
  preserved.

## Code Style

- **Python**: [PEP 8](https://peps.python.org/pep-0008/) with Google-style
  docstrings. Format and lint with `ruff`.
- **JavaScript/TypeScript**: [Airbnb style](https://github.com/airbnb/javascript),
  lint with `eslint --fix`, format with `prettier --write`.
- **YAML, Markdown, shell**: enforced by `pre-commit` (`yamllint`,
  `markdownlint`, `shellcheck`).
- **Imports** (Python): standard library, third-party, local, each group
  separated by a blank line.

## Reporting Security Issues

Do not file security problems as public issues. Follow [SECURITY.md](SECURITY.md).

Last updated: May 15, 2026
