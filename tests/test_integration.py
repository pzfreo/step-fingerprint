"""Integration tests for analyze_step and analyze_stl.

Requires build123d and OCC. Marked with pytest.mark.integration
but run by default (no special flag needed — they're just slower).
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")
PEGHEAD_STEP = os.path.join(EXAMPLES_DIR, "peghead7mm.step")


# ── analyze_step ─────────────────────────────────────────────────────

@pytest.mark.skipif(not os.path.exists(PEGHEAD_STEP), reason="peghead7mm.step not found")
class TestAnalyzeStep:
    def setup_method(self):
        from cad_fingerprint.analyze import analyze_step
        self.result = analyze_step(PEGHEAD_STEP)

    def test_returns_all_keys(self):
        expected = {
            "file", "source_format", "bounding_box", "volume_and_area",
            "moments_of_inertia", "topology", "face_inventory",
            "cross_sections", "radial_profile", "build_quality", "description",
        }
        assert expected.issubset(self.result.keys())

    def test_source_format(self):
        assert self.result["source_format"] == "step"

    def test_volume(self):
        # peghead: 375.64 mm³ from reference test file header
        vol = self.result["volume_and_area"]["volume"]
        assert abs(vol - 375.64) / 375.64 < 0.01

    def test_bounding_box_positive(self):
        bb = self.result["bounding_box"]
        for dim in bb["size"]:
            assert dim > 0

    def test_face_inventory_has_cylinders(self):
        faces = self.result["face_inventory"]
        types = {f["type"] for f in faces}
        assert "Cylinder" in types, f"No cylinders found; types = {types}"

    def test_cross_sections_count(self):
        assert len(self.result["cross_sections"]) == 20

    def test_cross_sections_positive_area(self):
        areas = [cs["area"] for cs in self.result["cross_sections"]]
        assert any(a > 0 for a in areas), "All cross-section areas are zero"

    def test_radial_profile_count(self):
        # 15 slices × 12 angles
        assert len(self.result["radial_profile"]) == 15
        for rp in self.result["radial_profile"]:
            assert len(rp["radii"]) == 12

    def test_inertia_diagonal_positive(self):
        moi = self.result["moments_of_inertia"]
        assert moi["Ixx"] > 0
        assert moi["Iyy"] > 0
        assert moi["Izz"] > 0

    def test_build_quality_single_solid(self):
        bq = self.result["build_quality"]
        assert bq["solid_count"] == 1
        assert bq["is_valid"] is True


# ── analyze_stl ──────────────────────────────────────────────────────

class TestAnalyzeStlBox:
    """Analyze a 10×20×30 box exported from build123d as STL.

    A rectangular box has flat faces — the triangulation is exact,
    so volume and surface area should match the analytical values tightly.
    """

    @pytest.fixture(autouse=True)
    def create_and_analyze(self, tmp_path):
        from build123d import Box, export_stl
        from cad_fingerprint.analyze import analyze_stl

        stl_path = str(tmp_path / "box.stl")
        box = Box(10, 20, 30)
        export_stl(box, stl_path, tolerance=1e-4)

        self.result = analyze_stl(stl_path)

    def test_returns_all_keys(self):
        expected = {
            "file", "source_format", "bounding_box", "volume_and_area",
            "moments_of_inertia", "topology", "face_inventory",
            "cross_sections", "radial_profile", "build_quality",
        }
        assert expected.issubset(self.result.keys())

    def test_source_format(self):
        assert self.result["source_format"] == "stl"

    def test_volume(self):
        # 10×20×30 = 6000 mm³; flat faces → exact triangulation
        vol = self.result["volume_and_area"]["volume"]
        assert abs(vol - 6000.0) < 0.1

    def test_surface_area(self):
        # 2*(10*20 + 10*30 + 20*30) = 2200 mm²
        area = self.result["volume_and_area"]["surface_area"]
        assert abs(area - 2200.0) < 0.1

    def test_bounding_box(self):
        bb = self.result["bounding_box"]
        sizes = sorted(bb["size"])
        assert abs(sizes[0] - 10) < 0.01
        assert abs(sizes[1] - 20) < 0.01
        assert abs(sizes[2] - 30) < 0.01

    def test_center_of_mass_at_origin(self):
        com = self.result["volume_and_area"]["center_of_mass"]
        for v in com:
            assert abs(v) < 0.01, f"CoM component {v} not near origin"

    def test_inertia_diagonal(self):
        # Ixx = (M/12)*(b²+c²) about CoM; M=6000, a=10, b=20, c=30
        moi = self.result["moments_of_inertia"]
        expected_Ixx = (6000 / 12) * (20**2 + 30**2)   # 650000
        expected_Iyy = (6000 / 12) * (10**2 + 30**2)   # 500000
        expected_Izz = (6000 / 12) * (10**2 + 20**2)   # 250000
        assert abs(moi["Ixx"] - expected_Ixx) / expected_Ixx < 0.001
        assert abs(moi["Iyy"] - expected_Iyy) / expected_Iyy < 0.001
        assert abs(moi["Izz"] - expected_Izz) / expected_Izz < 0.001

    def test_products_of_inertia_near_zero(self):
        moi = self.result["moments_of_inertia"]
        # Box centered at origin — all products of inertia should vanish
        assert abs(moi["Ixy"]) < 1.0
        assert abs(moi["Ixz"]) < 1.0
        assert abs(moi["Iyz"]) < 1.0

    def test_face_inventory_is_mesh(self):
        faces = self.result["face_inventory"]
        assert len(faces) == 1
        assert faces[0]["type"] == "mesh"
        assert faces[0]["triangle_count"] > 0

    def test_cross_sections_count(self):
        assert len(self.result["cross_sections"]) == 20

    def test_cross_sections_area(self):
        # Cross-sections along Z: each should be 10×20 = 200 mm²
        for cs in self.result["cross_sections"]:
            assert abs(cs["area"] - 200.0) < 1.0, (
                f"Cross-section at Z={cs['position']}: area={cs['area']:.2f}, expected ~200"
            )

    def test_radial_profile_has_data(self):
        assert len(self.result["radial_profile"]) == 15
        # At least some radii should be non-None
        any_hit = any(
            r is not None
            for rp in self.result["radial_profile"]
            for r in rp["radii"].values()
        )
        assert any_hit, "All radial profile rays missed the shape"


# ── surface mesh + Hausdorff distance ────────────────────────────────

class TestSurfaceMeshAndHausdorff:
    """Mesh capture and end-to-end Hausdorff distance on real B-rep parts."""

    def test_step_fingerprint_carries_a_mesh(self):
        from cad_fingerprint.analyze import analyze_step, decoded_mesh

        if not os.path.exists(PEGHEAD_STEP):
            pytest.skip("peghead7mm.step not found")
        mesh = analyze_step(PEGHEAD_STEP)["surface_mesh"]
        assert mesh["triangle_count"] > 100
        assert mesh["deflection"] > 0
        vertices, triangles = decoded_mesh(mesh)
        assert len(vertices) == mesh["vertex_count"]
        assert len(triangles) == mesh["triangle_count"]
        assert max(max(t) for t in triangles) < len(vertices)

    def test_mesh_covers_the_whole_part(self):
        """Every mesh vertex must sit inside the part's bounding box."""
        from build123d import Box
        from cad_fingerprint.analyze import decoded_mesh, mesh_shape

        box = Box(10, 20, 30)
        vertices, _ = decoded_mesh(mesh_shape(box))
        for x, y, z in vertices:
            assert abs(x) <= 5.001 and abs(y) <= 10.001 and abs(z) <= 15.001

    def test_identical_parts_have_zero_deviation(self):
        from build123d import Box
        from cad_fingerprint.analyze import decoded_mesh, mesh_shape
        from cad_fingerprint.hausdorff import hausdorff_distance

        mesh = decoded_mesh(mesh_shape(Box(10, 20, 30)))
        result = hausdorff_distance(mesh, mesh, samples=500)
        assert result["hausdorff"] < 1e-6

    def test_deviation_matches_a_known_offset(self):
        """A 0.4 mm shift must be measured as a 0.4 mm deviation."""
        from build123d import Box, Pos
        from cad_fingerprint.analyze import decoded_mesh, mesh_shape
        from cad_fingerprint.hausdorff import hausdorff_distance

        reference = decoded_mesh(mesh_shape(Box(10, 20, 30)))
        shifted = decoded_mesh(mesh_shape(Pos(0.4, 0, 0) * Box(10, 20, 30)))
        result = hausdorff_distance(reference, shifted, samples=1000)
        assert abs(result["hausdorff"] - 0.4) < 0.01

    def test_curved_part_deviation_below_mesh_resolution(self):
        """Two meshings of the same cylinder agree to within the deflection."""
        from build123d import Cylinder
        from cad_fingerprint.analyze import decoded_mesh, mesh_shape
        from cad_fingerprint.hausdorff import hausdorff_distance

        part = Cylinder(radius=8, height=20)
        coarse = decoded_mesh(mesh_shape(part, deflection=0.05))
        fine = decoded_mesh(mesh_shape(part, deflection=0.01))
        result = hausdorff_distance(coarse, fine, samples=1000)
        assert result["hausdorff"] < 0.06
        assert result["mean"] < 0.02


