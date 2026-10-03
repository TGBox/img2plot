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

# Remove current directory from sys.path if present to avoid shadowing the img2plot package
while "" in sys.path:
    sys.path.remove("")
while "." in sys.path:
    sys.path.remove(".")
while current_dir in sys.path:
    sys.path.remove(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Remove any shadowed module reference
if "img2plot" in sys.modules:
    del sys.modules["img2plot"]

from img2plot.app import main

if __name__ == "__main__":
    main()
