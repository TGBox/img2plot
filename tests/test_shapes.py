import math
import numpy as np
import pytest

from img2plot.core.shapes import (
    _make_heart,
    _make_diamond,
    _make_triangle,
    _make_star,
    _make_hexagon,
    generate_shapes,
)
from img2plot.core.parameters import PlotParameters


def test_make_heart():
    cx, cy, size = 50.0, 50.0, 40.0
    heart = _make_heart(cx, cy, size, angle=0.0)

    assert heart is not None
    assert heart.is_bezier is True
    assert len(heart.cubic_segments) == 4

    # Top cleft is start and end
    p_start = heart.cubic_segments[0][0]
    p_end = heart.cubic_segments[-1][-1]
    assert math.isclose(p_start[0], p_end[0], abs_tol=1e-3)
    assert math.isclose(p_start[1], p_end[1], abs_tol=1e-3)

    # Discretized points are present, smooth, and closed
    assert len(heart.points) >= 20
    assert math.isclose(heart.points[0][0], heart.points[-1][0], abs_tol=1e-2)
    assert math.isclose(heart.points[0][1], heart.points[-1][1], abs_tol=1e-2)

    # SVG d string is valid and closed
    assert heart.svg_d.startswith("M ")
    assert "C " in heart.svg_d
    assert heart.svg_d.endswith("Z")

    # Metadata
    assert heart.shape_metadata.get("type") == "heart"

    # Rotation changes points
    heart_rot = _make_heart(cx, cy, size, angle=math.pi / 2)
    assert heart_rot is not None
    assert not math.isclose(heart.cubic_segments[1][3][0], heart_rot.cubic_segments[1][3][0], abs_tol=1.0)


def test_make_diamond():
    cx, cy, size = 50.0, 50.0, 40.0
    diamond = _make_diamond(cx, cy, size, angle=0.0)

    assert diamond is not None
    # 4 corners + 1 closing point = 5 points
    assert len(diamond.points) == 5

    # Completely closed
    assert diamond.points[0] == diamond.points[-1]

    # Check top, right, bottom, left geometry
    p_top, p_right, p_bot, p_left, _ = diamond.points
    assert math.isclose(p_top[0], cx, abs_tol=1e-3)
    assert p_top[1] < cy  # Top is above center
    assert p_right[0] > cx  # Right is to the right
    assert math.isclose(p_right[1], cy, abs_tol=1e-3)
    assert math.isclose(p_bot[0], cx, abs_tol=1e-3)
    assert p_bot[1] > cy  # Bottom is below center
    assert p_left[0] < cx  # Left is to the left
    assert math.isclose(p_left[1], cy, abs_tol=1e-3)

    # SVG d string
    assert diamond.svg_d.startswith("M ")
    assert "L " in diamond.svg_d
    assert diamond.svg_d.endswith("Z")

    # Metadata
    assert diamond.shape_metadata.get("type") == "diamond"


def test_polygons_are_closed():
    cx, cy, size = 50.0, 50.0, 40.0
    for maker in (_make_triangle, _make_star, _make_hexagon):
        shape = maker(cx, cy, size, 0.0)
        assert shape is not None
        assert shape.points[0] == shape.points[-1], f"{maker.__name__} points not closed"
        assert shape.svg_d.endswith("Z")


def test_generate_shapes_diamonds_and_hearts():
    # 100x100 grayscale image (dark circle in center)
    gray = np.ones((100, 100), dtype=np.float32)
    y, x = np.ogrid[:100, :100]
    mask = (x - 50) ** 2 + (y - 50) ** 2 < 30 ** 2
    gray[mask] = 0.2

    grad_x = np.zeros_like(gray)
    grad_y = np.zeros_like(gray)

    # Test diamond generation
    params_d = PlotParameters(
        use_shapes=True,
        shape_type="diamonds",
        shape_placement="grid",
        shape_density=0.5,
    )
    d_strokes = generate_shapes(gray, grad_x, grad_y, params_d)
    assert len(d_strokes) > 0
    assert all(s.is_shape for s in d_strokes)
    assert all(len(s.points) == 5 for s in d_strokes)

    # Test heart generation
    params_h = PlotParameters(
        use_shapes=True,
        shape_type="hearts",
        shape_placement="grid",
        shape_density=0.5,
    )
    h_strokes = generate_shapes(gray, grad_x, grad_y, params_h)
    assert len(h_strokes) > 0
    assert all(s.is_shape for s in h_strokes)
    assert all(s.is_bezier for s in h_strokes)
    assert all(len(s.cubic_segments) == 4 for s in h_strokes)
