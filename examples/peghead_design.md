# Peg Head Design Description

## Overview

A guitar tuning peg button (head). The part you grip between your fingers to turn the tuning machine. Oriented with the Z axis along the central axis. The gear shaft end is at most positive Z; the pip end is at most negative Z.

## Part Order (positive Z to negative Z, bottom to top in viewing orientation)

1. **Gear shaft** — long cylinder that fits into the gear mechanism
2. **Shoulder** — flat disc stepping up from gear shaft
3. **Cap** — wider disc with dramatic fillet on ring-shaft side
4. **Ring shaft** — short narrow cylinder connecting cap to ring
5. **Ring** — spherical shell finger grip (the widest feature)
6. **Stalk** — barely perceptible tiny neck
7. **Pip** — small decorative nub at the very top

## Construction Sequence

### 1. Gear Shaft

A plain cylinder, 3.8mm diameter. Extends from the shoulder to Z=+10.4. In the real part this has threading/gearing, but the STEP model represents it as a smooth cylinder. This is the longest single feature.

### 2. Shoulder

A short cylinder, 7.0mm diameter, approximately 1mm tall. Steps up from the gear shaft diameter, providing a bearing surface.

### 3. Cap

A flat cylinder, 8.5mm diameter, 2mm tall. The face toward the shoulder is flat. The opposite face (toward the ring) has a dramatic fillet that blends the 8.5mm OD smoothly down to the ring shaft diameter (3.8mm), creating a flowing sculptural transition. This fillet corresponds to the torus face (major_r=2.52, minor_r=2.0) in the fingerprint.

Small r=0.3mm fillets on the cap's outer edges (torus faces at major_r=5.84, minor_r=0.3).

### 4. Ring Shaft

A plain cylinder, 3.8mm diameter, 2.5mm long. Connects the cap to the ring. The cap's fillet flows into this shaft, and the shaft transitions into the ring bore.

### 5. Ring (the finger grip)

Start with a solid sphere, 12.5mm diameter, centered on the axis.

Cut the sphere with two planes roughly perpendicular to Z, but slightly angled relative to each other so the ring tapers:
- **Thin side** (pip end, more negative Z): 2.5mm tall
- **Thick side** (ring shaft end, more positive Z): 3.2mm tall

Bore a cylinder of 9.8mm diameter through the center (along Z), turning the solid disc into a ring. The radial wall thickness at the widest point of the sphere is (12.5 - 9.8) / 2 = 1.35mm.

Fillet the sharp edges where the cut planes meet the spherical surface and the bore cylinder, using a 2.0mm radius. This creates the smooth, comfortable finger-grip profile (producing the BSpline surfaces seen in the STEP file).

### 6. Stalk

A tiny cylinder, 1.0mm diameter, less than 0.5mm long. Barely perceptible — just a neck connecting the ring face to the pip.

### 7. Pip

A small cylinder, 2.0mm OD, 1.3mm tall before filleting. Both ends are heavily filleted (r=0.3mm, torus faces at major_r=0.75, minor_r=0.3) making it appear almost — but not quite — spherical.

## Key Dimensions Summary

| Feature | Diameter | Height/Length | Approx Z range |
|---------|----------|---------------|----------------|
| Gear shaft | 3.8mm | ~9mm | +10.4 to ~+1 |
| Shoulder | 7.0mm | ~1.0mm | ~+1 to ~0 |
| Cap | 8.5mm | 2.0mm | ~0 to ~-2 |
| Ring shaft | 3.8mm | 2.5mm | ~-2 to ~-4.5 |
| Ring (sphere) | 12.5mm outer | 2.5–3.2mm (tapered) | ~-4.5 to ~-17 |
| Ring bore | 9.8mm | — | — |
| Ring wall (radial) | — | 1.35mm | — |
| Stalk | 1.0mm | <0.5mm | ~-17 to ~-17.5 |
| Pip | 2.0mm | 1.3mm | ~-17.5 to ~-19 |

## Fillets

| Location | Radius | Fingerprint signature |
|----------|--------|-----------------------|
| Ring edges (cut plane to sphere/bore) | 2.0mm | BSpline faces |
| Cap ring-side face (OD to ring shaft blend) | 2.0mm | Torus major=2.52, minor=2.0 |
| Cap outer edges | 0.3mm | Torus major=5.84, minor=0.3 |
| Pip ends | 0.3mm | Torus major=0.75, minor=0.3 |

## Bounding Box

- X: -6.25 to +6.25 (12.5mm — sphere diameter)
- Y: -4.25 to +4.25 (8.5mm — limited by bore through sphere)
- Z: -19.03 to +10.4 (29.4mm total)

## Fingerprint Validation

The implementation must pass 43 geometric assertions in `test_peghead.py`, covering:
- Volume: 375.64 mm³
- Surface area: 568.40 mm²
- Moments of inertia (sensitive to mass distribution)
- 27 faces (6 BSpline, 7 Cylinder, 8 Plane, 1 Sphere, 5 Torus)
- Cross-sectional areas at 20 Z positions
- Radial profiles at 15 Z positions × 12 angles
