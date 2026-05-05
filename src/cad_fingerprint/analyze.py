"""Low-level STEP geometry analysis using OCCT via build123d.

All functions operate on build123d Part objects and return plain Python
data structures (dicts, lists, tuples) — no OCCT types leak out.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from build123d import Axis, Part, Plane, Compound, import_step, import_stl
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.BRepGProp import BRepGProp
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.GeomAbs import (
    GeomAbs_BSplineCurve,
    GeomAbs_BSplineSurface,
    GeomAbs_Circle,
    GeomAbs_Cone,
    GeomAbs_Cylinder,
    GeomAbs_Ellipse,
    GeomAbs_Line,
    GeomAbs_Plane,
    GeomAbs_Sphere,
    GeomAbs_Torus,
)
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Dir, gp_Lin, gp_Pln, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopTools import TopTools_HSequenceOfShape
from OCP.TopoDS import TopoDS

_SURFACE_NAMES = {
    GeomAbs_Plane: "Plane",
    GeomAbs_Cylinder: "Cylinder",
    GeomAbs_Cone: "Cone",
    GeomAbs_Sphere: "Sphere",
    GeomAbs_Torus: "Torus",
    GeomAbs_BSplineSurface: "BSpline",
}


# ── helpers ──────────────────────────────────────────────────────────


def load_stl(path: str):
    """Import an STL file and return a build123d Face (triangulated mesh)."""
    return import_stl(str(path))


def load_step(path: str) -> Part:
    """Import a STEP file and return a single fused Part."""
    imported = import_step(path)
    if hasattr(imported, "__iter__") and not isinstance(imported, (Part, Compound)):
        shapes = list(imported)
        shape = shapes[0]
        for s in shapes[1:]:
            shape = shape + s
        return Part(shape.wrapped) if not isinstance(shape, Part) else shape
    return imported if isinstance(imported, Part) else Part(imported.wrapped)


# ── global properties ────────────────────────────────────────────────


def bounding_box(shape: Part) -> dict:
    """Return bounding box as dict with min/max per axis and dimensions."""
    bb = shape.bounding_box()
    return {
        "min": (bb.min.X, bb.min.Y, bb.min.Z),
        "max": (bb.max.X, bb.max.Y, bb.max.Z),
        "size": (bb.max.X - bb.min.X, bb.max.Y - bb.min.Y, bb.max.Z - bb.min.Z),
    }


def volume_and_area(shape: Part) -> dict:
    """Return volume (mm³) and surface area (mm²)."""
    vol_props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, vol_props)
    surf_props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape.wrapped, surf_props)
    return {
        "volume": vol_props.Mass(),
        "surface_area": surf_props.Mass(),
        "center_of_mass": (
            vol_props.CentreOfMass().X(),
            vol_props.CentreOfMass().Y(),
            vol_props.CentreOfMass().Z(),
        ),
    }


def moments_of_inertia(shape: Part) -> dict:
    """Return principal moments of inertia about the center of mass.

    The inertia tensor is very sensitive to mass distribution — if two
    shapes have matching Ixx, Iyy, Izz they are almost certainly the
    same geometry.
    """
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, props)
    mat = props.MatrixOfInertia()
    return {
        "Ixx": mat.Value(1, 1),
        "Iyy": mat.Value(2, 2),
        "Izz": mat.Value(3, 3),
        "Ixy": mat.Value(1, 2),
        "Ixz": mat.Value(1, 3),
        "Iyz": mat.Value(2, 3),
    }


def topology_counts(shape: Part) -> dict:
    """Count faces, edges, vertices."""
    counts = {}
    for name, topo_type in [
        ("faces", TopAbs_FACE),
        ("edges", TopAbs_EDGE),
        ("vertices", TopAbs_VERTEX),
    ]:
        explorer = TopExp_Explorer(shape.wrapped, topo_type)
        n = 0
        while explorer.More():
            n += 1
            explorer.Next()
        counts[name] = n
    return counts


# ── face inventory ───────────────────────────────────────────────────


def face_inventory(shape: Part) -> list[dict]:
    """Classify every face: type, area, and type-specific parameters.

    Cylinders get diameter + axis, tori get major/minor radii, etc.
    """
    explorer = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    faces = []
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        adaptor = BRepAdaptor_Surface(face)
        stype = adaptor.GetType()
        type_name = _SURFACE_NAMES.get(stype, f"Other({stype})")

        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        area = props.Mass()
        com = props.CentreOfMass()

        info = {
            "type": type_name,
            "area": round(area, 4),
            "com": (round(com.X(), 4), round(com.Y(), 4), round(com.Z(), 4)),
        }

        if stype == GeomAbs_Cylinder:
            cyl = adaptor.Cylinder()
            info["diameter"] = round(cyl.Radius() * 2, 4)
            d = cyl.Axis().Direction()
            info["axis"] = (round(d.X(), 3), round(d.Y(), 3), round(d.Z(), 3))

        elif stype == GeomAbs_Cone:
            cone = adaptor.Cone()
            info["semi_angle_deg"] = round(math.degrees(cone.SemiAngle()), 2)

        elif stype == GeomAbs_Sphere:
            sph = adaptor.Sphere()
            info["radius"] = round(sph.Radius(), 4)

        elif stype == GeomAbs_Torus:
            t = adaptor.Torus()
            info["major_r"] = round(t.MajorRadius(), 4)
            info["minor_r"] = round(t.MinorRadius(), 4)

        faces.append(info)
        explorer.Next()

    # Sort for stable ordering
    faces.sort(key=lambda f: (f["type"], -f["area"]))
    return faces


# ── edge inventory ────────────────────────────────────────────────────

_CURVE_NAMES = {
    GeomAbs_Line: "Line",
    GeomAbs_Circle: "Circle",
    GeomAbs_Ellipse: "Ellipse",
    GeomAbs_BSplineCurve: "BSpline",
}


def edge_inventory(shape: Part) -> list[dict]:
    """Classify every edge in the shape by curve type and extract parameters.

    Returns a sorted list of dicts, each with:
      - type: "Line", "Circle", "Ellipse", "BSpline", or "Other(N)"
      - length: edge length in mm
      - radius: (Circle only) circle radius in mm

    Sorted by type name, then descending length (matching face_inventory).
    """
    explorer = TopExp_Explorer(shape.wrapped, TopAbs_EDGE)
    edges = []
    while explorer.More():
        edge = TopoDS.Edge_s(explorer.Current())
        adaptor = BRepAdaptor_Curve(edge)
        ctype = adaptor.GetType()
        type_name = _CURVE_NAMES.get(ctype, f"Other({int(ctype)})")
        length = GCPnts_AbscissaPoint.Length_s(adaptor)
        info = {"type": type_name, "length": round(length, 4)}
        if ctype == GeomAbs_Circle:
            info["radius"] = round(adaptor.Circle().Radius(), 4)
        elif ctype == GeomAbs_Ellipse:
            info["major_r"] = round(adaptor.Ellipse().MajorRadius(), 4)
            info["minor_r"] = round(adaptor.Ellipse().MinorRadius(), 4)
        edges.append(info)
        explorer.Next()
    edges.sort(key=lambda e: (e["type"], -e["length"]))
    return edges


# ── cross-sections ───────────────────────────────────────────────────


def cross_section_areas(
    shape: Part,
    axis: str = "Z",
    num_slices: int = 20,
    margin: float = 0.01,
) -> list[dict]:
    """Slice the shape at evenly-spaced planes along an axis.

    Returns list of {position, area, centroid_u, centroid_v} where u,v
    are the two axes perpendicular to the slicing axis.

    Args:
        shape: Part to slice.
        axis: "X", "Y", or "Z".
        num_slices: Number of evenly-spaced slices.
        margin: Fraction of range to inset from exact min/max to avoid
                slicing exactly on a face boundary.
    """
    bb = shape.bounding_box()
    axis = axis.upper()
    if axis == "X":
        lo, hi = bb.min.X, bb.max.X
        make_plane = lambda v: gp_Pln(gp_Pnt(v, 0, 0), gp_Dir(1, 0, 0))
        uv = ("Y", "Z")
        get_uv = lambda p: (p.Y(), p.Z())
    elif axis == "Y":
        lo, hi = bb.min.Y, bb.max.Y
        make_plane = lambda v: gp_Pln(gp_Pnt(0, v, 0), gp_Dir(0, 1, 0))
        uv = ("X", "Z")
        get_uv = lambda p: (p.X(), p.Z())
    else:
        lo, hi = bb.min.Z, bb.max.Z
        make_plane = lambda v: gp_Pln(gp_Pnt(0, 0, v), gp_Dir(0, 0, 1))
        uv = ("X", "Y")
        get_uv = lambda p: (p.X(), p.Y())

    span = hi - lo
    inset = span * margin
    lo += inset
    hi -= inset

    if num_slices < 2:
        num_slices = 2
    step = (hi - lo) / (num_slices - 1)

    slices = []
    for i in range(num_slices):
        pos = lo + i * step
        plane = make_plane(pos)

        section = BRepAlgoAPI_Section(shape.wrapped, plane, False)
        section.ComputePCurveOn1(True)
        section.Approximation(True)
        section.Build()

        if not section.IsDone():
            slices.append({"position": round(pos, 4), "area": 0.0,
                           f"centroid_{uv[0].lower()}": 0.0,
                           f"centroid_{uv[1].lower()}": 0.0})
            continue

        # Section produces edges (wires). Compute total wire length and
        # centroid from the line properties.
        result_shape = section.Shape()
        props = GProp_GProps()
        BRepGProp.LinearProperties_s(result_shape, props)

        # Wire length (perimeter of the cross-section)
        perimeter = props.Mass()

        # For area, we need to build faces from the section wires.
        # Use BRepBuilderAPI_MakeFace to fill the wires.
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
        from OCP.TopTools import TopTools_HSequenceOfShape
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire

        # Collect edges into wires
        edges_seq = TopTools_HSequenceOfShape()
        wires_seq = TopTools_HSequenceOfShape()
        edge_exp = TopExp_Explorer(result_shape, TopAbs_EDGE)
        while edge_exp.More():
            edges_seq.Append(edge_exp.Current())
            edge_exp.Next()

        if edges_seq.Length() == 0:
            slices.append({"position": round(pos, 4), "area": 0.0,
                           f"centroid_{uv[0].lower()}": 0.0,
                           f"centroid_{uv[1].lower()}": 0.0})
            continue

        # Connect edges into wires
        ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(
            edges_seq, 1e-4, False, wires_seq
        )

        total_area = 0.0
        total_cu = 0.0
        total_cv = 0.0
        total_Iuu = 0.0
        total_Ivv = 0.0

        # Indices into the 3x3 inertia matrix for the in-plane axes
        # (1-indexed for gp_Mat): X=1, Y=2, Z=3
        _axis_idx = {"X": 1, "Y": 2, "Z": 3}
        u_idx = _axis_idx[uv[0]]
        v_idx = _axis_idx[uv[1]]

        for w_idx in range(1, wires_seq.Length() + 1):
            wire = TopoDS.Wire_s(wires_seq.Value(w_idx))
            try:
                face_maker = BRepBuilderAPI_MakeFace(plane, wire, True)
                if face_maker.IsDone():
                    face_shape = face_maker.Face()
                    face_props = GProp_GProps()
                    BRepGProp.SurfaceProperties_s(face_shape, face_props)
                    a = abs(face_props.Mass())
                    com = face_props.CentreOfMass()
                    u, v = get_uv(com)
                    total_area += a
                    total_cu += u * a
                    total_cv += v * a
                    # 2D shape moments (about origin — summing is correct)
                    mat = face_props.MatrixOfInertia()
                    total_Iuu += mat.Value(u_idx, u_idx)
                    total_Ivv += mat.Value(v_idx, v_idx)
            except Exception:
                continue

        cu = total_cu / total_area if total_area > 1e-9 else 0.0
        cv = total_cv / total_area if total_area > 1e-9 else 0.0

        slices.append({
            "position": round(pos, 4),
            "area": round(total_area, 4),
            f"centroid_{uv[0].lower()}": round(cu, 4),
            f"centroid_{uv[1].lower()}": round(cv, 4),
            f"I{uv[0].lower()}{uv[0].lower()}_2d": round(total_Iuu, 4),
            f"I{uv[1].lower()}{uv[1].lower()}_2d": round(total_Ivv, 4),
        })

    return slices


# ── radial profile ───────────────────────────────────────────────────


def radial_profile(
    shape: Part,
    axis: str = "Z",
    num_slices: int = 15,
    num_angles: int = 12,
    margin: float = 0.01,
) -> list[dict]:
    """Sample the outer radius at multiple Z positions and angles.

    At each slice, casts rays from the axis outward at each angle and
    measures the distance to the first intersection with the shape.

    Returns list of {position, angles: {deg: radius, ...}}.

    This creates a dense fingerprint that catches profile errors even
    when total area matches (e.g. material in the wrong angular position).
    """
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector

    bb = shape.bounding_box()
    axis = axis.upper()

    if axis == "X":
        lo, hi = bb.min.X, bb.max.X
        max_r = max(bb.max.Y - bb.min.Y, bb.max.Z - bb.min.Z)
        def make_ray_origin(pos, angle):
            return gp_Pnt(pos, 0, 0)
        def make_ray_dir(angle):
            return gp_Dir(0, math.cos(angle), math.sin(angle))
    elif axis == "Y":
        lo, hi = bb.min.Y, bb.max.Y
        max_r = max(bb.max.X - bb.min.X, bb.max.Z - bb.min.Z)
        def make_ray_origin(pos, angle):
            return gp_Pnt(0, pos, 0)
        def make_ray_dir(angle):
            return gp_Dir(math.cos(angle), 0, math.sin(angle))
    else:  # Z
        lo, hi = bb.min.Z, bb.max.Z
        max_r = max(bb.max.X - bb.min.X, bb.max.Y - bb.min.Y)
        def make_ray_origin(pos, angle):
            return gp_Pnt(0, 0, pos)
        def make_ray_dir(angle):
            return gp_Dir(math.cos(angle), math.sin(angle), 0)

    span = hi - lo
    inset = span * margin
    lo += inset
    hi -= inset

    if num_slices < 2:
        num_slices = 2
    step = (hi - lo) / (num_slices - 1)
    max_r = max_r / 2 + 1.0  # search radius

    profiles = []
    for i in range(num_slices):
        pos = lo + i * step
        angle_data = {}

        for j in range(num_angles):
            angle_deg = j * (360.0 / num_angles)
            angle_rad = math.radians(angle_deg)

            origin = make_ray_origin(pos, angle_rad)
            direction = make_ray_dir(angle_rad)

            line = gp_Lin(origin, direction)
            intersector = IntCurvesFace_ShapeIntersector()
            intersector.Load(shape.wrapped, 1e-6)
            intersector.PerformNearest(line, 0.0, max_r)

            if intersector.NbPnt() > 0:
                pt = intersector.Pnt(1)
                dx = pt.X() - origin.X()
                dy = pt.Y() - origin.Y()
                dz = pt.Z() - origin.Z()
                dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                angle_data[angle_deg] = round(dist, 4)
            else:
                angle_data[angle_deg] = None

        profiles.append({
            "position": round(pos, 4),
            "radii": angle_data,
        })

    return profiles


# ── build quality ────────────────────────────────────────────────────


def build_quality(shape: Part, step_path: str | None = None) -> dict:
    """Analyze build quality metrics for the shape.

    Returns solid count, free edge count, OCCT validity, and optionally
    the STEP file size. These metrics help catch common CAD build errors:
    - Multiple solids from failed booleans
    - Free edges from open shells
    - Invalid geometry from degenerate operations
    - BSpline bloat inflating STEP file size
    """
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopAbs import TopAbs_SOLID

    # Count solids
    solid_count = 0
    exp = TopExp_Explorer(shape.wrapped, TopAbs_SOLID)
    while exp.More():
        solid_count += 1
        exp.Next()

    # Count free edges (edges belonging to only one face = open shell)
    free_edges = TopTools_HSequenceOfShape()
    closed_wires = TopTools_HSequenceOfShape()
    ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(
        _collect_free_edges(shape), 1e-4, False, free_edges
    )
    free_edge_count = free_edges.Length()

    # OCCT validity check
    analyzer = BRepCheck_Analyzer(shape.wrapped)
    is_valid = analyzer.IsValid()

    result = {
        "solid_count": solid_count,
        "free_edge_count": free_edge_count,
        "is_valid": is_valid,
    }

    # STEP file size (if path provided)
    if step_path:
        import os
        try:
            result["step_file_bytes"] = os.path.getsize(step_path)
        except OSError:
            pass

    return result


def _collect_free_edges(shape: Part):
    """Collect free boundary edges using ShapeAnalysis_FreeBounds."""
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopTools import TopTools_HSequenceOfShape

    fb = ShapeAnalysis_FreeBounds(shape.wrapped)
    closed_wires = fb.GetClosedWires()
    open_wires = fb.GetOpenWires()

    edges = TopTools_HSequenceOfShape()
    for wires in [open_wires]:
        exp = TopExp_Explorer(wires, TopAbs_EDGE)
        while exp.More():
            edges.Append(exp.Current())
            exp.Next()
    return edges


# ── part description ─────────────────────────────────────────────────


def describe_part(
    bb: dict,
    va: dict,
    topo: dict,
    faces: list[dict],
    cross_sections: list[dict],
    axis: str = "Z",
) -> dict:
    """Auto-generate a structural description of the part from fingerprint data.

    Returns a dict with:
    - overall_size: bounding box dimensions
    - cylinder_features: list of cylinder diameters found
    - fillet_features: list of torus (fillet) radii found
    - sphere_features: list of sphere radii
    - bspline_count: number of complex BSpline faces
    - symmetry: whether the part appears symmetric
    - transitions: Z positions where cross-section area changes significantly
    """
    # Cylinder features (sorted by area, largest first)
    cylinders = sorted(
        [f for f in faces if f["type"] == "Cylinder"],
        key=lambda f: -f["area"],
    )
    cylinder_features = []
    seen_diams = set()
    for c in cylinders:
        d = round(c["diameter"], 2)
        if d not in seen_diams:
            cylinder_features.append({
                "diameter": d,
                "area": round(c["area"], 2),
            })
            seen_diams.add(d)

    # Torus features (fillets)
    tori = sorted(
        [f for f in faces if f["type"] == "Torus"],
        key=lambda f: -f["area"],
    )
    fillet_features = []
    seen_fillets = set()
    for t in tori:
        key = (round(t["major_r"], 2), round(t["minor_r"], 2))
        if key not in seen_fillets:
            fillet_features.append({
                "major_r": key[0],
                "minor_r": key[1],
                "area": round(t["area"], 2),
            })
            seen_fillets.add(key)

    # Sphere features
    spheres = [f for f in faces if f["type"] == "Sphere"]
    sphere_features = [{"radius": round(s["radius"], 2), "area": round(s["area"], 2)}
                       for s in spheres]

    # BSpline count
    bspline_count = sum(1 for f in faces if f["type"] == "BSpline")

    # Detect significant cross-section transitions
    transitions = []
    for i in range(1, len(cross_sections)):
        prev = cross_sections[i - 1]["area"]
        curr = cross_sections[i]["area"]
        if prev > 0.01 and curr > 0.01:
            ratio = max(curr / prev, prev / curr)
            if ratio > 1.5:
                transitions.append({
                    "position": cross_sections[i]["position"],
                    "from_area": round(prev, 2),
                    "to_area": round(curr, 2),
                })

    return {
        "overall_size": bb["size"],
        "volume": round(va["volume"], 2),
        "surface_area": round(va["surface_area"], 2),
        "face_count": topo["faces"],
        "cylinder_features": cylinder_features,
        "fillet_features": fillet_features,
        "sphere_features": sphere_features,
        "bspline_count": bspline_count,
        "transitions": transitions,
    }


# ── STL / mesh analysis ──────────────────────────────────────────────


def _compute_mesh_props(triangles: list) -> tuple[dict, dict]:
    """Core mesh math: volume, area, CoM, inertia from a triangle list.

    triangles: list of ((x1,y1,z1), (x2,y2,z2), (x3,y3,z3))

    Uses signed tetrahedral decomposition (Mirtich 1996). Exact for any
    closed, consistently-wound triangulated surface.

    Returns (volume_and_area dict, moments_of_inertia dict).
    Pure Python — no OCC dependency. Testable without build123d.
    """
    vol = 0.0
    area = 0.0
    cx = cy = cz = 0.0
    Ixx = Iyy = Izz = Ixy = Ixz = Iyz = 0.0

    for (p1, p2, p3) in triangles:
        x1, y1, z1 = p1
        x2, y2, z2 = p2
        x3, y3, z3 = p3

        ax, ay, az = x2 - x1, y2 - y1, z2 - z1
        bx, by, bz = x3 - x1, y3 - y1, z3 - z1
        area += 0.5 * math.sqrt(
            (ay * bz - az * by) ** 2 + (az * bx - ax * bz) ** 2 + (ax * by - ay * bx) ** 2
        )

        det = (x1 * (y2 * z3 - y3 * z2) +
               x2 * (y3 * z1 - y1 * z3) +
               x3 * (y1 * z2 - y2 * z1))
        v = det / 6.0
        vol += v
        cx += v * (x1 + x2 + x3) / 4.0
        cy += v * (y1 + y2 + y3) / 4.0
        cz += v * (z1 + z2 + z3) / 4.0

        # Inertia about origin — Mirtich 1996 / polyhedral mass properties
        Ixx += (det / 60.0) * (
            y1*y1 + y2*y2 + y3*y3 + y1*y2 + y1*y3 + y2*y3 +
            z1*z1 + z2*z2 + z3*z3 + z1*z2 + z1*z3 + z2*z3
        )
        Iyy += (det / 60.0) * (
            x1*x1 + x2*x2 + x3*x3 + x1*x2 + x1*x3 + x2*x3 +
            z1*z1 + z2*z2 + z3*z3 + z1*z2 + z1*z3 + z2*z3
        )
        Izz += (det / 60.0) * (
            x1*x1 + x2*x2 + x3*x3 + x1*x2 + x1*x3 + x2*x3 +
            y1*y1 + y2*y2 + y3*y3 + y1*y2 + y1*y3 + y2*y3
        )
        Ixy -= (det / 120.0) * (
            2*x1*y1 + 2*x2*y2 + 2*x3*y3 +
            x1*y2 + x2*y1 + x1*y3 + x3*y1 + x2*y3 + x3*y2
        )
        Ixz -= (det / 120.0) * (
            2*x1*z1 + 2*x2*z2 + 2*x3*z3 +
            x1*z2 + x2*z1 + x1*z3 + x3*z1 + x2*z3 + x3*z2
        )
        Iyz -= (det / 120.0) * (
            2*y1*z1 + 2*y2*z2 + 2*y3*z3 +
            y1*z2 + y2*z1 + y1*z3 + y3*z1 + y2*z3 + y3*z2
        )

    vol = abs(vol)
    if vol > 1e-12:
        cx /= vol
        cy /= vol
        cz /= vol
    com = (cx, cy, cz)

    # Shift inertia from origin to CoM via parallel axis theorem.
    # OCCT convention: off-diagonal element = -product_of_inertia.
    Ixx_c = Ixx - vol * (cy * cy + cz * cz)
    Iyy_c = Iyy - vol * (cx * cx + cz * cz)
    Izz_c = Izz - vol * (cx * cx + cy * cy)
    Ixy_c = Ixy + vol * cx * cy
    Ixz_c = Ixz + vol * cx * cz
    Iyz_c = Iyz + vol * cy * cz

    va = {"volume": vol, "surface_area": area, "center_of_mass": com}
    moi = {"Ixx": Ixx_c, "Iyy": Iyy_c, "Izz": Izz_c,
           "Ixy": Ixy_c, "Ixz": Ixz_c, "Iyz": Iyz_c}
    return va, moi


def _mesh_properties(stl_face) -> tuple[dict, dict]:
    """Extract Poly_Triangulation from an STL face and compute properties."""
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(stl_face.wrapped, loc)
    if tri is None:
        raise ValueError("STL face contains no triangulation")

    nodes = tri.Nodes()
    triangles = []
    for i in range(1, tri.NbTriangles() + 1):
        t = tri.Triangle(i)
        n1, n2, n3 = t.Get()
        p1, p2, p3 = nodes.Value(n1), nodes.Value(n2), nodes.Value(n3)
        triangles.append((
            (p1.X(), p1.Y(), p1.Z()),
            (p2.X(), p2.Y(), p2.Z()),
            (p3.X(), p3.Y(), p3.Z()),
        ))
    return _compute_mesh_props(triangles)


def _segments_to_area(segments: list) -> tuple[float, float, float]:
    """Assemble 2D line segments into polygons; return (area, cx, cy).

    Uses greedy chain-following then the shoelace formula.
    """
    if not segments:
        return 0.0, 0.0, 0.0

    EPS2 = 1e-6

    def dist2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    used = [False] * len(segments)
    polygons = []

    for start in range(len(segments)):
        if used[start]:
            continue
        chain = list(segments[start])
        used[start] = True
        for _ in range(len(segments)):
            tail = chain[-1]
            found = False
            for j in range(len(segments)):
                if used[j]:
                    continue
                s = segments[j]
                if dist2(s[0], tail) < EPS2:
                    chain.append(s[1])
                    used[j] = True
                    found = True
                    break
                if dist2(s[1], tail) < EPS2:
                    chain.append(s[0])
                    used[j] = True
                    found = True
                    break
            if not found or dist2(chain[-1], chain[0]) < EPS2:
                break
        if len(chain) >= 3:
            polygons.append(chain)

    total_area = 0.0
    total_cx = 0.0
    total_cy = 0.0
    for poly in polygons:
        a = 0.0
        pcx = 0.0
        pcy = 0.0
        n = len(poly)
        for k in range(n):
            x0, y0 = poly[k]
            x1, y1 = poly[(k + 1) % n]
            cross = x0 * y1 - x1 * y0
            a += cross
            pcx += (x0 + x1) * cross
            pcy += (y0 + y1) * cross
        signed_area = a / 2.0
        abs_area = abs(signed_area)
        if abs_area > 1e-10:
            total_area += abs_area
            total_cx += (pcx / (6.0 * signed_area)) * abs_area
            total_cy += (pcy / (6.0 * signed_area)) * abs_area

    if total_area < 1e-10:
        return 0.0, 0.0, 0.0
    return total_area, total_cx / total_area, total_cy / total_area


def cross_section_areas_mesh(
    stl_face,
    axis: str = "Z",
    num_slices: int = 20,
    margin: float = 0.01,
) -> list[dict]:
    """Cross-sections for an STL mesh via triangle-plane intersection.

    Replaces the BRepAlgoAPI_Section approach (which requires analytical
    B-Rep surfaces) with direct triangle clipping against the cut plane.
    """
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(stl_face.wrapped, loc)
    if tri is None:
        return []

    nodes = tri.Nodes()
    axis = axis.upper()
    if axis == "X":
        ai, uv = 0, ("y", "z")
        proj = lambda p: (p[1], p[2])
    elif axis == "Y":
        ai, uv = 1, ("x", "z")
        proj = lambda p: (p[0], p[2])
    else:
        ai, uv = 2, ("x", "y")
        proj = lambda p: (p[0], p[1])

    pts = []
    for i in range(1, tri.NbNodes() + 1):
        n = nodes.Value(i)
        pts.append((n.X(), n.Y(), n.Z()))

    axis_vals = [p[ai] for p in pts]
    lo, hi = min(axis_vals), max(axis_vals)
    span = hi - lo
    lo += span * margin
    hi -= span * margin
    if num_slices < 2:
        num_slices = 2
    step = (hi - lo) / (num_slices - 1)

    triangles = []
    for i in range(1, tri.NbTriangles() + 1):
        t = tri.Triangle(i)
        n1, n2, n3 = t.Get()
        triangles.append((pts[n1 - 1], pts[n2 - 1], pts[n3 - 1]))

    slices = []
    for i in range(num_slices):
        pos = lo + i * step
        segments = []
        for (p1, p2, p3) in triangles:
            v1, v2, v3 = p1[ai] - pos, p2[ai] - pos, p3[ai] - pos
            edge_pts = []
            for (a, va), (b, vb) in (
                ((p1, v1), (p2, v2)),
                ((p2, v2), (p3, v3)),
                ((p3, v3), (p1, v1)),
            ):
                if va * vb < 0:
                    t_ = va / (va - vb)
                    interp = tuple(a[k] + t_ * (b[k] - a[k]) for k in range(3))
                    edge_pts.append(proj(interp))
            if len(edge_pts) == 2:
                segments.append((edge_pts[0], edge_pts[1]))

        area, cu, cv = _segments_to_area(segments)
        slices.append({
            "position": round(pos, 4),
            "area": round(area, 4),
            f"centroid_{uv[0]}": round(cu, 4),
            f"centroid_{uv[1]}": round(cv, 4),
        })
    return slices


def build_quality_stl(stl_face, stl_path: str | None = None) -> dict:
    """Build quality metrics for an STL mesh."""
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(stl_face.wrapped, loc)
    result = {
        "solid_count": 1,
        "free_edge_count": 0,
        "is_valid": tri is not None,
        "triangle_count": tri.NbTriangles() if tri else 0,
    }
    if stl_path:
        import os
        try:
            result["stl_file_bytes"] = os.path.getsize(stl_path)
        except OSError:
            pass
    return result


def analyze_stl(
    path: str,
    axis: str = "Z",
    num_cross_sections: int = 20,
    num_radial_slices: int = 15,
    num_angles: int = 12,
) -> dict:
    """Run full geometric analysis on an STL file.

    Face inventory is replaced by mesh-level stats (no surface type
    classification without detect_primitives, which is not yet released).
    Cross-sections use triangle-plane intersection instead of BRepAlgoAPI_Section.
    All other metrics are equivalent to analyze_step.
    """
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    stl_face = load_stl(path)

    bb = bounding_box(stl_face)
    va, moi = _mesh_properties(stl_face)

    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(stl_face.wrapped, loc)
    topo = {
        "faces": tri.NbTriangles() if tri else 0,
        "edges": 0,
        "vertices": tri.NbNodes() if tri else 0,
    }
    faces = [{"type": "mesh", "triangle_count": tri.NbTriangles() if tri else 0,
              "area": round(va["surface_area"], 4)}]

    xs = cross_section_areas_mesh(stl_face, axis=axis, num_slices=num_cross_sections)
    rp = radial_profile(stl_face, axis=axis, num_slices=num_radial_slices, num_angles=num_angles)
    bq = build_quality_stl(stl_face, stl_path=path)
    desc = describe_part(bb, va, topo, faces, xs, axis=axis)

    return {
        "file": str(path),
        "source_format": "stl",
        "bounding_box": bb,
        "volume_and_area": va,
        "moments_of_inertia": moi,
        "topology": topo,
        "face_inventory": faces,
        "cross_sections": xs,
        "radial_profile": rp,
        "build_quality": bq,
        "description": desc,
    }


# ── full analysis ────────────────────────────────────────────────────


def analyze_step(
    path: str,
    axis: str = "Z",
    num_cross_sections: int = 20,
    num_radial_slices: int = 15,
    num_angles: int = 12,
) -> dict:
    """Run full geometric analysis on a STEP file.

    Returns a dict with all fingerprint data that can be used to generate
    test assertions.
    """
    shape = load_step(path)

    bb = bounding_box(shape)
    va = volume_and_area(shape)
    topo = topology_counts(shape)
    faces = face_inventory(shape)
    edges = edge_inventory(shape)
    xs = cross_section_areas(shape, axis=axis, num_slices=num_cross_sections)

    result = {
        "file": str(path),
        "source_format": "step",
        "bounding_box": bb,
        "volume_and_area": va,
        "moments_of_inertia": moments_of_inertia(shape),
        "topology": topo,
        "face_inventory": faces,
        "edge_inventory": edges,
        "cross_sections": xs,
        "radial_profile": radial_profile(
            shape, axis=axis, num_slices=num_radial_slices,
            num_angles=num_angles,
        ),
        "build_quality": build_quality(shape, step_path=path),
        "description": describe_part(bb, va, topo, faces, xs, axis=axis),
    }

    return result
