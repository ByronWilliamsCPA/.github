# Contributing to Our Projects

Thank you for your interest in contributing! We welcome all contributions that
help improve our code, documentation, and community processes.

## How to Contribute

1. **Review the Code of Conduct**  
   Ensure your interactions align with our [Code of Conduct](CODE_OF_CONDUCT.md).

2. **Find or File an Issue**  
   - Search existing issues to avoid duplication.  
   - To report a bug, use the [bug template](.github/ISSUE_TEMPLATE/bug.yml).  
   - To propose a feature, use the [feature template]
   (.github/ISSUE_TEMPLATE/feature.yml).

3. **Fork & Clone**

   ```bash
   git clone https://github.com/<org>/<repo>.git
   cd <repo>
   git remote add upstream https://github.com/<org>/<repo>.git
   ```

## Pull Request Guidelines

- **Branch from main**  

  ```bash
  git checkout -b feature/<short-description>
  ```
  
- **Link your issue**  
  Include "Closes #ISSUE-NUMBER" in your PR description to auto-close the issue.
- **Commit messages**  
  Use the format:

  ```text
  <type>(<scope>): <subject>
  ```
  
  where `<type>` is one of `feat`, `fix`, `docs`, `style`, `refactor`, `test`,
  or `chore`.  
  _Example:_ `feat(api): add retry logic to request handler`
- **DCO Sign-off Required**  
  Every commit must include:

  ```text
  Signed-off-by: Your Name <you@example.com>
  ```

  Add with:

  ```bash
  git commit --signoff
  ```

## Code Style

- **Language conventions**  
  - **Python:** follow [PEP 8](https://peps.python.org/pep-0008/) and
    Google‐style docstrings  
  - **JavaScript/TypeScript:** follow
    [Airbnb style](https://github.com/airbnb/javascript)
- **Linters & formatters**  
  - Python: `ruff --fix`, `black`  
  - JavaScript/TypeScript: `eslint --fix`, `prettier --write`  
- **Imports**  
  Group imports in this order, with a blank line between groups:  
  1. Standard library  
  2. Third-party  
  3. Local application

## Local Development Setup

1. **Create a virtual environment** (Python example)

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Install dependencies** (Node example)  

   ```bash
   npm install
   ```

3. **Run tests**  

   ```bash
   pytest
   # or
   npm test
   ```

## Last updated: November 16, 2025
