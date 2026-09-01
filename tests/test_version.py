# Copyright (C) 2026 1Claw
# SPDX-License-Identifier: Apache-2.0
"""The package version must match the one that will be published."""

import importlib
import pathlib
import re


def test_dunder_version_matches_pyproject() -> None:
    """__version__ and pyproject.toml must not drift.

    They did: 1claw-crewai-tools 
    shipped a release whose __version__ named an earlier version, because the
    literal in __init__.py was hand-maintained alongside the one in
    pyproject.toml. __version__ now reads the installed distribution metadata,
    so there is one source of truth; this asserts it stayed that way.
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    declared = re.search(
        r'^version\s*=\s*"([^"]+)"', (root / "pyproject.toml").read_text(), re.M
    )
    assert declared, "pyproject.toml has no version"

    mod = importlib.import_module("oneclaw_crewai")
    assert mod.__version__ == declared.group(1), (
        f"__version__ is {mod.__version__} but pyproject.toml says {declared.group(1)}; "
        "a published package would report the wrong version"
    )