class TestGeneratedHausdorffTests:
    """The embedded Hausdorff code in generated test files actually runs."""

    @pytest.fixture(scope="class")
    def generated(self, tmp_path_factory):
        from build123d import Box, export_step
        from cad_fingerprint import CadFingerprint
        from cad_fingerprint.generate import generate_test_file

        step_path = str(tmp_path_factory.mktemp("gen") / "box.step")
        export_step(Box(10, 20, 30), step_path)
        fp = CadFingerprint.from_step(step_path)
        source = generate_test_file(fp, module_name="box")
        namespace = {}
        exec(compile(source, "generated_test_box.py", "exec"), namespace)
        return namespace

    def test_emits_reference_mesh_and_tests(self, generated):
        assert generated["REF_MESH"]["triangle_count"] >= 12
        assert generated["HAUSDORFF_SAMPLES"] > 0
        assert "TestSurfaceDeviation" in generated

    def test_reference_part_has_no_deviation(self, generated):
        from build123d import Box

        result = generated["_hausdorff_vs_reference"](Box(10, 20, 30))
        assert result["hausdorff"] < 1e-3
        assert result["mean"] < 1e-3

    def test_wrong_part_is_caught(self, generated):
        from build123d import Box

        result = generated["_hausdorff_vs_reference"](Box(10, 20, 30.8))
        # 0.8 mm longer, centred — each end face is 0.4 mm out
        assert abs(result["hausdorff"] - 0.4) < 0.02

    def test_results_are_cached_across_fixture_rebuilds(self, generated):
        """A function-scoped fixture rebuilds the part for every test.

        The cache has to key on geometry, not object identity, or the max and
        mean tests each pay for the whole measurement.
        """
        from build123d import Box

        first = generated["_hausdorff_vs_reference"](Box(10, 20, 30))
        second = generated["_hausdorff_vs_reference"](Box(10, 20, 30))
        assert second is first

    def test_cache_distinguishes_different_parts(self, generated):
        from build123d import Box

        same = generated["_hausdorff_vs_reference"](Box(10, 20, 30))
        other = generated["_hausdorff_vs_reference"](Box(10, 20, 30.8))
        assert other is not same
        assert other["hausdorff"] > same["hausdorff"]

    def test_fixture_part_is_not_mutated(self, generated):
        """Meshing the part under test must not alter the caller's shape."""
        from build123d import Box
        from OCP.BRep import BRep_Tool
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopLoc import TopLoc_Location
        from OCP.TopoDS import TopoDS

        part = Box(10, 20, 30)

        def triangulated_faces():
            count = 0
            explorer = TopExp_Explorer(part.wrapped, TopAbs_FACE)
            while explorer.More():
                face = TopoDS.Face_s(explorer.Current())
                if BRep_Tool.Triangulation_s(face, TopLoc_Location()) is not None:
                    count += 1
                explorer.Next()
            return count

        before = triangulated_faces()
        generated["_hausdorff_vs_reference"](part)
        assert triangulated_faces() == before


