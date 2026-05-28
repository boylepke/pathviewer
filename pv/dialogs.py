"""
pv/dialogs.py
─────────────
All blocking Toplevel dialogs as standalone functions.

Every object dialog shows BOTH absolute (lat/lon) AND relative (ΔX/ΔY from
the reference origin) coordinates, with conversion buttons between the two.

Functions
─────────
ask_point_params  — create a Point
ask_line_params   — create a Line
ask_rect_params   — create a Rectangle
edit_obj          — edit any existing object
"""

import tkinter as tk
from tkinter import ttk, messagebox

from .constants import (PANEL, CARD, BORDER, ACCENT, ACCENT2,
                        DIM, YELLOW, FONT_BODY, FONT_BOLD, FONT_HEAD,
                        WHITE, OBJ_ICON)
from .geo import (latlon_to_local, local_to_latlon,
                  heading_between, endpoint_from_bearing, haversine)


# ── Shared layout helpers ─────────────────────────────────────────────────────

def _header(dlg, color, title):
    tk.Frame(dlg, bg=color, height=2).pack(fill="x")
    ttk.Label(dlg, text=title, style="H.TLabel").pack(
        pady=(10, 4), padx=14, anchor="w")

def _sep(dlg):
    tk.Frame(dlg, bg=BORDER, height=1).pack(fill="x", padx=14, pady=(6, 2))

def _subsec(dlg, title):
    r = ttk.Frame(dlg); r.pack(fill="x", padx=10, pady=(4,1))
    ttk.Label(r, text=title, style="Dim.TLabel",
              font=("Consolas",8,"bold")).pack(side="left")
    tk.Frame(r, bg=BORDER, height=1).pack(side="left", fill="x",
                                           expand=True, padx=4)

def _frow(parent, label, value, decimals=6, lw=14, ew=14):
    """Single label + entry row. Returns StringVar."""
    r = ttk.Frame(parent); r.pack(fill="x", padx=14, pady=2)
    ttk.Label(r, text=label+":", style="Dim.TLabel",
              width=lw, anchor="w").pack(side="left")
    fmt = f"{float(value):.{decimals}f}" if decimals >= 0 else str(value)
    var = tk.StringVar(value=fmt)
    ttk.Entry(r, textvariable=var, width=ew, font=FONT_BODY).pack(side="left")
    return var

def _pair_row(parent, label_a, val_a, dec_a, label_b, val_b, dec_b, lw=14, ew=10):
    """Two label+entry pairs on one row. Returns (var_a, var_b).
    Use dec=-1 to keep the value as a plain string."""
    def _fmt(v, d):
        return f"{float(v):.{d}f}" if d >= 0 else str(v)
    r = ttk.Frame(parent); r.pack(fill="x", padx=14, pady=2)
    ttk.Label(r, text=label_a+":", style="Dim.TLabel",
              width=lw, anchor="w").pack(side="left")
    va = tk.StringVar(value=_fmt(val_a, dec_a))
    ttk.Entry(r, textvariable=va, width=ew, font=FONT_BODY).pack(side="left",
                                                                   padx=(0,8))
    ttk.Label(r, text=label_b+":", style="Dim.TLabel").pack(side="left")
    vb = tk.StringVar(value=_fmt(val_b, dec_b))
    ttk.Entry(r, textvariable=vb, width=ew, font=FONT_BODY).pack(side="left")
    return va, vb

def _conv_buttons(parent, lbl_a2r, fn_a2r, lbl_r2a, fn_r2a):
    """Row with two conversion buttons."""
    r = ttk.Frame(parent); r.pack(fill="x", padx=14, pady=(2,4))
    ttk.Button(r, text=lbl_a2r, command=fn_a2r).pack(side="left")
    ttk.Button(r, text=lbl_r2a, command=fn_r2a).pack(side="left", padx=6)

def _name_row(dlg, default):
    r = ttk.Frame(dlg); r.pack(fill="x", padx=14, pady=(4,2))
    ttk.Label(r, text="Name:", style="Dim.TLabel",
              width=14, anchor="w").pack(side="left")
    v = tk.StringVar(value=default)
    ttk.Entry(r, textvariable=v, width=16, font=FONT_BODY).pack(side="left")
    return v


