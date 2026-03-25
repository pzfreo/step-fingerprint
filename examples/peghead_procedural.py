"""Procedural build123d implementation of the peghead.

Builds a guitar tuning peg button by:
1. Cutting a sphere with two slightly tilted planes (using split)
2. Boring a cylinder along Y through the disc
3. Adding shaft, shoulder, cap torus dome, connecting shaft, stalk, and pip
4. Fusing all raw geometry, then applying fillets on the complete solid
"""

import math
import build123d as bd


def create_peghead():
    """Build the guitar tuning peg head."""

    # ═══════════════════════════════════════════════════════════
    # Primary dimensions (from reference STEP face analysis)
    # ═══════════════════════════════════════════════════════════

    # Ring: sphere sliced by two tilted planes, bored through Y
    sphere_r = 6.25
    sphere_cz = -11.45
    bore_r = 4.9
    bore_cz = -11.7

    # Tilted cut planes: Y = ±intercept, tilted by slope in Z
    plane_slope = 0.0355
    plane_intercept = 1.829

    # Gear shaft: cylinder from shoulder top to shaft tip
    shaft_r = 1.9
    shaft_height = 10.4

    # Shoulder: wide disc between gear shaft and dome
    shoulder_r = 3.5
    shoulder_height = 1.2

    # Cap torus dome: mushroom-cap below shoulder
    torus_major_r = 2.5179
    torus_minor_r = 2.0
    torus_cz = -0.2
    torus_arc_start_angle = 30   # degrees from torus equator
    torus_arc_end_angle = 60     # degrees from torus equator

    # Connecting shaft: links dome bottom into ring interior
    conn_r = 1.78               # narrower than gear shaft
    conn_flare_r = 2.95         # cone widens to blend into ring
    conn_flare_z = -4.5         # Z where cylinder transitions to cone
    conn_overlap = 0.1          # overlap into dome for clean boolean union
    conn_ring_penetration = 1.0 # how far cone extends below sphere top

    # Pip and stalk: small cylinder hanging below ring
    pip_r = 1.05
    pip_height = 1.2
    pip_bot_z = -19.026
    stalk_r = 0.5
    stalk_ring_penetration = 0.5  # how far stalk extends into ring interior

    # Fillets (explicit torus geometry, matching reference STEP)
    ring_outer_fillet_r = 0.5   # sphere-plane intersection edges
    pip_fillet_r = 0.3          # pip top and bottom edges

    # Cosmetic boss on shaft tip (matches reference d≈0.597 cylinder face)
    boss_r = 0.2985
    boss_h = 0.005

    # ═══════════════════════════════════════════════════════════
    # Derived positions (Z=0 is at shoulder top)
    # ═══════════════════════════════════════════════════════════

    shoulder_top_z = 0.0
    shoulder_bot_z = shoulder_top_z - shoulder_height
    shaft_top_z = shoulder_top_z + shaft_height
    dome_top_z = shoulder_bot_z
    dome_bot_z = torus_cz - torus_minor_r
    conn_shaft_top_z = dome_bot_z + conn_overlap
    conn_shaft_bot_z = (sphere_cz + sphere_r) - conn_ring_penetration
    sphere_top_z = sphere_cz + sphere_r
    sphere_bot_z = sphere_cz - sphere_r
    pip_top_z = pip_bot_z + pip_height
    stalk_top_z = sphere_bot_z + stalk_ring_penetration

    # Plane normal normalisation factor
    n = math.sqrt(1 + plane_slope**2)

    # Tilted cut planes (reused for sphere and shaft clipping)
    plane1 = bd.Plane(
        origin=(0, plane_intercept, 0),
        z_dir=(0, -1 / n, plane_slope / n),
    )
    plane2 = bd.Plane(
        origin=(0, -plane_intercept, 0),
        z_dir=(0, 1 / n, plane_slope / n),
    )

    # ═══════════════════════════════════════════════════════════
    # 1. Ring: sphere → split by two tilted planes → bore
    # ═══════════════════════════════════════════════════════════

    sphere = bd.Sphere(radius=sphere_r).translate(bd.Vector(0, 0, sphere_cz))
    half1 = sphere.split(plane1)
    ring_disc = half1.split(plane2)

    # Bore cylinder along Y axis — oversized to cut cleanly through sphere
    bore_cyl = bd.Cylinder(
        radius=bore_r, height=4 * sphere_r,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER),
    )
    bore_cyl = bore_cyl.rotate(bd.Axis.X, 90).translate(bd.Vector(0, 0, bore_cz))

    ring = ring_disc - bore_cyl
    ring = ring.solids()[0]

    # Fillet ring outer edges (sphere-plane) while ring is simple geometry.
    # Must happen before fusing with other parts — OCCT fillet on the
    # full solid produces bloated BSplines, and subsequent fillet() calls
    # rebuild from shape history, undoing any earlier torus subtracts.
    ring_outer_edges = []
    for edge in ring.edges():
        center = edge.center()
        d_sphere = abs(
            math.sqrt(center.X ** 2 + center.Y ** 2 + (center.Z - sphere_cz) ** 2)
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
            pass  # Fall back to unfilleted ring

    # ═══════════════════════════════════════════════════════════
    # 2. Connecting shaft: dome bottom into ring
    #    Clipped by tilted planes for correct Y extent
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

    conn_shaft = conn_upper.fuse(conn_lower)
    conn_shaft = conn_shaft.split(plane1)
    conn_shaft = conn_shaft.split(plane2)

    # ═══════════════════════════════════════════════════════════
    # 3. Gear shaft (Z=0 to shaft_top_z)
    # ═══════════════════════════════════════════════════════════

    gear_shaft = bd.Cylinder(
        radius=shaft_r,
        height=shaft_height,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )

    # ═══════════════════════════════════════════════════════════
    # 4. Shoulder (shoulder_bot_z to 0)
    # ═══════════════════════════════════════════════════════════

    shoulder = bd.Cylinder(
        radius=shoulder_r,
        height=shoulder_height,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).translate(bd.Vector(0, 0, shoulder_bot_z))

    # ═══════════════════════════════════════════════════════════
    # 5. Cap torus dome (dome_top_z to dome_bot_z)
    # ═══════════════════════════════════════════════════════════

    arc_start_r = torus_major_r + torus_minor_r * math.cos(math.radians(torus_arc_start_angle))
    arc_start_z = torus_cz - torus_minor_r * math.sin(math.radians(torus_arc_start_angle))
    arc_mid_r = torus_major_r + torus_minor_r * math.cos(math.radians(torus_arc_end_angle))
    arc_mid_z = torus_cz - torus_minor_r * math.sin(math.radians(torus_arc_end_angle))
    arc_end_r = torus_major_r
    arc_end_z = dome_bot_z

    with bd.BuildPart() as dome_build:
        with bd.BuildSketch(bd.Plane.XZ) as sk:
            with bd.BuildLine() as ln:
                bd.Line((0, dome_bot_z), (0, dome_top_z))
                bd.Line((0, dome_top_z), (arc_start_r, arc_start_z))
                bd.ThreePointArc(
                    (arc_start_r, arc_start_z),
                    (arc_mid_r, arc_mid_z),
                    (arc_end_r, arc_end_z),
                )
                bd.Line((arc_end_r, arc_end_z), (0, dome_bot_z))
            bd.make_face()
        bd.revolve(axis=bd.Axis.Z)
    dome = dome_build.part

    # ═══════════════════════════════════════════════════════════
    # 6. Stalk and pip
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
    # 7. Fuse all raw geometry before filleting
    #    Ring + connecting shaft fused first (coplanar tilted planes),
    #    then fused with remaining parts
    # ═══════════════════════════════════════════════════════════

    ring_assembly = ring.fuse(conn_shaft)
    solid = (
        ring_assembly
        .fuse(dome)
        .fuse(shoulder)
        .fuse(gear_shaft)
        .fuse(stalk)
        .fuse(pip)
    )

    # Cosmetic boss on gear shaft tip
    boss = bd.Cylinder(
        radius=boss_r, height=boss_h,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    ).translate(bd.Vector(0, 0, shaft_top_z))
    solid = solid.fuse(boss)

    # ═══════════════════════════════════════════════════════════
    # 8. Fillets: ring inner (bore-plane) edges + pip edges
    # ═══════════════════════════════════════════════════════════

    def _extract_solid(shape):
        """Extract the largest Solid from a boolean result."""
        if hasattr(shape, "solids") and shape.solids():
            return max(shape.solids(), key=lambda s: s.volume)
        return shape

    # Ring inner edges: where bore cylinder meets each tilted plane
    bore_edges = []
    for edge in solid.edges():
        center = edge.center()
        # Bore is along Y axis at z=bore_cz — distance from bore surface
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

    # Pip edges: top and bottom circular edges of pip cylinder
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

    solid = create_peghead()

    # Fix geometry and export as AP203 ManifoldSolidBrep (most compatible)
    fixer = ShapeFix_Shape(solid.wrapped)
    fixer.Perform()
    fixed = fixer.Shape()

    out_path = os.path.join(os.path.dirname(__file__), "peghead_procedural.step")
    writer = STEPControl_Writer()
    Interface_Static.SetCVal_s("write.step.schema", "AP203")
    writer.Transfer(fixed, STEPControl_ManifoldSolidBrep)
    writer.Write(out_path)
    print(f"Exported STEP to {out_path}")

    # Show in OCP CAD Viewer if available (VS Code extension)
    try:
        from ocp_vscode import show
        show(solid)
    except Exception:
        pass
