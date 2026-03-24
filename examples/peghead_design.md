# Peg Head Design Description

## Overview

A guitar tuning peg button (head). The part you grip between your fingers to turn the tuning machine. Oriented with the Z axis along the central axis. The cap and shaft are at positive Z; the ring, stalk, and pip extend into negative Z.

## Part Order (top to bottom, positive Z to negative Z)

1. **Cap** — flat cylinder at the very top
2. **Shoulder** — stepped-down cylinder below the cap
3. **Shaft** — narrow cylinder connecting shoulder to ring
4. **Ring** — spherical shell finger grip (the widest feature)
5. **Stalk** — tiny neck below the ring
6. **Pip** — small decorative nub at the very bottom

## Construction Sequence

### 1. Cap

A flat cylinder, 8.5mm diameter, 2mm tall. The top face is flat and untouched. The bottom face connects to the shoulder/shaft. A large fillet blends the 8.5mm OD on the bottom face down toward the shaft diameter (3.8mm), creating a smooth flowing transition rather than a sharp step. The fillet corresponds to the torus face (major_r=2.52, minor_r=2.0) in the fingerprint.

Small r=0.3mm fillets on the cap edges (torus faces at major_r=5.84, minor_r=0.3).

### 2. Shoulder

A short cylinder, 7.0mm diameter, approximately 1mm tall. Sits directly below the cap, stepping down from the cap OD before the fillet transitions to the shaft.

### 3. Shaft

A plain cylinder, 3.8mm diameter, 2.5mm long. Connects the shoulder above to the ring below. In the real part this would have threading/gearing, but the STEP model represents it as a smooth cylinder.

### 4. Ring (the finger grip)

Start with a solid sphere, 12.5mm diameter, centered on the axis.

Cut the sphere with two planes roughly perpendicular to Z, but slightly angled relative to each other so the ring tapers:
- **Thin side** (pip end, more negative Z): 2.5mm tall
- **Thick side** (shaft end, more positive Z): 3.2mm tall

Bore a cylinder of 9.8mm diameter through the center (along Z), turning the solid disc into a ring. The radial wall thickness at the widest point of the sphere is (12.5 - 9.8) / 2 = 1.35mm.

Fillet the sharp edges where the cut planes meet the spherical surface and the bore cylinder, using a 2.0mm radius. This creates the smooth, comfortable finger-grip profile (producing the BSpline surfaces seen in the STEP file).

### 5. Stalk

A tiny cylinder, 1.0mm diameter, less than 0.5mm long. Barely perceptible — just a neck connecting the ring face to the pip.

### 6. Pip

A small cylinder, 2.0mm OD, 1.3mm tall before filleting. Both ends are heavily filleted (r=0.3mm, torus faces at major_r=0.75, minor_r=0.3) making it appear almost — but not quite — spherical.

## Key Dimensions Summary

| Feature | Diameter | Height/Length |
|---------|----------|---------------|
| Cap | 8.5mm | 2.0mm |
| Shoulder | 7.0mm | ~1.0mm |
| Shaft | 3.8mm | 2.5mm |
| Ring (sphere) | 12.5mm outer | 2.5–3.2mm (tapered) |
| Ring bore | 9.8mm | — |
| Ring wall (radial) | — | 1.35mm |
| Ring edge fillet | — | r=2.0mm |
| Stalk | 1.0mm | <0.5mm |
| Pip | 2.0mm | 1.3mm |

## Fillets

| Location | Radius | Fingerprint signature |
|----------|--------|-----------------------|
| Ring edges (cut plane to sphere/bore) | 2.0mm | BSpline faces |
| Cap bottom face (OD to shaft blend) | 2.0mm | Torus major=2.52, minor=2.0 |
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
