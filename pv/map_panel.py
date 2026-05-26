"""
pv/map_panel.py
───────────────
MapPanel: satellite map widget + draw / erase methods for paths and objects.
No highlight system — measurement is handled purely through the sidebar.
"""
import tkinter as tk
from tkinter import ttk

try:
    import tkintermapview
except ImportError:
    import sys, subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "tkintermapview"])
    import tkintermapview

from .constants import (BG, CARD, BORDER, ACCENT, ACCENT2,
                        TEXT, DIM, YELLOW, FONT_BODY,
                        TILE_SERVERS, OBJ_ICON)
from .geo import local_to_latlon, rect_corners
from .models import _n

# Colours for the two temporary map-measure pins
_PIN_A = "#00d4ff"   # cyan  — Point A
_PIN_B = "#f5c518"   # amber — Point B


class MapPanel:
    """Public attribute: map_w — the TkinterMapView widget."""

    def __init__(self, host):
        self._build(host)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self, host):
        ctrl = tk.Frame(host, bg=BG, height=34)
        ctrl.pack(fill="x"); ctrl.pack_propagate(False)
        tk.Label(ctrl, text="Tile layer:", bg=BG, fg=DIM,
                 font=FONT_BODY).pack(side="left", padx=(8, 2))
        self._tile_var = tk.StringVar(value="Satellite")
        om = tk.OptionMenu(ctrl, self._tile_var, *TILE_SERVERS.keys(),
                           command=self.set_tile)
        om.config(bg=CARD, fg=TEXT, activebackground=BORDER,
                  activeforeground=TEXT, font=FONT_BODY,
                  relief="flat", bd=0, highlightthickness=0)
        om["menu"].config(bg=CARD, fg=TEXT, activebackground=ACCENT2)
        om.pack(side="left")
        tk.Label(ctrl, text="Right-click map to add / move objects",
                 bg=BG, fg=DIM, font=FONT_BODY).pack(side="right", padx=10)
        tk.Frame(host, bg=BORDER, height=1).pack(fill="x")

        self.map_w = tkintermapview.TkinterMapView(host, corner_radius=0)
        self.map_w.pack(fill="both", expand=True)
        self.map_w.set_tile_server(TILE_SERVERS["Satellite"], max_zoom=22)
        self.map_w.set_position(47.18, 19.07)
        self.map_w.set_zoom(15)

    # ── Tile switching ────────────────────────────────────────────────────────
    def set_tile(self, name):
        if name in TILE_SERVERS:
            self.map_w.set_tile_server(TILE_SERVERS[name], max_zoom=22)

    # ── Path drawing ──────────────────────────────────────────────────────────
    def erase_path(self, pd):
        for m in pd["_markers"]:
            try: m.delete()
            except Exception: pass
        pd["_markers"] = []
        if pd["_line"]:
            try: pd["_line"].delete()
            except Exception: pass
        pd["_line"]     = None
        pd["keypoints"] = []

    def draw_path(self, pd):
        self.erase_path(pd)
        if not pd["segments"]:
            return
        color   = pd["color"]
        lat0    = pd["lat0"]
        lon0    = pd["lon0"]
        bearing = pd["bearing"]

        coords, seen = [], set()
        for s in pd["segments"]:
            key = (round(s["x"], 4), round(s["y"], 4))
            if key in seen: continue
            seen.add(key)
            coords.append(local_to_latlon(s["x"], s["y"], lat0, lon0, bearing))

        root_el = pd["xml_tree"].getroot()
        ep      = root_el.find(_n("Header") + "/" + _n("EndPoint"))
        ep_lat  = ep_lon = None
        if ep is not None:
            ex, ey  = float(ep.get("x", 0)), float(ep.get("y", 0))
            ep_lat, ep_lon = local_to_latlon(ex, ey, lat0, lon0, bearing)
            if (round(ex, 4), round(ey, 4)) not in seen:
                coords.append((ep_lat, ep_lon))

        if len(coords) >= 2:
            pd["_line"] = self.map_w.set_path(coords, color=color, width=3)

        def mk(lat, lon, name, label):
            m = self.map_w.set_marker(lat, lon, text=label,
                marker_color_circle=color,
                marker_color_outside=color,
                font=FONT_BODY)
            pd["keypoints"].append({"name": name, "lat": lat, "lon": lon,
                                     "marker": m})
            pd["_markers"].append(m)

        mk(lat0, lon0, "Origin", "⊕ Origin")
        placed = set()
        for s in pd["segments"]:
            lat, lon = local_to_latlon(s["x"], s["y"], lat0, lon0, bearing)
            key = (round(lat, 7), round(lon, 7))
            if key in placed: continue
            placed.add(key)
            mk(lat, lon, s["type"],
               "◼ Stop" if s["type"] == "Stop" else "● Seg")
        if ep_lat is not None:
            mk(ep_lat, ep_lon, "End", "◼ End")

    # ── Custom object drawing ─────────────────────────────────────────────────
    def erase_obj(self, obj):
        for m in obj["_markers"]:
            try: m.delete()
            except Exception: pass
        for p in obj["_paths"]:
            try: p.delete()
            except Exception: pass
        obj["_markers"] = []
        obj["_paths"]   = []

    def draw_obj(self, obj, on_click=None):
        self.erase_obj(obj)
        col  = YELLOW
        icon = OBJ_ICON[obj["type"]]

        def mk(lat, lon, label):
            cb = (lambda _m, o=obj: on_click(o)) if on_click else None
            m  = self.map_w.set_marker(lat, lon, text=label,
                marker_color_circle=col,
                marker_color_outside=col,
                font=FONT_BODY, command=cb)
            obj["_markers"].append(m)

        if obj["type"] == "point":
            mk(obj["lat"], obj["lon"], f"{icon} {obj['name']}")
        elif obj["type"] == "line":
            mk(obj["lat1"], obj["lon1"], "")
            mk(obj["lat2"], obj["lon2"], f"{icon} {obj['name']}")
            obj["_paths"].append(self.map_w.set_path(
                [(obj["lat1"], obj["lon1"]), (obj["lat2"], obj["lon2"])],
                color=col, width=2))
        elif obj["type"] == "rect":
            corners = rect_corners(
                obj["clat"], obj["clon"],
                obj["width_m"], obj["height_m"],
                obj.get("heading", 0.0))
            obj["_paths"].append(
                self.map_w.set_path(corners + [corners[0]],
                                    color=col, width=2))
            mk(obj["clat"], obj["clon"], f"{icon} {obj['name']}")

    # ── Map-measure pins (Way 2) ──────────────────────────────────────────────
    def set_measure_pin(self, lat, lon, label, which="A"):
        """Place a temporary measurement pin. Returns the marker object."""
        color = _PIN_A if which == "A" else _PIN_B
        return self.map_w.set_marker(lat, lon,
            text=f"  {which}",
            marker_color_circle=color,
            marker_color_outside=color,
            font=("Consolas", 9, "bold"))

    # ── Viewport helpers ──────────────────────────────────────────────────────
    def fit_to_coords(self, coords, zoom=18):
        if not coords: return
        clat = sum(c[0] for c in coords) / len(coords)
        clon = sum(c[1] for c in coords) / len(coords)
        self.map_w.set_position(clat, clon)
        self.map_w.set_zoom(zoom)

    def fit_to_all_paths(self, paths):
        all_c = [(kp["lat"], kp["lon"])
                 for pd in paths for kp in pd["keypoints"]]
        if not all_c: return
        clat = sum(c[0] for c in all_c) / len(all_c)
        clon = sum(c[1] for c in all_c) / len(all_c)
        lats = [c[0] for c in all_c]; lons = [c[1] for c in all_c]
        span = max(max(lats)-min(lats), max(lons)-min(lons))
        zoom = 18 if span < 0.001 else (16 if span < 0.005 else 14)
        self.map_w.set_position(clat, clon)
        self.map_w.set_zoom(zoom)
