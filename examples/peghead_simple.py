"""Simplified peghead build using revolve + targeted fillets.

Improvements over the procedural version:
- Upper body (shaft + shoulder + dome) built as a single revolve
  instead of 4 separate fuse operations
- Ring fillets applied on simple ring geometry before fusing
  with the rest of the body (cleaner topology)
- Fewer boolean operations overall
"""

import math
import build123d as bd


def create_peghead_simple():
    """Build the guitar tuning peg head."""

    # ═══════════════════════════════════════════════════════════
    # Dimensions (identical to procedural version)
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
    dome_top_z = shoulder_bot_z
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
    # 1. Upper body: single revolve (shaft + shoulder + dome)
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
                # Boss
                bd.Line((0, shaft_top_z + boss_h), (boss_r, shaft_top_z + boss_h))
                bd.Line((boss_r, shaft_top_z + boss_h), (boss_r, shaft_top_z))
                # Shaft
                bd.Line((boss_r, shaft_top_z), (shaft_r, shaft_top_z))
                bd.Line((shaft_r, shaft_top_z), (shaft_r, shoulder_top_z))
                # Shoulder
                bd.Line((shaft_r, shoulder_top_z), (shoulder_r, shoulder_top_z))
                bd.Line((shoulder_r, shoulder_top_z), (shoulder_r, shoulder_bot_z))
                # Dome: shoulder → torus arc → dome bottom
                bd.Line((shoulder_r, shoulder_bot_z), (arc_start_r, arc_start_z))
                bd.ThreePointArc(
                    (arc_start_r, arc_start_z),
                    (arc_mid_r, arc_mid_z),
                    (arc_end_r, arc_end_z),
                )
                bd.Line((arc_end_r, arc_end_z), (0, arc_end_z))
                # Close along axis
                bd.Line((0, arc_end_z), (0, shaft_top_z + boss_h))
            bd.make_face()
        bd.revolve(axis=bd.Axis.Z)
    upper_body = upper_build.part

    # ═══════════════════════════════════════════════════════════
    # 2. Ring: sphere → split → bore → fillet on simple geometry
    # ═══════════════════════════════════════════════════════════

    sphere = bd.Sphere(radius=sphere_r).translate(bd.Vector(0, 0, sphere_cz))
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

    # Fillet ring outer edges (sphere-plane) on simple ring
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
        except Exception as e:
            print(f"Warning: ring outer fillet failed: {e}")

    # ═══════════════════════════════════════════════════════════
    # 3. Connecting shaft: clipped by tilted planes
    # ═══════════════════════════════════════════════════════════

    conn_upper = bd.Cylinder(
        radius=conn_r,
        height=conn_shaft_top_z - conn_flare_z,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).translate(bd.Vector(0, 0, conn_flare_z))

    conn_lower = bd.Cone(
        bottom_radius=conn_flare_r,
        top_radius=conn_r,
        height=conn_flare_z - conn_shaft_bot_z,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).translate(bd.Vector(0, 0, conn_shaft_bot_z))

    conn_shaft = conn_upper.fuse(conn_lower).split(plane1).split(plane2)

    # ═══════════════════════════════════════════════════════════
    # 4. Stalk and pip
    # ═══════════════════════════════════════════════════════════

    stalk = bd.Cylinder(
        radius=stalk_r,
        height=stalk_top_z - pip_top_z,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MAX),
    ).translate(bd.Vector(0, 0, stalk_top_z))

    pip = bd.Cylinder(
        radius=pip_r,
        height=pip_height,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).translate(bd.Vector(0, 0, pip_bot_z))

    # ═══════════════════════════════════════════════════════════
    # 5. Fuse all: ring+conn first (coplanar planes), then rest
    # ═══════════════════════════════════════════════════════════

    ring_assembly = ring.fuse(conn_shaft)
    solid = (
        ring_assembly
        .fuse(upper_body)
        .fuse(stalk)
        .fuse(pip)
    )

    # ═══════════════════════════════════════════════════════════
    # 6. Post-fuse fillets: bore inner edges + pip edges
    # ═══════════════════════════════════════════════════════════

    def _extract_solid(shape):
        if hasattr(shape, "solids") and shape.solids():
            return max(shape.solids(), key=lambda s: s.volume)
        return shape

    # Bore-plane inner edges
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

    # Pip edges
    pip_edges = []
    for edge in solid.edges():
        center = edge.center()
        r = math.sqrt(center.X ** 2 + center.Y ** 2)
        for z_target in [pip_top_z, pip_bot_z]:
            if abs(center.Z - z_target) < 0.01 and abs(r - pip_r) < 0.1:
                pip_edges.append(edge)
                break

    if pip_edges:
        try:
            solid = solid.fillet(pip_fillet_r, pip_edges)
            solid = _extract_solid(solid)
        except Exception:
            pass

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

    # Show in OCP CAD Viewer if available
    try:
        from ocp_vscode import show
        show(solid)
    except Exception:
        pass
