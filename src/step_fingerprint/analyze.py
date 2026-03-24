"""Low-level STEP geometry analysis using OCCT via build123d.

All functions operate on build123d Part objects and return plain Python
data structures (dicts, lists, tuples) — no OCCT types leak out.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from build123d import Axis, Part, Plane, Compound, import_step
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import (
    GeomAbs_BSplineSurface,
    GeomAbs_Cone,
    GeomAbs_Cylinder,
    GeomAbs_Plane,
    GeomAbs_Sphere,
    GeomAbs_Torus,
)
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Dir, gp_Lin, gp_Pln, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
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
            except Exception:
                continue

        cu = total_cu / total_area if total_area > 1e-9 else 0.0
        cv = total_cv / total_area if total_area > 1e-9 else 0.0

        slices.append({
            "position": round(pos, 4),
            "area": round(total_area, 4),
            f"centroid_{uv[0].lower()}": round(cu, 4),
            f"centroid_{uv[1].lower()}": round(cv, 4),
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

    result = {
        "file": str(path),
        "bounding_box": bounding_box(shape),
        "volume_and_area": volume_and_area(shape),
        "moments_of_inertia": moments_of_inertia(shape),
        "topology": topology_counts(shape),
        "face_inventory": face_inventory(shape),
        "cross_sections": cross_section_areas(
            shape, axis=axis, num_slices=num_cross_sections,
        ),
        "radial_profile": radial_profile(
            shape, axis=axis, num_slices=num_radial_slices,
            num_angles=num_angles,
        ),
    }

    return result
