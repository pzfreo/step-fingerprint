# Lessons Learned: Procedural CAD with build123d / OCCT

Notes from building `peghead_procedural.py` and `peghead_simple.py` — a guitar tuning peg button modelled procedurally in build123d, targeting clean STEP output.

## 1. OCCT fillets produce BSpline approximations on complex edges

OCCT's fillet algorithm (`BRepFilletAPI_MakeFillet`) uses a rolling-ball approach that produces exact toroidal surfaces only on simple edges (cylinder meets plane). On complex edges like sphere-plane intersections, it generates dense BSpline surface approximations.

**Impact**: A 77 KB reference STEP (Onshape, all analytic surfaces) became 3.8 MB with 14 BSpline faces when filleted by OCCT. These BSpline faces also caused rendering artifacts (transparent/missing faces) in some STEP viewers.

**Workaround**: Fillet simple edges with the OCCT API (pip cylinder edges → torus surfaces). For sphere-plane edges, accept the BSpline or use explicit torus subtract (mathematically correct but subtle at shallow angles).

## 2. Boolean operations return unpredictable types

`build123d` boolean operations (`fuse`, `cut`, `-`) can return `Solid`, `Compound`, or `ShapeList` depending on the input geometry. Multi-arg `fuse(a, b, c)` always returns `Compound`.

**Fix**: Always extract the result with a helper:
```python
def _extract_solid(shape):
    if hasattr(shape, "solids") and shape.solids():
        return max(shape.solids(), key=lambda s: s.volume)
    return shape
```

Use sequential `.fuse(a).fuse(b)` instead of multi-arg fuse.

## 3. Build order matters enormously for fillets

Filleting the complete fused solid vs filleting sub-assemblies first produces very different results:

- **Fillet-then-fuse**: Fillet on simple geometry (clean edges, predictable surfaces), but fusing afterwards can create new sharp edges at junctions.
- **Fuse-then-fillet**: All edges exist, but complex topology causes OCCT to produce BSpline or fail entirely.
- **Best approach**: Fillet each piece on its simplest geometry, then fuse. Apply remaining fillets (bore-plane, etc.) on the fused solid.

## 4. Edge selection is fragile and geometry-dependent

Finding the "right" edges to fillet requires geometric heuristics (distance from sphere surface, distance from plane, radial distance from axis). These break easily when:

- Edges move after boolean operations
- The edge center doesn't reflect the edge's geometric identity (large arcs have centers far from the interesting part)
- Topology changes between build steps

**Lesson**: Use multiple geometric criteria (on-sphere AND on-plane) rather than a single filter. Test edge selection by printing what was found before applying fillets.

## 5. Revolve profiles eliminate fuse operations and embed fillets

Drawing a 2D profile and revolving it replaces multiple primitive-creation + fuse steps. Fillets that would need the OCCT API can instead be drawn as arcs directly in the profile.

**Example**: The stalk + pip (2 cylinders + 2 fillet operations) becomes one revolve with fillet arcs in the profile — zero boolean operations, zero OCCT fillet calls, exact toroidal surfaces.

**Limitation**: Only works for axially symmetric features. The bore (Y-axis cylinder) and tilted plane cuts break Z-axis symmetry, so the ring cannot be a pure revolve.

## 6. STEP export format matters for viewer compatibility

- **AP214 with `STEPControl_AsIs`**: Some viewers show empty geometry.
- **AP203 with `STEPControl_ManifoldSolidBrep`**: Most widely compatible.
- **`ShapeFix_Shape`** before export catches minor geometry issues.
- **`build123d.export_step()`** can wrap solids in `TopoDS_Compound`; direct `STEPControl_Writer` gives more control.

## 7. Convex vs concave fillets need different boolean operations

When building fillets as explicit torus geometry:
- **Convex edge** (exterior corner): **subtract** the torus to round it off
- **Concave edge** (interior corner): **fuse** the torus to fill it

A full torus subtract can split a solid into multiple pieces. Use `max(solids, key=volume)` to keep the main body.

## 8. Reference STEP files are invaluable for validation

The Onshape-generated `peghead7mm.step` provided:
- Exact surface types and parameters (5 toroidal, 14 BSpline, etc.)
- Reference volume (375.64 mm³) and surface area (568.40 mm²)
- Torus major/minor radii for fillet geometry validation
- A baseline STEP file size (77 KB) to compare against

Parsing the reference with `GeomAdaptor_Surface` to extract face types and parameters was essential for understanding what "correct" output looks like.

## 9. The angle at an edge determines fillet visibility

A 0.5 mm fillet on a 160° dihedral angle (shallow sphere-plane intersection) is barely visible. The same radius on a 90° edge (pip cylinder meets flat face) is prominent. When fillets appear missing, check the dihedral angle before debugging the code.

## 10. Don't fight the kernel — work with its strengths

OCCT excels at:
- Filleting simple edges (cylinder-plane, cylinder-cylinder)
- Boolean operations on primitives
- Revolve/extrude of 2D profiles

OCCT struggles with:
- Filleting complex intersection edges (sphere-plane → BSpline bloat)
- Maintaining clean topology through many sequential booleans

Design the build pipeline to play to these strengths: use revolve profiles where possible, fillet simple geometry early, accept BSpline where unavoidable.
