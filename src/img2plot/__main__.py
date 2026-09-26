"""
Package executable entry point for python -m img2plot.
"""

from __future__ import annotations
import sys
from .app import main

if __name__ == "__main__":
    sys.exit(main())
