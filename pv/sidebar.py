"""
pv/sidebar.py
─────────────
Simplified sidebar: path viewer + measurement tool only.

Sections
────────
1. LOADED PATHS     – list with toggle/remove; selected path's origin read-out
2. REFERENCE ORIGIN – choose which path origin is used for relative coords
3. MEASUREMENT OBJECTS – add / edit / remove Points, Lines, Rectangles
4. DETAILS          – 0 sel → hint  |  1 sel → abs + rel coords  |  2 sel → distance

Public attributes (all set during __init__)
───────────────────────────────────────────
  path_tv                    ttk.Treeview
  btn_add, btn_toggle,
    btn_remove, btn_fit       ttk.Button
  lbl_sel_name, lbl_sel_lat,
    lbl_sel_lon, lbl_sel_brg,
    lbl_sel_alt               ttk.Label  (selected path origin read-out)
  ref_origin_var             tk.StringVar  (dropdown)
  lbl_ref_coords             ttk.Label  (ref origin coords)
  obj_type_var               tk.StringVar
  lbl_obj_hint, btn_cancel_line
  meas_tv                    ttk.Treeview
  btn_edit_obj, btn_move_obj,
    btn_remove_obj,btn_clear_objs   ttk.Button
  lbl_details                ttk.Label  (adaptive details/distance panel)
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

        # ── 1. LOADED PATHS ───────────────────────────────────────────────────
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

        # Selected path origin read-out (read-only)
        orig = ttk.Frame(f, style="Card.TFrame")
        orig.pack(fill="x", padx=12, pady=(2,4))
        self.lbl_sel_name = ttk.Label(orig, text="— no path selected —",
                                       style="Dim.TLabel",
                                       font=("Consolas",8,"bold"))
        self.lbl_sel_name.pack(anchor="w", padx=8, pady=(4,2))
        grid = ttk.Frame(orig); grid.pack(fill="x", padx=8, pady=(0,4))
        self.lbl_sel_lat = self._ro_pair(grid, "Lat",     0, 0)
        self.lbl_sel_lon = self._ro_pair(grid, "Lon",     0, 2)
        self.lbl_sel_brg = self._ro_pair(grid, "Bearing", 1, 0)
        self.lbl_sel_alt = self._ro_pair(grid, "Alt (m)", 1, 2)

        # ── 2. REFERENCE ORIGIN ───────────────────────────────────────────────
        self._sec(f, "REFERENCE ORIGIN")
        ttk.Label(f, text="Relative coords computed from:",
                  style="Dim.TLabel").pack(anchor="w", padx=12, pady=(0,2))

        self.ref_origin_var = tk.StringVar(value="— none —")
        self._ref_om_frame = ttk.Frame(f)
        self._ref_om_frame.pack(fill="x", padx=12, pady=(0,4))
        self._ref_om = tk.OptionMenu(self._ref_om_frame, self.ref_origin_var,
                                      "— none —")
        self._ref_om.config(bg=CARD, fg=TEXT, activebackground=BORDER,
                             activeforeground=TEXT, font=FONT_BODY,
                             relief="flat", bd=0, highlightthickness=0,
                             width=28)
        self._ref_om["menu"].config(bg=CARD, fg=TEXT, activebackground=ACCENT2)
        self._ref_om.pack(side="left")

        self.lbl_ref_coords = ttk.Label(f, text="",
                                         style="Dim.TLabel", wraplength=290)
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
        # not packed until line is pending

        self.meas_tv = ttk.Treeview(f, columns=("typ","name","info"),
                                     show="headings", height=8,
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
        self.btn_move_obj   = ttk.Button(mr, text="✥ Move",       command=lambda: None)
        self.btn_remove_obj = ttk.Button(mr, text="🗑 Remove",     command=lambda: None)
        self.btn_clear_objs = ttk.Button(mr, text="Clear all",    command=lambda: None)
        for btn in (self.btn_edit_obj, self.btn_move_obj,
                    self.btn_remove_obj, self.btn_clear_objs):
            btn.pack(side="left", padx=2)

        # ── 4. DETAILS ────────────────────────────────────────────────────────
        self._sec(f, "DETAILS")
        self.lbl_details = ttk.Label(
            f,
            text="—  select an object for coordinates\n"
                 "—  select two for distance",
            style="Dim.TLabel",
            wraplength=300, justify="left")
        self.lbl_details.pack(anchor="w", padx=12, pady=6)

    # ── Private layout helpers ────────────────────────────────────────────────
    def _sec(self, parent, title):
        row = ttk.Frame(parent); row.pack(fill="x", padx=8, pady=(12,1))
        ttk.Label(row, text=title, style="H.TLabel").pack(side="left")
        tk.Frame(row, bg=BORDER, height=1).pack(side="left", fill="x",
                                                  expand=True, padx=6)

    def _ro_pair(self, grid, label, row, col):
        """Add a read-only label-value pair in a grid. Returns the value Label."""
        ttk.Label(grid, text=label+":", style="Dim.TLabel",
                  width=9, anchor="w").grid(row=row, column=col,
                                             sticky="w", padx=(0,2))
        lbl = ttk.Label(grid, text="—", anchor="w", font=FONT_BODY)
        lbl.grid(row=row, column=col+1, sticky="w", padx=(0,10))
        return lbl

    # ── Public display-update API ─────────────────────────────────────────────
    def set_obj_hint(self, text):
        self.lbl_obj_hint.config(text=text)

    def show_details(self, text, color=None, font=None):
        kw = dict(text=text)
        if color: kw["foreground"] = color
        if font:  kw["font"]       = font
        self.lbl_details.config(**kw)

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

    def show_path_origin(self, pd):
        self.lbl_sel_name.config(text=pd["name"], foreground=pd["color"])
        self.lbl_sel_lat.config(text=f"{pd['lat0']:.6f}°")
        self.lbl_sel_lon.config(text=f"{pd['lon0']:.6f}°")
        self.lbl_sel_brg.config(text=f"{pd['bearing']:.2f}°")
        self.lbl_sel_alt.config(text=f"{pd['alt0']:.1f}")

    def clear_path_origin(self):
        self.lbl_sel_name.config(text="— no path selected —",
                                  foreground=DIM)
        for lbl in (self.lbl_sel_lat, self.lbl_sel_lon,
                    self.lbl_sel_brg, self.lbl_sel_alt):
            lbl.config(text="—")

    def rebuild_ref_menu(self, paths, current_name, on_change):
        """Rebuild the reference-origin dropdown from the current path list."""
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
        # keep current selection if still valid, else default to first
        names = [pd["name"] for pd in paths]
        if current_name in names:
            self.ref_origin_var.set(current_name)
        else:
            self.ref_origin_var.set(names[0])
            on_change(names[0])

    def show_ref_coords(self, pd):
        if pd is None:
            self.lbl_ref_coords.config(text="")
            return
        self.lbl_ref_coords.config(
            text=f"Lat {pd['lat0']:.6f}°   "
                 f"Lon {pd['lon0']:.6f}°   "
                 f"Brg {pd['bearing']:.2f}°")

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
