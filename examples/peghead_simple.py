"""Simplified peghead build using revolve profiles where possible.

Part anatomy (top to bottom, positive Z to negative Z):
  gear shaft → shoulder → cap → ringshaft → ring → stalk → pip

Build approach:
- Upper body (gear shaft + shoulder + cap + boss) as one revolve
- Ringshaft as smooth spline revolve, tangent to cap and ring
- Ring as sphere → split → bore → fillet
- Stalk + pip as one revolve with pip fillets in the 2D profile

Z-axis convention: Z=0 at shoulder top (datum), positive up (gear shaft),
negative down (cap → ringshaft → ring → stalk → pip).
"""

import math
import build123d as bd


def create_peghead_simple():
    """Build the guitar tuning peg head."""

    # ═══════════════════════════════════════════════════════════
    # Design parameters
    # ═══════════════════════════════════════════════════════════

    # -- Cross-section radii --
    shaft_r = 1.9                # gear shaft
    shoulder_r = 3.5             # wider step at shaft base
    ringshaft_r = 1.78           # narrow neck between cap and ring
    stalk_r = 0.75               # rod connecting ring to pip (dia 1.5mm)
    pip_r = 1.05                 # locating pip at bottom
    bore_r = 4.9                 # string bore through ring

    # -- Section lengths (measured along Z from shoulder datum) --
    shaft_length = 10.4          # gear shaft extends upward
    shoulder_height = 1.2        # shoulder step below datum
    pip_height = 1.2             # pip cylinder height

    # -- Cap (rounded underside of shoulder, built as a torus arc) --
    #    Three design parameters define the cap shape. The torus arc
    #    geometry (arc radius, start angle) is derived to fit them.
    cap_r = 4.25                     # outer radius of the cap
    cap_flat_r = cap_r * 3 / 4      # radius where the dome goes flat
    cap_depth = 1.0                  # Z depth of the dome

    # Derive torus arc geometry to fit cap_r, cap_flat_r, cap_depth
    _dr = cap_r - cap_flat_r
    _hyp = math.sqrt(cap_depth ** 2 + _dr ** 2)
    cap_arc_start_deg = math.degrees(
        math.asin(_dr / _hyp) - math.atan2(cap_depth, _dr)
    )
    cap_minor_r = cap_depth / (1 - math.sin(math.radians(cap_arc_start_deg)))
    cap_arc_mid_deg = (cap_arc_start_deg + 90) / 2

    # -- Ring (sphere sliced by two near-parallel planes, bored out) --
    sphere_r = 6.25              # ring sphere radius
    ring_center_depth = 11.45    # depth from shoulder datum to sphere centre
    bore_offset = 0.25           # bore axis sits this far below sphere centre
    ring_half_thickness = 1.829  # half-thickness of ring at string axis
    ring_taper = 0.0355          # slight inward taper of cut planes (slope)

    # -- Ringshaft (smooth spline from cap bottom to ring top) --
    ringshaft_flare_depth = 2.3  # spline waypoint: depth below cap bottom
                                 # (controls where ringshaft begins to flare
                                 #  outward toward the ring sphere)
    ringshaft_overlap = 0.1      # overlap into cap for clean boolean
    ringshaft_ring_penetration = 1.0  # penetration into ring sphere

    # -- Stalk + pip placement --
    stalk_ring_penetration = 0.5 # stalk extends up into ring for boolean
    stalk_pip_gap = 0.2          # exposed gap between ring bottom and pip top

    # -- Fillets --
    ring_outer_fillet_r = 0.5    # fillet on ring outer edges (sphere-plane)
    pip_fillet_r = 0.3           # fillet on pip top and bottom edges

    # ═══════════════════════════════════════════════════════════
    # Derived positions (all Z computed from section lengths)
    # ═══════════════════════════════════════════════════════════

    shoulder_top_z = 0.0                          # datum
    shoulder_bot_z = -shoulder_height              # = -1.2
    shaft_top_z = shaft_length                     # = 10.4

    # Cap Z positions
    cap_bot_z = shoulder_bot_z - cap_depth         # bottom of cap dome
    cap_torus_cz = cap_bot_z + cap_minor_r         # torus arc centre

    # Ring sphere
    sphere_cz = -ring_center_depth                 # sphere centre
    sphere_top_z = sphere_cz + sphere_r            # top of sphere
    sphere_bot_z = sphere_cz - sphere_r            # bottom of sphere
    bore_cz = sphere_cz - bore_offset              # bore axis

    # Ringshaft Z range
    ringshaft_top_z = cap_bot_z + ringshaft_overlap
    ringshaft_bot_z = sphere_top_z - ringshaft_ring_penetration
    ringshaft_flare_z = cap_bot_z - ringshaft_flare_depth

    # Stalk and pip
    stalk_top_z = sphere_bot_z + stalk_ring_penetration
    pip_top_z = sphere_bot_z - stalk_pip_gap
    pip_bot_z = pip_top_z - pip_height

    # Ring cut planes (nearly parallel, slight taper)
    n = math.sqrt(1 + ring_taper ** 2)
    plane1 = bd.Plane(
        origin=(0, ring_half_thickness, 0),
        z_dir=(0, -1 / n, ring_taper / n),
    )
    plane2 = bd.Plane(
        origin=(0, -ring_half_thickness, 0),
        z_dir=(0, 1 / n, ring_taper / n),
    )

    # ═══════════════════════════════════════════════════════════
    # 1. Upper body: single revolve (gear shaft + shoulder + cap)
    # ═══════════════════════════════════════════════════════════

    # Cap arc points (torus cross-section in the XZ half-plane)
    arc_start_r = cap_flat_r + cap_minor_r * math.cos(
        math.radians(cap_arc_start_deg)
    )
    arc_start_z = cap_torus_cz - cap_minor_r * math.sin(
        math.radians(cap_arc_start_deg)
    )
    arc_mid_r = cap_flat_r + cap_minor_r * math.cos(
        math.radians(cap_arc_mid_deg)
    )
    arc_mid_z = cap_torus_cz - cap_minor_r * math.sin(
        math.radians(cap_arc_mid_deg)
    )
    arc_end_r = cap_flat_r
    arc_end_z = cap_bot_z

    with bd.BuildPart() as upper_build:
        with bd.BuildSketch(bd.Plane.XZ) as sk:
            with bd.BuildLine() as ln:
                bd.Line((0, shaft_top_z), (shaft_r, shaft_top_z))
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
                bd.Line((0, arc_end_z), (0, shaft_top_z))
            bd.make_face()
        bd.revolve(axis=bd.Axis.Z)
    upper_body = upper_build.part

    # ═══════════════════════════════════════════════════════════
    # 2. Ring: sphere → split → bore
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

    # Ring outer fillets deferred to after ringshaft fuse (section 5)
    # so the fillet flows smoothly over the ringshaft-sphere junction

    # ═══════════════════════════════════════════════════════════
    # 3. Ringshaft: smooth spline revolve, clipped by ring planes
    #    Meets cap tangentially at top and sphere tangentially at bottom
    # ═══════════════════════════════════════════════════════════

    # Sphere radius at ringshaft connection point
    r_at_sphere = math.sqrt(
        sphere_r ** 2 - (ringshaft_bot_z - sphere_cz) ** 2
    )
    # Sphere tangent at (r, z): perpendicular to radius, pointing downward
    # along sphere surface = (z-cz, -r) in (dr, dz) convention
    sphere_dz = ringshaft_bot_z - sphere_cz
    sphere_tan = (sphere_dz, -r_at_sphere)  # (dr, dz) continuing down sphere

    # Cap tangent at bottom: the torus arc ends vertically (horizontal
    # tangent in the radial direction), so ringshaft enters vertically
    cap_tan = (0, -1)  # pointing downward along axis

    with bd.BuildPart() as ringshaft_build:
        with bd.BuildSketch(bd.Plane.XZ) as sk:
            with bd.BuildLine() as ln:
                bd.Spline(
                    (ringshaft_r, ringshaft_top_z),
                    (ringshaft_r, ringshaft_flare_z),
                    (r_at_sphere, ringshaft_bot_z),
                    tangents=(cap_tan, sphere_tan),
                )
                # Close: along sphere radius to axis, up axis, back out
                bd.Line(
                    (r_at_sphere, ringshaft_bot_z), (0, ringshaft_bot_z)
                )
                bd.Line((0, ringshaft_bot_z), (0, ringshaft_top_z))
                bd.Line((0, ringshaft_top_z), (ringshaft_r, ringshaft_top_z))
            bd.make_face()
        bd.revolve(axis=bd.Axis.Z)
    ringshaft = ringshaft_build.part.split(plane1).split(plane2)

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
                if stalk_r < pip_r - pip_fillet_r - 1e-6:
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
    # 5. Fuse all parts + ring outer fillets
    # ═══════════════════════════════════════════════════════════

    def _extract_solid(shape):
        if hasattr(shape, "solids") and shape.solids():
            return max(shape.solids(), key=lambda s: s.volume)
        return shape

    ring_assembly = ring.fuse(ringshaft)

    # Fillet ring outer edges on ring+ringshaft assembly so the fillet
    # flows smoothly over the ringshaft-sphere junction (no sharp point)
    ring_outer_edges = []
    for edge in ring_assembly.edges():
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
            ring_assembly = ring_assembly.fillet(
                ring_outer_fillet_r, ring_outer_edges
            )
            if hasattr(ring_assembly, "solids") and ring_assembly.solids():
                ring_assembly = ring_assembly.solids()[0]
        except Exception as e:
            print(f"Warning: ring outer fillet failed: {e}")

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
