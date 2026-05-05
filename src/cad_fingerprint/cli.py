"""CLI for cad-fingerprint.

Usage:
    cad-fingerprint reference.step                    # print JSON fingerprint
    cad-fingerprint reference.stl  -o test_part.py    # generate pytest file
    cad-fingerprint reference.step --json fp.json     # save JSON fingerprint
    cad-fingerprint compare ref.step impl.step        # compare two STEP files
"""

import argparse
import sys
from pathlib import Path


def _add_tolerance_args(parser):
    """Add shared tolerance arguments to a parser."""
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
    parser.add_argument("--xs-moment-tol", type=float, default=5.0,
                        help="Cross-section 2D moment tolerance %% (default: 5.0)")
    parser.add_argument("--radial-tol", type=float, default=0.15,
                        help="Radial profile tolerance mm (default: 0.15)")


def _add_analysis_args(parser):
    """Add shared analysis arguments to a parser."""
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


def _run_analyze(args):
    """Run the fingerprint analysis workflow."""
    cad_path = Path(args.cad_file)
    if not cad_path.exists():
        print(f"Error: file not found: {cad_path}", file=sys.stderr)
        sys.exit(1)

    suffix = cad_path.suffix.lower()
    is_stl = suffix == ".stl"
    is_step = suffix in (".step", ".stp")
    if not is_stl and not is_step:
        print(f"Error: unsupported format '{suffix}' (expected .step, .stp, or .stl)",
              file=sys.stderr)
        sys.exit(1)

    module_name = args.name or cad_path.stem

    print(f"Analyzing {cad_path}...")
    from .fingerprint import CadFingerprint
    if is_stl:
        fp = CadFingerprint.from_stl(
            cad_path,
            axis=args.axis,
            num_cross_sections=args.cross_sections,
            num_radial_slices=args.radial_slices,
            num_angles=args.angles,
        )
        print("  (STL mode: face inventory shows mesh stats only, no surface type classification)")
    else:
        fp = CadFingerprint.from_step(
            cad_path,
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
            cross_section_moment_tol_pct=args.xs_moment_tol,
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
        print(fp.to_json())


def _run_compare(args):
    """Compare two STEP files."""
    from .fingerprint import CadFingerprint
    from .compare import compare_fingerprints, format_comparison

    ref_path = Path(args.ref_step)
    impl_path = Path(args.impl_step)

    for p in (ref_path, impl_path):
        if not p.exists():
            print(f"Error: STEP file not found: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"Analyzing reference: {ref_path}...")
    ref_fp = CadFingerprint.from_step(
        ref_path,
        axis=args.axis,
        num_cross_sections=args.cross_sections,
        num_radial_slices=args.radial_slices,
        num_angles=args.angles,
    )

    print(f"Analyzing implementation: {impl_path}...")
    impl_fp = CadFingerprint.from_step(
        impl_path,
        axis=args.axis,
        num_cross_sections=args.cross_sections,
        num_radial_slices=args.radial_slices,
        num_angles=args.angles,
    )

    print()
    result = compare_fingerprints(
        ref_fp, impl_fp,
        volume_tol_pct=args.volume_tol,
        area_tol_pct=args.area_tol,
        bbox_tol_mm=args.bbox_tol,
        inertia_tol_pct=args.inertia_tol,
        cross_section_area_tol_pct=args.xs_area_tol,
        cross_section_centroid_tol_mm=args.xs_centroid_tol,
        radial_tol_mm=args.radial_tol,
    )
    print(format_comparison(result))

    if result["summary"]["fail"] > 0:
        sys.exit(1)


def main():
    # Check if first arg is "compare" for backward compatibility
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        parser = argparse.ArgumentParser(
            description="Compare two STEP files geometrically",
            prog="cad-fingerprint compare",
        )
        parser.add_argument("_cmd", help=argparse.SUPPRESS)  # consume "compare"
        parser.add_argument("ref_step", help="Reference STEP file")
        parser.add_argument("impl_step", help="Implementation STEP file to compare")
        _add_analysis_args(parser)
        _add_tolerance_args(parser)
        args = parser.parse_args()
        _run_compare(args)
    else:
        parser = argparse.ArgumentParser(
            description="Generate geometric fingerprint tests from STEP or STL files",
            prog="cad-fingerprint",
        )
        parser.add_argument("cad_file", help="Path to the STEP or STL file to fingerprint")
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
            help="Human-readable part name (default: stem of input filename)",
        )
        parser.add_argument(
            "--fixture", default="part_under_test",
            help="pytest fixture name (default: part_under_test)",
        )
        _add_analysis_args(parser)
        _add_tolerance_args(parser)
        args = parser.parse_args()
        _run_analyze(args)


if __name__ == "__main__":
    main()
