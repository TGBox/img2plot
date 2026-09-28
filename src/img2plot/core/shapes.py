"""
Shape generation module for img2plot.
Converts grayscale images into artistic primitive shapes (dots, circles,
rectangles, triangles, stars, hexagons, spirals, hearts, ASCII, etc.).

Each shape is represented as a StrokePath.  The svg_d field uses a lightweight
marker protocol so the SVG exporter can emit native SVG elements:
  __circle__ cx=X cy=Y r=R [fill=1]   -> <circle>
  __rect__   cx=X cy=Y w=W h=H a=A   -> <rect> (rotated via transform)
  __text__   cx=X cy=Y s=S c=C        -> <text> (ASCII character)
All other svg_d values are treated as standard SVG path data strings.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Callable

import numpy as np

from .parameters import PlotParameters
from .engine import StrokePath

Point2D = tuple[float, float]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_shapes(
    gray_image: np.ndarray,
    grad_x: np.ndarray,
    grad_y: np.ndarray,
    params: PlotParameters,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate primitive shape strokes from a grayscale image.

    Args:
        gray_image: Normalised float array [0..1], shape (H, W).
        grad_x:     Sobel gradient X component, same shape.
        grad_y:     Sobel gradient Y component, same shape.
        params:     Full PlotParameters; only shape_* fields are used here.
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects (one per shape instance).
    """
    rng = random.Random()  # Local RNG - does not disturb global state

    # Placement points: list of (px, py, brightness)
    points = _get_placement_points(gray_image, params, rng)

    # Dispatch to the correct shape generator
    shape_type = params.shape_type.lower()
    maker = _SHAPE_MAKERS.get(shape_type, _make_dot)

    strokes: List[StrokePath] = []
    for i, (px, py, brightness) in enumerate(points):
        if i % 500 == 0 and is_cancelled and is_cancelled():
            break

        size = _get_shape_size(brightness, params)
        if size <= 0:
            continue

        angle = _get_rotation(px, py, grad_x, grad_y, params, rng)

        if shape_type == "ascii":
            stroke = _make_ascii(px, py, size, brightness, params.shape_ascii_charset)
        else:
            stroke = maker(px, py, size, angle)

        if stroke is not None:
            stroke.is_shape = True
            strokes.append(stroke)

    return strokes


# ---------------------------------------------------------------------------
# Placement helpers
# ---------------------------------------------------------------------------

