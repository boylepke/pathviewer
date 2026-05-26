"""
pv/sidebar.py
─────────────
Sidebar: path viewer + measurement tool.

Sections
────────
1. LOADED PATHS      – list; below it: selected-path origin editor + transform
2. REFERENCE ORIGIN  – choose which origin drives relative-coord calculations
3. MEASUREMENT OBJECTS – Point / Line / Rectangle add / edit / remove
4. DETAILS           – adaptive: coords (1 sel) or distance (2 sel)
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

        # ── Selected path editor ──────────────────────────────────────────────
        self._sec(f, "SELECTED PATH")

        # name + modified indicator on same row
        nr = ttk.Frame(f); nr.pack(fill="x", padx=12, pady=(2,4))
        self.lbl_sel_name = ttk.Label(nr, text="— select a path —",
                                       style="Dim.TLabel",
                                       font=("Consolas", 9, "bold"))
        self.lbl_sel_name.pack(side="left")
        self.lbl_modified = ttk.Label(nr, text="", foreground=ORANGE,
                                       font=("Consolas", 8, "bold"),
                                       background=PANEL)
        self.lbl_modified.pack(side="right", padx=4)

        # Editable origin fields
        self.var_sel_lat     = self._field(f, "Latitude    (°N)", w=20)
        self.var_sel_lon     = self._field(f, "Longitude   (°E)", w=20)
        self.var_sel_bearing = self._field(f, "Bearing       (°)", w=20)
        self.var_sel_alt     = self._field(f, "Altitude      (m)", w=20)

        # Separator
        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(6,4))

        # Shift row
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

        # Rotate row
        rr = ttk.Frame(f); rr.pack(fill="x", padx=12, pady=2)
        ttk.Label(rr, text="Rotate  Δ  (°):", style="Dim.TLabel",
                  width=14, anchor="w").pack(side="left")
        self.var_dbrg = tk.StringVar(value="0")
        ttk.Entry(rr, textvariable=self.var_dbrg, width=8,
                  font=FONT_BODY).pack(side="left")
        ttk.Label(rr, text="  (rotates around origin)",
                  style="Dim.TLabel").pack(side="left", padx=4)

        # Apply / Reset buttons
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

        # ── 3. MEASUREMENT OBJECTS ────────────────────────────────────────────
        self._sec(f, "MEASUREMENT OBJECTS")
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

        self.meas_tv = ttk.Treeview(f, columns=("typ","name","info"),
                                     show="headings", height=7,
                                     selectmode="extended")
        self.meas_tv.heading("typ",  text="")
        self.meas_tv.heading("name", text="Name")
        self.meas_tv.heading("info", text="Info")
        self.meas_tv.column("typ",  width=24,  anchor="center", stretch=False)
        self.meas_tv.column("name", width=80,  anchor="w",      stretch=False)
        self.meas_tv.column("info", width=165, anchor="w",      stretch=True)
        self.meas_tv.pack(fill="x", **p)

        mr = ttk.Frame(f); mr.pack(fill="x", padx=12, pady=2)
        self.btn_edit_obj   = ttk.Button(mr, text="✏ Edit",    command=lambda: None)
        self.btn_move_obj   = ttk.Button(mr, text="✥ Move",    command=lambda: None)
        self.btn_remove_obj = ttk.Button(mr, text="🗑 Remove",  command=lambda: None)
        self.btn_clear_objs = ttk.Button(mr, text="Clear all", command=lambda: None)
        for btn in (self.btn_edit_obj, self.btn_move_obj,
                    self.btn_remove_obj, self.btn_clear_objs):
            btn.pack(side="left", padx=2)

        # ── 4. DETAILS ────────────────────────────────────────────────────────
        self._sec(f, "DETAILS")
        self.lbl_details = ttk.Label(
            f,
            text="—  select an object for coordinates\n"
                 "—  select two for distance",
            style="Dim.TLabel", wraplength=300, justify="left")
        self.lbl_details.pack(anchor="w", padx=12, pady=6)

    # ── Private layout helpers ────────────────────────────────────────────────
    def _sec(self, parent, title):
        row = ttk.Frame(parent); row.pack(fill="x", padx=8, pady=(12,1))
        ttk.Label(row, text=title, style="H.TLabel").pack(side="left")
        tk.Frame(row, bg=BORDER, height=1).pack(side="left", fill="x",
                                                  expand=True, padx=6)

    def _field(self, parent, key, w=18):
        row = ttk.Frame(parent); row.pack(fill="x", padx=12, pady=1)
        ttk.Label(row, text=key+":", style="Dim.TLabel",
                  width=w, anchor="w").pack(side="left")
        var = tk.StringVar()
        ttk.Entry(row, textvariable=var, width=18,
                  font=FONT_BODY).pack(side="left")
        return var

    # ── Public display-update API ─────────────────────────────────────────────
    def set_obj_hint(self, text):
        self.lbl_obj_hint.config(text=text)

    def show_details(self, text, color=None, font=None):
        kw = dict(text=text)
        if color: kw["foreground"] = color
        if font:  kw["font"]       = font
        self.lbl_details.config(**kw)

    def show_path_fields(self, pd):
        """Populate the selected-path editor from pd. Show ⚠ if modified."""
        self.lbl_sel_name.config(text=pd["name"], foreground=pd["color"])
        self.var_sel_lat.set(    f"{pd['lat0']:.8f}")
        self.var_sel_lon.set(    f"{pd['lon0']:.8f}")
        self.var_sel_bearing.set(f"{pd['bearing']:.5f}")
        self.var_sel_alt.set(    f"{pd['alt0']:.3f}")
        self.var_dx.set("0")
        self.var_dy.set("0")
        self.var_dbrg.set("0")
        self._refresh_modified_indicator(pd)

    def clear_path_fields(self):
        self.lbl_sel_name.config(text="— select a path —", foreground=DIM)
        self.lbl_modified.config(text="")
        for v in (self.var_sel_lat, self.var_sel_lon,
                  self.var_sel_bearing, self.var_sel_alt):
            v.set("")
        self.var_dx.set("0"); self.var_dy.set("0"); self.var_dbrg.set("0")

    def _refresh_modified_indicator(self, pd):
        eps = 1e-9
        changed = (abs(pd["lat0"]    - pd["orig_lat0"])    > eps or
                   abs(pd["lon0"]    - pd["orig_lon0"])    > eps or
                   abs(pd["bearing"] - pd["orig_bearing"]) > eps)
        self.lbl_modified.config(text="⚠ modified" if changed else "")

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
            self.ref_origin_var.set("— none —")
            return
        for pd in paths:
            name = pd["name"]
            menu.add_command(label=name,
                             command=lambda n=name: (
                                 self.ref_origin_var.set(n), on_change(n)))
        names = [pd["name"] for pd in paths]
        if current_name in names:
            self.ref_origin_var.set(current_name)
        else:
            self.ref_origin_var.set(names[0])
            on_change(names[0])

    def show_ref_coords(self, pd):
        if pd is None:
            self.lbl_ref_coords.config(text=""); return
        self.lbl_ref_coords.config(
            text=f"Lat {pd['lat0']:.6f}°   "
                 f"Lon {pd['lon0']:.6f}°   "
                 f"Brg {pd['bearing']:.2f}°")

    def refresh_meas_table(self, paths, custom_objs):
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
