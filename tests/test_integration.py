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