class TestCompareHausdorff:
    """The compare command reports surface deviation alongside the rest."""

    @staticmethod
    def _fingerprint(part, tmp_path, name, **kwargs):
        from build123d import export_step
        from cad_fingerprint import CadFingerprint

        path = str(tmp_path / f"{name}.step")
        export_step(part, path)
        return CadFingerprint.from_step(path, **kwargs)

    def test_reports_deviation_of_a_bad_part(self, tmp_path):
        from build123d import Box
        from cad_fingerprint.compare import compare_fingerprints, format_comparison

        ref = self._fingerprint(Box(10, 20, 30), tmp_path, "ref")
        impl = self._fingerprint(Box(10, 20, 30.8), tmp_path, "impl")
        result = compare_fingerprints(ref, impl, hausdorff_samples=500)

        h = result["hausdorff"]
        # Each end face is 0.4 mm out — past the 0.3 mm tolerance but
        # within 2x, which the report grades as "close".
        assert abs(h["max"] - 0.4) < 0.02
        assert h["status"] == "close"
        assert "Hausdorff" in format_comparison(result)

    def test_grossly_wrong_part_fails(self, tmp_path):
        from build123d import Box
        from cad_fingerprint.compare import compare_fingerprints

        ref = self._fingerprint(Box(10, 20, 30), tmp_path, "big_ref")
        impl = self._fingerprint(Box(10, 20, 32), tmp_path, "big_impl")
        result = compare_fingerprints(ref, impl, hausdorff_samples=500)
        assert abs(result["hausdorff"]["max"] - 1.0) < 0.02
        assert result["hausdorff"]["status"] == "fail"
        assert result["summary"]["fail"] >= 1

    def test_matching_parts_pass(self, tmp_path):
        from build123d import Box
        from cad_fingerprint.compare import compare_fingerprints

        ref = self._fingerprint(Box(10, 20, 30), tmp_path, "a")
        impl = self._fingerprint(Box(10, 20, 30), tmp_path, "b")
        result = compare_fingerprints(ref, impl, hausdorff_samples=500)
        assert result["hausdorff"]["status"] == "pass"
        assert result["hausdorff"]["max"] < 1e-3

    def test_skipped_when_meshes_were_not_captured(self, tmp_path):
        from build123d import Box
        from cad_fingerprint.compare import compare_fingerprints, format_comparison

        ref = self._fingerprint(Box(10, 20, 30), tmp_path, "c", capture_mesh=False)
        impl = self._fingerprint(Box(10, 20, 30), tmp_path, "d", capture_mesh=False)
        result = compare_fingerprints(ref, impl)
        assert "hausdorff" not in result
        assert "Hausdorff" not in format_comparison(result)


