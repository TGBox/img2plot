"""
Core vectorization engine for img2plot.
Transforms raster images into artistic line drawings and vector paths.
"""

from __future__ import annotations
import os
import math
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable
import numpy as np
from PIL import Image
import scipy.ndimage
import skimage.exposure
import skimage.draw

from .parameters import PlotParameters
from .bezier import Point, CubicSegment, fit_cubic_spline, segments_to_svg_path, discretize_segments
from .hatching import generate_hatching

Point2D = Tuple[float, float]

# Bounded single-entry cache for expensive preprocessing and gradient fields
_PREPROCESS_CACHE: dict = {}


@dataclass
class StrokePath:
    """Represents a single pen stroke (straight line, polyline, or Bezier curve)."""
    points: List[Point2D]
    is_bezier: bool = False
    cubic_segments: List[CubicSegment] = field(default_factory=list)
    svg_d: str = ""
    is_hatch: bool = False
    is_shape: bool = False
    shape_metadata: dict = field(default_factory=dict)

    def length(self) -> float:
        """Calculate approximate length in pixels."""
        if self.is_bezier and self.cubic_segments:
            pts = discretize_segments(self.cubic_segments, steps_per_segment=4)
        else:
            pts = self.points

        if len(pts) < 2:
            return 0.0
        total = 0.0
        for i in range(len(pts) - 1):
            total += math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        return total

    def __iter__(self):
        """Allows unpacking as (start_pt, end_pt) for backward compatibility."""
        if len(self.points) >= 2:
            return iter((self.points[0], self.points[-1]))
        elif len(self.points) == 1:
            return iter((self.points[0], self.points[0]))
        return iter(())


@dataclass
class PlotStats:
    """Statistics about generated plot paths."""
    total_strokes: int = 0
    contour_strokes: int = 0
    hatch_strokes: int = 0
    shape_strokes: int = 0
    total_length_px: float = 0.0
    pen_up_distance_px: float = 0.0
    elapsed_time_sec: float = 0.0
    image_width: int = 0
    image_height: int = 0


@dataclass
class EngineResult:
    """Container for complete vectorization results."""
    paths: List[StrokePath]
    width: int
    height: int
    preprocessed_gray: np.ndarray  # float 0..1
    sobel_magnitude: np.ndarray    # float 0..1
    stats: PlotStats


def trace_line_from_gradient(
    mag: np.ndarray,
    px: int,
    py: int,
    grad_x: np.ndarray,
    grad_y: np.ndarray,
    line_continue_thresh: float,
    max_curve_angle_deg: float,
    lpf_atk: float
) -> Tuple[List[Point2D], float]:
    """
    Trace along the edge perpendicular to the local gradient direction.
    Returns:
        (sampled_points, total_length)
    """
    h, w = mag.shape
    initial_angle = math.atan2(grad_y[py, px], grad_x[py, px])
    max_angle_diff = math.radians(max_curve_angle_deg)
    center_val = mag[py, px]
    thresh_val = line_continue_thresh * center_val

    # --- Left arm ---
    left_points: List[Point2D] = []
    len_left = 0
    mangle = initial_angle
    curr_x, curr_y = float(px), float(py)

    while True:
        len_left += 1
        curr_x = px + len_left * math.sin(mangle)
        curr_y = py - len_left * math.cos(mangle)

        if not (0 < curr_x < w - 1 and 0 < curr_y < h - 1):
            break

        ix = int(round(curr_x))
        iy = int(round(curr_y))
        if not (0 <= ix < w and 0 <= iy < h):
            break

        val = float(mag[iy, ix])
        if val <= thresh_val:
            break

        cangle = math.atan2(grad_y[iy, ix], grad_x[iy, ix])
        mangle = mangle * (1.0 - lpf_atk) + cangle * lpf_atk

        if abs(initial_angle - mangle) > max_angle_diff:
            break

        left_points.append((curr_x, curr_y))

    # --- Right arm ---
    right_points: List[Point2D] = []
    len_right = 0
    mangle = initial_angle
    curr_x, curr_y = float(px), float(py)

    while True:
        len_right += 1
        curr_x = px - len_right * math.sin(mangle)
        curr_y = py + len_right * math.cos(mangle)

        if not (0 < curr_x < w - 1 and 0 < curr_y < h - 1):
            break

        ix = int(round(curr_x))
        iy = int(round(curr_y))
        if not (0 <= ix < w and 0 <= iy < h):
            break

        val = float(mag[iy, ix])
        if val <= thresh_val:
            break

        cangle = math.atan2(grad_y[iy, ix], grad_x[iy, ix])
        mangle = mangle * (1.0 - lpf_atk) + cangle * lpf_atk

        if abs(initial_angle - mangle) > max_angle_diff:
            break

        right_points.append((curr_x, curr_y))

    total_len = len_left + len_right + 1.0
    full_path: List[Point2D] = list(reversed(left_points)) + [(float(px), float(py))] + right_points
    return full_path, total_len