# ── Point creation dialog ─────────────────────────────────────────────────────

def ask_point_params(root, lat, lon, default_name, ref_path=None):
    """Create a Point. Returns obj dict or None if cancelled."""
    result = {"obj": None}
    dlg = tk.Toplevel(root)
    dlg.title("Add Point")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()

    _header(dlg, YELLOW, f"📍  New Point")
    v_name = _name_row(dlg, default_name)

    _subsec(dlg, "Absolute position")
    v_lat = _frow(dlg, "Latitude  (°N)", lat,  decimals=6)
    v_lon = _frow(dlg, "Longitude (°E)", lon,  decimals=6)

    if ref_path:
        x0, y0 = latlon_to_local(lat, lon,
                                  ref_path["lat0"], ref_path["lon0"],
                                  ref_path["bearing"])
        _subsec(dlg, f"Relative to  {ref_path['name']}")
        v_dx, v_dy = _pair_row(dlg, "ΔX (m)", x0, 3, "ΔY (m)", y0, 3)

        def a2r():
            try:
                x, y = latlon_to_local(
                    float(v_lat.get()), float(v_lon.get()),
                    ref_path["lat0"], ref_path["lon0"], ref_path["bearing"])
                v_dx.set(f"{x:.3f}"); v_dy.set(f"{y:.3f}")
            except ValueError as e:
                messagebox.showerror("Bad value", str(e), parent=dlg)

        def r2a():
            try:
                la, lo = local_to_latlon(
                    float(v_dx.get()), float(v_dy.get()),
                    ref_path["lat0"], ref_path["lon0"], ref_path["bearing"])
                v_lat.set(f"{la:.6f}"); v_lon.set(f"{lo:.6f}")
            except ValueError as e:
                messagebox.showerror("Bad value", str(e), parent=dlg)

        _conv_buttons(dlg, "↻ Abs → ΔXY", a2r, "↻ ΔXY → Abs", r2a)

    def ok():
        try:
            la = float(v_lat.get()); lo = float(v_lon.get())
        except ValueError as e:
            messagebox.showerror("Bad value", str(e), parent=dlg); return
        n = v_name.get().strip() or default_name
        result["obj"] = {"type":"point", "name":n, "lat":la, "lon":lo,
                         "_markers":[], "_paths":[]}
        dlg.destroy()

    ttk.Button(dlg, text="Add", command=ok,
               style="Accent.TButton").pack(pady=8)
    dlg.update_idletasks()
    dlg.geometry(f"{dlg.winfo_reqwidth()}x{dlg.winfo_reqheight()}")
    dlg.wait_window()
    return result["obj"]


# ── Line creation dialog ──────────────────────────────────────────────────────

