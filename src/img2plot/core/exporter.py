"""
SVG and PNG export utilities for img2plot vector drawings.
Supports physical page dimensions, margins, pen width, and multi-layer SVG groups.
"""

from __future__ import annotations
import math
import os
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw

from .parameters import PlotParameters
from .engine import StrokePath, EngineResult
from .bezier import discretize_segments


PAGE_SIZES_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
}


# ---------------------------------------------------------------------------
# SVG marker-protocol parsers
# ---------------------------------------------------------------------------

def _parse_marker(svg_d: str) -> dict:
    """Parse a shape marker string into a dict of key=value pairs."""
    parts = svg_d.split()
    result: dict = {"__type__": parts[0]}
    for token in parts[1:]:
        if "=" in token:
            k, v = token.split("=", 1)
            result[k] = v
    return result


def _render_circle_tag(marker: dict, transform_pt, scale: float, stroke_col: str, stroke_w_mm: float) -> str:
    cx, cy = transform_pt(float(marker["cx"]), float(marker["cy"]))
    r = float(marker["r"]) * scale
    filled = marker.get("fill", "0") == "1"
    fill_attr = stroke_col if filled else "none"
    return (
        f'    <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" '
        f'fill="{fill_attr}" stroke="{stroke_col}" stroke-width="{stroke_w_mm:.3f}mm" />'
    )


def _render_rect_tag(marker: dict, transform_pt, scale: float, stroke_col: str, stroke_w_mm: float) -> str:
    cx, cy = transform_pt(float(marker["cx"]), float(marker["cy"]))
    w = float(marker["w"]) * scale
    h = float(marker["h"]) * scale
    angle_rad = float(marker.get("a", "0"))
    angle_deg = math.degrees(angle_rad)
    return (
        f'    <rect x="{cx - w / 2:.3f}" y="{cy - h / 2:.3f}" '
        f'width="{w:.3f}" height="{h:.3f}" '
        f'fill="none" stroke="{stroke_col}" stroke-width="{stroke_w_mm:.3f}mm" '
        f'transform="rotate({angle_deg:.2f},{cx:.3f},{cy:.3f})" />'
    )


def _render_text_tag(marker: dict, transform_pt, scale: float, stroke_col: str) -> str:
    cx, cy = transform_pt(float(marker["cx"]), float(marker["cy"]))
    font_size = float(marker["s"]) * scale
    char = marker.get("c", "?")
    if char == "_":
        char = " "
    return (
        f'    <text x="{cx:.3f}" y="{cy:.3f}" '
        f'font-size="{font_size:.2f}" '
        f'fill="{stroke_col}" '
        f'text-anchor="middle" dominant-baseline="central" '
        f'font-family="monospace">{char}</text>'
    )


def _transform_path_d(svg_d: str, transform_pt) -> str:
    """Apply coordinate transform to a standard SVG path d-string (M/L/C/Z commands)."""
    tokens = svg_d.split()
    out: List[str] = []
    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        if cmd == "Z":
            out.append("Z")
            i += 1
        elif cmd in ("M", "L"):
            out.append(cmd)
            i += 1
            if i < len(tokens):
                x, y = map(float, tokens[i].split(","))
                tx, ty = transform_pt(x, y)
                out.append(f"{tx:.3f},{ty:.3f}")
                i += 1
        elif cmd == "C":
            out.append("C")
            i += 1
            for _ in range(3):
                if i < len(tokens):
                    x, y = map(float, tokens[i].split(","))
                    tx, ty = transform_pt(x, y)
                    out.append(f"{tx:.3f},{ty:.3f}")
                    i += 1
        else:
            out.append(cmd)
            i += 1
    return " ".join(out)


# ---------------------------------------------------------------------------
# Main export functions
# ---------------------------------------------------------------------------