def optimize_pen_travel(paths: List[StrokePath]) -> Tuple[List[StrokePath], float]:
    """
    Fast nearest-neighbor sorting of stroke paths to minimize pen-up travel distance
    using spatial bucket hashing for O(N) performance on large path sets.
    """
    if len(paths) <= 1:
        return paths, 0.0

    n = len(paths)
    xs = [p.points[0][0] for p in paths] + [p.points[-1][0] for p in paths]
    ys = [p.points[0][1] for p in paths] + [p.points[-1][1] for p in paths]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(1.0, max(max_x - min_x, max_y - min_y))

    cell_size = max(10.0, span / max(10, int(math.sqrt(n))))

    from collections import defaultdict
    grid = defaultdict(set)
    for idx, path in enumerate(paths):
        s_cx = int(path.points[0][0] / cell_size)
        s_cy = int(path.points[0][1] / cell_size)
        e_cx = int(path.points[-1][0] / cell_size)
        e_cy = int(path.points[-1][1] / cell_size)
        grid[(s_cx, s_cy)].add(idx)
        grid[(e_cx, e_cy)].add(idx)

    visited = [False] * n
    sorted_paths: List[StrokePath] = []
    curr_pos: Point2D = (0.0, 0.0)
    total_pen_up = 0.0

    for _ in range(n):
        c_cx = int(curr_pos[0] / cell_size)
        c_cy = int(curr_pos[1] / cell_size)

        best_idx = -1
        best_dist = float("inf")
        best_reverse = False

        # Search in expanding rings of grid cells
        max_ring = 3
        found_in_ring = False
        for ring in range(0, max_ring + 1):
            ring_candidates = set()
            for dx in range(-ring, ring + 1):
                dy_vals = (-ring, ring) if ring > 0 else (0,)
                for dy in dy_vals:
                    ring_candidates.update(grid.get((c_cx + dx, c_cy + dy), ()))
                    ring_candidates.update(grid.get((c_cx + dy, c_cy + dx), ()))

            for p_idx in ring_candidates:
                if visited[p_idx]:
                    continue
                path = paths[p_idx]
                s_pt = path.points[0]
                e_pt = path.points[-1]
                d_s = math.hypot(s_pt[0] - curr_pos[0], s_pt[1] - curr_pos[1])
                d_e = math.hypot(e_pt[0] - curr_pos[0], e_pt[1] - curr_pos[1])

                if d_s < best_dist:
                    best_dist = d_s
                    best_idx = p_idx
                    best_reverse = False
                if d_e < best_dist:
                    best_dist = d_e
                    best_idx = p_idx
                    best_reverse = True

            if best_idx != -1:
                found_in_ring = True
                break

        # Fallback if no neighbor found within max_ring: scan remaining unvisited
        if not found_in_ring:
            for p_idx in range(n):
                if visited[p_idx]:
                    continue
                path = paths[p_idx]
                s_pt = path.points[0]
                e_pt = path.points[-1]
                d_s = math.hypot(s_pt[0] - curr_pos[0], s_pt[1] - curr_pos[1])
                d_e = math.hypot(e_pt[0] - curr_pos[0], e_pt[1] - curr_pos[1])
                if d_s < best_dist:
                    best_dist = d_s
                    best_idx = p_idx
                    best_reverse = False
                if d_e < best_dist:
                    best_dist = d_e
                    best_idx = p_idx
                    best_reverse = True

        visited[best_idx] = True
        chosen = paths[best_idx]
        total_pen_up += best_dist

        if best_reverse:
            rev_pts = list(reversed(chosen.points))
            if chosen.is_bezier:
                segs = fit_cubic_spline(rev_pts, tension=0.35)
                chosen = StrokePath(
                    points=rev_pts,
                    is_bezier=True,
                    cubic_segments=segs,
                    svg_d=segments_to_svg_path(segs),
                    is_hatch=chosen.is_hatch,
                )
            else:
                chosen = StrokePath(
                    points=rev_pts,
                    is_bezier=False,
                    svg_d=f"M {rev_pts[0][0]:.2f},{rev_pts[0][1]:.2f} L {rev_pts[-1][0]:.2f},{rev_pts[-1][1]:.2f}",
                    is_hatch=chosen.is_hatch,
                )

        sorted_paths.append(chosen)
        curr_pos = chosen.points[-1]

    return sorted_paths, total_pen_up

