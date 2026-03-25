"""CLI for step-fingerprint.

Usage:
    step-fingerprint reference.step                    # print JSON fingerprint
    step-fingerprint reference.step -o test_part.py    # generate pytest file
    step-fingerprint reference.step --json fp.json     # save JSON fingerprint
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate geometric fingerprint tests from STEP files",
        prog="step-fingerprint",
    )
    parser.add_argument("step_file", help="Path to the STEP file to fingerprint")
    parser.add_argument(
        "-o", "--output",
        help="Output pytest file path (e.g. test_my_part.py)",
    )
    parser.add_argument(
        "--json",
        help="Save fingerprint as JSON (for inspection or later use)",
    )
    parser.add_argument(
        "--prompt",
        help="Output prompt/guide file path (e.g. PROMPT.md)",
    )
    parser.add_argument(
        "--name", default=None,
        help="Human-readable part name (default: stem of STEP filename)",
    )
    parser.add_argument(
        "--fixture", default="part_under_test",
        help="pytest fixture name (default: part_under_test)",
    )
    parser.add_argument(
        "--axis", default="Z", choices=["X", "Y", "Z"],
        help="Primary axis of the part (default: Z)",
    )
    parser.add_argument(
        "--cross-sections", type=int, default=20,
        help="Number of cross-section slices (default: 20)",
    )
    parser.add_argument(
        "--radial-slices", type=int, default=15,
        help="Number of radial profile slices (default: 15)",
    )
    parser.add_argument(
        "--angles", type=int, default=12,
        help="Number of angular samples per radial slice (default: 12)",
    )

    # Tolerance overrides
    parser.add_argument("--volume-tol", type=float, default=1.0,
                        help="Volume tolerance %% (default: 1.0)")
    parser.add_argument("--area-tol", type=float, default=2.0,
                        help="Surface area tolerance %% (default: 2.0)")
    parser.add_argument("--bbox-tol", type=float, default=0.1,
                        help="Bounding box tolerance mm (default: 0.1)")
    parser.add_argument("--inertia-tol", type=float, default=2.0,
                        help="Inertia tolerance %% (default: 2.0)")
    parser.add_argument("--xs-area-tol", type=float, default=3.0,
                        help="Cross-section area tolerance %% (default: 3.0)")
    parser.add_argument("--xs-centroid-tol", type=float, default=0.2,
                        help="Cross-section centroid tolerance mm (default: 0.2)")
    parser.add_argument("--radial-tol", type=float, default=0.15,
                        help="Radial profile tolerance mm (default: 0.15)")

    args = parser.parse_args()

    step_path = Path(args.step_file)
    if not step_path.exists():
        print(f"Error: STEP file not found: {step_path}", file=sys.stderr)
        sys.exit(1)

    module_name = args.name or step_path.stem

    print(f"Analyzing {step_path}...")
    from .fingerprint import StepFingerprint
    fp = StepFingerprint.from_step(
        step_path,
        axis=args.axis,
        num_cross_sections=args.cross_sections,
        num_radial_slices=args.radial_slices,
        num_angles=args.angles,
    )

    va = fp.volume_and_area
    bb = fp.bounding_box
    print(f"  Volume: {va['volume']:.2f} mm³")
    print(f"  Surface area: {va['surface_area']:.2f} mm²")
    print(f"  Bounding box: {bb['size'][0]:.2f} × {bb['size'][1]:.2f} × {bb['size'][2]:.2f} mm")
    print(f"  Faces: {fp.topology['faces']}, Edges: {fp.topology['edges']}")

    if args.json:
        fp.to_json(args.json)
        print(f"  JSON fingerprint saved to: {args.json}")

    if args.output:
        from .generate import generate_test_file
        generate_test_file(
            fp,
            output_path=args.output,
            module_name=module_name,
            fixture_name=args.fixture,
            axis=args.axis,
            volume_tol_pct=args.volume_tol,
            area_tol_pct=args.area_tol,
            bbox_tol_mm=args.bbox_tol,
            inertia_tol_pct=args.inertia_tol,
            cross_section_area_tol_pct=args.xs_area_tol,
            cross_section_centroid_tol_mm=args.xs_centroid_tol,
            radial_tol_mm=args.radial_tol,
        )
        print(f"  Test file generated: {args.output}")

    if args.prompt:
        from .generate import generate_prompt
        generate_prompt(
            fp,
            output_path=args.prompt,
            module_name=module_name,
            axis=args.axis,
        )
        print(f"  Prompt file generated: {args.prompt}")

    if not args.output and not args.json and not args.prompt:
        # No output specified — print JSON to stdout
        print(fp.to_json())


if __name__ == "__main__":
    main()
