# Qlty Cloud Integration Guide

Integrate Qlty Cloud into your reusable workflows for centralized code quality management across all repositories.

## 🎯 What is Qlty?

Qlty Cloud is a centralized code quality platform that:
- ✅ Aggregates quality metrics across all repositories
- ✅ Provides unified quality dashboards
- ✅ Enforces organization-wide quality standards
- ✅ Integrates with GitHub Actions seamlessly
- ✅ Supports multiple languages and tools

## 📋 Prerequisites

1. **Qlty Cloud Account**
   - Sign up at https://qlty.cloud
   - Create an organization

2. **Qlty VS Code Extension** (Optional)
   - Install from VS Code marketplace
   - Provides inline quality feedback

3. **GitHub Organization Access**
   - Admin access to `ByronWilliamsCPA` organization
   - Ability to add GitHub Apps

---

## 🚀 Setup

### Step 1: Install Qlty GitHub App

1. Go to https://qlty.cloud/github-app
2. Click "Install Qlty for GitHub"
3. Select the `ByronWilliamsCPA` organization
4. Grant permissions:
   - ✅ Read access to code
   - ✅ Read/Write access to checks
   - ✅ Read/Write access to pull requests
5. Install on all repositories or select specific ones

### Step 2: Generate Qlty API Token

