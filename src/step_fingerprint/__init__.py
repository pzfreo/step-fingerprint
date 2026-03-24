"""step-fingerprint: Generate geometric fingerprint tests from STEP files.

Usage:
    step-fingerprint reference.step -o tests/test_reference.py

Generates a pytest test file containing a comprehensive geometric fingerprint
of the STEP file. Any procedural build123d implementation that passes all
tests is geometrically equivalent to the reference for manufacturing purposes.
"""

from .fingerprint import StepFingerprint
from .analyze import analyze_step

__all__ = ["StepFingerprint", "analyze_step"]