class TestMeshResolutionLimits:
    """Mesh resolution has to bound what the generated tolerances claim."""

    def test_coarse_reference_raises_the_tolerances(self, tmp_path):
        """A mesh too coarse to resolve 0.3 mm must not assert 0.3 mm."""
        from build123d import Sphere, export_step
        from cad_fingerprint import CadFingerprint
        from cad_fingerprint.generate import generate_test_file
        from cad_fingerprint.hausdorff import tolerance_floor

        path = str(tmp_path / "coarse.step")
        export_step(Sphere(radius=10), path)
        fp = CadFingerprint.from_step(path, mesh_deflection=1.0)
        floor = tolerance_floor(fp.surface_mesh)
        assert floor > 0.3, "1 mm facets on a 10 mm ball should exceed 0.3 mm"

        source = generate_test_file(fp, module_name="coarse")
        assert "tolerances were raised" in source
        assert f"< {floor}," in source

        namespace = {}
        exec(compile(source, "coarse_test.py", "exec"), namespace)
        assert namespace["REF_MESH"]["resolution"] > 0.1

    def test_flat_part_keeps_its_tolerances_however_coarse(self, tmp_path):
        """A box's facets are exact — deflection is irrelevant to its error."""
        from build123d import Box, export_step
        from cad_fingerprint import CadFingerprint
        from cad_fingerprint.generate import generate_test_file

        path = str(tmp_path / "flat.step")
        export_step(Box(10, 20, 30), path)
        fp = CadFingerprint.from_step(path, mesh_deflection=2.0)
        assert fp.surface_mesh["resolution"] == 0.0

        source = generate_test_file(fp, module_name="flat")
        assert "tolerances were raised" not in source
        assert "< 0.3," in source

    def test_finer_deflection_tightens_the_angular_limit(self, tmp_path):
        """Asking for a finer mesh has to actually produce a finer one.

        On blends and small fillets the angular limit, not the linear one,
        is what bounds the chord error.
        """
        from build123d import Sphere, export_step
        from cad_fingerprint import CadFingerprint

        path = str(tmp_path / "ball.step")
        export_step(Sphere(radius=10), path)
        default = CadFingerprint.from_step(path).surface_mesh
        finer = CadFingerprint.from_step(
            path, mesh_deflection=default["deflection"] / 10,
            max_mesh_triangles=200000,
        ).surface_mesh

        assert finer["angular_deflection"] < default["angular_deflection"]
        assert finer["triangle_count"] > default["triangle_count"]
        assert finer["resolution"] < default["resolution"]

    def test_triangle_budget_is_configurable(self, tmp_path):
        from build123d import Sphere, export_step
        from cad_fingerprint import CadFingerprint

        path = str(tmp_path / "budget.step")
        export_step(Sphere(radius=10), path)
        small = CadFingerprint.from_step(path, max_mesh_triangles=500).surface_mesh
        assert small["triangle_count"] <= 500

    def test_fine_reference_keeps_the_requested_tolerances(self, tmp_path):
        from build123d import Box, export_step
        from cad_fingerprint import CadFingerprint
        from cad_fingerprint.generate import generate_test_file

        path = str(tmp_path / "fine.step")
        export_step(Box(10, 20, 30), path)
        fp = CadFingerprint.from_step(path)
        source = generate_test_file(fp, module_name="fine")

        assert "tolerances were raised" not in source
        assert "< 0.3," in source
        assert "< 0.05," in source

    def test_stl_facet_error_is_measured(self, tmp_path):
        """A curved STL is itself an approximation — that must be recorded.

        Otherwise a coarsely exported reference holds implementations to a
        tolerance its own facets cannot meet.
        """
        from build123d import Box, Sphere, export_stl
        from cad_fingerprint.analyze import analyze_stl

        ball = str(tmp_path / "ball_res.stl")
        block = str(tmp_path / "block_res.stl")
        export_stl(Sphere(radius=10), ball)
        export_stl(Box(10, 20, 30), block)

        # Curved: facets are chords, so they carry a real error
        assert analyze_stl(ball)["surface_mesh"]["resolution"] > 0.0
        # Flat: a box's facets are exact, and its sharp edges are features,
        # not chord error
        assert analyze_stl(block)["surface_mesh"]["resolution"] == 0.0

    def test_stl_deflection_clusters_the_reference_mesh(self, tmp_path):
        """--mesh-deflection has to do something for STL, not silently pass."""
        from build123d import Sphere, export_stl
        from cad_fingerprint.analyze import analyze_stl

        path = str(tmp_path / "ball.stl")
        export_stl(Sphere(radius=10), path, tolerance=0.01)

        as_supplied = analyze_stl(path)["surface_mesh"]
        clustered = analyze_stl(path, mesh_deflection=1.5)["surface_mesh"]

        assert clustered["triangle_count"] < as_supplied["triangle_count"]
        assert clustered["cluster_cell"] == 1.5
        assert clustered["resolution"] == 1.5

    def test_stl_triangle_budget_is_enforced(self, tmp_path):
        from build123d import Sphere, export_stl
        from cad_fingerprint.analyze import decoded_mesh, load_stl, mesh_shape
        from cad_fingerprint.hausdorff import hausdorff_distance

        path = str(tmp_path / "dense.stl")
        export_stl(Sphere(radius=10), path, tolerance=0.005)
        face = load_stl(path)

        full = mesh_shape(face, remesh=False, max_triangles=10**9)
        capped = mesh_shape(face, remesh=False, max_triangles=1500)
        assert full["triangle_count"] > 1500
        assert capped["triangle_count"] <= 1500

        # Decimation must stay within the resolution it reports
        deviation = hausdorff_distance(
            decoded_mesh(full), decoded_mesh(capped), samples=800,
        )
        assert deviation["hausdorff"] < capped["resolution"] * 2


