# Implementation Plan: Overhaul of Reaction-Diffusion, Physarum, and Differential Growth Artistic Styles

## Overview

The artistic styles "Reaktions-Diffusion (Turing-Muster)", "Physarum-Simulation (Schleimpilz-Netzwerk)", and "Differenzielles Wachstum (Differential Growth)" currently produce outputs that do not resemble the input image. This overhaul re-engineers all three algorithms with image-faithful generative mechanics so that they accurately reflect the input image's contours, tonal values, and anatomy while preserving their unique generative aesthetics for pen plotters.

## Root Cause Analysis Summary

1. **Reaction-Diffusion (`reaction_diffusion.py`):**
   - Uses isotropic Laplacian diffusion with random noise seeding everywhere, ignoring image gradient tangents.
   - Global isoline extraction on chemical `V` without edge-alignment or tone-based masking populates empty backgrounds and fails to convey image features.
   - *Fix:* Anisotropic diffusion oriented along image gradient tangents, feature-weighted chemical seeding, stable Gray-Scott parameter modulation, and tonal-masked isoline extraction.
2. **Physarum Slime Mold (`physarum_art.py`):**
   - Uses `find_contours` on a blurred scalar trail map, creating hollow bubble rings / boundary loops around agent clusters instead of the actual vein network.
   - Agents run for only 40 steps with random orientations and no edge flow guidance.
   - *Fix:* Sensory steering guided by image darkness, edge magnitude, and tangent flow; proper vein centerline/ridge skeleton extraction (or trajectory tracing) into continuous plotter paths.
3. **Differential Growth (`diffgrowth_art.py`):**
   - Seeds a single small circle in the exact center of the canvas and returns exactly 1 closed loop, ignoring image features.
   - *Fix:* Multi-curve differential growth seeded on prominent image contours and dark feature regions, with splitting rate and collision repulsion modulated by local image luminance so curves meander and pack densely in shadows.

## Architecture Decisions

- **Consistency with Existing Engine Architecture:** Keep input/output signatures compatible with `PlotEngine.process_image()`, returning `List[StrokePath]`.
- **Performance & Responsiveness:** Simulation grids and node counts are chosen so execution finishes in < 2.0s during preview, with cooperative `is_cancelled()` checks.
- **Plotter Compatibility:** Outputs are clean, smooth vector paths (`StrokePath`) suitable for pen plotters and SVG export.

## Task List

### Phase 1: Overhaul Reaction-Diffusion (`reaction_diffusion.py`)

- [ ] Task 1: Implement anisotropic Turing diffusion guided by image gradient tangents and tone-masked isolines.

### Checkpoint 1: Reaction-Diffusion

- [ ] Verify Reaction-Diffusion clearly resembles input image tones and contours in automated tests and visual verification.

### Phase 2: Overhaul Physarum Slime Mold Simulation (`physarum_art.py`)

- [ ] Task 2: Implement edge-guided Physarum multi-agent network with ridge skeleton / vein centerline path extraction.

### Checkpoint 2: Physarum Slime Mold

- [ ] Verify Physarum creates authentic vein networks that trace the input image structure.

### Phase 3: Overhaul Differential Growth (`diffgrowth_art.py`)

- [ ] Task 3: Implement feature-seeded multi-curve differential growth modulated by local image density.

### Checkpoint 3: Differential Growth

- [ ] Verify Differential Growth covers image features with intricate meandering lines instead of a single central circle.

### Phase 4: Integration, Presets, GUI & Verification

- [ ] Task 4: Tune default parameters in `core/parameters.py`, `core/presets.py`, and `core/randomizer.py`.
- [ ] Task 5: Comprehensive automated test suite in `tests/test_artistic_overhaul.py` and regression testing.

### Checkpoint 4: Complete

- [ ] All 71+ existing tests pass.
- [ ] All new tests pass.
- [ ] Visual output reflects test images cleanly.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| ------ | -------- | ------------ |
| Simulation slowdown on high-resolution images | Medium | Run simulation on adaptive resolution grid (160–240px) and scale paths to original dimensions. |
| Numerical instability in anisotropic Euler steps | High | Bound diffusion coefficients and clamp concentration arrays at every timestep. |
| Complex node KDTree queries in differential growth | Medium | Use multi-seed spatial partitioning and cap total nodes per curve with adaptive relaxation. |
