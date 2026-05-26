"""
pv/sidebar.py
─────────────
Sidebar: path viewer + measurement.

Sections
────────
1. LOADED PATHS  — list + selected-path origin editor / transform
2. REFERENCE ORIGIN — drives relative-coord calculations
3. OBJECTS       — add / edit / remove permanent Points, Lines, Rectangles
4. MEASURE       — Way 1 (select 2 from table) | Way 2 (pick on map)
"""
import tkinter as tk
from tkinter import ttk
from .constants import (PANEL, CARD, BORDER, ACCENT, ACCENT2,
                        TEXT, DIM, GREEN, RED, YELLOW, ORANGE,
                        FONT_BODY, FONT_BOLD, OBJ_ICON)
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

        # ── 1. LOADED PATHS ───────────────────────────────────────────────────
        self._sec(f, "LOADED PATHS")
        self.path_tv = ttk.Treeview(f, columns=("clr","name","vis"),
                                     show="headings", height=4,
                                     selectmode="browse")
        self.path_tv.heading("clr",  text="")
        self.path_tv.heading("name", text="Path name")
        self.path_tv.heading("vis",  text="Vis")
        self.path_tv.column("clr",  width=22,  anchor="center", stretch=False)
        self.path_tv.column("name", width=185, anchor="w",      stretch=True)
        self.path_tv.column("vis",  width=30,  anchor="center", stretch=False)
        self.path_tv.pack(fill="x", **p)

        br = ttk.Frame(f); br.pack(fill="x", padx=12, pady=(2,2))
        self.btn_add    = ttk.Button(br, text="➕ Add",     command=lambda: None)
        self.btn_toggle = ttk.Button(br, text="👁 Toggle",  command=lambda: None)
        self.btn_remove = ttk.Button(br, text="🗑 Remove",  command=lambda: None)
        self.btn_fit    = ttk.Button(br, text="⛶ Fit all", command=lambda: None)
        for btn in (self.btn_add, self.btn_toggle, self.btn_remove, self.btn_fit):
            btn.pack(side="left", padx=2)

        # Selected path editor
        self._sec(f, "SELECTED PATH")
        nr = ttk.Frame(f); nr.pack(fill="x", padx=12, pady=(2,4))
        self.lbl_sel_name = ttk.Label(nr, text="— select a path —",
                                       style="Dim.TLabel",
                                       font=("Consolas", 9, "bold"))
        self.lbl_sel_name.pack(side="left")
        self.lbl_modified = ttk.Label(nr, text="", foreground=ORANGE,
                                       font=("Consolas", 8, "bold"),
                                       background=PANEL)
        self.lbl_modified.pack(side="right", padx=4)

        self.var_sel_lat     = self._field(f, "Latitude    (°N)")
        self.var_sel_lon     = self._field(f, "Longitude   (°E)")
        self.var_sel_bearing = self._field(f, "Bearing       (°)")
        self.var_sel_alt     = self._field(f, "Altitude      (m)")

        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(6,4))

        sr = ttk.Frame(f); sr.pack(fill="x", padx=12, pady=2)
        ttk.Label(sr, text="Shift  ΔX (m):", style="Dim.TLabel",
                  width=14, anchor="w").pack(side="left")
        self.var_dx = tk.StringVar(value="0")
        ttk.Entry(sr, textvariable=self.var_dx, width=8,
                  font=FONT_BODY).pack(side="left", padx=(0,8))
        ttk.Label(sr, text="ΔY (m):", style="Dim.TLabel").pack(side="left")
        self.var_dy = tk.StringVar(value="0")
        ttk.Entry(sr, textvariable=self.var_dy, width=8,
                  font=FONT_BODY).pack(side="left")

        rr = ttk.Frame(f); rr.pack(fill="x", padx=12, pady=2)
        ttk.Label(rr, text="Rotate  Δ  (°):", style="Dim.TLabel",
                  width=14, anchor="w").pack(side="left")
        self.var_dbrg = tk.StringVar(value="0")
        ttk.Entry(rr, textvariable=self.var_dbrg, width=8,
                  font=FONT_BODY).pack(side="left")
        ttk.Label(rr, text="  (around origin)",
                  style="Dim.TLabel").pack(side="left", padx=4)

        abr = ttk.Frame(f); abr.pack(fill="x", padx=12, pady=(4,6))
        self.btn_apply_transform = ttk.Button(
            abr, text="✓ Apply", command=lambda: None, style="Accent.TButton")
        self.btn_reset_transform = ttk.Button(
            abr, text="↺ Reset to file", command=lambda: None)
        self.btn_apply_transform.pack(side="left")
        self.btn_reset_transform.pack(side="left", padx=6)

        # ── 2. REFERENCE ORIGIN ───────────────────────────────────────────────
        self._sec(f, "REFERENCE ORIGIN")
        ttk.Label(f, text="Relative coords computed from:",
                  style="Dim.TLabel").pack(anchor="w", padx=12, pady=(0,2))
        self.ref_origin_var = tk.StringVar(value="— none —")
        self._ref_om_frame  = ttk.Frame(f)
        self._ref_om_frame.pack(fill="x", padx=12, pady=(0,2))
        self._ref_om = tk.OptionMenu(self._ref_om_frame,
                                      self.ref_origin_var, "— none —")
        self._ref_om.config(bg=CARD, fg=TEXT, activebackground=BORDER,
                             activeforeground=TEXT, font=FONT_BODY,
                             relief="flat", bd=0, highlightthickness=0, width=28)
        self._ref_om["menu"].config(bg=CARD, fg=TEXT, activebackground=ACCENT2)
        self._ref_om.pack(side="left")
        self.lbl_ref_coords = ttk.Label(f, text="", style="Dim.TLabel",
                                         wraplength=290)
        self.lbl_ref_coords.pack(anchor="w", padx=12, pady=(0,4))

        # ── 3. OBJECTS ────────────────────────────────────────────────────────
        self._sec(f, "OBJECTS")

        top = ttk.Frame(f); top.pack(fill="x", padx=12, pady=(4,2))
        ttk.Label(top, text="Add:", style="Dim.TLabel").pack(side="left")
        self.obj_type_var = tk.StringVar(value="Point")
        om = tk.OptionMenu(top, self.obj_type_var,
                           "Point", "Line", "Rectangle")
        om.config(bg=CARD, fg=TEXT, activebackground=BORDER,
                  activeforeground=TEXT, font=FONT_BODY,
                  relief="flat", bd=0, highlightthickness=0, width=10)
        om["menu"].config(bg=CARD, fg=TEXT, activebackground=ACCENT2)
        om.pack(side="left", padx=6)
        self.lbl_obj_hint = ttk.Label(top, text="right-click map",
                                       style="Dim.TLabel")
        self.lbl_obj_hint.pack(side="left")
        self.btn_cancel_line = ttk.Button(top, text="✕ Cancel",
                                           command=lambda: None)

        self.obj_tv = ttk.Treeview(f, columns=("typ","name","info"),
                                    show="headings", height=6,
                                    selectmode="browse")
        self.obj_tv.heading("typ",  text="")
        self.obj_tv.heading("name", text="Name")
        self.obj_tv.heading("info", text="Info")
        self.obj_tv.column("typ",  width=24,  anchor="center", stretch=False)
        self.obj_tv.column("name", width=80,  anchor="w",      stretch=False)
        self.obj_tv.column("info", width=165, anchor="w",      stretch=True)
        self.obj_tv.pack(fill="x", **p)

        mr = ttk.Frame(f); mr.pack(fill="x", padx=12, pady=2)
        self.btn_edit_obj   = ttk.Button(mr, text="✏ Edit",    command=lambda: None)
        self.btn_move_obj   = ttk.Button(mr, text="✥ Move",    command=lambda: None)
        self.btn_remove_obj = ttk.Button(mr, text="🗑 Remove",  command=lambda: None)
        self.btn_clear_objs = ttk.Button(mr, text="Clear all", command=lambda: None)
        for btn in (self.btn_edit_obj, self.btn_move_obj,
                    self.btn_remove_obj, self.btn_clear_objs):
            btn.pack(side="left", padx=2)

        # ── 4. MEASURE ────────────────────────────────────────────────────────
        self._sec(f, "MEASURE")

        # Way 1
        self._subsec(f, "Way 1 — select 2 objects from the list")
        ttk.Label(f,
                  text="Select any 2 rows from the Objects list above.",
                  style="Dim.TLabel", wraplength=295).pack(
                  anchor="w", padx=12, pady=(2,2))

        self.meas_tv = ttk.Treeview(f, columns=("typ","name","info"),
                                     show="headings", height=6,
                                     selectmode="extended")
        self.meas_tv.heading("typ",  text="")
        self.meas_tv.heading("name", text="Name")
        self.meas_tv.heading("info", text="Info")
        self.meas_tv.column("typ",  width=24,  anchor="center", stretch=False)
        self.meas_tv.column("name", width=80,  anchor="w",      stretch=False)
        self.meas_tv.column("info", width=165, anchor="w",      stretch=True)
        self.meas_tv.pack(fill="x", **p)

        # Way 2
        self._subsec(f, "Way 2 — pick 2 points on the map")
        w2 = ttk.Frame(f); w2.pack(fill="x", padx=12, pady=(4,2))
        self.btn_map_measure = ttk.Button(
            w2, text="📏 Start picking", command=lambda: None,
            style="Accent.TButton")
        self.btn_map_measure.pack(side="left")
        self.btn_clear_meas = ttk.Button(
            w2, text="✕ Clear", command=lambda: None)
        self.btn_clear_meas.pack(side="left", padx=8)

        self.lbl_pt_a = ttk.Label(f, text="  A :  —",
                                   style="Dim.TLabel", font=FONT_BODY)
        self.lbl_pt_a.pack(anchor="w", padx=12, pady=1)
        self.lbl_pt_b = ttk.Label(f, text="  B :  —",
                                   style="Dim.TLabel", font=FONT_BODY)
        self.lbl_pt_b.pack(anchor="w", padx=12, pady=1)

        # Result (shared by both ways)
        self._subsec(f, "Result")
        self.lbl_result = ttk.Label(
            f, text="—  set 2 points or select 2 objects  —",
            style="Dim.TLabel", wraplength=300, justify="left")
        self.lbl_result.pack(anchor="w", padx=12, pady=(4,8))

    # ── Layout helpers ────────────────────────────────────────────────────────
    def _sec(self, parent, title):
        row = ttk.Frame(parent); row.pack(fill="x", padx=8, pady=(12,1))
        ttk.Label(row, text=title, style="H.TLabel").pack(side="left")
        tk.Frame(row, bg=BORDER, height=1).pack(side="left", fill="x",
                                                  expand=True, padx=6)

    def _subsec(self, parent, title):
        row = ttk.Frame(parent); row.pack(fill="x", padx=12, pady=(8,1))
        ttk.Label(row, text=title, style="Dim.TLabel",
                  font=("Consolas", 8, "bold")).pack(side="left")
        tk.Frame(row, bg=BORDER, height=1).pack(side="left", fill="x",
                                                  expand=True, padx=4)

    def _field(self, parent, key):
        row = ttk.Frame(parent); row.pack(fill="x", padx=12, pady=1)
        ttk.Label(row, text=key+":", style="Dim.TLabel",
                  width=20, anchor="w").pack(side="left")
        var = tk.StringVar()
        ttk.Entry(row, textvariable=var, width=18, font=FONT_BODY).pack(side="left")
        return var

    # ── Public display API ────────────────────────────────────────────────────
    def set_obj_hint(self, text):
        self.lbl_obj_hint.config(text=text)

    def show_result(self, text, color=None, font=None):
        kw = dict(text=text)
        if color: kw["foreground"] = color
        if font:  kw["font"]       = font
        self.lbl_result.config(**kw)

    def show_path_fields(self, pd):
        self.lbl_sel_name.config(text=pd["name"], foreground=pd["color"])
        self.var_sel_lat.set(    f"{pd['lat0']:.8f}")
        self.var_sel_lon.set(    f"{pd['lon0']:.8f}")
        self.var_sel_bearing.set(f"{pd['bearing']:.5f}")
        self.var_sel_alt.set(    f"{pd['alt0']:.3f}")
        self.var_dx.set("0"); self.var_dy.set("0"); self.var_dbrg.set("0")
        eps = 1e-9
        changed = (abs(pd["lat0"]    - pd["orig_lat0"])    > eps or
                   abs(pd["lon0"]    - pd["orig_lon0"])    > eps or
                   abs(pd["bearing"] - pd["orig_bearing"]) > eps)
        self.lbl_modified.config(text="⚠ modified" if changed else "")

    def clear_path_fields(self):
        self.lbl_sel_name.config(text="— select a path —", foreground=DIM)
        self.lbl_modified.config(text="")
        for v in (self.var_sel_lat, self.var_sel_lon,
                  self.var_sel_bearing, self.var_sel_alt):
            v.set("")
        self.var_dx.set("0"); self.var_dy.set("0"); self.var_dbrg.set("0")

    def refresh_path_list(self, paths, active_idx):
        for row in self.path_tv.get_children():
            self.path_tv.delete(row)
        for i, pd in enumerate(paths):
            vis   = "●" if pd["visible"] else "○"
            short = pd["name"][:26] + ("…" if len(pd["name"]) > 26 else "")
            iid   = f"p{i}"
            self.path_tv.insert("", "end", iid=iid,
                                values=("■", short, vis), tags=(f"pc{i}",))
            self.path_tv.tag_configure(f"pc{i}", foreground=pd["color"])
        if 0 <= active_idx < len(paths):
            self.path_tv.selection_set(f"p{active_idx}")
            self.path_tv.see(f"p{active_idx}")

    def rebuild_ref_menu(self, paths, current_name, on_change):
        menu = self._ref_om["menu"]
        menu.delete(0, "end")
        if not paths:
            menu.add_command(label="— none —",
                             command=lambda: self.ref_origin_var.set("— none —"))
            self.ref_origin_var.set("— none —"); return
        for pd in paths:
            name = pd["name"]
            menu.add_command(label=name,
                             command=lambda n=name: (
                                 self.ref_origin_var.set(n), on_change(n)))
        names = [pd["name"] for pd in paths]
        if current_name in names:
            self.ref_origin_var.set(current_name)
        else:
            self.ref_origin_var.set(names[0]); on_change(names[0])

    def show_ref_coords(self, pd):
        if pd is None:
            self.lbl_ref_coords.config(text=""); return
        self.lbl_ref_coords.config(
            text=f"Lat {pd['lat0']:.6f}°   "
                 f"Lon {pd['lon0']:.6f}°   "
                 f"Brg {pd['bearing']:.2f}°")

    def refresh_obj_table(self, paths, custom_objs):
        """Refresh both obj_tv (objects only) and meas_tv (all items)."""
        # obj_tv — custom objects only
        for row in self.obj_tv.get_children():
            self.obj_tv.delete(row)
        for obj in custom_objs:
            self.obj_tv.insert("", "end",
                values=(OBJ_ICON[obj["type"]], obj["name"], obj_info(obj)),
                tags=("custom",))
        self.obj_tv.tag_configure("custom", foreground=YELLOW)

        # meas_tv — path keypoints + custom objects (for Way 1 measurement)
        for row in self.meas_tv.get_children():
            self.meas_tv.delete(row)
        for i, pd in enumerate(paths):
            if not pd["visible"]: continue
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