def ask_line_params(root, lat1, lon1, lat2, lon2, default_name, ref_path=None):
    """Create a Line. Returns obj dict or None if cancelled."""
    result = {"obj": None}
    dlg = tk.Toplevel(root)
    dlg.title("Add Line")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()

    _header(dlg, YELLOW, "📏  New Line")
    v_name = _name_row(dlg, default_name)

    # ── Absolute endpoints ──
    _subsec(dlg, "Start point (absolute)")
    v_la1 = _frow(dlg, "Latitude  (°N)", lat1, decimals=6)
    v_lo1 = _frow(dlg, "Longitude (°E)", lon1, decimals=6)

    _subsec(dlg, "End point (absolute)")
    v_la2 = _frow(dlg, "Latitude  (°N)", lat2, decimals=6)
    v_lo2 = _frow(dlg, "Longitude (°E)", lon2, decimals=6)

    # ── Relative ──
    if ref_path:
        x1, y1 = latlon_to_local(lat1, lon1,
                                  ref_path["lat0"], ref_path["lon0"],
                                  ref_path["bearing"])
        x2, y2 = latlon_to_local(lat2, lon2,
                                  ref_path["lat0"], ref_path["lon0"],
                                  ref_path["bearing"])
        _subsec(dlg, f"Start — relative to  {ref_path['name']}")
        v_dx1, v_dy1 = _pair_row(dlg, "ΔX (m)", x1, 3, "ΔY (m)", y1, 3)
        _subsec(dlg, "End — relative")
        v_dx2, v_dy2 = _pair_row(dlg, "ΔX (m)", x2, 3, "ΔY (m)", y2, 3)

        def a2r():
            try:
                _x1,_y1 = latlon_to_local(float(v_la1.get()),float(v_lo1.get()),
                    ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                _x2,_y2 = latlon_to_local(float(v_la2.get()),float(v_lo2.get()),
                    ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                v_dx1.set(f"{_x1:.3f}"); v_dy1.set(f"{_y1:.3f}")
                v_dx2.set(f"{_x2:.3f}"); v_dy2.set(f"{_y2:.3f}")
            except ValueError as e:
                messagebox.showerror("Bad value", str(e), parent=dlg)

        def r2a():
            try:
                _la1,_lo1 = local_to_latlon(float(v_dx1.get()),float(v_dy1.get()),
                    ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                _la2,_lo2 = local_to_latlon(float(v_dx2.get()),float(v_dy2.get()),
                    ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                v_la1.set(f"{_la1:.6f}"); v_lo1.set(f"{_lo1:.6f}")
                v_la2.set(f"{_la2:.6f}"); v_lo2.set(f"{_lo2:.6f}")
            except ValueError as e:
                messagebox.showerror("Bad value", str(e), parent=dlg)

        _conv_buttons(dlg, "↻ Abs → ΔXY", a2r, "↻ ΔXY → Abs", r2a)

    # ── Heading / length (derived, editable) ──
    hdg0 = heading_between(lat1, lon1, lat2, lon2)
    len0 = haversine(lat1, lon1, lat2, lon2)
    _subsec(dlg, "Direction")
    v_hdg, v_len = _pair_row(dlg, "Heading (°)", hdg0, 2,
                                   "Length  (m)", len0, 3, lw=12)

    def recalc_end():
        try:
            la1_ = float(v_la1.get()); lo1_ = float(v_lo1.get())
            la2_, lo2_ = endpoint_from_bearing(
                la1_, lo1_, float(v_hdg.get()) % 360.0, float(v_len.get()))
            v_la2.set(f"{la2_:.6f}"); v_lo2.set(f"{lo2_:.6f}")
            if ref_path:
                x2_, y2_ = latlon_to_local(la2_, lo2_,
                    ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                v_dx2.set(f"{x2_:.3f}"); v_dy2.set(f"{y2_:.3f}")
        except ValueError as e:
            messagebox.showerror("Bad value", str(e), parent=dlg)

    ttk.Button(dlg, text="↻  Recalc end from heading + length",
               command=recalc_end).pack(padx=14, pady=(2,4), anchor="w")

    def ok():
        try:
            la1_ = float(v_la1.get()); lo1_ = float(v_lo1.get())
            la2_ = float(v_la2.get()); lo2_ = float(v_lo2.get())
        except ValueError as e:
            messagebox.showerror("Bad value", str(e), parent=dlg); return
        n   = v_name.get().strip() or default_name
        hdg = round(heading_between(la1_, lo1_, la2_, lo2_), 2)
        result["obj"] = {"type":"line", "name":n,
                         "lat1":la1_,"lon1":lo1_,"lat2":la2_,"lon2":lo2_,
                         "heading":hdg, "_markers":[], "_paths":[]}
        dlg.destroy()

    ttk.Button(dlg, text="Add", command=ok,
               style="Accent.TButton").pack(pady=8)
    dlg.update_idletasks()
    dlg.geometry(f"{dlg.winfo_reqwidth()}x{dlg.winfo_reqheight()}")
    dlg.wait_window()
    return result["obj"]


# ── Rectangle creation dialog ─────────────────────────────────────────────────

def ask_rect_params(root, clat, clon, default_name, ref_path=None):
    """Create a Rectangle. Returns obj dict or None if cancelled."""
    result = {"obj": None}
    dlg = tk.Toplevel(root)
    dlg.title("Add Rectangle")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()

    _header(dlg, YELLOW, "▭  New Rectangle")
    v_name = _name_row(dlg, default_name)

    _subsec(dlg, "Centre (absolute)")
    v_clat = _frow(dlg, "Latitude  (°N)", clat, decimals=6)
    v_clon = _frow(dlg, "Longitude (°E)", clon, decimals=6)

    if ref_path:
        cx, cy = latlon_to_local(clat, clon,
                                  ref_path["lat0"], ref_path["lon0"],
                                  ref_path["bearing"])
        _subsec(dlg, f"Centre — relative to  {ref_path['name']}")
        v_dx, v_dy = _pair_row(dlg, "ΔX (m)", cx, 3, "ΔY (m)", cy, 3)

        def a2r():
            try:
                x, y = latlon_to_local(
                    float(v_clat.get()), float(v_clon.get()),
                    ref_path["lat0"], ref_path["lon0"], ref_path["bearing"])
                v_dx.set(f"{x:.3f}"); v_dy.set(f"{y:.3f}")
            except ValueError as e:
                messagebox.showerror("Bad value", str(e), parent=dlg)

        def r2a():
            try:
                la, lo = local_to_latlon(
                    float(v_dx.get()), float(v_dy.get()),
                    ref_path["lat0"], ref_path["lon0"], ref_path["bearing"])
                v_clat.set(f"{la:.6f}"); v_clon.set(f"{lo:.6f}")
            except ValueError as e:
                messagebox.showerror("Bad value", str(e), parent=dlg)

        _conv_buttons(dlg, "↻ Abs → ΔXY", a2r, "↻ ΔXY → Abs", r2a)

    _subsec(dlg, "Dimensions")
    v_w, v_h   = _pair_row(dlg, "Width  (m)", "10.00", -1,
                                  "Length (m)", "5.00",  -1, lw=12)
    v_hdg      = _frow(dlg, "Heading    (°)", "0.00", decimals=-1)

    def ok():
        try:
            la   = float(v_clat.get()); lo  = float(v_clon.get())
            w    = round(float(v_w.get()), 2)
            h_m  = round(float(v_h.get()), 2)
            hdg  = round(float(v_hdg.get()), 2) % 360.0
        except ValueError as e:
            messagebox.showerror("Bad value", str(e), parent=dlg); return
        n = v_name.get().strip() or default_name
        result["obj"] = {"type":"rect", "name":n,
                         "clat":la, "clon":lo,
                         "width_m":w, "height_m":h_m, "heading":hdg,
                         "_markers":[], "_paths":[]}
        dlg.destroy()

    ttk.Button(dlg, text="Add", command=ok,
               style="Accent.TButton").pack(pady=8)
    dlg.update_idletasks()
    dlg.geometry(f"{dlg.winfo_reqwidth()}x{dlg.winfo_reqheight()}")
    dlg.wait_window()
    return result["obj"]


# ── Generic object editor ─────────────────────────────────────────────────────

def edit_obj(root, obj, ref_path=None):
    """Edit any custom measurement object in-place. Returns True if applied."""
    result = {"ok": False}
    t    = obj["type"]
    icon = OBJ_ICON[t]

    dlg = tk.Toplevel(root)
    dlg.title(f"Edit  {icon}  {obj['name']}")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()

    _header(dlg, YELLOW, f"{icon}  {obj['name']}  ({t})")

    # Name
    v_name = _name_row(dlg, obj["name"])

    # ── Point ──────────────────────────────────────────────────────────────────
    if t == "point":
        h = 285 if ref_path else 195
        _subsec(dlg, "Absolute position")
        v_lat = _frow(dlg, "Latitude  (°N)", obj["lat"])
        v_lon = _frow(dlg, "Longitude (°E)", obj["lon"])
        if ref_path:
            x0, y0 = latlon_to_local(obj["lat"], obj["lon"],
                                      ref_path["lat0"], ref_path["lon0"],
                                      ref_path["bearing"])
            _subsec(dlg, f"Relative to  {ref_path['name']}")
            v_dx, v_dy = _pair_row(dlg, "ΔX (m)", x0, 3, "ΔY (m)", y0, 3)
            def a2r():
                try:
                    x, y = latlon_to_local(float(v_lat.get()),float(v_lon.get()),
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    v_dx.set(f"{x:.3f}"); v_dy.set(f"{y:.3f}")
                except ValueError as e: messagebox.showerror("Bad value",str(e),parent=dlg)
            def r2a():
                try:
                    la, lo = local_to_latlon(float(v_dx.get()),float(v_dy.get()),
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    v_lat.set(f"{la:.6f}"); v_lon.set(f"{lo:.6f}")
                except ValueError as e: messagebox.showerror("Bad value",str(e),parent=dlg)
            _conv_buttons(dlg, "↻ Abs → ΔXY", a2r, "↻ ΔXY → Abs", r2a)
        def collect():
            obj["name"] = v_name.get().strip() or obj["name"]
            obj["lat"]  = float(v_lat.get())
            obj["lon"]  = float(v_lon.get())

    # ── Line ───────────────────────────────────────────────────────────────────
    elif t == "line":
        h = 460 if ref_path else 325
        _subsec(dlg, "Start point (absolute)")
        v_la1 = _frow(dlg, "Latitude  (°N)", obj["lat1"])
        v_lo1 = _frow(dlg, "Longitude (°E)", obj["lon1"])
        _subsec(dlg, "End point (absolute)")
        v_la2 = _frow(dlg, "Latitude  (°N)", obj["lat2"])
        v_lo2 = _frow(dlg, "Longitude (°E)", obj["lon2"])
        if ref_path:
            x1,y1 = latlon_to_local(obj["lat1"],obj["lon1"],
                ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
            x2,y2 = latlon_to_local(obj["lat2"],obj["lon2"],
                ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
            _subsec(dlg, f"Start — relative to  {ref_path['name']}")
            v_dx1, v_dy1 = _pair_row(dlg, "ΔX (m)", x1, 3, "ΔY (m)", y1, 3)
            _subsec(dlg, "End — relative")
            v_dx2, v_dy2 = _pair_row(dlg, "ΔX (m)", x2, 3, "ΔY (m)", y2, 3)
            def a2r():
                try:
                    _x1,_y1=latlon_to_local(float(v_la1.get()),float(v_lo1.get()),
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    _x2,_y2=latlon_to_local(float(v_la2.get()),float(v_lo2.get()),
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    v_dx1.set(f"{_x1:.3f}");v_dy1.set(f"{_y1:.3f}")
                    v_dx2.set(f"{_x2:.3f}");v_dy2.set(f"{_y2:.3f}")
                except ValueError as e: messagebox.showerror("Bad value",str(e),parent=dlg)
            def r2a():
                try:
                    _la1,_lo1=local_to_latlon(float(v_dx1.get()),float(v_dy1.get()),
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    _la2,_lo2=local_to_latlon(float(v_dx2.get()),float(v_dy2.get()),
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    v_la1.set(f"{_la1:.6f}");v_lo1.set(f"{_lo1:.6f}")
                    v_la2.set(f"{_la2:.6f}");v_lo2.set(f"{_lo2:.6f}")
                except ValueError as e: messagebox.showerror("Bad value",str(e),parent=dlg)
            _conv_buttons(dlg, "↻ Abs → ΔXY", a2r, "↻ ΔXY → Abs", r2a)
        cur_hdg = obj.get("heading",
                          heading_between(obj["lat1"],obj["lon1"],
                                          obj["lat2"],obj["lon2"]))
        cur_len = haversine(obj["lat1"],obj["lon1"],obj["lat2"],obj["lon2"])
        _subsec(dlg, "Direction")
        v_hdg, v_len = _pair_row(dlg, "Heading (°)", cur_hdg, 2,
                                       "Length  (m)", cur_len, 3, lw=12)
        def recalc():
            try:
                la1_ = float(v_la1.get()); lo1_ = float(v_lo1.get())
                la2_, lo2_ = endpoint_from_bearing(
                    la1_, lo1_, float(v_hdg.get()) % 360.0, float(v_len.get()))
                v_la2.set(f"{la2_:.6f}"); v_lo2.set(f"{lo2_:.6f}")
                if ref_path:
                    x2_,y2_=latlon_to_local(la2_,lo2_,
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    v_dx2.set(f"{x2_:.3f}");v_dy2.set(f"{y2_:.3f}")
            except ValueError as e: messagebox.showerror("Bad value",str(e),parent=dlg)
        ttk.Button(dlg, text="↻  Recalc end from heading + length",
                   command=recalc).pack(padx=14, pady=(2,4), anchor="w")
        def collect():
            la1_ = float(v_la1.get()); lo1_ = float(v_lo1.get())
            la2_ = float(v_la2.get()); lo2_ = float(v_lo2.get())
            obj["name"] = v_name.get().strip() or obj["name"]
            obj["lat1"] = la1_; obj["lon1"] = lo1_
            obj["lat2"] = la2_; obj["lon2"] = lo2_
            obj["heading"] = round(heading_between(la1_,lo1_,la2_,lo2_), 2)

    # ── Rectangle ──────────────────────────────────────────────────────────────
    elif t == "rect":
        h = 340 if ref_path else 255
        _subsec(dlg, "Centre (absolute)")
        v_clat = _frow(dlg, "Latitude  (°N)", obj["clat"])
        v_clon = _frow(dlg, "Longitude (°E)", obj["clon"])
        if ref_path:
            cx,cy = latlon_to_local(obj["clat"],obj["clon"],
                ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
            _subsec(dlg, f"Centre — relative to  {ref_path['name']}")
            v_dx, v_dy = _pair_row(dlg, "ΔX (m)", cx, 3, "ΔY (m)", cy, 3)
            def a2r():
                try:
                    x,y=latlon_to_local(float(v_clat.get()),float(v_clon.get()),
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    v_dx.set(f"{x:.3f}");v_dy.set(f"{y:.3f}")
                except ValueError as e: messagebox.showerror("Bad value",str(e),parent=dlg)
            def r2a():
                try:
                    la,lo=local_to_latlon(float(v_dx.get()),float(v_dy.get()),
                        ref_path["lat0"],ref_path["lon0"],ref_path["bearing"])
                    v_clat.set(f"{la:.6f}");v_clon.set(f"{lo:.6f}")
                except ValueError as e: messagebox.showerror("Bad value",str(e),parent=dlg)
            _conv_buttons(dlg, "↻ Abs → ΔXY", a2r, "↻ ΔXY → Abs", r2a)
        _subsec(dlg, "Dimensions")
        v_w, v_h_   = _pair_row(dlg, "Width  (m)", obj["width_m"],  2,
                                       "Length (m)", obj["height_m"], 2, lw=12)
        v_hdg       = _frow(dlg, "Heading    (°)", obj.get("heading",0.0), decimals=2)
        def collect():
            obj["name"]     = v_name.get().strip() or obj["name"]
            obj["clat"]     = float(v_clat.get())
            obj["clon"]     = float(v_clon.get())
            obj["width_m"]  = round(float(v_w.get()),   2)
            obj["height_m"] = round(float(v_h_.get()),  2)
            obj["heading"]  = round(float(v_hdg.get()), 2) % 360.0

    def ok():
        try:
            collect()
            result["ok"] = True
            dlg.destroy()
        except ValueError as e:
            messagebox.showerror("Bad value", str(e), parent=dlg)

    ttk.Button(dlg, text="Apply", command=ok,
               style="Accent.TButton").pack(pady=8)
    dlg.update_idletasks()
    dlg.geometry(f"{dlg.winfo_reqwidth()}x{dlg.winfo_reqheight()}")
    dlg.wait_window()
    return result["ok"]
