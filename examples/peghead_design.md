# Peg Head Design Description

## Overview

A guitar tuning peg button (head). The part you grip between your fingers to turn the tuning machine. Oriented with the Z axis along the central axis. The gear shaft end is at most positive Z; the pip end is at most negative Z.

Z=0 datum is the top of the shoulder.

## Part Anatomy (positive Z to negative Z)

```
        ┌──┐
        │  │  ← gear shaft (long cylinder into gear mechanism)
        │  │
    ┌───┘  └───┐  ← shoulder (wider bearing step)
    │          │
    └──╮    ╭──┘  ← cap (rounded underside, torus arc profile)
       │    │
       │    │     ← ringshaft (narrow neck, spline profile)
       ╰╮  ╭╯
    ╭────╯  ╰────╮
   ╭╯    ○ bore  ╰╮  ← ring (sphere slice, finger grip)
    ╰────╮  ╭────╯
         │  │
         ╰──╯     ← stalk + pip (locating nub)
```

1. **Gear shaft** — long cylinder that fits into the gear mechanism
2. **Shoulder** — flat disc stepping out from gear shaft, provides bearing surface
3. **Cap** — rounded underside of the shoulder, curves inward like a mushroom cap. Built as a torus arc of revolution that blends from the shoulder outer edge down to the ringshaft diameter.
4. **Ringshaft** — narrow neck connecting cap to ring. Built as a smooth spline revolve that meets the cap tangentially at the top and the ring sphere tangentially at the bottom.
5. **Ring** — spherical-shell finger grip, the widest feature. A sphere sliced by two slightly tapered planes, with a cylindrical bore for the string.
6. **Stalk** — thin rod below the ring
7. **Pip** — small locating nub at the very bottom, with filleted top and bottom edges

## Construction (peghead_simple.py)

### 1. Upper body (gear shaft + shoulder + cap + boss) — single revolve

The gear shaft, shoulder, and cap are built as one revolved profile. The profile traces:
- Boss nub at the very top (tiny centering feature)
- Gear shaft cylinder wall downward
- Step out to shoulder width
- Shoulder cylinder wall downward
- Short straight connecting shoulder edge to cap arc start
- Torus arc curving inward and downward (the cap)
- Straight line back to the Z axis

The cap's torus arc starts where the shoulder ends and sweeps from `cap_arc_start_deg` (30°) to 90°. The torus centre Z is derived so the arc begins exactly at the shoulder bottom — not a free parameter.

### 2. Ring — sphere → split → bore → fillet

A full sphere, sliced by two near-parallel planes (forming the ring disc), then bored through with a cylinder for the string. The cut planes have a slight taper (`ring_taper`) so the ring is marginally thicker on one side.

Outer edge fillets are applied after fusing with the ringshaft (step 5) so the fillet flows smoothly across the junction.

### 3. Ringshaft — smooth spline revolve

A spline profile revolved around Z, then clipped by the ring cut planes. The spline passes through three points:
1. Top: at `ringshaft_r`, entering vertically (tangent to cap bottom)
2. Waypoint: at `ringshaft_r`, at the flare depth (controls where it starts curving outward)
3. Bottom: at the sphere surface radius, entering tangent to the sphere

This gives a smooth, tangent-continuous transition from cap to ring with no sharp edges.

### 4. Stalk + pip — single revolve

The stalk and pip are one revolved profile. The pip fillets are drawn directly as arcs in the 2D profile rather than using the OCCT fillet API. When the stalk radius equals the pip fillet tangent point (as it does at 0.75mm), the horizontal step is omitted and the stalk meets the fillet arc directly.

### 5. Assembly + fillets

- Ring fused with ringshaft → outer edge fillets applied on this assembly
- Fused with upper body and stalk+pip
- Bore-plane inner edge fillets applied last on the full solid

## Key Dimensions

| Feature | Diameter | Length | Notes |
|---------|----------|--------|-------|
| Gear shaft | 3.8mm | 10.4mm | Smooth cylinder (real part has gearing) |
| Shoulder | 7.0mm | 1.2mm | Bearing surface |
| Cap | varies | ~1.0mm depth | Torus arc: flat_r=2.52, minor_r=2.0 |
| Ringshaft | 3.56mm | ~4.0mm | Spline profile, flares to meet ring |
| Ring (sphere) | 12.5mm outer | ~3.7mm thick | Slightly tapered |
| Ring bore | 9.8mm | — | Offset 0.25mm below sphere centre |
| Stalk | 1.5mm | ~0.2mm exposed | Mostly hidden inside ring |
| Pip | 2.1mm | 1.2mm | Filleted top and bottom (r=0.3mm) |

## Fillets

| Location | Radius | Notes |
|----------|--------|-------|
| Ring outer edges (sphere-plane) | 0.5mm | Applied on ring+ringshaft assembly |
| Ring bore edges (bore-plane) | 0.5mm | Applied post-fuse on full solid |
| Pip top and bottom | 0.3mm | Drawn as arcs in revolve profile |
| Cap underside (torus arc) | 2.0mm | Built into the revolve profile |

## Bounding Box

- X: ±6.25mm (12.5mm — ring sphere diameter)
- Y: ±4.25mm (limited by bore through sphere)
- Z: ~-19.1 to +10.4 (~29.5mm total)
