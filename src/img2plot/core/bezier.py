"""
Bezier curve utilities for smoothing sampled stroke paths.
"""

from __future__ import annotations
import math
from typing import List, Tuple

Point = Tuple[float, float]
CubicSegment = Tuple[Point, Point, Point, Point]  # (p1, c1, c2, p2)


def fit_cubic_spline(
    points: List[Point],
    tension: float = 0.35,
    sample_step: int = 2
) -> List[CubicSegment]:
    """
    Convert a sequence of 2D points into smooth cubic Bezier segments using
    Catmull-Rom / Cardinal spline tangents.
    
    Args:
        points: Ordered list of (x, y) coordinates along the traced stroke.
        tension: Tangent scale factor (0.0 = straight segments, 0.3-0.5 = smooth curves).
        sample_step: Subsampling step to skip redundant dense points.
        
    Returns:
        List of cubic segments, each defined by (p1, c1, c2, p2).
    """
    if len(points) < 2:
        return []

    # Subsample if too dense
    if sample_step > 1 and len(points) > 4:
        subsampled = points[::sample_step]
        if subsampled[-1] != points[-1]:
            subsampled.append(points[-1])
        pts = subsampled
    else:
        pts = points

    n = len(pts)
    if n == 2:
        # Simple straight segment represented as cubic bezier
        p1, p2 = pts[0], pts[1]
        c1 = (p1[0] + (p2[0] - p1[0]) / 3.0, p1[1] + (p2[1] - p1[1]) / 3.0)
        c2 = (p1[0] + 2.0 * (p2[0] - p1[0]) / 3.0, p1[1] + 2.0 * (p2[1] - p1[1]) / 3.0)
        return [(p1, c1, c2, p2)]

    segments: List[CubicSegment] = []

    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[i + 1]

        # Tangents at p1 and p2
        t1x = tension * (p2[0] - p0[0])
        t1y = tension * (p2[1] - p0[1])

        t2x = tension * (p3[0] - p1[0])
        t2y = tension * (p3[1] - p1[1])

        c1 = (p1[0] + t1x, p1[1] + t1y)
        c2 = (p2[0] - t2x, p2[1] - t2y)

        segments.append((p1, c1, c2, p2))

    return segments


def segments_to_svg_path(segments: List[CubicSegment]) -> str:
    """Convert a list of cubic Bezier segments into an SVG path 'd' string."""
    if not segments:
        return ""

    first_p1 = segments[0][0]
    parts = [f"M {first_p1[0]:.2f},{first_p1[1]:.2f}"]

    for _, c1, c2, p2 in segments:
        parts.append(
            f"C {c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} {p2[0]:.2f},{p2[1]:.2f}"
        )

    return " ".join(parts)


def evaluate_cubic_bezier(p1: Point, c1: Point, c2: Point, p2: Point, t: float) -> Point:
    """Evaluate cubic Bezier curve at parameter t in [0, 1]."""
    u = 1.0 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t

    x = uuu * p1[0] + 3.0 * uu * t * c1[0] + 3.0 * u * tt * c2[0] + ttt * p2[0]
    y = uuu * p1[1] + 3.0 * uu * t * c1[1] + 3.0 * u * tt * c2[1] + ttt * p2[1]
    return (x, y)


def discretize_segments(segments: List[CubicSegment], steps_per_segment: int = 6) -> List[Point]:
    """Sample points along cubic segments for rasterization and distance calculations."""
    pts: List[Point] = []
    for seg_idx, (p1, c1, c2, p2) in enumerate(segments):
        start_step = 0 if seg_idx == 0 else 1
        for s in range(start_step, steps_per_segment + 1):
            t = s / float(steps_per_segment)
            pts.append(evaluate_cubic_bezier(p1, c1, c2, p2, t))
    return pts
