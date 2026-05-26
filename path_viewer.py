#!/usr/bin/env python3
"""
path_viewer.py — entry point
Run:  python path_viewer.py
Deps: pip install tkintermapview
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pv.app import PathViewerApp

if __name__ == "__main__":
    PathViewerApp()