def export_svg(
    result: EngineResult,
    params: PlotParameters,
    output_path: str
) -> None:
    """
    Export vectorized paths to an SVG file optimized for pen plotters and vector graphics.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    img_w = float(result.width)
    img_h = float(result.height)
    aspect = img_w / max(1.0, img_h)

    # Calculate page size in mm
    if params.page_format in PAGE_SIZES_MM:
        pw, ph = PAGE_SIZES_MM[params.page_format]
        # Orient page to match aspect ratio
        if (aspect > 1.0 and pw < ph) or (aspect < 1.0 and pw > ph):
            pw, ph = ph, pw
    elif params.page_format == "Custom":
        pw = params.page_width_mm
        ph = params.page_height_mm
    else:  # "Original"
        # 96 DPI: 1 px ~ 0.264583 mm
        pw = img_w * 0.264583
        ph = img_h * 0.264583

    margin = params.margin_mm if params.page_format != "Original" else 0.0
    drawable_w = max(1.0, pw - 2.0 * margin)
    drawable_h = max(1.0, ph - 2.0 * margin)

    # Scale to fit inside drawable area preserving aspect ratio
    scale = min(drawable_w / img_w, drawable_h / img_h)
    target_w = img_w * scale
    target_h = img_h * scale

    # Center on page
    offset_x = margin + (drawable_w - target_w) / 2.0
    offset_y = margin + (drawable_h - target_h) / 2.0

    stroke_col = params.stroke_color
    stroke_w_mm = params.stroke_width_mm

    def transform_pt(x: float, y: float) -> Tuple[float, float]:
        return (offset_x + x * scale, offset_y + y * scale)

    svg_lines: List[str] = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{pw:.2f}mm" height="{ph:.2f}mm" viewBox="0 0 {pw:.2f} {ph:.2f}" '
        f'version="1.1">',
        '  <desc>Generated by img2plot (Python Vectorizer)</desc>',
        f'  <!-- Layer 1: Contours and Main Edges -->',
        f'  <g id="layer_contours" stroke="{stroke_col}" stroke-width="{stroke_w_mm:.3f}mm" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round">',
    ]

    hatch_lines: List[str] = [
        f'  <!-- Layer 2: Hatching and Shadows -->',
        f'  <g id="layer_hatching" stroke="{stroke_col}" stroke-width="{stroke_w_mm * 0.85:.3f}mm" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round">',
    ]

    shape_lines: List[str] = [
        f'  <!-- Layer 3: Artistic Shapes -->',
        f'  <g id="layer_shapes" stroke="{stroke_col}" stroke-width="{stroke_w_mm:.3f}mm" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round">',
    ]

    for path in result.paths:
        svg_d = path.svg_d

        # Determine target layer
        if path.is_shape:
            target = shape_lines
        elif path.is_hatch:
            target = hatch_lines
        else:
            target = svg_lines

        # Render correct SVG element based on marker protocol or path type
        if svg_d.startswith("__circle__"):
            marker = _parse_marker(svg_d)
            tag = _render_circle_tag(marker, transform_pt, scale, stroke_col, stroke_w_mm)
        elif svg_d.startswith("__rect__"):
            marker = _parse_marker(svg_d)
            tag = _render_rect_tag(marker, transform_pt, scale, stroke_col, stroke_w_mm)
        elif svg_d.startswith("__text__"):
            marker = _parse_marker(svg_d)
            tag = _render_text_tag(marker, transform_pt, scale, stroke_col)
        elif path.is_bezier and path.cubic_segments:
            # Transform cubic bezier segments
            segs_str = []
            p1_x, p1_y = transform_pt(*path.cubic_segments[0][0])
            segs_str.append(f"M {p1_x:.3f},{p1_y:.3f}")
            for _, c1, c2, p2 in path.cubic_segments:
                c1_t = transform_pt(*c1)
                c2_t = transform_pt(*c2)
                p2_t = transform_pt(*p2)
                segs_str.append(
                    f"C {c1_t[0]:.3f},{c1_t[1]:.3f} {c2_t[0]:.3f},{c2_t[1]:.3f} {p2_t[0]:.3f},{p2_t[1]:.3f}"
                )
            d = " ".join(segs_str)
            tag = f'    <path d="{d}" />'
        elif svg_d and (svg_d[0] in ("M", "C") or svg_d.startswith("M ")):
            # Multi-command path (polygon shapes, spirals, hearts, etc.)
            d = _transform_path_d(svg_d, transform_pt)
            tag = f'    <path d="{d}" />'
        else:
            # Simple two-point line
            p_start = transform_pt(*path.points[0])
            p_end = transform_pt(*path.points[-1])
            d = f"M {p_start[0]:.3f},{p_start[1]:.3f} L {p_end[0]:.3f},{p_end[1]:.3f}"
            tag = f'    <path d="{d}" />'

        target.append(tag)

    svg_lines.append('  </g>')
    hatch_lines.append('  </g>')
    shape_lines.append('  </g>')

    svg_lines.extend(hatch_lines)
    svg_lines.extend(shape_lines)
    svg_lines.append('</svg>\n')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def export_png(
    result: EngineResult,
    params: PlotParameters,
    output_path: str,
    bg_color: str = "white",
    scale_factor: float = 2.0,
) -> None:
    """
    Render vector paths to a high-resolution raster PNG image.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    w = int(result.width * scale_factor)
    h = int(result.height * scale_factor)

    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255) if bg_color == "white" else (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    line_color = params.stroke_color
    line_width = max(1, int(round(params.stroke_width_mm * 2.5 * scale_factor)))

    for path in result.paths:
        svg_d = path.svg_d

        if svg_d.startswith("__circle__"):
            marker = _parse_marker(svg_d)
            cx = float(marker["cx"]) * scale_factor
            cy = float(marker["cy"]) * scale_factor
            r = float(marker["r"]) * scale_factor
            filled = marker.get("fill", "0") == "1"
            bbox = [cx - r, cy - r, cx + r, cy + r]
            if filled:
                draw.ellipse(bbox, fill=line_color, outline=line_color, width=line_width)
            else:
                draw.ellipse(bbox, fill=None, outline=line_color, width=line_width)
            continue

        if svg_d.startswith("__rect__"):
            marker = _parse_marker(svg_d)
            cx = float(marker["cx"]) * scale_factor
            cy = float(marker["cy"]) * scale_factor
            rw = float(marker["w"]) * scale_factor
            rh = float(marker["h"]) * scale_factor
            angle_rad = float(marker.get("a", "0"))
            half_w, half_h = rw / 2, rh / 2
            cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
            corners = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
            rotated = [
                (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)
                for dx, dy in corners
            ]
            draw.polygon(rotated, outline=line_color, width=line_width)
            continue

        if svg_d.startswith("__text__"):
            marker = _parse_marker(svg_d)
            cx = float(marker["cx"]) * scale_factor
            cy = float(marker["cy"]) * scale_factor
            char = marker.get("c", "?")
            if char == "_":
                char = " "
            draw.text((cx, cy), char, fill=line_color, anchor="mm")
            continue

        if path.is_bezier and path.cubic_segments:
            pts = discretize_segments(path.cubic_segments, steps_per_segment=6)
        else:
            pts = path.points

        if len(pts) >= 2:
            scaled_pts = [(p[0] * scale_factor, p[1] * scale_factor) for p in pts]
            draw.line(scaled_pts, fill=line_color, width=line_width, joint="curve")

    canvas.save(output_path, "PNG")

