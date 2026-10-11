# Tasks Checklist: Artistic Styles Overhaul

## Phase 1: Overhaul Reaction-Diffusion (`reaction_diffusion.py`)

- [x] Task 1: Re-engineer `generate_reaction_diffusion` with anisotropic gradient-tangent diffusion and tone-masked isolines
  - Acceptance criteria:
    - Diffusion aligns with image edges using tangent vectors.
    - Seeding is concentrated in dark and high-contrast regions.
    - Contours are masked and density-weighted by image darkness (clean highlights, dense shadow labyrinths).
    - Output faithfully reflects the input image silhouette and tones.
  - Verification: Focused unit test with synthetic test image verifying edge alignment and path density correlation with darkness.

## Checkpoint: Reaction-Diffusion

- [x] Automated tests for reaction-diffusion pass.

## Phase 2: Overhaul Physarum Slime Mold (`physarum_art.py`)

- [x] Task 2: Re-engineer `generate_physarum_art` with edge/nutrient attractors and skeleton vein extraction
  - Acceptance criteria:
    - Agents steer toward nutrient rich (dark/edge) areas and align along flow directions.
    - Trail extraction uses ridge skeletonization / centerlines instead of hollow boundary loops (`find_contours`).
    - Output is a continuous branching vein network that clearly captures the input image.
  - Verification: Focused unit test with image verifying vein paths occupy dark feature areas.

## Checkpoint: Physarum

- [x] Automated tests for Physarum pass.

## Phase 3: Overhaul Differential Growth (`diffgrowth_art.py`)

- [x] Task 3: Re-engineer `generate_diffgrowth_art` with multi-curve feature seeding and density-driven growth
  - Acceptance criteria:
    - Multiple curves are seeded across image feature contours / shadow clusters (not a single center circle).
    - Splitting rate and collision packing are driven by local image darkness.
    - Output covers the subject with meandering coral/tissue folds that outline and shade the image.
  - Verification: Focused unit test verifying multiple curves cover image features.

## Checkpoint: Differential Growth

- [x] Automated tests for Differential Growth pass.

## Phase 4: Presets, Integration & Verification

- [x] Task 4: Harmonize default parameters in `parameters.py`, `presets.py`, and `randomizer.py`
  - Acceptance criteria:
    - Default presets produce immediate, recognizable results on sample images.
- [x] Task 5: Full test suite execution and verification
  - Acceptance criteria:
    - `uv run pytest` passes 100% (83/83 tests passing).
    - All 3 styles produce rich, recognizable plotter paths for test images.

## Final Checkpoint

- [x] All acceptance criteria met across all 3 styles.
- [x] Performance remains snappy (< 2s preview).