def _reverse_stroke(chosen: "StrokePath") -> "StrokePath":
    """Gibt eine Kopie von `chosen` mit umgekehrter Richtung zurück
    (identische Logik wie bisher in optimize_pen_travel)."""
    rev_pts = list(reversed(chosen.points))
    if chosen.is_bezier:
        segs = fit_cubic_spline(rev_pts, tension=0.35)
        return StrokePath(
            points=rev_pts,
            is_bezier=True,
            cubic_segments=segs,
            svg_d=segments_to_svg_path(segs),
            is_hatch=chosen.is_hatch,
        )
    return StrokePath(
        points=rev_pts,
        is_bezier=False,
        svg_d=f"M {rev_pts[0][0]:.2f},{rev_pts[0][1]:.2f} L {rev_pts[-1][0]:.2f},{rev_pts[-1][1]:.2f}",
        is_hatch=chosen.is_hatch,
    )


def two_opt_pen_travel(
    paths: List[StrokePath],
    start_pos: Point2D = (0.0, 0.0),
    max_passes: int = 20,
    time_budget_sec: Optional[float] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Tuple[List[StrokePath], float]:
    """
    Verbessert eine bereits (z. B. per Nearest-Neighbor) sortierte Liste von
    StrokePaths per 2-opt: Teilsequenzen werden umgedreht (inkl. der
    Einzelrichtung jeder Linie), wenn das die Pen-Up-Weglänge verkuerzt.

    Erwartet, dass `paths` bereits in einer Reihenfolge vorliegt (z. B. das
    Ergebnis von optimize_pen_travel). Gibt (neue_liste, neue_pen_up_distanz)
    zurueck.
    """
    n = len(paths)
    if n < 3:
        total = 0.0
        pos = start_pos
        for p in paths:
            total += math.hypot(p.points[0][0] - pos[0], p.points[0][1] - pos[1])
            pos = p.points[-1]
        return paths, total

    paths = list(paths)
    t0 = time.perf_counter()

    for _ in range(max_passes):
        if is_cancelled and is_cancelled():
            break
        if time_budget_sec is not None and (time.perf_counter() - t0) > time_budget_sec:
            break

        improved = False
        i = 0
        while i < n:
            prev_end = paths[i - 1].points[-1] if i > 0 else start_pos
            best_k = -1
            best_delta = -1e-9  # nur echte Verbesserungen

            for j in range(i, n):
                s_i = paths[i].points[0]
                e_j = paths[j].points[-1]
                next_start = paths[j + 1].points[0] if j + 1 < n else None

                old = math.hypot(prev_end[0] - s_i[0], prev_end[1] - s_i[1])
                new = math.hypot(prev_end[0] - e_j[0], prev_end[1] - e_j[1])
                if next_start is not None:
                    old += math.hypot(paths[j].points[-1][0] - next_start[0],
                                       paths[j].points[-1][1] - next_start[1])
                    new += math.hypot(paths[i].points[0][0] - next_start[0],
                                       paths[i].points[0][1] - next_start[1])

                delta = new - old
                if delta < best_delta:
                    best_delta = delta
                    best_k = j

            if best_k >= 0:
                segment = paths[i:best_k + 1]
                reversed_segment = [_reverse_stroke(s) for s in reversed(segment)]
                paths[i:best_k + 1] = reversed_segment
                improved = True

            i += 1

        if not improved:
            break

    total = 0.0
    pos = start_pos
    for p in paths:
        total += math.hypot(p.points[0][0] - pos[0], p.points[0][1] - pos[1])
        pos = p.points[-1]

    return paths, total

class PlotEngine:
    """Main image processing and line extraction engine."""

    def __init__(self, params: Optional[PlotParameters] = None):
        self.params = params or PlotParameters()

    def process_image(
        self,
        image_input: str | np.ndarray | Image.Image,
        is_preview: bool = False,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> EngineResult:
        """
        Execute full vectorization pipeline.
        
        Args:
            image_input: File path, numpy array, or PIL Image.
            is_preview: If True, uses downscaling according to preview_max_dim for speed.
            progress_callback: Optional callback(fraction 0..1, status_message).
            is_cancelled: Optional callback returning True if worker should abort.
            
        Returns:
            EngineResult with paths, intermediate images, and statistics.
        """
        start_time = time.perf_counter()

        def update_progress(p: float, msg: str):
            if progress_callback:
                progress_callback(p, msg)

        update_progress(0.05, "Bild wird geladen...")

        # 1. Load image and convert to grayscale
        if isinstance(image_input, str):
            img_pil = Image.open(image_input)
        elif isinstance(image_input, np.ndarray):
            img_pil = Image.fromarray(image_input)
        elif isinstance(image_input, Image.Image):
            img_pil = image_input
        else:
            raise ValueError(f"Ungültige Bildquelle: {type(image_input)}")

        orig_w, orig_h = img_pil.size

        # Downscale for live preview if needed
        max_dim = self.params.preview_max_dim if is_preview else 0
        if max_dim > 0 and (orig_w > max_dim or orig_h > max_dim):
            scale = max_dim / float(max(orig_w, orig_h))
            new_w = max(1, int(round(orig_w * scale)))
            new_h = max(1, int(round(orig_h * scale)))
            img_pil = img_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)

        w, h = img_pil.size

        # Determine cache key for expensive filtering and gradient stage
        if isinstance(image_input, str):
            try:
                mtime = os.path.getmtime(image_input)
            except OSError:
                mtime = 0.0
            img_cache_id = (image_input, mtime, is_preview)
        elif isinstance(image_input, np.ndarray):
            img_cache_id = (id(image_input), image_input.shape, is_preview)
        elif isinstance(image_input, Image.Image):
            img_cache_id = (id(image_input), image_input.size, is_preview)
        else:
            img_cache_id = (id(image_input), is_preview)

        filter_cache_key = (
            img_cache_id,
            w,
            h,
            self.params.use_clahe,
            self.params.clahe_kernel_size,
            self.params.clahe_clip_limit,
            self.params.use_gaussian_blur,
            self.params.gaussian_kernel_size,
        )

        if filter_cache_key in _PREPROCESS_CACHE:
            cached = _PREPROCESS_CACHE[filter_cache_key]
            norm_gray = cached["norm_gray"]
            mag = cached["mag"].copy()
            display_mag = cached["display_mag"]
            grad_x = cached["grad_x"]
            grad_y = cached["grad_y"]
        else:
            # Convert to RGB then grayscale float array in [0.0, 1.0]
            rgb = np.array(img_pil.convert("RGB"), dtype=np.float32)
            gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

            min_val = gray.min()
            max_val = gray.max()
            norm_gray = (gray - min_val) / max(1e-6, max_val - min_val)

            update_progress(0.15, "Vorverarbeitung (Filter & Kontrast)...")

            # 2. Preprocessing: CLAHE
            if self.params.use_clahe:
                norm_gray = skimage.exposure.equalize_adapthist(
                    norm_gray,
                    kernel_size=self.params.clahe_kernel_size,
                    clip_limit=self.params.clahe_clip_limit,
                )

            # 3. Preprocessing: Gaussian Blur
            if self.params.use_gaussian_blur and self.params.gaussian_kernel_size > 0:
                norm_gray = scipy.ndimage.gaussian_filter(
                    norm_gray, sigma=self.params.gaussian_kernel_size
                )

            update_progress(0.25, "Kanten und Gradienten berechnen...")

            # 4. Sobel & Gradient extraction
            sobel_dx = scipy.ndimage.sobel(norm_gray, axis=1)
            sobel_dy = scipy.ndimage.sobel(norm_gray, axis=0)
            mag = np.hypot(sobel_dx, sobel_dy)

            # Modulate by low-frequency darkness to increase probability in dark regions
            img_blur = scipy.ndimage.gaussian_filter(norm_gray, sigma=2.0)
            mag = np.multiply(mag, img_blur.max() - img_blur)

            sum_mag = np.sum(mag)
            if sum_mag > 0:
                mag = mag / sum_mag

            # Keep a copy of magnitude for preview display
            display_mag = mag.copy()
            if display_mag.max() > 0:
                display_mag /= display_mag.max()

            grad_y, grad_x = np.gradient(norm_gray)

            # Keep cache size bounded to 1 entry
            _PREPROCESS_CACHE.clear()
            _PREPROCESS_CACHE[filter_cache_key] = {
                "norm_gray": norm_gray,
                "mag": mag.copy(),
                "display_mag": display_mag,
                "grad_x": grad_x,
                "grad_y": grad_y,
            }

        update_progress(0.35, "Linien werden extrahiert...")

        init_max_p = float(mag.max())
        term_thresh = init_max_p * self.params.termination_ratio
        cmax = init_max_p
        iteration = 0
        max_iter = self.params.max_iterations

        paths: List[StrokePath] = []
        is_bezier = self.params.line_mode.lower() == "bezier"

        while cmax > term_thresh and iteration < max_iter:
            if is_cancelled and is_cancelled():
                break

            iteration += 1
            if iteration % 50 == 0:
                time.sleep(0.0001)  # Yield Python GIL to keep GUI thread completely fluid
                if is_cancelled and is_cancelled():
                    break
                p_progress = 0.35 + 0.45 * (1.0 - (cmax - term_thresh) / max(1e-6, init_max_p - term_thresh))
                update_progress(min(0.80, p_progress), f"Linien extrahieren ({len(paths)} Linien)...")

            pix_idx = int(mag.argmax())
            py = pix_idx // w
            px = pix_idx % w
            cmax = float(mag[py, px])

            full_pts, total_len = trace_line_from_gradient(
                mag=mag,
                px=px,
                py=py,
                grad_x=grad_x,
                grad_y=grad_y,
                line_continue_thresh=self.params.line_continue_thresh,
                max_curve_angle_deg=self.params.max_curve_angle_deg,
                lpf_atk=self.params.lpf_atk,
            )

            if total_len < self.params.min_line_length or len(full_pts) < 2:
                # Suppress the failed peak neighborhood so argmax() does not get stuck in repetitive iterations
                mag[max(0, py - 1) : min(h, py + 2), max(0, px - 1) : min(w, px + 2)] = 0.0
                continue

            start_pt = full_pts[0]
            end_pt = full_pts[-1]

            # Construct path representation
            if is_bezier and len(full_pts) >= 3:
                cubic_segs = fit_cubic_spline(
                    full_pts,
                    tension=self.params.bezier_smoothness,
                    sample_step=self.params.curve_sample_step,
                )
                svg_d = segments_to_svg_path(cubic_segs)
                stroke = StrokePath(
                    points=full_pts,
                    is_bezier=True,
                    cubic_segments=cubic_segs,
                    svg_d=svg_d,
                    is_hatch=False,
                )
            else:
                svg_d = f"M {start_pt[0]:.2f},{start_pt[1]:.2f} L {end_pt[0]:.2f},{end_pt[1]:.2f}"
                stroke = StrokePath(
                    points=[start_pt, end_pt],
                    is_bezier=False,
                    svg_d=svg_d,
                    is_hatch=False,
                )

            paths.append(stroke)

            # Suppress edge magnitude along the drawn path so it is not re-visited
            sy = int(round(start_pt[1]))
            sx = int(round(start_pt[0]))
            ey = int(round(end_pt[1]))
            ex = int(round(end_pt[0]))

            rr, cc, _ = skimage.draw.line_aa(sy, sx, ey, ex)
            valid = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
            mag[rr[valid], cc[valid]] = 0.0
            mag[py, px] = 0.0

        contour_count = len(paths)
        update_progress(0.82, "Schraffur & Schattenlinien prüfen...")

        # 5. Hatching for shadows / dark areas if requested
        hatch_count = 0
        if self.params.use_hatching:
            hatch_strokes = generate_hatching(
                gray_image=norm_gray,
                threshold=self.params.hatching_threshold,
                spacing=self.params.hatching_spacing,
                angle_deg=self.params.hatching_angle_deg,
                cross_hatch=self.params.cross_hatch,
                min_length=self.params.hatching_min_length,
                mode=self.params.hatch_mode,
                curve_strength=self.params.hatch_curve_strength,
                wobble=self.params.hatch_wobble,
                bezier_smoothness=self.params.bezier_smoothness,
                is_cancelled=is_cancelled,
            )
            for hs in hatch_strokes:
                paths.append(
                    StrokePath(
                        points=hs.points,
                        is_bezier=hs.is_bezier,
                        cubic_segments=hs.cubic_segments,
                        svg_d=hs.svg_d,
                        is_hatch=True,
                    )
                )
                hatch_count += 1

        # 6. Shape generation if requested
        shape_count = 0
        if self.params.use_shapes:
            from .shapes import generate_shapes
            update_progress(0.85, "Formen generieren...")
            shape_strokes = generate_shapes(
                gray_image=norm_gray,
                grad_x=grad_x,
                grad_y=grad_y,
                params=self.params,
                is_cancelled=is_cancelled,
            )
            for ss in shape_strokes:
                ss.is_shape = True
                paths.append(ss)
                shape_count += 1

        update_progress(0.90, "Wegoptimierung (Plotter-Sortierung)...")

        pen_up_dist = 0.0
        if self.params.sort_paths and paths:
            paths, pen_up_dist = optimize_pen_travel(paths)

        total_drawing_len = sum(p.length() for p in paths)
        elapsed = time.perf_counter() - start_time

        stats = PlotStats(
            total_strokes=len(paths),
            contour_strokes=contour_count,
            hatch_strokes=hatch_count,
            shape_strokes=shape_count,
            total_length_px=total_drawing_len,
            pen_up_distance_px=pen_up_dist,
            elapsed_time_sec=elapsed,
            image_width=w,
            image_height=h,
        )

        update_progress(1.0, f"Fertig ({len(paths)} Pfade in {elapsed:.2f}s)")

        return EngineResult(
            paths=paths,
            width=w,
            height=h,
            preprocessed_gray=norm_gray,
            sobel_magnitude=display_mag,
            stats=stats,
        )
