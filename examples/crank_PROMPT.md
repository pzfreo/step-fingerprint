# Reverse-Engineer a STEP File into build123d

## Goal

Recreate the geometry in the reference STEP file as procedural build123d Python code. The test suite in `test_crank.py` defines geometric assertions that your implementation must pass.

## Part Overview

- **Bounding box**: 56.0 × 15.0 × 16.0 mm
- **Volume**: 8230.2 mm³
- **Surface area**: 3868.7 mm²
- **Faces**: 3402 (0 BSpline / complex)
- **Primary axis**: Z

## Key Dimensions (extracted from fingerprint)

### Profile transitions

Significant cross-section area changes along the Z axis:

- At Z=56.0: area 95.5 → 230.7 mm²
- At Z=58.5: area 356.0 → 721.5 mm²
- At Z=68.4: area 738.9 → 373.3 mm²
- At Z=70.9: area 248.0 → 80.1 mm²

## Process

1. **Study the fingerprint data** in the test file. The reference data tells you everything about the shape:
   - `REF_FACE_INVENTORY` — every face type, area, and key dimensions (diameters, radii)
   - `REF_EDGE_INVENTORY` — every edge type, length, and radii (circle edges indicate fillets/rounds)
   - `REF_CROSS_SECTIONS` — cross-sectional area at multiple Z positions
   - `REF_RADIAL_PROFILE` — outer radius at multiple positions × angles
   - `REF_VOLUME`, `REF_SURFACE_AREA`, `REF_BBOX_*` — global properties
   - `REF_INERTIA` — moments of inertia (very sensitive to mass distribution)

2. **Create your implementation** in a new file that exports a function returning a build123d `Part`.

3. **Create a conftest.py** with a fixture:
   ```python
   import pytest
   from my_implementation import create_crank

   @pytest.fixture
   def part_under_test():
       return create_crank()
   ```

4. **Run the tests**: `pytest test_crank.py -v`

5. **Iterate**. Read the failures, adjust your code, repeat.

## Tips for Reading the Fingerprint

- **Cross-sections** show area vs position. Large jumps indicate transitions between features. Constant areas indicate cylindrical or prismatic sections.
- **Radial profiles** show radius vs angle at each position. Uniform radius = circular. Varying radius = sculpted/oval. `None` values mean the ray missed (bore or concavity).
- **Face inventory** lists every surface. BSpline faces are sculpted regions — you may need `fillet`, `sweep`, or `loft` operations, or accept that OCCT will approximate them as BSplines.
- **Cylinder diameters** give you key feature sizes directly.
- **Torus faces** are fillets/rounds — the minor radius is the fillet radius.

## Build Quality Rules

The test suite includes build quality checks. Follow these rules to avoid common failures:

### After every boolean (fuse, subtract, split)
- Verify the result is a single solid. Boolean operations in build123d can return `Compound`, `ShapeList`, or multiple solids.
- Use a helper like `max(result.solids(), key=lambda s: s.volume)` to extract the largest solid if needed.
- Check for unexpected topology changes (face count, edge count).

### After every fillet
- Verify the fillet actually applied (face count should increase).
- If OCCT produces BSpline surfaces where the reference has Torus faces, consider alternative approaches (torus subtract, arcs in revolve profiles).
- Fillets on complex edge intersections (sphere-plane, cone-plane) will almost always produce BSpline approximations.

### STEP export
- Use AP203 with `STEPControl_ManifoldSolidBrep` for best compatibility.
- Run `ShapeFix_Shape` before export to catch minor geometry issues.

## What Success Looks Like

All tests passing means your procedural code produces geometry that is manufacturing-equivalent to the reference STEP file. Minor surface representation differences are OK — the tolerances are calibrated to accept these while catching real geometry errors.
