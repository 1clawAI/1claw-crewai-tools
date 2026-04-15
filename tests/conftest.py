"""Pytest fixtures for 1claw-crewai-tools tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def api_base() -> str:
    """Test API base URL (respx will intercept)."""
    return "https://api.1claw.example"
