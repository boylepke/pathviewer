"""
pv/dialogs.py
─────────────
All blocking Toplevel dialogs as standalone functions.
Each function modifies its data argument in-place and returns True on Apply,
False / None if the user cancels.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from .constants import PANEL, CARD, YELLOW, FONT_BODY, FONT_HEAD, DIM, GREEN, RED
from .geo import heading_between, endpoint_from_bearing, haversine


# ── Shared helpers ────────────────────────────────────────────────────────────

def _header(dlg, color, title):
    tk.Frame(dlg, bg=color, height=2).pack(fill="x")
    ttk.Label(dlg, text=title, style="H.TLabel").pack(
        pady=(12, 6), padx=16, anchor="w")


def _frow(dlg, label, value, decimals=6, width_lbl=20, width_ent=16):
    """Add a label + entry row; return the StringVar."""
    row = ttk.Frame(dlg); row.pack(fill="x", padx=16, pady=3)
    ttk.Label(row, text=label + ":", style="Dim.TLabel",
              width=width_lbl, anchor="w").pack(side="left")
    fmt = f"{float(value):.{decimals}f}" if decimals >= 0 else str(value)
    var = tk.StringVar(value=fmt)
    ttk.Entry(row, textvariable=var, width=width_ent,
              font=FONT_BODY).pack(side="left")
    return var


# ── Segment editor ────────────────────────────────────────────────────────────

def edit_segment(root, seg, color):
    """Edit a path segment dict in-place. Returns True if user applied."""
    if seg["type"] == "Stop":
        messagebox.showinfo("Stop segment",
                            "Stop segments have no editable length or speed.")
        return False

    result = {"ok": False}
    dlg = tk.Toplevel(root)
    dlg.title(f"Edit Segment  —  {seg['type']}")
    dlg.configure(bg=PANEL)
    dlg.geometry("340x200")
    dlg.resizable(False, False)
    dlg.grab_set()

    _header(dlg, color, f"Segment  —  {seg['type']}")
    v_len = _frow(dlg, "Length       (m)",   seg["length"] or 0,       decimals=4)
    v_ev  = _frow(dlg, "End vel  (km/h)",    seg["end_velocity"] * 3.6, decimals=4)
    v_sv  = _frow(dlg, "Start vel (km/h)",   seg["velocity"] * 3.6,    decimals=4)

    def apply():
        try:
            if seg["length"] is not None:
                seg["length"] = float(v_len.get())
            seg["end_velocity"] = float(v_ev.get()) / 3.6
            seg["velocity"]     = float(v_sv.get()) / 3.6
            result["ok"] = True
            dlg.destroy()
        except ValueError as e:
            messagebox.showerror("Bad value", str(e), parent=dlg)

    ttk.Button(dlg, text="Apply", command=apply,
               style="Accent.TButton").pack(pady=10)
    dlg.wait_window()
    return result["ok"]


# ── Rectangle creator ─────────────────────────────────────────────────────────

def ask_rect_params(root, clat, clon, default_name):
    """Show Add Rectangle dialog. Returns a new obj dict or None if cancelled."""
    result = {"obj": None}
    dlg = tk.Toplevel(root)
    dlg.title("Add Rectangle")
    dlg.configure(bg=PANEL)
    dlg.geometry("330x265")
    dlg.resizable(False, False)
    dlg.grab_set()

    _header(dlg, YELLOW, "New Rectangle")
    v_name = _frow(dlg, "Name",          default_name, decimals=-1)
    v_w    = _frow(dlg, "Width  (m)",    "10.00",      decimals=-1)
    v_h    = _frow(dlg, "Height (m)",    "5.00",       decimals=-1)
    v_hdg  = _frow(dlg, "Heading  (°)",  "0.00",       decimals=-1)
    ttk.Label(dlg, text=f"Centre: {clat:.6f}°,  {clon:.6f}°",
              style="Dim.TLabel").pack(padx=16, anchor="w")

    def ok():
        try:
            w   = round(float(v_w.get()),   2)
            h   = round(float(v_h.get()),   2)
            hdg = round(float(v_hdg.get()), 2) % 360.0
        except ValueError:
            messagebox.showerror("Bad value",
                "Width, height and heading must be numbers.", parent=dlg)
            return
        result["obj"] = {
            "type": "rect", "name": v_name.get().strip() or default_name,
            "clat": clat, "clon": clon,
            "width_m": w, "height_m": h, "heading": hdg,
            "_markers": [], "_paths": [],
        }
        dlg.destroy()

    ttk.Button(dlg, text="Add", command=ok,
               style="Accent.TButton").pack(pady=10)
    dlg.wait_window()
    return result["obj"]


# ── Generic object editor ─────────────────────────────────────────────────────

def edit_obj(root, obj):
    """Edit any custom measurement object in-place. Returns True if applied."""
    from .constants import OBJ_ICON
    result = {"ok": False}

    dlg = tk.Toplevel(root)
    dlg.title(f"Edit  {OBJ_ICON[obj['type']]}  {obj['name']}")
    dlg.configure(bg=PANEL)
    dlg.resizable(False, False)
    dlg.grab_set()

    _header(dlg, YELLOW,
            f"{OBJ_ICON[obj['type']]}  {obj['name']}  ({obj['type']})")

    # Name row (all types)
    r = ttk.Frame(dlg); r.pack(fill="x", padx=16, pady=3)
    ttk.Label(r, text="Name:", style="Dim.TLabel",
              width=20, anchor="w").pack(side="left")
    v_name = tk.StringVar(value=obj["name"])
    ttk.Entry(r, textvariable=v_name, width=16,
              font=FONT_BODY).pack(side="left")

    if obj["type"] == "point":
        dlg.geometry("360x190")
        v_lat = _frow(dlg, "Latitude  (°N)", obj["lat"])
        v_lon = _frow(dlg, "Longitude (°E)", obj["lon"])
        def collect():
            obj["name"] = v_name.get().strip() or obj["name"]
            obj["lat"]  = float(v_lat.get())
            obj["lon"]  = float(v_lon.get())

    elif obj["type"] == "line":
        dlg.geometry("360x345")
        v_la1 = _frow(dlg, "Start latitude",  obj["lat1"])
        v_lo1 = _frow(dlg, "Start longitude", obj["lon1"])
        v_la2 = _frow(dlg, "End latitude",    obj["lat2"])
        v_lo2 = _frow(dlg, "End longitude",   obj["lon2"])
        cur_hdg = obj.get("heading",
                          heading_between(obj["lat1"], obj["lon1"],
                                          obj["lat2"], obj["lon2"]))
        cur_len = haversine(obj["lat1"], obj["lon1"], obj["lat2"], obj["lon2"])
        v_hdg = _frow(dlg, "Heading        (°)", round(cur_hdg, 2), decimals=2)
        v_len = _frow(dlg, "Length          (m)", round(cur_len, 3), decimals=3)
        ttk.Label(dlg,
                  text="  ↑ edit heading / length → click Recalc to update end point",
                  style="Dim.TLabel", wraplength=300).pack(anchor="w", padx=16)
        def recalc():
            try:
                la1 = float(v_la1.get()); lo1 = float(v_lo1.get())
                la2, lo2 = endpoint_from_bearing(
                    la1, lo1, float(v_hdg.get()) % 360.0, float(v_len.get()))
                v_la2.set(f"{la2:.6f}"); v_lo2.set(f"{lo2:.6f}")
            except ValueError as e:
                messagebox.showerror("Bad value", str(e), parent=dlg)
        ttk.Button(dlg, text="↻  Recalc end point",
                   command=recalc).pack(padx=16, pady=(0, 4), anchor="w")
        def collect():
            la1 = float(v_la1.get()); lo1 = float(v_lo1.get())
            la2 = float(v_la2.get()); lo2 = float(v_lo2.get())
            obj["name"] = v_name.get().strip() or obj["name"]
            obj["lat1"] = la1; obj["lon1"] = lo1
            obj["lat2"] = la2; obj["lon2"] = lo2
            obj["heading"] = round(heading_between(la1, lo1, la2, lo2), 2)

    elif obj["type"] == "rect":
        dlg.geometry("360x270")
        v_clat = _frow(dlg, "Centre latitude",  obj["clat"])
        v_clon = _frow(dlg, "Centre longitude", obj["clon"])
        v_w    = _frow(dlg, "Width  (m)",       obj["width_m"],         decimals=2)
        v_h    = _frow(dlg, "Height (m)",       obj["height_m"],        decimals=2)
        v_hdg  = _frow(dlg, "Heading  (°)",     obj.get("heading",0.0), decimals=2)
        def collect():
            obj["name"]     = v_name.get().strip() or obj["name"]
            obj["clat"]     = float(v_clat.get())
            obj["clon"]     = float(v_clon.get())
            obj["width_m"]  = round(float(v_w.get()),   2)
            obj["height_m"] = round(float(v_h.get()),   2)
            obj["heading"]  = round(float(v_hdg.get()), 2) % 360.0

    def ok():
        try:
            collect()
            result["ok"] = True
            dlg.destroy()
        except ValueError as e:
            messagebox.showerror("Bad value", str(e), parent=dlg)

    ttk.Button(dlg, text="Apply", command=ok,
               style="Accent.TButton").pack(pady=10)
    dlg.wait_window()
    return result["ok"]