1. Go to https://qlty.cloud/settings/tokens
2. Click "Create New Token"
3. Name it: `GitHub Actions - ByronWilliamsCPA`
4. Copy the token (you'll need it next)

### Step 3: Add Token to GitHub Secrets

> ✅ **COMPLETED**: `QLTY_TOKEN` is already configured as an organization-level secret and available to all repositories in ByronWilliamsCPA.

#### For Organization Accounts (Current Setup)

**Organization-level secret** (recommended):

1. Go to https://github.com/organizations/ByronWilliamsCPA/settings/secrets/actions
2. Click "New organization secret"
3. Name: `QLTY_TOKEN`
4. Value: Paste the token from Step 2
5. Repository access: "All repositories"

#### For Personal Accounts

Since personal accounts don't support organization-level secrets, you'll need to add the secret to each repository.

**Option A: GitHub CLI (Automated - Recommended)**

```bash
# Install GitHub CLI
brew install gh  # macOS
# or: sudo apt install gh  # Linux

# Authenticate
gh auth login

# Add QLTY_TOKEN to all Python repos
for repo in $(gh repo list --limit 100 --json name,primaryLanguage -q '.[] | select(.primaryLanguage.name == "Python") | .name'); do
  echo "Adding QLTY_TOKEN to $repo..."
  gh secret set QLTY_TOKEN --repo "williaby/$repo" --body "your-qlty-token-here"
done
```

**Option B: Manual Setup**

1. Go to each repo: `https://github.com/williaby/REPO-NAME/settings/secrets/actions`
2. Click "New repository secret"
3. Name: `QLTY_TOKEN`
4. Value: Paste the token from Step 2
5. Click "Add secret"
6. Repeat for each Python repository

**Option C: Use Provided Script**

We've created a helper script to automate this:

```bash
# From your .github repository
./.github/scripts/sync-secrets.sh

# Follow the prompts to add QLTY_TOKEN to all Python repos
```

See the script in `.github/scripts/sync-secrets.sh` (created above).

---

## 🔧 Integration Methods

### Method 1: Integrate into Reusable CI Workflow (Recommended)

Update the `python-ci.yml` reusable workflow to include Qlty checks.

**Add to `.github/workflows/python-ci.yml`**:

```yaml
name: Python CI (Reusable)

on:
  workflow_call:
    # ... existing inputs ...

    inputs:
      run-qlty:
        description: 'Run Qlty quality checks'
        type: boolean
        required: false
        default: true

    secrets:
      QLTY_TOKEN:
        description: 'Qlty API token for quality reporting'
        required: false
      # ... other secrets ...

jobs:
  # ... existing jobs ...

  qlty-check:
    name: Qlty Quality Check
    if: ${{ inputs.run-qlty }}
    runs-on: ubuntu-latest
    permissions:
      contents: read
      checks: write
      pull-requests: write

    steps:
      - name: Harden Runner
        uses: step-security/harden-runner@91182cccc01eb5e619899d80e4e971d6181294a7  # v2.10.1
        with:
          egress-policy: audit

      - name: Checkout code
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
        with:
          fetch-depth: 0  # Full history for better analysis

      - name: Set up Python
        uses: actions/setup-python@8d9ed9ac5c53483de85588cdf95a591a75ab9f55  # v5.5.0
        with:
          python-version: '3.12'

      - name: Run Qlty Check
        uses: qltysh/qlty-action@v1
        with:
          token: ${{ secrets.QLTY_TOKEN }}
          upload-results: true
          fail-on-violations: false  # Don't fail CI, just report

      - name: Qlty Summary
        if: always()
        run: |
          echo "## Qlty Quality Report" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "View detailed results at: https://qlty.cloud" >> $GITHUB_STEP_SUMMARY
```

**Usage in downstream repos**:

```yaml
jobs:
  ci:
    uses: williaby/.github/.github/workflows/python-ci.yml@main
    with:
      python-versions: '["3.11", "3.12"]'
      run-qlty: true  # Enable Qlty checks
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
      QLTY_TOKEN: ${{ secrets.QLTY_TOKEN }}  # Pass Qlty token
```

---

### Method 2: Standalone Qlty Workflow

Create a dedicated reusable workflow for Qlty checks.

**Create `.github/workflows/qlty-check.yml`**:

```yaml
# Qlty Quality Check - Reusable Workflow
name: Qlty Check (Reusable)

on:
  workflow_call:
    inputs:
      fail-on-violations:
        description: 'Fail CI on quality violations'
        type: boolean
        required: false
        default: false

      python-version:
        description: 'Python version for checks'
        type: string
        required: false
        default: '3.12'

    secrets:
      QLTY_TOKEN:
        description: 'Qlty API token'
        required: true

permissions:
  contents: read
  checks: write
  pull-requests: write

jobs:
  qlty:
    name: Quality Analysis
    runs-on: ubuntu-latest

    steps:
      - name: Harden Runner
        uses: step-security/harden-runner@91182cccc01eb5e619899d80e4e971d6181294a7  # v2.10.1
        with:
          egress-policy: audit

      - name: Checkout code
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@8d9ed9ac5c53483de85588cdf95a591a75ab9f55  # v5.5.0
        with:
          python-version: ${{ inputs.python-version }}

      - name: Run Qlty Analysis
        uses: qltysh/qlty-action@v1
        with:
          token: ${{ secrets.QLTY_TOKEN }}
          upload-results: true
          fail-on-violations: ${{ inputs.fail-on-violations }}

      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '## Qlty Quality Report\n\nView detailed quality metrics at [Qlty Dashboard](https://qlty.cloud)'
            })
```

**Usage**:

```yaml
# Separate Qlty workflow
jobs:
  qlty:
    uses: williaby/.github/.github/workflows/qlty-check.yml@main
    secrets:
      QLTY_TOKEN: ${{ secrets.QLTY_TOKEN }}
```

---

### Method 3: Qlty CLI in Existing Workflows

Add Qlty directly to existing workflow steps.

```yaml
jobs:
  quality-checks:
    steps:
      # ... existing steps ...

      - name: Install Qlty CLI
        run: |
          curl -sSL https://install.qlty.sh | sh
          echo "$HOME/.qlty/bin" >> $GITHUB_PATH

      - name: Run Qlty Check
        env:
          QLTY_TOKEN: ${{ secrets.QLTY_TOKEN }}
        run: |
          qlty check --upload

      - name: Qlty Format Report
        if: always()
        run: |
          qlty report --format json > qlty-report.json

      - name: Upload Qlty Report
        if: always()
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02  # v4.6.2
        with:
          name: qlty-quality-report
          path: qlty-report.json
```

---

## 📊 What Qlty Checks

Qlty integrates with existing tools and aggregates results:

### Python Tools

- ✅ **Ruff** - Linting (already in CI workflow)
- ✅ **MyPy** - Type checking (already in CI workflow)
- ✅ **Bandit** - Security (already in security workflow)
- ✅ **Black** - Formatting (already in CI workflow)
- ✅ **Coverage** - Test coverage (already tracked)

### Qlty Adds

- ✅ **Trend Analysis** - Quality metrics over time
- ✅ **Cross-Repo Comparison** - Compare repos in organization
- ✅ **Quality Gates** - Enforce minimum standards
- ✅ **Debt Tracking** - Technical debt quantification
- ✅ **Custom Rules** - Organization-specific standards

---

## 🔒 Security Considerations

### Token Security

- Store `QLTY_TOKEN` as organization secret
- Never commit tokens to code
- Rotate tokens regularly (quarterly recommended)

### Permissions

Qlty GitHub App needs:
- **Read**: Repository contents, workflows
- **Write**: Checks (for status updates), PRs (for comments)
- **No** write access to code

### Data Privacy

- Qlty analyzes code quality metrics only
- No source code is stored (only metadata)
- Results are private to your organization
- GDPR/SOC2 compliant

---

## 📈 Qlty Dashboard Features

### Organization Dashboard

- **Quality Score** - Overall org code quality
- **Trend Analysis** - Quality over time
- **Repository Comparison** - Compare projects
- **Hot Spots** - Files needing attention

### Pull Request Integration

- **PR Comments** - Quality feedback on PRs
- **Quality Gates** - Block merges on violations
- **Diff Analysis** - Only check changed code
- **Inline Annotations** - Issues marked in code

### Team Features

- **Quality Goals** - Set org-wide targets
- **Reports** - Weekly/monthly summaries
- **Notifications** - Slack/email alerts
- **Custom Rules** - Org-specific quality rules

---

## 🎨 Configuration

### `.qlty.yaml` in Org Repo

Create `.qlty.yaml` in `williaby/.github` for org-wide config:

```yaml
# Qlty Organization Configuration
version: '1.0'

rules:
  # Python rules
  python:
    enabled: true
    tools:
      - ruff
      - mypy
      - bandit

    severity:
      high: error    # Fail CI on high severity
      medium: warning
      low: info

  # Quality gates
  gates:
    coverage:
      minimum: 80
      target: 90

    complexity:
      max_cyclomatic: 10
      max_cognitive: 15

    maintainability:
      min_score: 'B'  # A, B, C, D, F scale

# File ignores
ignore:
  - 'tests/**'
  - '**/migrations/**'
  - '**/__pycache__/**'
  - '.venv/**'

# Custom rules
custom_rules:
  - id: 'no-print-statements'
    pattern: 'print\('
    message: 'Use logging instead of print()'
    severity: warning
    languages: [python]
```

---

## 🔄 Workflow Examples

### Example 1: Full CI with Qlty

```yaml
name: Complete CI

on: [push, pull_request]

jobs:
  # Standard CI (includes Ruff, MyPy, tests)
  ci:
    uses: williaby/.github/.github/workflows/python-ci.yml@main
    with:
      python-versions: '["3.11", "3.12"]'
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}

  # Qlty aggregates and reports
  qlty:
    needs: ci
    uses: williaby/.github/.github/workflows/qlty-check.yml@main
    secrets:
      QLTY_TOKEN: ${{ secrets.QLTY_TOKEN }}
```

### Example 2: Quality Gate on PRs

```yaml
name: PR Quality Gate

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  quality-gate:
    uses: williaby/.github/.github/workflows/qlty-check.yml@main
    with:
      fail-on-violations: true  # Block merge on violations
    secrets:
      QLTY_TOKEN: ${{ secrets.QLTY_TOKEN }}
```

### Example 3: Scheduled Quality Report

```yaml
name: Weekly Quality Report

on:
  schedule:
    - cron: '0 0 * * 1'  # Monday midnight

jobs:
  quality-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate Qlty Report
        env:
          QLTY_TOKEN: ${{ secrets.QLTY_TOKEN }}
        run: |
          curl -sSL https://install.qlty.sh | sh
          $HOME/.qlty/bin/qlty report --format markdown > quality-report.md

      - name: Create Issue
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('quality-report.md', 'utf8');

            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'Weekly Quality Report',
              body: report,
              labels: ['quality', 'automated']
            });
```

---

## 🎯 Benefits of Qlty Integration

### For Individual Developers

- ✅ **Instant Feedback** - Quality issues in VS Code
- ✅ **Pre-commit Checks** - Catch issues before PR
- ✅ **Learning Tool** - Best practices suggestions

### For Teams

- ✅ **Consistency** - Same standards across all repos
- ✅ **Visibility** - See quality trends
- ✅ **Collaboration** - Shared quality goals

### For Organization

- ✅ **Governance** - Enforce quality policies
- ✅ **Metrics** - Track quality org-wide
- ✅ **Efficiency** - Reduce code review time

---

## 🛠️ Troubleshooting

### "Qlty token invalid"

**Fix**: Regenerate token at https://qlty.cloud/settings/tokens

### "Permission denied"

**Fix**: Ensure Qlty GitHub App is installed with correct permissions

### "No quality data"

**Fix**: Run `qlty check --upload` locally first to initialize

### "Tool not found"

**Fix**: Ensure tools (ruff, mypy) are in `pyproject.toml` dependencies

---

## 📚 Additional Resources

- **Qlty Docs**: https://docs.qlty.cloud
- **GitHub Action**: https://github.com/marketplace/actions/qlty
- **VS Code Extension**: https://marketplace.visualstudio.com/items?itemName=qlty.qlty-vscode
- **API Reference**: https://api.qlty.cloud/docs

---

## ✅ Quick Start Checklist

- [ ] Sign up for Qlty Cloud
- [ ] Install Qlty GitHub App on organization
- [ ] Generate API token
- [ ] Add `QLTY_TOKEN` to GitHub organization secrets
- [ ] Create `.qlty.yaml` config in `.github` repo
- [ ] Add Qlty step to `python-ci.yml` workflow
- [ ] Test on a pull request
- [ ] Review results at https://qlty.cloud
- [ ] Install VS Code extension (optional)
- [ ] Configure quality gates (optional)

---

**Last Updated**: 2025-11-18
**Maintained by**: williaby organization
**Questions?**: Contact Qlty support or open issue in this repo
