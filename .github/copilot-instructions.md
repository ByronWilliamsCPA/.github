# GitHub Copilot Instructions

## Repository Context

This is the ByronWilliamsCPA GitHub org-level community health file repository
and reusable GitHub Actions workflow library. There is no Python package or
application code in this repo.

## Writing Rules

Never use em-dashes in any generated text, comments, or code.
Replace with comma, semicolon, colon, or restructure the sentence.

## Workflow Editing Guidelines

- Always include `permissions: {}` at the workflow level and explicit permissions at the job level
- Always include `timeout-minutes` on every job
- Always include `step-security/harden-runner` as the first step in every job
- Use SHA-pinned action refs (e.g., `uses: actions/checkout@<sha>`)

## Branch Naming

Use `claude/<description>-<id>` for AI-assisted branches.
