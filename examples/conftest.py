"""Conftest for validating the procedural peghead implementation."""

import pytest
from peghead_procedural import create_peghead


@pytest.fixture
def part_under_test():
    """Return the procedurally built peghead as the Part under test."""
    return create_peghead()
