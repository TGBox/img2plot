"""
img2plot - Turn images into vector drawings for pen plotters.
Entry point and backward-compatible CLI/GUI launcher.
"""

from __future__ import annotations
import sys
import os

# Ensure src is on sys.path if running directly from project root
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from img2plot.app import main

if __name__ == "__main__":
    main()