class TestEmptyMesh:
    """A shape with no triangulation must degrade gracefully, not report inf."""

    def test_generator_skips_an_empty_mesh(self, tmp_path):
        from build123d import Box, export_step
        from cad_fingerprint import CadFingerprint
        from cad_fingerprint.generate import generate_test_file

        path = str(tmp_path / "empty.step")
        export_step(Box(10, 20, 30), path)
        fp = CadFingerprint.from_step(path)
        fp.surface_mesh = {"encoding": "q16", "vertex_count": 0,
                           "triangle_count": 0, "bbox_min": (0.0, 0.0, 0.0),
                           "bbox_max": (0.0, 0.0, 0.0), "index_bits": 16,
                           "vertices": "", "triangles": "", "deflection": 0.1,
                           "resolution": 0.1}
        source = generate_test_file(fp, module_name="empty")
        assert "REF_MESH" not in source
        assert "TestSurfaceDeviation" not in source

    def test_compare_skips_an_empty_mesh(self, tmp_path):
        from build123d import Box, export_step
        from cad_fingerprint import CadFingerprint
        from cad_fingerprint.compare import compare_fingerprints

        path = str(tmp_path / "cmp.step")
        export_step(Box(10, 20, 30), path)
        ref = CadFingerprint.from_step(path)
        impl = CadFingerprint.from_step(path)
        impl.surface_mesh = dict(impl.surface_mesh, triangle_count=0)
        assert "hausdorff" not in compare_fingerprints(ref, impl)


