"""Simplified peghead build using revolve profiles where possible.

Improvements over the procedural version:
- Upper body (shaft + shoulder + dome + boss) built as one revolve
  instead of 4 separate primitives + fuses
- Stalk + pip built as one revolve with pip fillets drawn directly
  into the 2D profile (no OCCT fillet API for pip edges)
- Ring still uses sphere → split → bore → fillet (OCCT always
  produces BSpline for sphere-plane fillets regardless of approach)
"""

import math
import build123d as bd


def create_peghead_simple():
    """Build the guitar tuning peg head."""

    # ═══════════════════════════════════════════════════════════
    # Dimensions
    # ═══════════════════════════════════════════════════════════

    sphere_r = 6.25
    sphere_cz = -11.45
    bore_r = 4.9
    bore_cz = -11.7

    plane_slope = 0.0355
    plane_intercept = 1.829

    shaft_r = 1.9
    shaft_height = 10.4
    shoulder_r = 3.5
    shoulder_height = 1.2

    torus_major_r = 2.5179
    torus_minor_r = 2.0
    torus_cz = -0.2
    torus_arc_start_angle = 30
    torus_arc_end_angle = 60

    conn_r = 1.78
    conn_flare_r = 2.95
    conn_flare_z = -4.5
    conn_overlap = 0.1
    conn_ring_penetration = 1.0

    pip_r = 1.05
    pip_height = 1.2
    pip_bot_z = -19.026
    stalk_r = 0.5
    stalk_ring_penetration = 0.5

    ring_outer_fillet_r = 0.5
    pip_fillet_r = 0.3
    boss_r = 0.2985
    boss_h = 0.005

    # ═══════════════════════════════════════════════════════════
    # Derived positions
    # ═══════════════════════════════════════════════════════════

    shoulder_top_z = 0.0
    shoulder_bot_z = -shoulder_height
    shaft_top_z = shaft_height
    dome_bot_z = torus_cz - torus_minor_r
    conn_shaft_top_z = dome_bot_z + conn_overlap
    conn_shaft_bot_z = (sphere_cz + sphere_r) - conn_ring_penetration
    sphere_bot_z = sphere_cz - sphere_r
    pip_top_z = pip_bot_z + pip_height
    stalk_top_z = sphere_bot_z + stalk_ring_penetration

    n = math.sqrt(1 + plane_slope ** 2)
    plane1 = bd.Plane(
        origin=(0, plane_intercept, 0),
        z_dir=(0, -1 / n, plane_slope / n),
    )
    plane2 = bd.Plane(
        origin=(0, -plane_intercept, 0),
        z_dir=(0, 1 / n, plane_slope / n),
    )

    # ═══════════════════════════════════════════════════════════
    # 1. Upper body: single revolve (shaft+shoulder+dome+boss)
    # ═══════════════════════════════════════════════════════════

    arc_start_r = torus_major_r + torus_minor_r * math.cos(
        math.radians(torus_arc_start_angle)
    )
    arc_start_z = torus_cz - torus_minor_r * math.sin(
        math.radians(torus_arc_start_angle)
    )
    arc_mid_r = torus_major_r + torus_minor_r * math.cos(
        math.radians(torus_arc_end_angle)
    )
    arc_mid_z = torus_cz - torus_minor_r * math.sin(
        math.radians(torus_arc_end_angle)
    )
    arc_end_r = torus_major_r
    arc_end_z = dome_bot_z

    with bd.BuildPart() as upper_build:
        with bd.BuildSketch(bd.Plane.XZ) as sk:
            with bd.BuildLine() as ln:
                bd.Line((0, shaft_top_z + boss_h), (boss_r, shaft_top_z + boss_h))
                bd.Line((boss_r, shaft_top_z + boss_h), (boss_r, shaft_top_z))
                bd.Line((boss_r, shaft_top_z), (shaft_r, shaft_top_z))
                bd.Line((shaft_r, shaft_top_z), (shaft_r, shoulder_top_z))
                bd.Line((shaft_r, shoulder_top_z), (shoulder_r, shoulder_top_z))
                bd.Line((shoulder_r, shoulder_top_z), (shoulder_r, shoulder_bot_z))
                bd.Line((shoulder_r, shoulder_bot_z), (arc_start_r, arc_start_z))
                bd.ThreePointArc(
                    (arc_start_r, arc_start_z),
                    (arc_mid_r, arc_mid_z),
                    (arc_end_r, arc_end_z),
                )
                bd.Line((arc_end_r, arc_end_z), (0, arc_end_z))
                bd.Line((0, arc_end_z), (0, shaft_top_z + boss_h))
            bd.make_face()
        bd.revolve(axis=bd.Axis.Z)
    upper_body = upper_build.part

    # ═══════════════════════════════════════════════════════════
    # 2. Ring: sphere → split → bore → fillet on simple geometry
    # ═══════════════════════════════════════════════════════════

    sphere = bd.Sphere(radius=sphere_r).translate(
        bd.Vector(0, 0, sphere_cz)
    )
    ring_disc = sphere.split(plane1).split(plane2)

    bore_cyl = bd.Cylinder(
        radius=bore_r,
        height=4 * sphere_r,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER),
    )
    bore_cyl = bore_cyl.rotate(bd.Axis.X, 90).translate(
        bd.Vector(0, 0, bore_cz)
    )
    ring = (ring_disc - bore_cyl).solids()[0]

    # Fillet ring outer edges while ring is simple
    ring_outer_edges = []
    for edge in ring.edges():
        center = edge.center()
        d_sphere = abs(
            math.sqrt(
                center.X ** 2
                + center.Y ** 2
                + (center.Z - sphere_cz) ** 2
            )
            - sphere_r
        )
        if d_sphere < 0.1:
            for plane in [plane1, plane2]:
                po = bd.Vector(plane.origin)
                pn = bd.Vector(plane.z_dir)
                ec = bd.Vector(center.X, center.Y, center.Z)
                if abs((ec - po).dot(pn)) < 0.01:
                    ring_outer_edges.append(edge)
                    break

    if ring_outer_edges:
        try:
            ring = ring.fillet(ring_outer_fillet_r, ring_outer_edges)
            if hasattr(ring, "solids") and ring.solids():
                ring = ring.solids()[0]
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # 3. Connecting shaft: smooth spline revolve, clipped by planes
    #    Meets dome tangentially at top and sphere tangentially at bottom
    # ═══════════════════════════════════════════════════════════

    # Sphere tangent at connection point (conn_shaft_bot_z)
    r_at_sphere = math.sqrt(
        sphere_r ** 2 - (conn_shaft_bot_z - sphere_cz) ** 2
    )
    # Sphere tangent at (r, z): perpendicular to radius, pointing downward
    # along sphere surface = (z-cz, -r) in (dr, dz) convention
    sphere_dz = conn_shaft_bot_z - sphere_cz
    sphere_tan = (sphere_dz, -r_at_sphere)  # (dr, dz) continuing down sphere

    # Dome tangent at bottom: the torus arc ends with horizontal tangent
    # (purely radial, no Z component), so connector top tangent is vertical
    dome_tan = (0, -1)  # pointing downward along axis

    with bd.BuildPart() as conn_build:
        with bd.BuildSketch(bd.Plane.XZ) as sk:
            with bd.BuildLine() as ln:
                bd.Spline(
                    (conn_r, conn_shaft_top_z),
                    (conn_r, conn_flare_z),
                    (r_at_sphere, conn_shaft_bot_z),
                    tangents=(dome_tan, sphere_tan),
                )
                # Close: bottom along sphere radius to axis, up axis, back
                bd.Line(
                    (r_at_sphere, conn_shaft_bot_z), (0, conn_shaft_bot_z)
                )
                bd.Line((0, conn_shaft_bot_z), (0, conn_shaft_top_z))
                bd.Line((0, conn_shaft_top_z), (conn_r, conn_shaft_top_z))
            bd.make_face()
        bd.revolve(axis=bd.Axis.Z)
    conn_shaft = conn_build.part.split(plane1).split(plane2)

    # ═══════════════════════════════════════════════════════════
    # 4. Stalk + pip: single revolve with pip fillets in profile
    # ═══════════════════════════════════════════════════════════

    f45 = pip_fillet_r * (1 - math.cos(math.radians(45)))

    with bd.BuildPart() as pip_build:
        with bd.BuildSketch(bd.Plane.XZ) as sk:
            with bd.BuildLine() as ln:
                # Stalk
                bd.Line((0, stalk_top_z), (stalk_r, stalk_top_z))
                bd.Line((stalk_r, stalk_top_z), (stalk_r, pip_top_z))
                # Pip top: step out with fillet arc
                bd.Line(
                    (stalk_r, pip_top_z),
                    (pip_r - pip_fillet_r, pip_top_z),
                )
                bd.ThreePointArc(
                    (pip_r - pip_fillet_r, pip_top_z),
                    (pip_r - f45, pip_top_z - f45),
                    (pip_r, pip_top_z - pip_fillet_r),
                )
                # Pip side
                bd.Line(
                    (pip_r, pip_top_z - pip_fillet_r),
                    (pip_r, pip_bot_z + pip_fillet_r),
                )
                # Pip bottom fillet arc
                bd.ThreePointArc(
                    (pip_r, pip_bot_z + pip_fillet_r),
                    (pip_r - f45, pip_bot_z + f45),
                    (pip_r - pip_fillet_r, pip_bot_z),
                )
                # Pip bottom back to axis
                bd.Line((pip_r - pip_fillet_r, pip_bot_z), (0, pip_bot_z))
                # Close along axis
                bd.Line((0, pip_bot_z), (0, stalk_top_z))
            bd.make_face()
        bd.revolve(axis=bd.Axis.Z)
    stalk_pip = pip_build.part

    # ═══════════════════════════════════════════════════════════
    # 5. Fuse all parts
    # ═══════════════════════════════════════════════════════════

    def _extract_solid(shape):
        if hasattr(shape, "solids") and shape.solids():
            return max(shape.solids(), key=lambda s: s.volume)
        return shape

    ring_assembly = ring.fuse(conn_shaft)
    solid = (
        ring_assembly
        .fuse(upper_body)
        .fuse(stalk_pip)
    )

    # ═══════════════════════════════════════════════════════════
    # 6. Bore-plane inner edge fillets (post-fuse)
    # ═══════════════════════════════════════════════════════════

    bore_edges = []
    for edge in solid.edges():
        center = edge.center()
        d_from_bore = abs(
            math.sqrt(center.X ** 2 + (center.Z - bore_cz) ** 2) - bore_r
        )
        if d_from_bore < 0.1:
            for plane in [plane1, plane2]:
                po = bd.Vector(plane.origin)
                pn = bd.Vector(plane.z_dir)
                ec = bd.Vector(center.X, center.Y, center.Z)
                if abs((ec - po).dot(pn)) < 0.05:
                    bore_edges.append(edge)
                    break

    if bore_edges:
        try:
            solid = solid.fillet(ring_outer_fillet_r, bore_edges)
            solid = _extract_solid(solid)
        except Exception as e:
            print(f"Warning: bore fillet failed: {e}")

    return solid


if __name__ == "__main__":
    import os
    from OCP.STEPControl import (
        STEPControl_Writer,
        STEPControl_ManifoldSolidBrep,
    )
    from OCP.Interface import Interface_Static
    from OCP.ShapeFix import ShapeFix_Shape

    solid = create_peghead_simple()

    fixer = ShapeFix_Shape(solid.wrapped)
    fixer.Perform()
    fixed = fixer.Shape()

    out_path = os.path.join(os.path.dirname(__file__), "peghead_simple.step")
    writer = STEPControl_Writer()
    Interface_Static.SetCVal_s("write.step.schema", "AP203")
    writer.Transfer(fixed, STEPControl_ManifoldSolidBrep)
    writer.Write(out_path)
    print(f"Exported STEP to {out_path}")

    try:
        from ocp_vscode import show
        show(solid)
    except Exception:
        pass
