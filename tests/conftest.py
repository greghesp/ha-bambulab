"""Root conftest for the unit test suite.

pybambu/ is a plain-Python library nested inside custom_components/bambu_lab/,
whose own __init__.py imports Home Assistant. Tests intentionally live here at
the repo root, outside custom_components/, rather than under
pybambu/tests/: that keeps pytest's package-collection from ever needing to
import custom_components/bambu_lab/__init__.py (and therefore homeassistant)
just to reach these tests. See docs/misc/contributing for details.

This just puts custom_components/bambu_lab on sys.path so tests can
`import pybambu` as a top-level package, the same way Home Assistant imports
it via a relative import from within the integration at runtime.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "bambu_lab"))
