"""Conftest for validating against the original peg head STEP.

This is the "gold standard" test — the reference STEP should pass its own
fingerprint with zero tolerance violations.
"""

import pytest
from step_fingerprint.analyze import load_step

PEGHEAD_STEP = "/app/workspaces/pzfreo/gib-tuners-mk2/reference/peghead7mm.step"


@pytest.fixture
def part_under_test():
    """Return the reference STEP as the Part under test."""
    return load_step(PEGHEAD_STEP)
