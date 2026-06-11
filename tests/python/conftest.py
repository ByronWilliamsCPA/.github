"""Pytest configuration: make scripts/ importable without a package install.

This repo has no Python package or build system; the license checker lives at
scripts/check_licenses.py as a standalone module.  Inserting the scripts/
directory here (before test collection imports the test modules) keeps the
sys.path manipulation out of the test files themselves.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