class TestCompareMeanTolerance:
    """--hausdorff-mean-tol has to reach compare, not just the generator."""

    def test_mean_tolerance_is_applied(self, tmp_path):
        from build123d import Box, export_step
        from cad_fingerprint import CadFingerprint
        from cad_fingerprint.compare import compare_fingerprints

        ref_path = str(tmp_path / "a.step")
        impl_path = str(tmp_path / "b.step")
        export_step(Box(10, 20, 30), ref_path)
        export_step(Box(10, 20, 31), impl_path)
        ref = CadFingerprint.from_step(ref_path)
        impl = CadFingerprint.from_step(impl_path)

        relaxed = compare_fingerprints(ref, impl, hausdorff_mean_tol_mm=1.0,
                                       hausdorff_samples=500)
        strict = compare_fingerprints(ref, impl, hausdorff_mean_tol_mm=0.001,
                                      hausdorff_samples=500)
        assert relaxed["hausdorff"]["mean_status"] == "pass"
        assert strict["hausdorff"]["mean_status"] == "fail"
        assert strict["hausdorff"]["status"] == "fail"

    def test_mean_tolerance_is_never_below_the_mesh_resolution(self, tmp_path):
        from build123d import Sphere, export_step
        from cad_fingerprint import CadFingerprint
        from cad_fingerprint.compare import compare_fingerprints

        path = str(tmp_path / "res.step")
        export_step(Sphere(radius=10), path)
        ref = CadFingerprint.from_step(path, mesh_deflection=1.0)
        impl = CadFingerprint.from_step(path, mesh_deflection=1.0)
        result = compare_fingerprints(ref, impl, hausdorff_mean_tol_mm=0.0001,
                                      hausdorff_samples=500)
        assert result["hausdorff"]["mean_tolerance"] > 0.0001
        assert result["hausdorff"]["resolution_limited"] is True
