#!/usr/bin/env bash
# ============================================================================
# check-python-versions.sh
# ----------------------------------------------------------------------------
# Enforce the Python version policy in docs/python-versions.md across all
# workflow and template YAML. Fails (exit 1) if any python-version(s) input
# default or test matrix references a version outside the supported set.
#
# GitHub Actions does not allow a workflow_call input default to read a
# variable, so the supported versions cannot be injected from one place at
# runtime. This script is the enforcement half of that single source of truth:
# the doc declares the policy, the script proves the workflows match it.
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$REPO_ROOT/docs/python-versions.md"

if [[ ! -f "$POLICY" ]]; then
  echo "ERROR: policy file not found: $POLICY" >&2
  exit 2
fi

supported="$(sed -n 's/.*python-versions:supported = \([0-9. ]*\).*/\1/p' "$POLICY" | head -1)"
primary="$(sed -n 's/.*python-versions:primary = \([0-9.]*\).*/\1/p' "$POLICY" | head -1)"
supported="${supported%"${supported##*[![:space:]]}"}"  # rstrip

if [[ -z "$supported" || -z "$primary" ]]; then
  echo "ERROR: could not parse supported/primary markers from $POLICY" >&2
  exit 2
fi

echo "Policy (docs/python-versions.md): supported = [$supported], primary = $primary"
echo

# A line "selects" a Python version when it sets a python-version(s) key
# (matrix array or scalar) or is the default of a python-version(s) input.
# Conditional artifact handlers (codecov per-version steps gated on hashFiles)
# do not use that key, so they are correctly ignored.
scan_one() {
  awk -v supported="$supported" '
    BEGIN { n = split(supported, a, " "); for (i = 1; i <= n; i++) ok[a[i]] = 1 }
    function check(s,   v) {
      while (match(s, /3\.[0-9]+/)) {
        v = substr(s, RSTART, RLENGTH)
        if (!(v in ok)) {
          printf "DRIFT: %s:%d selects Python %s (not in supported set)\n", FILENAME, FNR, v
          bad++
        }
        s = substr(s, RSTART + RLENGTH)
      }
    }
    {
      line = $0
      sub(/#.*/, "", line)                       # drop trailing comments/pins
      # Track the nearest input name (a 6-space key with an empty value).
      if (line ~ /^      [a-zA-Z0-9_-]+:[[:space:]]*$/) {
        curinput = line
        sub(/^ +/, "", curinput); sub(/:.*/, "", curinput)
      }
      # Inline python-version key (matrix array or scalar value).
      if (line ~ /python-version/) check(line)
      # default: of a python-version(s) input.
      else if (curinput ~ /^python-versions?[a-z-]*$/ && line ~ /^[[:space:]]+default:/) check(line)
    }
    END { if (bad > 0) exit 1 }
  ' "$1"
}

violations=0
while IFS= read -r file; do
  scan_one "$file" || violations=$((violations + 1))
done < <(find "$REPO_ROOT/.github/workflows" "$REPO_ROOT/workflow-templates" \
              \( -name '*.yml' -o -name '*.yaml' \) | sort)

echo
if [[ "$violations" -gt 0 ]]; then
  echo "FAIL: Python-version policy violations found in $violations file(s)."
  echo "Fix the workflow, or update docs/python-versions.md if the policy changed."
  exit 1
fi

echo "OK: all python-version defaults and matrices are within the supported set."
