"""cad-fingerprint: Generate geometric fingerprint tests from STEP and STL files.

Usage:
    cad-fingerprint reference.step -o tests/test_reference.py
    cad-fingerprint reference.stl  -o tests/test_reference.py

Generates a pytest test file containing a comprehensive geometric fingerprint
of the reference file. Any procedural build123d implementation that passes all
tests is geometrically equivalent to the reference for manufacturing purposes.
"""

from .fingerprint import CadFingerprint
from .analyze import analyze_step, analyze_stl

# Backwards compatibility alias
StepFingerprint = CadFingerprint

__all__ = ["CadFingerprint", "StepFingerprint", "analyze_step", "analyze_stl"]
