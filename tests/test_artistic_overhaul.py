"""
Tests for the overhauled artistic styles:
- Reaktions-Diffusion (Turing-Muster)
- Physarum-Simulation (Schleimpilz-Netzwerk)
- Differenzielles Wachstum (Differential Growth)
"""

import numpy as np
import pytest

from img2plot.core.reaction_diffusion import generate_reaction_diffusion
from img2plot.core.physarum_art import generate_physarum_art
from img2plot.core.diffgrowth_art import generate_diffgrowth_art
from img2plot.core.engine import PlotEngine, StrokePath
from img2plot.core.parameters import PlotParameters


@pytest.fixture
def synthetic_face_image():
    """Create a 160x160 synthetic portrait-like test image with distinct features."""
    img = np.ones((160, 160), dtype=np.float32)
    y, x = np.ogrid[:160, :160]
    # Head boundary
    head_mask = (x - 80) ** 2 + (y - 80) ** 2 < 55 ** 2
    img[head_mask] = 0.35
    # Left eye
    img[(x - 60) ** 2 + (y - 70) ** 2 < 10 ** 2] = 0.05
    # Right eye
    img[(x - 100) ** 2 + (y - 70) ** 2 < 10 ** 2] = 0.05
    # Mouth
    mouth_mask = ((x - 80) ** 2 + (y - 105) ** 2 < 24 ** 2) & (y > 105)
    img[mouth_mask] = 0.10
    return img


class TestReactionDiffusionOverhaul:
    def test_generates_valid_paths_and_captures_subject(self, synthetic_face_image):
        paths = generate_reaction_diffusion(
            synthetic_face_image,
            sim_resolution=120,
            iterations=100,
            feed_rate=0.037,
            kill_rate=0.060,
        )
        assert len(paths) > 0, "Reaction-Diffusion must generate stroke paths."
        for p in paths:
            assert isinstance(p, StrokePath)
            assert p.is_artistic is True
            assert len(p.points) >= 3

        # Verify paths are concentrated in the dark head region, not the pure white background
        head_pts = 0
        bg_pts = 0
        for p in paths:
            for x, y in p.points:
                dist_center = np.hypot(x - 80, y - 80)
                if dist_center <= 60:
                    head_pts += 1
                elif dist_center > 75:
                    bg_pts += 1

        assert head_pts > 0, "Paths must be present in the subject area."
        assert head_pts > bg_pts, "Path density must be significantly higher in the subject than background."

    def test_cancellation(self, synthetic_face_image):
        paths = generate_reaction_diffusion(
            synthetic_face_image,
            iterations=150,
            is_cancelled=lambda: True,
        )
        assert paths == []

    def test_small_image_fallback(self):
        tiny = np.ones((2, 2), dtype=np.float32)
        assert generate_reaction_diffusion(tiny) == []


class TestPhysarumSlimeMoldOverhaul:
    def test_generates_valid_paths_and_captures_subject(self, synthetic_face_image):
        paths = generate_physarum_art(
            synthetic_face_image,
            num_agents=1200,
            iterations=35,
            sim_resolution=120,
            contour_level=0.35,
        )
        assert len(paths) > 0, "Physarum must generate stroke paths."
        for p in paths:
            assert isinstance(p, StrokePath)
            assert p.is_artistic is True
            assert len(p.points) >= 3

        # Verify paths are concentrated in the dark head region
        head_pts = 0
        bg_pts = 0
        for p in paths:
            for x, y in p.points:
                dist_center = np.hypot(x - 80, y - 80)
                if dist_center <= 60:
                    head_pts += 1
                elif dist_center > 75:
                    bg_pts += 1

        assert head_pts > 0, "Physarum veins must trace subject features."
        assert head_pts > bg_pts, "Physarum veins must concentrate in subject, avoiding pure white margins."

    def test_cancellation(self, synthetic_face_image):
        paths = generate_physarum_art(
            synthetic_face_image,
            iterations=50,
            is_cancelled=lambda: True,
        )
        assert paths == []

    def test_small_image_fallback(self):
        tiny = np.ones((3, 3), dtype=np.float32)
        assert generate_physarum_art(tiny) == []


class TestDiffGrowthOverhaul:
    def test_generates_multiple_curves_covering_subject(self, synthetic_face_image):
        paths = generate_diffgrowth_art(
            synthetic_face_image,
            iterations=30,
            max_nodes=1200,
            split_dist=5.0,
            collision_radius=6.0,
        )
        # In the overhaul, differential growth MUST generate multiple feature curves across the image
        assert len(paths) >= 2, f"DiffGrowth must generate multiple curves, got {len(paths)}"

        total_pts = sum(len(p.points) for p in paths)
        assert total_pts >= 50, f"Expected rich curve node representation, got {total_pts} points"

        for p in paths:
            assert isinstance(p, StrokePath)
            assert p.is_artistic is True
            assert bool(p.svg_d), "DiffGrowth curves must have smooth spline svg_d"

        # Verify curves span the features
        head_pts = 0
        for p in paths:
            for x, y in p.points:
                dist_center = np.hypot(x - 80, y - 80)
                if dist_center <= 65:
                    head_pts += 1

        assert head_pts >= 40, "DiffGrowth curves must densely meander inside the subject."

    def test_cancellation(self, synthetic_face_image):
        paths = generate_diffgrowth_art(
            synthetic_face_image,
            iterations=40,
            is_cancelled=lambda: True,
        )
        assert paths == []

    def test_small_image_fallback(self):
        tiny = np.ones((2, 2), dtype=np.float32)
        assert generate_diffgrowth_art(tiny) == []


class TestEngineIntegrationArtisticModes:
    def test_engine_reaction_diffusion(self, synthetic_face_image):
        params = PlotParameters(
            artistic_mode="reaction_diffusion",
            rd_sim_resolution=100,
            rd_iterations=60,
        )
        engine = PlotEngine(params)
        res = engine.process_image(synthetic_face_image, is_preview=True)
        assert len(res.paths) > 0, "Engine must produce paths for reaction_diffusion"
        assert any(p.is_artistic for p in res.paths)

    def test_engine_physarum(self, synthetic_face_image):
        params = PlotParameters(
            artistic_mode="physarum",
            physarum_sim_res=100,
            physarum_iterations=30,
            physarum_agents=800,
        )
        engine = PlotEngine(params)
        res = engine.process_image(synthetic_face_image, is_preview=True)
        assert len(res.paths) > 0, "Engine must produce paths for physarum"
        assert any(p.is_artistic for p in res.paths)

    def test_engine_diffgrowth(self, synthetic_face_image):
        params = PlotParameters(
            artistic_mode="diffgrowth",
            diffgrowth_iterations=25,
            diffgrowth_max_nodes=800,
        )
        engine = PlotEngine(params)
        res = engine.process_image(synthetic_face_image, is_preview=True)
        assert len(res.paths) > 0, "Engine must produce paths for diffgrowth"
        assert any(p.is_artistic for p in res.paths)
