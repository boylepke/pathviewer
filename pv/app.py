"""
pv/app.py
─────────
PathViewerApp — viewer + measurement tool.
Loads AB Dynamics .path files, displays them on a satellite map,
and lets the user place / measure Points, Lines and Rectangles.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import xml.etree.ElementTree as ET
import math
import os

from .constants  import (BG, PANEL, ACCENT, ACCENT2, TEXT, DIM,
                          FONT_BODY, FONT_BOLD, PATH_COLORS, OBJ_ICON)
from .geo        import latlon_to_local, heading_between, haversine
from .models     import (new_path_dict, parse_path, item_rep, NS)
from .styles     import apply_styles
from .dialogs    import ask_rect_params, edit_obj
from .sidebar    import Sidebar
from .map_panel  import MapPanel


class PathViewerApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Path Viewer  —  Kenguru Tools")
        self.root.geometry("1440x860")
        self.root.configure(bg=BG)
        self.root.minsize(900, 600)

        # ── State ─────────────────────────────────────────────────────────────
        self.paths         = []
        self.active_idx    = -1       # path selected in the list
        self._ref_path     = None     # path used for relative-coord calculations
        self.custom_objs   = []
        self._line_pending = None
        self._line_tmp_mk  = None
        self._sel_obj_idx  = None

        apply_styles(self.root)
        self._build_ui()
        self.root.mainloop()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Toolbar
        tb = tk.Frame(self.root, bg=BG, height=46)
        tb.pack(fill="x"); tb.pack_propagate(False)
        tk.Label(tb, text="⬡  KENGURU PATH TOOLS", bg=BG, fg=ACCENT,
                 font=("Consolas", 12, "bold")).pack(side="left", padx=14)
        for txt, cmd in [("📂  Open .path", self.open_file),
                         ("📂+  Add .path",  self.add_file)]:
            ttk.Button(tb, text=txt, command=cmd,
                       style="Accent.TButton").pack(side="left", padx=4, pady=6)
        self._status = tk.StringVar(value="No file loaded")
        tk.Label(tb, textvariable=self._status,
                 bg=BG, fg=DIM, font=FONT_BODY).pack(side="right", padx=14)
        tk.Frame(self.root, bg=ACCENT2, height=1).pack(fill="x")

        # Paned layout
        pane = tk.PanedWindow(self.root, orient="horizontal", bg=BG,
                              sashwidth=4, sashrelief="flat",
                              sashpad=0, handlesize=0)
        pane.pack(fill="both", expand=True)
        sb_host  = tk.Frame(pane, bg=PANEL, width=330)
        map_host = tk.Frame(pane, bg=BG)
        pane.add(sb_host,  minsize=280)
        pane.add(map_host, minsize=480)

        self.sidebar   = Sidebar(sb_host)
        self.map_panel = MapPanel(map_host)
        self._wire_events()

    def _wire_events(self):
        sb = self.sidebar
        mp = self.map_panel

        # Path list buttons
        sb.btn_add.config(   command=self.add_file)
        sb.btn_toggle.config(command=self._toggle_visibility)
        sb.btn_remove.config(command=self._remove_path)
        sb.btn_fit.config(   command=self._fit_all)
        sb.path_tv.bind("<<TreeviewSelect>>", self._on_path_select)
        sb.path_tv.bind("<Double-1>",          self._toggle_visibility)

        # Object type dropdown
        sb.obj_type_var.trace_add("write",
            lambda *_: self._on_obj_type_change(sb.obj_type_var.get()))
        sb.btn_cancel_line.config(command=self._cancel_line_pending)

        # Object buttons + table
        sb.btn_edit_obj.config(  command=self._edit_obj_btn)
        sb.btn_move_obj.config(  command=self._start_move_mode)
        sb.btn_remove_obj.config(command=self._remove_obj)
        sb.btn_clear_objs.config(command=self._clear_custom_objs)
        sb.meas_tv.bind("<<TreeviewSelect>>", self._on_meas_select)
        sb.meas_tv.bind("<Double-1>",          self._edit_obj_table)

        # Map right-click
        mp.map_w.add_right_click_menu_command(
            "📐  Add object here",
            self._rcm_add_obj, pass_coords=True)
        mp.map_w.add_right_click_menu_command(
            "✥   Move selected object here",
            self._rcm_move_obj, pass_coords=True)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_status(self, msg): self._status.set(msg)

    def _n_kp(self):
        return sum(len(pd["keypoints"]) for pd in self.paths if pd["visible"])

    def _all_items(self):
        items = []
        for pd in self.paths:
            if pd["visible"]:
                items.extend(pd["keypoints"])
        items.extend(self.custom_objs)
        return items

    def _get_ref_path(self):
        name = self.sidebar.ref_origin_var.get()
        for pd in self.paths:
            if pd["name"] == name:
                return pd
        return self.paths[0] if self.paths else None

    # ── File loading ──────────────────────────────────────────────────────────
    def _pick_file(self):
        return filedialog.askopenfilename(
            title="Open AB Dynamics .path file",
            filetypes=[("Path files","*.path"),
                       ("XML files", "*.xml"),
                       ("All files", "*.*")])

    def open_file(self):
        fp = self._pick_file()
        if not fp: return
        for pd in self.paths:
            self.map_panel.erase_path(pd)
        self.paths.clear()
        self.active_idx = -1
        self.sidebar.refresh_path_list([], -1)
        self._load_path(fp, fit=True)

    def add_file(self):
        fp = self._pick_file()
        if fp: self._load_path(fp, fit=False)

    def _load_path(self, filepath, fit=True):
        try:
            xml_tree = ET.parse(filepath)
        except Exception as exc:
            messagebox.showerror("Parse error", str(exc)); return

        color = PATH_COLORS[len(self.paths) % len(PATH_COLORS)]
        pd    = new_path_dict(filepath, xml_tree, color)
        parse_path(pd)
        self.paths.append(pd)
        self.active_idx = len(self.paths) - 1

        self.sidebar.refresh_path_list(self.paths, self.active_idx)
        self.sidebar.show_path_origin(pd)

        # Rebuild reference-origin dropdown
        cur = self.sidebar.ref_origin_var.get()
        self.sidebar.rebuild_ref_menu(
            self.paths, cur, self._on_ref_origin_change)
        if self._ref_path is None:
            self._ref_path = pd
        self.sidebar.show_ref_coords(self._ref_path)

        self.map_panel.draw_path(pd)
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)

        if fit:
            self.map_panel.fit_to_coords(
                [(kp["lat"], kp["lon"]) for kp in pd["keypoints"]])

        self._set_status(
            f"{len(self.paths)} path(s) loaded  |  {pd['name']}")

    def _on_ref_origin_change(self, name):
        for pd in self.paths:
            if pd["name"] == name:
                self._ref_path = pd
                break
        self.sidebar.show_ref_coords(self._ref_path)
        self._update_details()   # recalculate displayed coords

    # ── Path list management ──────────────────────────────────────────────────
    def _on_path_select(self, _e=None):
        sel = self.sidebar.path_tv.selection()
        if not sel: return
        try: idx = int(sel[0][1:])
        except (ValueError, IndexError): return
        if 0 <= idx < len(self.paths):
            self.active_idx = idx
            self.sidebar.show_path_origin(self.paths[idx])

    def _toggle_visibility(self, _e=None):
        sel = self.sidebar.path_tv.selection()
        if not sel: return
        try: idx = int(sel[0][1:])
        except (ValueError, IndexError): return
        pd = self.paths[idx]
        pd["visible"] = not pd["visible"]
        if pd["visible"]:
            self.map_panel.draw_path(pd)
        else:
            self.map_panel.erase_path(pd)
        self.sidebar.refresh_path_list(self.paths, self.active_idx)
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)

    def _remove_path(self):
        sel = self.sidebar.path_tv.selection()
        if not sel: return
        try: idx = int(sel[0][1:])
        except (ValueError, IndexError): return
        self.map_panel.erase_path(self.paths[idx])
        self.paths.pop(idx)
        self.active_idx = (max(0, min(self.active_idx, len(self.paths)-1))
                           if self.paths else -1)
        self.sidebar.refresh_path_list(self.paths, self.active_idx)
        self.sidebar.rebuild_ref_menu(
            self.paths, self.sidebar.ref_origin_var.get(),
            self._on_ref_origin_change)
        self.sidebar.show_ref_coords(self._get_ref_path())
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
        if self.active_idx >= 0:
            self.sidebar.show_path_origin(self.paths[self.active_idx])
        else:
            self.sidebar.clear_path_origin()
        self._set_status(
            f"{len(self.paths)} path(s) loaded" if self.paths else "No file loaded")

    def _fit_all(self):
        self.map_panel.fit_to_all_paths(self.paths)

    # ── Object type selection ─────────────────────────────────────────────────
    _OBJ_HINTS = {
        "Point":     "right-click map to place",
        "Line":      "right-click: 1st = start,  2nd = end",
        "Rectangle": "right-click map → set size",
    }

    def _on_obj_type_change(self, val):
        self._cancel_line_pending()
        self.sidebar.set_obj_hint(self._OBJ_HINTS.get(val, ""))

    # ── Right-click map handlers ──────────────────────────────────────────────
    def _rcm_add_obj(self, coords):
        lat, lon = coords
        t = self.sidebar.obj_type_var.get()
        if   t == "Point":     self._add_point(lat, lon)
        elif t == "Line":      self._line_click(lat, lon)
        elif t == "Rectangle": self._open_rect_dialog(lat, lon)

    def _rcm_move_obj(self, coords):
        if self._sel_obj_idx is None:
            self._set_status("Select an object first (click its marker or table row)")
            return
        lat, lon = coords
        obj = self.custom_objs[self._sel_obj_idx]
        if obj["type"] == "point":
            obj["lat"] = lat; obj["lon"] = lon
        elif obj["type"] == "line":
            mlat = (obj["lat1"]+obj["lat2"])/2
            mlon = (obj["lon1"]+obj["lon2"])/2
            obj["lat1"] += lat-mlat; obj["lat2"] += lat-mlat
            obj["lon1"] += lon-mlon; obj["lon2"] += lon-mlon
        elif obj["type"] == "rect":
            obj["clat"] = lat; obj["clon"] = lon
        self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
        self._sel_obj_idx = None
        self._update_details()
        self._set_status("Object moved  ✓")

    # ── Custom object creation ────────────────────────────────────────────────
    def _default_name(self, typ):
        n = sum(1 for o in self.custom_objs if o["type"] == typ) + 1
        return f"{typ[0].upper()}{n}"

    def _add_point(self, lat, lon):
        name = simpledialog.askstring(
            "Point", "Name:",
            initialvalue=self._default_name("point"), parent=self.root)
        if name is None: return
        obj = {"type":"point",
               "name": name.strip() or self._default_name("point"),
               "lat": lat, "lon": lon, "_markers":[], "_paths":[]}
        self.custom_objs.append(obj)
        self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
        self._set_status(f"Point '{obj['name']}' added")

    def _add_line(self, lat1, lon1, lat2, lon2):
        name = simpledialog.askstring(
            "Line", "Name:",
            initialvalue=self._default_name("line"), parent=self.root)
        if name is None: return
        h   = heading_between(lat1, lon1, lat2, lon2)
        obj = {"type":"line",
               "name": name.strip() or self._default_name("line"),
               "lat1":lat1,"lon1":lon1,"lat2":lat2,"lon2":lon2,
               "heading": round(h,2), "_markers":[], "_paths":[]}
        self.custom_objs.append(obj)
        self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
        d = haversine(lat1, lon1, lat2, lon2)
        self._set_status(f"Line '{obj['name']}'  {d:.2f} m  hdg {h:.1f}°")

    def _line_click(self, lat, lon):
        if self._line_pending is None:
            self._line_pending = (lat, lon)
            self._line_tmp_mk  = self.map_panel.map_w.set_marker(
                lat, lon, text="▸ start",
                marker_color_circle="#fb923c",
                marker_color_outside="#fb923c",
                font=FONT_BODY)
            self._set_status("Line: start set — right-click to set end point")
            self.sidebar.set_obj_hint("end point: right-click  |")
            self.sidebar.btn_cancel_line.pack(side="left", padx=4)
        else:
            s_lat, s_lon = self._line_pending
            self._cancel_line_pending()
            self._add_line(s_lat, s_lon, lat, lon)

    def _cancel_line_pending(self):
        if self._line_tmp_mk:
            try: self._line_tmp_mk.delete()
            except Exception: pass
            self._line_tmp_mk = None
        self._line_pending = None
        self.sidebar.btn_cancel_line.pack_forget()
        self.sidebar.set_obj_hint(
            self._OBJ_HINTS.get(self.sidebar.obj_type_var.get(), ""))

    def _open_rect_dialog(self, clat, clon):
        obj = ask_rect_params(self.root, clat, clon, self._default_name("rect"))
        if obj is None: return
        self.custom_objs.append(obj)
        self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
        self._set_status(
            f"Rectangle '{obj['name']}'  "
            f"{obj['width_m']}×{obj['height_m']} m  "
            f"hdg {obj['heading']:.1f}°")

    # ── Object editing / removal ──────────────────────────────────────────────
    def _obj_marker_clicked(self, obj):
        idx   = self.custom_objs.index(obj)
        rows  = self.sidebar.meas_tv.get_children()
        row_i = self._n_kp() + idx
        if row_i < len(rows):
            self.sidebar.meas_tv.selection_set(rows[row_i])
            self.sidebar.meas_tv.see(rows[row_i])
        self._sel_obj_idx = idx
        self._update_details()
        self._set_status(f"'{obj['name']}' selected")

    def _get_selected_custom_obj(self):
        sel  = self.sidebar.meas_tv.selection()
        if not sel: return None
        rows = list(self.sidebar.meas_tv.get_children())
        i    = rows.index(sel[0])
        n_kp = self._n_kp()
        return self.custom_objs[i - n_kp] if i >= n_kp else None

    def _edit_obj_btn(self):
        obj = self._get_selected_custom_obj()
        if obj is None:
            messagebox.showinfo("Nothing to edit",
                                "Select a custom object row in the table.")
            return
        if edit_obj(self.root, obj):
            self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
            self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
            self._update_details()

    def _edit_obj_table(self, _e=None):
        obj = self._get_selected_custom_obj()
        if obj and edit_obj(self.root, obj):
            self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
            self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
            self._update_details()

    def _start_move_mode(self):
        sel  = self.sidebar.meas_tv.selection()
        if not sel:
            messagebox.showinfo("Nothing selected",
                                "Select a custom object first.")
            return
        rows = list(self.sidebar.meas_tv.get_children())
        i    = rows.index(sel[0])
        n_kp = self._n_kp()
        if i < n_kp:
            messagebox.showinfo("Path keypoint",
                                "Path keypoints cannot be moved here.")
            return
        self._sel_obj_idx = i - n_kp
        self._set_status(
            f"Move mode — right-click map to place  "
            f"'{self.custom_objs[self._sel_obj_idx]['name']}'")

    def _remove_obj(self):
        sel  = self.sidebar.meas_tv.selection()
        if not sel: return
        rows = list(self.sidebar.meas_tv.get_children())
        n_kp = self._n_kp()
        to_rm = sorted(
            [rows.index(s) - n_kp for s in sel if rows.index(s) >= n_kp],
            reverse=True)
        for ci in to_rm:
            self.map_panel.erase_obj(self.custom_objs[ci])
            self.custom_objs.pop(ci)
        if self._sel_obj_idx is not None and \
                self._sel_obj_idx >= len(self.custom_objs):
            self._sel_obj_idx = None
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
        self._update_details()

    def _clear_custom_objs(self):
        for obj in self.custom_objs:
            self.map_panel.erase_obj(obj)
        self.custom_objs.clear()
        self._sel_obj_idx = None
        self.sidebar.refresh_meas_table(self.paths, self.custom_objs)
        self.sidebar.show_details(
            "—  select an object for coordinates\n"
            "—  select two for distance", DIM)

    # ── Details / distance panel ──────────────────────────────────────────────
    def _on_meas_select(self, _e=None):
        self._update_details()

    def _update_details(self):
        sel   = self.sidebar.meas_tv.selection()
        items = self._all_items()
        rows  = list(self.sidebar.meas_tv.get_children())
        ref   = self._get_ref_path()

        def _rel(lat, lon):
            """Relative X/Y string, or empty if no reference."""
            if ref is None:
                return ""
            x, y = latlon_to_local(lat, lon,
                                   ref["lat0"], ref["lon0"], ref["bearing"])
            return (f"\n  X = {x:+.3f} m     Y = {y:+.3f} m"
                    f"\n  (ref: {ref['name']})")

        # ── 0 selected ────────────────────────────────────────────────────────
        if len(sel) == 0:
            self.sidebar.show_details(
                "—  select an object for coordinates\n"
                "—  select two for distance", DIM)
            return

        # ── 1 selected ────────────────────────────────────────────────────────
        if len(sel) == 1:
            i = rows.index(sel[0])
            if i >= len(items): return
            it  = items[i]
            lat, lon = item_rep(it)
            name = it.get("name", "?")
            icon = OBJ_ICON.get(it.get("type",""), "■")
            lines = [f"{icon}  {name}",
                     f"  Lat  {lat:.6f}°",
                     f"  Lon  {lon:.6f}°"]

            # extra per-type info
            t = it.get("type")
            if t == "line":
                d   = haversine(it["lat1"],it["lon1"],it["lat2"],it["lon2"])
                lines.append(f"  L = {d:.3f} m   hdg {it.get('heading',0):.1f}°")
            elif t == "rect":
                lines.append(
                    f"  {it['width_m']:.2f} × {it['height_m']:.2f} m"
                    f"   hdg {it.get('heading',0):.1f}°")

            lines.append(_rel(lat, lon))
            self.sidebar.show_details(
                "\n".join(l for l in lines if l), ACCENT, FONT_BODY)
            return

        # ── 2 selected ────────────────────────────────────────────────────────
        if len(sel) == 2:
            idx = [rows.index(s) for s in sel]
            if any(i >= len(items) for i in idx): return
            it1, it2 = items[idx[0]], items[idx[1]]
            la1, lo1 = item_rep(it1)
            la2, lo2 = item_rep(it2)
            geo_d    = haversine(la1, lo1, la2, lo2)

            lines = [f"{it1.get('name','?')}  ↔  {it2.get('name','?')}",
                     f"  Geo distance :  {geo_d:.3f} m"]

            if ref:
                x1,y1 = latlon_to_local(la1,lo1,ref["lat0"],ref["lon0"],ref["bearing"])
                x2,y2 = latlon_to_local(la2,lo2,ref["lat0"],ref["lon0"],ref["bearing"])
                ld    = math.sqrt((x2-x1)**2+(y2-y1)**2)
                lines += [f"  Local XY dist:  {ld:.3f} m",
                          f"  ΔX = {x2-x1:+.3f} m   ΔY = {y2-y1:+.3f} m",
                          f"  (ref: {ref['name']})"]

            self.sidebar.show_details("\n".join(lines), ACCENT, FONT_BOLD)
            return

        # ── > 2 selected ──────────────────────────────────────────────────────
        self.sidebar.show_details(
            f"{len(sel)} objects selected — select exactly 2 to measure", DIM)
