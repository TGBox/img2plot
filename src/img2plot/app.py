"""
Application launcher and CLI interface for img2plot.
Supports interactive GUI mode as well as headless command-line vectorization.
"""

from __future__ import annotations
import sys
import os
import argparse
from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for img2plot."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="img2plot",
        description="img2plot - Vektor-Zeichenvorlagen Generator für Stiftplotter.",
    )
    parser.add_argument(
        "image",
        nargs="?",
        default=None,
        help="Pfad zum Eingabebild (optional, öffnet direkt in der GUI)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Pfad für die Ausgabedatei (.svg oder .png)",
    )
    parser.add_argument(
        "--cli", "--headless",
        action="store_true",
        help="Ohne Benutzeroberfläche ausführen und direkt SVG generieren",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="GUI direkt im Vollbildmodus starten",
    )
    parser.add_argument(
        "--preset",
        default="Standard",
        help="Preset für CLI-Modus (z. B. 'Standard', 'Feine Details', 'Künstlerische Skizze')",
    )

    args = parser.parse_args(argv)

    if args.cli:
        return run_cli(args)
    else:
        return run_gui(args)


def run_cli(args: argparse.Namespace) -> int:
    """Run vectorization headlessly via command line."""
    if not args.image:
        print("Fehler: Für den CLI-Modus muss ein Eingabebild angegeben werden.", file=sys.stderr)
        return 1

    if not os.path.isfile(args.image):
        print(f"Fehler: Datei nicht gefunden: {args.image}", file=sys.stderr)
        return 1

    from .core.presets import DEFAULT_PRESETS
    from .core.engine import PlotEngine
    from .core.exporter import export_svg, export_png

    preset_name = args.preset
    params = DEFAULT_PRESETS.get(preset_name, DEFAULT_PRESETS["Standard"])
    params.input_path = args.image

    out_path = args.output
    if not out_path:
        base, _ = os.path.splitext(args.image)
        out_path = base + "_plot.svg"
    params.output_path = out_path

    print(f"Verarbeite '{args.image}' mit Preset '{preset_name}'...")
    engine = PlotEngine(params)

    def progress_callback(frac: float, msg: str):
        percent = int(round(frac * 100))
        print(f"\r[{percent:3d}%] {msg}", end="", flush=True)

    result = engine.process_image(
        args.image,
        is_preview=False,
        progress_callback=progress_callback,
    )
    print()

    if out_path.lower().endswith(".png"):
        export_png(result, params, out_path)
    else:
        export_svg(result, params, out_path)

    print(f"Erfolgreich gespeichert: {out_path}")
    print(f"Statistiken: {result.stats.total_strokes} Pfade ({result.stats.total_length_px:.1f} px) in {result.stats.elapsed_time_sec:.2f}s")
    return 0


def run_gui(args: argparse.Namespace) -> int:
    """Launch the interactive PySide6 desktop GUI."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from .gui.main_window import MainWindow

    # Configure high-DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])

    app.setApplicationName("img2plot")
    app.setOrganizationName("img2plot")

    window = MainWindow(initial_image=args.image)
    if args.fullscreen:
        window.toggle_fullscreen()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
