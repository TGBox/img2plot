"""
Core vectorization engine for img2plot.
Transforms raster images into artistic line drawings and vector paths.
"""

from __future__ import annotations
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


@dataclass
class StrokePath:
    """Represents a single pen stroke (straight line, polyline, or Bezier curve)."""
    points: List[Point2D]
    is_bezier: bool = False
    cubic_segments: List[CubicSegment] = field(default_factory=list)
    svg_d: str = ""
    is_hatch: bool = False

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


def bilinear_interpolate(img: np.ndarray, x: float, y: float) -> float:
    """Sample continuous coordinates on a 2D float image with bilinear interpolation."""
    h, w = img.shape
    x_floor = int(math.floor(x))
    y_floor = int(math.floor(y))
    x_ceil = int(math.ceil(x))
    y_ceil = int(math.ceil(y))

    # Clamp bounds
    x_floor = max(0, min(w - 1, x_floor))
    x_ceil = max(0, min(w - 1, x_ceil))
    y_floor = max(0, min(h - 1, y_floor))
    y_ceil = max(0, min(h - 1, y_ceil))

    x_float = x - math.floor(x)
    y_float = y - math.floor(y)

    top_left = img[y_floor, x_floor]
    top_right = img[y_floor, x_ceil]
    bottom_left = img[y_ceil, x_floor]
    bottom_right = img[y_ceil, x_ceil]

    top_mid = x_float * top_right + (1.0 - x_float) * top_left
    bot_mid = x_float * bottom_right + (1.0 - x_float) * bottom_left

    return float(y_float * bot_mid + (1.0 - y_float) * top_mid)


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

        val = bilinear_interpolate(mag, curr_x, curr_y)
        if val <= thresh_val:
            break

        ix = int(round(curr_x))
        iy = int(round(curr_y))
        ix = max(0, min(w - 1, ix))
        iy = max(0, min(h - 1, iy))

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

        val = bilinear_interpolate(mag, curr_x, curr_y)
        if val <= thresh_val:
            break

        ix = int(round(curr_x))
        iy = int(round(curr_y))
        ix = max(0, min(w - 1, ix))
        iy = max(0, min(h - 1, iy))

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
            if iteration % 250 == 0:
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
                # Suppress the peak using neighbor mean
                acc = 0.0
                cnt = 0
                if py + 1 < h:
                    acc += mag[py + 1, px]
                    cnt += 1
                if px + 1 < w:
                    acc += mag[py, px + 1]
                    cnt += 1
                if py - 1 >= 0:
                    acc += mag[py - 1, px]
                    cnt += 1
                if px - 1 >= 0:
                    acc += mag[py, px - 1]
                    cnt += 1
                mag[py, px] = acc / max(1, cnt)
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
