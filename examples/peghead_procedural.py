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
    # 8. Explicit torus fillets (produces clean TOROIDAL_SURFACE
    #    in STEP, avoiding OCCT's BSpline fillet approximations)
    # ═══════════════════════════════════════════════════════════

    def _extract_solid(shape):
        """Extract the largest Solid from a boolean result (may be Compound or ShapeList)."""
        if hasattr(shape, "solids"):
            solids = shape.solids()
            if solids:
                return max(solids, key=lambda s: s.volume)
        return shape

    # --- Ring outer fillets (×2): explicit torus subtract at sphere-plane edges ---
    # OCCT fillet produces huge BSpline approximations for these edges,
    # so we use exact torus geometry instead.
    fillet_r = ring_outer_fillet_r
    for plane in [plane1, plane2]:
        plane_origin = bd.Vector(plane.origin)
        plane_normal = bd.Vector(plane.z_dir)
        sphere_center = bd.Vector(0, 0, sphere_cz)
        signed_d = (sphere_center - plane_origin).dot(plane_normal)
        d_to_plane = abs(signed_d)

        torus_major = math.sqrt(
            (sphere_r - fillet_r) ** 2 - (d_to_plane - fillet_r) ** 2
        )

        # Torus center: on plane, offset fillet_r toward sphere center
        proj = sphere_center - plane_normal * signed_d
        fillet_center = proj + plane_normal * (
            fillet_r if signed_d > 0 else -fillet_r
        )

        torus = bd.Torus(major_radius=torus_major, minor_radius=fillet_r)

        # Rotate torus from Z-axis to plane normal
        z_axis = bd.Vector(0, 0, 1)
        cross = z_axis.cross(plane_normal)
        cross_len = math.sqrt(cross.X ** 2 + cross.Y ** 2 + cross.Z ** 2)
        if cross_len > 1e-10:
            rot_axis = bd.Axis(bd.Vector(0, 0, 0), cross * (1.0 / cross_len))
            rot_angle = math.degrees(
                math.acos(max(-1, min(1, z_axis.dot(plane_normal))))
            )
            torus = torus.rotate(rot_axis, rot_angle)

        torus = torus.translate(fillet_center)
        solid = _extract_solid(solid - torus)

    # --- Pip + bore-plane fillets via OCCT fillet API ---
    fillet_edges = []

    # Bore-plane inner edges (where bore cylinder meets tilted planes)
    for edge in solid.edges():
        center = edge.center()
        r = math.sqrt(center.X ** 2 + center.Y ** 2)
        if abs(r - bore_r) < 0.5 and r > bore_r - 0.5:
            for plane in [plane1, plane2]:
                po = bd.Vector(plane.origin)
                pn = bd.Vector(plane.z_dir)
                ec = bd.Vector(center.X, center.Y, center.Z)
                dist = abs((ec - po).dot(pn))
                if dist < 0.01:
                    fillet_edges.append((edge, ring_outer_fillet_r))
                    break

    # Pip edges: top and bottom circular edges of pip cylinder
    for edge in solid.edges():
        center = edge.center()
        r = math.sqrt(center.X ** 2 + center.Y ** 2)
        for z_target in [pip_top_z, pip_bot_z]:
            if abs(center.Z - z_target) < 0.01 and abs(r - pip_r) < 0.1:
                fillet_edges.append((edge, pip_fillet_r))
                break

    # Apply fillets grouped by radius
    from collections import defaultdict
    by_radius = defaultdict(list)
    for edge, radius in fillet_edges:
        by_radius[radius].append(edge)

    for radius, edges in by_radius.items():
        try:
            solid = solid.fillet(radius, edges)
            solid = _extract_solid(solid)
        except Exception as e:
            print(f"Warning: fillet r={radius} failed: {e}")

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
