"""
pv/sidebar.py
─────────────
Sidebar class: builds the scrollable left panel and exposes all widgets
and refresh methods. Contains zero application logic.

Public attributes (available after __init__):
  StringVars (editable) : var_lat, var_lon, var_alt, var_bearing,
                          var_time_offset, var_sync, var_spd_ov
  StringVars (display)  : lbl_schema, lbl_onode, lbl_spd_ms, lbl_spd_kph
  Labels                : lbl_editing, lbl_dist  (use .config() to update)
  Treeviews             : path_tv, seg_tv, meas_tv
  Object-type controls  : obj_type_var, lbl_obj_hint, btn_cancel_line
  Path-list buttons     : btn_add, btn_toggle, btn_remove, btn_fit
  Object buttons        : btn_edit_obj, btn_move_obj, btn_remove_obj, btn_clear_objs
"""
import tkinter as tk
from tkinter import ttk
from .constants import (PANEL, CARD, BORDER, ACCENT, ACCENT2,
                        TEXT, DIM, GREEN, RED, YELLOW, FONT_BODY, OBJ_ICON)
from .models import obj_info


class Sidebar:

    def __init__(self, host):
        self._build(host)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self, host):
        cv  = tk.Canvas(host, bg=PANEL, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(host, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        self._frame = ttk.Frame(cv)
        self._frame.columnconfigure(0, weight=1)
        wid = cv.create_window((0, 0), window=self._frame, anchor="nw")
        self._frame.bind("<Configure>",
                         lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfig(wid, width=e.width))
        cv.bind_all("<MouseWheel>",
                    lambda e: cv.yview_scroll(-1*(e.delta//120), "units"))

        f = self._frame
        p = dict(padx=12, pady=2)

        # ── LOADED PATHS ──────────────────────────────────────────────────────
        self._sec(f, "LOADED PATHS")
        self.path_tv = ttk.Treeview(f, columns=("clr","name","vis"),
                                     show="headings", height=4,
                                     selectmode="browse")
        self.path_tv.heading("clr",  text="")
        self.path_tv.heading("name", text="Path name")
        self.path_tv.heading("vis",  text="Vis")
        self.path_tv.column("clr",  width=22,  anchor="center", stretch=False)
        self.path_tv.column("name", width=190, anchor="w",      stretch=True)
        self.path_tv.column("vis",  width=30,  anchor="center", stretch=False)
        self.path_tv.pack(fill="x", **p)

        br = ttk.Frame(f); br.pack(fill="x", padx=12, pady=(2,4))
        self.btn_add    = ttk.Button(br, text="➕ Add",     command=lambda: None)
        self.btn_toggle = ttk.Button(br, text="👁 Toggle",  command=lambda: None)
        self.btn_remove = ttk.Button(br, text="🗑 Remove",  command=lambda: None)
        self.btn_fit    = ttk.Button(br, text="⛶ Fit all", command=lambda: None)
        for btn in (self.btn_add, self.btn_toggle, self.btn_remove, self.btn_fit):
            btn.pack(side="left", padx=2)

        self.lbl_editing = ttk.Label(f, text="— no path selected —",
                                      style="Dim.TLabel")
        self.lbl_editing.pack(anchor="w", padx=12, pady=(6,0))

        # ── ORIGIN DATUM ──────────────────────────────────────────────────────
        self._sec(f, "ORIGIN DATUM")
        self.var_lat     = self._field(f, "Latitude   (°N)")
        self.var_lon     = self._field(f, "Longitude  (°E)")
        self.var_alt     = self._field(f, "Altitude     (m)")
        self.var_bearing = self._field(f, "Bearing      (°)")

        # ── HEADER PARAMS ─────────────────────────────────────────────────────
        self._sec(f, "HEADER PARAMS")
        self.lbl_schema      = self._kv(f, "Schema")
        self.lbl_onode       = self._kv(f, "Origin node")
        self.var_time_offset = self._field(f, "Start time offset")
        self.var_sync        = self._field(f, "Sync code")

        # ── TARGET SPEED ──────────────────────────────────────────────────────
        self._sec(f, "TARGET SPEED")
        self.lbl_spd_ms  = self._kv(f, "Cruise (m/s)")
        self.lbl_spd_kph = self._kv(f, "Cruise (km/h)")
        self.var_spd_ov  = self._field(f, "Override (km/h)")

        # ── SEGMENTS ──────────────────────────────────────────────────────────
        self._sec(f, "SEGMENTS  (double-click to edit)")
        self.seg_tv = ttk.Treeview(f, columns=("tp","len","ev"),
                                    show="headings", height=6,
                                    selectmode="browse")
        for col, hd, w in [("tp","Type",68),("len","Length (m)",80),
                            ("ev","End v (km/h)",90)]:
            self.seg_tv.heading(col, text=hd)
            self.seg_tv.column(col, width=w, anchor="center", stretch=False)
        self.seg_tv.pack(fill="x", **p)

        # ── MEASUREMENT OBJECTS ───────────────────────────────────────────────
        self._sec(f, "MEASUREMENT OBJECTS")
        top = ttk.Frame(f); top.pack(fill="x", padx=12, pady=(4,2))
        ttk.Label(top, text="Add:", style="Dim.TLabel").pack(side="left")
        self.obj_type_var = tk.StringVar(value="Point")
        om = tk.OptionMenu(top, self.obj_type_var, "Point", "Line", "Rectangle")
        om.config(bg=CARD, fg=TEXT, activebackground=BORDER, activeforeground=TEXT,
                  font=FONT_BODY, relief="flat", bd=0, highlightthickness=0, width=10)
        om["menu"].config(bg=CARD, fg=TEXT, activebackground=ACCENT2)
        om.pack(side="left", padx=6)
        self.lbl_obj_hint = ttk.Label(top, text="right-click map",
                                       style="Dim.TLabel")
        self.lbl_obj_hint.pack(side="left")
        self.btn_cancel_line = ttk.Button(top, text="✕ Cancel line",
                                           command=lambda: None)
        # not packed until a line is pending

        self.meas_tv = ttk.Treeview(f, columns=("typ","name","info"),
                                     show="headings", height=7,
                                     selectmode="extended")
        self.meas_tv.heading("typ",  text="")
        self.meas_tv.heading("name", text="Name")
        self.meas_tv.heading("info", text="Info")
        self.meas_tv.column("typ",  width=24,  anchor="center", stretch=False)
        self.meas_tv.column("name", width=85,  anchor="w",      stretch=False)
        self.meas_tv.column("info", width=165, anchor="w",      stretch=True)
        self.meas_tv.pack(fill="x", **p)

        mr = ttk.Frame(f); mr.pack(fill="x", padx=12, pady=2)
        self.btn_edit_obj   = ttk.Button(mr, text="✏ Edit",       command=lambda: None)
        self.btn_move_obj   = ttk.Button(mr, text="✥ Move on map",command=lambda: None)
        self.btn_remove_obj = ttk.Button(mr, text="🗑 Remove",     command=lambda: None)
        self.btn_clear_objs = ttk.Button(mr, text="Clear custom", command=lambda: None)
        for btn in (self.btn_edit_obj, self.btn_move_obj,
                    self.btn_remove_obj, self.btn_clear_objs):
            btn.pack(side="left", padx=2)

        # ── DISTANCE RESULT ───────────────────────────────────────────────────
        self._sec(f, "DISTANCE RESULT")
        self.lbl_dist = ttk.Label(f, text="—  select 2 objects above  —",
                                   style="Dim.TLabel", wraplength=300,
                                   justify="left")
        self.lbl_dist.pack(anchor="w", padx=12, pady=4)

    # ── Private layout helpers ────────────────────────────────────────────────
    def _sec(self, parent, title):
        row = ttk.Frame(parent); row.pack(fill="x", padx=8, pady=(10,1))
        ttk.Label(row, text=title, style="H.TLabel").pack(side="left")
        tk.Frame(row, bg=BORDER, height=1).pack(side="left", fill="x",
                                                  expand=True, padx=6)

    def _kv(self, parent, key):
        row = ttk.Frame(parent); row.pack(fill="x", padx=12, pady=1)
        ttk.Label(row, text=key+":", style="Dim.TLabel",
                  width=20, anchor="w").pack(side="left")
        var = tk.StringVar(value="—")
        ttk.Label(row, textvariable=var, anchor="w").pack(side="left")
        return var

    def _field(self, parent, key):
        row = ttk.Frame(parent); row.pack(fill="x", padx=12, pady=1)
        ttk.Label(row, text=key+":", style="Dim.TLabel",
                  width=20, anchor="w").pack(side="left")
        var = tk.StringVar()
        ttk.Entry(row, textvariable=var, width=18, font=FONT_BODY).pack(side="left")
        return var

    # ── Public display-update API ─────────────────────────────────────────────
    def set_editing_label(self, name, color):
        self.lbl_editing.config(text=f"✎  Editing:  {name}", foreground=color)

    def set_obj_hint(self, text):
        self.lbl_obj_hint.config(text=text)

    def set_dist_result(self, text, color, font):
        self.lbl_dist.config(text=text, foreground=color, font=font)

    def populate_path_fields(self, pd):
        """Fill all editable fields from a path dict."""
        self.set_editing_label(pd["name"], pd["color"])
        self.lbl_schema.set(pd["schema"])
        self.lbl_onode.set(pd["origin_node"])
        self.var_lat.set(f"{pd['lat0']:.8f}")
        self.var_lon.set(f"{pd['lon0']:.8f}")
        self.var_alt.set(f"{pd['alt0']:.3f}")
        self.var_bearing.set(f"{pd['bearing']:.5f}")
        self.var_time_offset.set(pd["start_time_offset"])
        self.var_sync.set(pd["sync_code"])
        speeds = [s["velocity"] for s in pd["segments"] if s["velocity"] > 0]
        cruise = max(speeds) if speeds else 0.0
        self.lbl_spd_ms.set(f"{cruise:.4f}")
        self.lbl_spd_kph.set(f"{cruise*3.6:.3f}")
        self.var_spd_ov.set(f"{cruise*3.6:.3f}")
        self.refresh_seg_table(pd["segments"])

    def clear_path_fields(self):
        self.lbl_editing.config(text="— no path selected —", foreground=DIM)
        for v in [self.var_lat, self.var_lon, self.var_alt, self.var_bearing,
                  self.var_time_offset, self.var_sync, self.var_spd_ov]:
            v.set("")
        for kv in [self.lbl_schema, self.lbl_onode,
                   self.lbl_spd_ms, self.lbl_spd_kph]:
            kv.set("—")
        for row in self.seg_tv.get_children():
            self.seg_tv.delete(row)

    def refresh_path_list(self, paths, active_idx):
        for row in self.path_tv.get_children():
            self.path_tv.delete(row)
        for i, pd in enumerate(paths):
            vis   = "●" if pd["visible"] else "○"
            short = pd["name"][:28] + ("…" if len(pd["name"]) > 28 else "")
            iid   = f"p{i}"
            self.path_tv.insert("", "end", iid=iid,
                                values=("■", short, vis), tags=(f"pc{i}",))
            self.path_tv.tag_configure(f"pc{i}", foreground=pd["color"])
        if 0 <= active_idx < len(paths):
            self.path_tv.selection_set(f"p{active_idx}")
            self.path_tv.see(f"p{active_idx}")

    def refresh_seg_table(self, segments):
        for row in self.seg_tv.get_children():
            self.seg_tv.delete(row)
        for s in segments:
            ln  = f"{s['length']:.2f}" if s["length"] is not None else "—"
            ev  = f"{s['end_velocity']*3.6:.3f}"
            tag = "stop" if s["type"] == "Stop" else "str8"
            self.seg_tv.insert("", "end", values=(s["type"], ln, ev), tags=(tag,))
        self.seg_tv.tag_configure("stop", foreground=RED)
        self.seg_tv.tag_configure("str8", foreground=GREEN)

    def refresh_meas_table(self, paths, custom_objs):
        for row in self.meas_tv.get_children():
            self.meas_tv.delete(row)
        for i, pd in enumerate(paths):
            if not pd["visible"]:
                continue
            tag = f"pc{i}"
            for kp in pd["keypoints"]:
                self.meas_tv.insert("", "end",
                    values=("■", f"#{i+1} {kp['name']}",
                            f"{kp['lat']:.5f}°,  {kp['lon']:.5f}°"),
                    tags=(tag,))
            self.meas_tv.tag_configure(tag, foreground=pd["color"])
        for obj in custom_objs:
            self.meas_tv.insert("", "end",
                values=(OBJ_ICON[obj["type"]], obj["name"], obj_info(obj)),
                tags=("custom",))
        self.meas_tv.tag_configure("custom", foreground=YELLOW)
