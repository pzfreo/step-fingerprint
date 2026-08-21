"""cad-fingerprint: Generate geometric fingerprint tests from STEP and STL files.

Usage:
    cad-fingerprint reference.step -o tests/test_reference.py
    cad-fingerprint reference.stl  -o tests/test_reference.py

Generates a pytest test file containing a comprehensive geometric fingerprint
of the reference file. Any procedural build123d implementation that passes all
tests is geometrically equivalent to the reference for manufacturing purposes.

Reading CAD files needs build123d and OCC, but measuring surface deviation
does not: a saved JSON fingerprint carries its own mesh, and
:mod:`cad_fingerprint.hausdorff` is pure Python. So the names that pull in a
CAD kernel resolve on first use rather than at import, and comparing two saved
fingerprints works with nothing but the standard library.
"""

__all__ = ["CadFingerprint", "StepFingerprint", "analyze_step", "analyze_stl"]


def __getattr__(name):
    """Import the CAD-backed names on demand (PEP 562)."""
    if name in ("CadFingerprint", "StepFingerprint"):
        from .fingerprint import CadFingerprint

        return CadFingerprint
    if name in ("analyze_step", "analyze_stl"):
        from . import analyze

        return getattr(analyze, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