def _get_placement_points(
    gray: np.ndarray,
    params: PlotParameters,
    rng: random.Random,
) -> List[tuple[int, int, float]]:
    """Compute a list of (x, y, brightness) positions for shape placement."""
    h, w = gray.shape

    # Cell size drives the base spacing between shapes.
    # Higher density -> smaller cell -> more shapes per area.
    cell = max(2, int(params.shape_max_size / max(0.05, params.shape_density)))

    points: List[tuple[int, int, float]] = []

    if params.shape_placement == "grid":
        for gy in range(0, h, cell):
            for gx in range(0, w, cell):
                # Jitter within the cell for a less mechanical look
                jitter_x = rng.randint(0, max(0, cell // 4))
                jitter_y = rng.randint(0, max(0, cell // 4))
                cx = min(w - 1, gx + cell // 2 + jitter_x)
                cy = min(h - 1, gy + cell // 2 + jitter_y)
                brightness = float(gray[cy, cx])

                if params.shape_density_by_brightness:
                    # Bright pixels -> skip with higher probability
                    if rng.random() < brightness * 0.85:
                        continue

                points.append((cx, cy, brightness))

    else:  # random placement
        n_shapes = int((w * h) / max(1, cell * cell) * max(0.05, params.shape_density))
        n_shapes = max(1, min(n_shapes, 80_000))  # Safety cap
        for _ in range(n_shapes):
            px = rng.randint(0, w - 1)
            py = rng.randint(0, h - 1)
            brightness = float(gray[py, px])

            if params.shape_density_by_brightness:
                if rng.random() < brightness * 0.85:
                    continue

            points.append((px, py, brightness))

    return points


def _get_shape_size(brightness: float, params: PlotParameters) -> float:
    """Map brightness to shape size.  Bright regions -> small, dark regions -> large."""
    if params.shape_size_by_brightness:
        t = 1.0 - brightness  # invert: 0=bright (small), 1=dark (large)
        return params.shape_min_size + t * (params.shape_max_size - params.shape_min_size)
    return (params.shape_min_size + params.shape_max_size) / 2.0


def _get_rotation(
    px: int,
    py: int,
    grad_x: np.ndarray,
    grad_y: np.ndarray,
    params: PlotParameters,
    rng: random.Random,
) -> float:
    """Compute shape rotation angle in radians."""
    mode = params.shape_rotation_mode

    if mode == "none":
        return 0.0

    if mode == "random":
        return rng.uniform(0.0, math.tau)

    h, w = grad_x.shape
    ix = min(w - 1, max(0, int(px)))
    iy = min(h - 1, max(0, int(py)))
    grad_angle = math.atan2(float(grad_y[iy, ix]), float(grad_x[iy, ix]))

    if mode == "gradient":
        return grad_angle

    # "mixed": blend random and gradient via complex interpolation
    rand_angle = rng.uniform(0.0, math.tau)
    alpha = max(0.0, min(1.0, params.shape_gradient_align))
    z = (1.0 - alpha) * math.e ** (1j * rand_angle) + alpha * math.e ** (1j * grad_angle)
    return math.atan2(z.imag, z.real)


# ---------------------------------------------------------------------------
# SVG path helpers
# ---------------------------------------------------------------------------

def _pts_to_path(pts: List[Point2D], close: bool = False) -> str:
    """Convert a list of 2-D points to an SVG path d-string (polyline or polygon)."""
    if not pts:
        return ""
    parts = [f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"]
    for x, y in pts[1:]:
        parts.append(f"L {x:.2f},{y:.2f}")
    if close:
        parts.append("Z")
    return " ".join(parts)


def _rotate_pts(pts: List[Point2D], cx: float, cy: float, angle: float) -> List[Point2D]:
    """Rotate a list of points around (cx, cy) by angle radians."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    result = []
    for x, y in pts:
        dx = x - cx
        dy = y - cy
        result.append((cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a))
    return result


def _stroke_from_path(svg_d: str, pts: List[Point2D]) -> StrokePath:
    """Create a StrokePath from an svg_d string and representative point list."""
    return StrokePath(points=pts if pts else [(0.0, 0.0)], svg_d=svg_d)


# ---------------------------------------------------------------------------
# Shape constructors (each returns a StrokePath or None)
# ---------------------------------------------------------------------------

def _make_dot(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Filled circle (dot)."""
    r = max(0.3, size / 2.0)
    svg_d = f"__circle__ cx={cx:.3f} cy={cy:.3f} r={r:.3f} fill=1"
    return StrokePath(
        points=[(cx, cy)],
        svg_d=svg_d,
        shape_metadata={"type": "circle", "cx": cx, "cy": cy, "r": r, "fill": True},
    )


def _make_circle(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Circle outline only."""
    r = max(0.3, size / 2.0)
    svg_d = f"__circle__ cx={cx:.3f} cy={cy:.3f} r={r:.3f}"
    return StrokePath(
        points=[(cx, cy)],
        svg_d=svg_d,
        shape_metadata={"type": "circle", "cx": cx, "cy": cy, "r": r, "fill": False},
    )


def _make_rect(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Rotated rectangle."""
    w = max(0.5, size)
    h = max(0.5, size * 0.7)
    svg_d = f"__rect__ cx={cx:.3f} cy={cy:.3f} w={w:.3f} h={h:.3f} a={angle:.4f}"
    return StrokePath(
        points=[(cx, cy)],
        svg_d=svg_d,
        shape_metadata={"type": "rect", "cx": cx, "cy": cy, "w": w, "h": h, "angle": angle},
    )


def _make_triangle(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Equilateral triangle."""
    r = max(0.5, size / 2.0)
    raw: List[Point2D] = [
        (cx, cy - r),
        (cx + r * math.sin(math.radians(120)), cy + r * math.cos(math.radians(120))),
        (cx - r * math.sin(math.radians(120)), cy + r * math.cos(math.radians(120))),
    ]
    pts = _rotate_pts(raw, cx, cy, angle)
    svg_d = _pts_to_path(pts, close=True)
    return _stroke_from_path(svg_d, pts)


def _make_line_seg(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Short oriented line segment."""
    half = max(0.5, size / 2.0)
    x0 = cx - half * math.cos(angle)
    y0 = cy - half * math.sin(angle)
    x1 = cx + half * math.cos(angle)
    y1 = cy + half * math.sin(angle)
    svg_d = f"M {x0:.2f},{y0:.2f} L {x1:.2f},{y1:.2f}"
    return _stroke_from_path(svg_d, [(x0, y0), (x1, y1)])


def _make_star(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Five-pointed star."""
    outer = max(0.5, size / 2.0)
    inner = outer * 0.4
    pts_raw: List[Point2D] = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        a = angle + math.pi * i / 5.0 - math.pi / 2.0
        pts_raw.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    svg_d = _pts_to_path(pts_raw, close=True)
    return _stroke_from_path(svg_d, pts_raw)


def _make_diamond(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Rhombus / diamond shape."""
    r = max(0.5, size / 2.0)
    raw: List[Point2D] = [(cx, cy - r), (cx + r * 0.6, cy), (cx, cy + r), (cx - r * 0.6, cy)]
    pts = _rotate_pts(raw, cx, cy, angle)
    svg_d = _pts_to_path(pts, close=True)
    return _stroke_from_path(svg_d, pts)


def _make_hexagon(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Regular hexagon."""
    r = max(0.5, size / 2.0)
    pts_raw: List[Point2D] = [
        (cx + r * math.cos(angle + math.pi * i / 3.0),
         cy + r * math.sin(angle + math.pi * i / 3.0))
        for i in range(6)
    ]
    svg_d = _pts_to_path(pts_raw, close=True)
    return _stroke_from_path(svg_d, pts_raw)


def _make_spiral(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Archimedean spiral approximated with cubic Bezier segments."""
    r_max = max(0.5, size / 2.0)
    turns = 2.5
    steps = max(8, int(r_max * 3))
    pts: List[Point2D] = []
    for i in range(steps + 1):
        t = i / steps
        a = angle + t * turns * math.tau
        r = t * r_max
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    if len(pts) < 2:
        return None

    # Build cubic bezier approximation for smooth SVG spiral
    path_parts = [f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"]
    i = 0
    while i + 3 < len(pts):
        p0 = pts[i]
        p1 = pts[i + 1]
        p2 = pts[i + 2]
        p3 = pts[i + 3]
        c1 = (p0[0] + (p1[0] - p0[0]) * 0.5, p0[1] + (p1[1] - p0[1]) * 0.5)
        c2 = (p3[0] + (p2[0] - p3[0]) * 0.5, p3[1] + (p2[1] - p3[1]) * 0.5)
        path_parts.append(
            f"C {c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} {p3[0]:.2f},{p3[1]:.2f}"
        )
        i += 3

    svg_d = " ".join(path_parts)
    return _stroke_from_path(svg_d, pts)


def _make_heart(cx: float, cy: float, size: float, angle: float = 0.0) -> Optional[StrokePath]:
    """Heart shape via cubic Bezier curves."""
    s = max(0.5, size / 2.0)
    # Two bumps on top, point at bottom
    svg_d = " ".join([
        f"M {cx:.2f},{cy - s * 0.25:.2f}",
        f"C {cx + s * 0.1:.2f},{cy - s:.2f} {cx + s:.2f},{cy - s * 0.5:.2f} {cx + s:.2f},{cy:.2f}",
        f"C {cx + s:.2f},{cy + s * 0.6:.2f} {cx:.2f},{cy + s * 0.9:.2f} {cx:.2f},{cy + s:.2f}",
        f"C {cx:.2f},{cy + s * 0.9:.2f} {cx - s:.2f},{cy + s * 0.6:.2f} {cx - s:.2f},{cy:.2f}",
        f"C {cx - s:.2f},{cy - s * 0.5:.2f} {cx - s * 0.1:.2f},{cy - s:.2f} {cx:.2f},{cy - s * 0.25:.2f}",
        "Z",
    ])
    # Approximate bounding points for QPainterPath rendering fallback
    pts: List[Point2D] = [(cx, cy - s * 0.25), (cx + s, cy), (cx, cy + s), (cx - s, cy)]
    pts = _rotate_pts(pts, cx, cy, angle)
    return StrokePath(
        points=pts,
        svg_d=svg_d,
        shape_metadata={"type": "heart", "cx": cx, "cy": cy, "size": s, "angle": angle},
    )


def _make_ascii(
    cx: float,
    cy: float,
    size: float,
    brightness: float,
    charset: str,
) -> Optional[StrokePath]:
    """ASCII character mapped from image brightness."""
    if not charset:
        charset = "@#S%?*+;:,. "
    n = len(charset)
    idx = min(n - 1, int(brightness * n))
    char = charset[idx]
    font_size = max(1.0, size)
    svg_d = f"__text__ cx={cx:.3f} cy={cy:.3f} s={font_size:.2f} c={char}"
    return StrokePath(
        points=[(cx, cy)],
        svg_d=svg_d,
        shape_metadata={"type": "ascii", "cx": cx, "cy": cy, "size": font_size, "char": char},
    )


# ---------------------------------------------------------------------------
# Shape type dispatch table
# ---------------------------------------------------------------------------

_SHAPE_MAKERS = {
    "dots":      _make_dot,
    "circles":   _make_circle,
    "rects":     _make_rect,
    "triangles": _make_triangle,
    "lines":     _make_line_seg,
    "stars":     _make_star,
    "diamonds":  _make_diamond,
    "hexagons":  _make_hexagon,
    "spirals":   _make_spiral,
    "hearts":    _make_heart,
    "ascii":     None,  # handled separately via _make_ascii in generate_shapes
}
