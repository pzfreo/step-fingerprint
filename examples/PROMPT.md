# Reverse-Engineer a STEP File into build123d

## Goal

Recreate the geometry in `peghead7mm.step` as procedural build123d Python code. The test suite in `test_peghead.py` defines 43 geometric assertions that your implementation must pass.

## Background

This is a guitar tuning peg head. It has:
- A decorative ring with a sculpted finger grip (the most complex part — BSpline surfaces)
- A bore through the ring offset slightly from center
- A cylindrical shaft ("join") running through the ring bore
- A cap flange on one end
- A shoulder cylinder below the cap
- A small decorative pip button on the opposite end, connected by a thin stalk
- Chamfers and fillets throughout

The part is oriented with:
- Z axis along the shaft
- Ring/pip at negative Z, shaft extending into positive Z
- The ring is wider in X than Y (oval finger grip)

## Process

1. **Study the fingerprint data** in `test_peghead.py`. The reference data tells you everything about the shape:
   - `REF_FACE_INVENTORY` — every face type, area, and key dimensions (diameters, radii)
   - `REF_CROSS_SECTIONS` — cross-sectional area at 20 Z positions
   - `REF_RADIAL_PROFILE` — outer radius at 15 Z positions × 12 angles
   - `REF_VOLUME`, `REF_SURFACE_AREA`, `REF_BBOX_*` — global properties
   - `REF_INERTIA` — moments of inertia (very sensitive to mass distribution)

2. **Create your implementation** in a new file (e.g. `peghead_procedural.py`) that exports a function returning a `Part`.

3. **Create a conftest.py** that wires your function to the `part_under_test` fixture:
   ```python
   import pytest
   from peghead_procedural import create_peghead

   @pytest.fixture
   def part_under_test():
       return create_peghead()
   ```

4. **Run the tests**: `pytest test_peghead.py -v`

5. **Iterate**. Read the failures, adjust your code, repeat. The test output tells you exactly what's wrong — e.g. "Area at Z=-6.59: 18.3 vs ref 24.25 (24.5% off)" means your cross-section is too small at that position.

## Tips for Reading the Fingerprint

- **Cross-sections** show area vs Z position. Large jumps indicate transitions (e.g. cap to ring). Constant areas indicate cylindrical sections.
- **Radial profiles** show radius vs angle at each Z. Uniform radius = circular. Varying radius = sculpted/oval. `None` values mean the ray missed (you're inside a bore or concavity).
- **Face inventory** lists every surface. The BSpline faces are the sculpted grip — you'll need `sweep` or `loft` operations to approximate these.
- **Cylinder diameters** give you all the key dimensions: 9.8mm bore, 7.0mm shoulder, 3.8mm shaft, 2.1mm pip, 1.0mm stalk, 0.597mm chamfer features.
- **Torus faces** are fillets/rounds: R=2.0mm (main ring round), R=0.3mm (small edge fillets).

## Key Dimensions (extracted from fingerprint)

| Feature | Diameter/Size | Z range (approx) |
|---------|--------------|-------------------|
| Pip tip | 2.1mm | -19.0 to -17.8 |
| Pip stalk | 1.0mm | -17.8 to -17.6 |
| Ring (sculpted) | ~12.5mm wide | -7 to -1 |
| Ring bore | 9.8mm | inside ring |
| Cap flange | ~8.5mm | -1.2 to 0 |
| Shoulder | 7.0mm | 0 to ~1 |
| Shaft | 3.8mm | 1 to 10.4 |

## What Success Looks Like

All 43 tests passing means your procedural code produces geometry that is manufacturing-equivalent to the OnShape STEP file. Minor surface representation differences are OK — the tolerances are calibrated to accept these while catching real geometry errors.
