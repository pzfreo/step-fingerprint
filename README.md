# cad-fingerprint

Generate pytest test suites from STEP or STL reference files. Any procedural
[build123d](https://github.com/gumyr/build123d) implementation that passes all
tests is geometrically equivalent to the reference for manufacturing purposes.

## What it does

`cad-fingerprint` analyses a CAD file and extracts a **geometric fingerprint**:
a set of measurements that together fully characterise the shape without
exposing the internal B-rep structure. It then generates a self-contained
pytest file that encodes those measurements as assertions.

The intended workflow is:

```
reference.step  ──►  cad-fingerprint  ──►  test_part.py
                                                │
procedural build123d code  ──►  pytest  ◄───────┘
                                   │
                              pass / fail
```

This lets you reverse-engineer a STEP file into clean parametric code
incrementally — run the tests, read the failures, adjust the code, repeat —
without needing to compare B-rep trees or CAD history.

## Fingerprint measurements

| Measurement | What it checks |
|---|---|
| Volume & surface area | Overall material quantity |
| Bounding box (min/max) | Overall envelope |
| Centre of mass | Mass distribution |
| Moments of inertia (6-component tensor) | Mass distribution in 3D — very sensitive |
| Face inventory | Surface types (Plane, Cylinder, Torus, BSpline …), counts, areas, and key dimensions (diameters, radii) |
| Edge inventory | Edge types (Line, Circle, BSpline …), counts, and key dimensions |
| Cross-sections | Area at N evenly-spaced planes along the primary axis |
| Radial profile | Outer radius at M axial positions × K angles |
| Build quality | Wall thickness, sharp edges, free edges, non-manifold geometry |

For STL files, face type classification is unavailable (no analytical surface
information exists in the mesh); all other measurements work normally. The
radial profile uses direct Möller-Trumbore ray-triangle intersection (rather
than OCCT's `IntCurvesFace_ShapeIntersector`, which only works on analytical
BREP surfaces) and shoots rays from the bounding-box centre so parts that are
not centred on the world origin still produce meaningful results.

## Installation

Requires Python ≥ 3.10 and [build123d](https://github.com/gumyr/build123d).

```bash
pip install cad-fingerprint
```

For development:

```bash
git clone https://github.com/pzfreo/cad-fingerprint.git
cd cad-fingerprint
pip install -e ".[dev]"
```

## Usage

### Generate a test file

```bash
cad-fingerprint reference.step -o tests/test_reference.py
cad-fingerprint reference.stl  -o tests/test_reference.py
```

Options:

| Flag | Default | Description |
|---|---|---|
| `-o / --output` | — | Output pytest file |
| `--json` | — | Also save the raw fingerprint as JSON |
| `--prompt` | — | Also generate a PROMPT.md reverse-engineering guide |
| `--name` | filename stem | Human-readable part name used in test docstrings |
| `--fixture` | `part_under_test` | pytest fixture name |
| `--axis` | `Z` | Primary axis (`X`, `Y`, or `Z`) |
| `--cross-sections` | 20 | Number of cross-section slices |
| `--radial-slices` | 15 | Number of axial positions for radial profile |
| `--angles` | 12 | Angular samples per radial position |

Tolerance flags (all have sensible defaults):
`--volume-tol`, `--area-tol`, `--bbox-tol`, `--inertia-tol`,
`--xs-area-tol`, `--xs-centroid-tol`, `--xs-moment-tol`, `--radial-tol`

### Run the generated tests

The generated file expects a `part_under_test` pytest fixture that returns a
build123d `Part`. Create a `conftest.py` alongside the test file:

```python
import pytest
from my_part import build_part

@pytest.fixture
def part_under_test():
    return build_part()
```

Then run:

```bash
pytest tests/test_reference.py -v
```

### Compare two STEP files directly

```bash
cad-fingerprint compare reference.step implementation.step
```

Produces a colour-coded terminal report (pass / close / fail per metric) and
exits non-zero if any metric fails.

### Python API

```python
from cad_fingerprint import CadFingerprint

fp = CadFingerprint.from_step("reference.step")
fp = CadFingerprint.from_stl("reference.stl")

fp.to_json("fingerprint.json")          # save
fp2 = CadFingerprint.from_json("fingerprint.json")  # load

from cad_fingerprint.compare import compare_fingerprints, format_comparison
result = compare_fingerprints(fp, fp2)
print(format_comparison(result))
```

## Approach

The analyser uses [OpenCASCADE](https://www.opencascade.com/) (via build123d's
OCP bindings) directly:

- **Global properties** — `BRepGProp` for volume, surface area, centre of mass,
  and the full 3×3 inertia tensor.
- **Bounding box** — axis-aligned bounding box from `Bnd_Box`.
- **Face inventory** — walks all faces with `TopExp_Explorer`; classifies each
  surface type via `BRepAdaptor_Surface`; extracts diameter/radius for
  cylinders, cones, spheres, and tori.
- **Edge inventory** — same approach for edges via `BRepAdaptor_Curve`;
  extracts radius for circular edges and arc length for all types.
- **Cross-sections** — slices the solid at N planes along the primary axis
  using `BRepAlgoAPI_Section`; computes area, centroid, and second moments of
  each cross-section polygon.
- **Radial profile** — for STEP: shoots rays from the axis at M axial heights ×
  K angles using `IntCurvesFace_ShapeIntersector`; records the outermost
  intersection radius at each angle. For STL: uses Möller-Trumbore
  ray-triangle intersection from the bounding-box centre to handle parts not
  aligned with the world origin.
- **Build quality** — `ShapeAnalysis_FreeBounds` for free/non-manifold edges;
  `BRepCheck_Analyzer` for invalid geometry; minimum wall thickness via
  ray-sampling.

The generated pytest file embeds all reference values as plain Python
constants. It has no dependency on `cad-fingerprint` at runtime — only on
`build123d` and `OCP` (which build123d already requires).

## Example

The `examples/` directory contains a guitar tuning-peg head (`peghead7mm.step`)
with its generated test file (`test_peghead.py`), a reverse-engineered
procedural implementation (`peghead_procedural.py`), and a reverse-engineering
guide (`PROMPT.md`).

```bash
cd examples
pytest test_peghead.py -v
```

## License

MIT
