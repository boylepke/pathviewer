"""
pv/app.py
─────────
PathViewerApp — viewer + object placement + two-way distance measurement.

Measurement Way 1: select 2 rows from the measurement table → distance shown.
Measurement Way 2: "Pick on map" mode → left-click A, left-click B → distance.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import xml.etree.ElementTree as ET
import math
import os

from .constants import (BG, PANEL, ACCENT, ACCENT2, TEXT, DIM,
                         FONT_BODY, FONT_BOLD, PATH_COLORS, OBJ_ICON)
from .geo       import (local_to_latlon, latlon_to_local,
                         heading_between, haversine)
from .models    import (new_path_dict, parse_path, item_rep, NS)
from .styles    import apply_styles
from .dialogs   import ask_point_params, ask_line_params, ask_rect_params, edit_obj
from .sidebar   import Sidebar
from .map_panel import MapPanel


class PathViewerApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Path Viewer  —  Kenguru Tools")
        self.root.geometry("1440x900")
        self.root.configure(bg=BG)
        self.root.minsize(900, 600)

        # ── Path state ────────────────────────────────────────────────────────
        self.paths       = []
        self.active_idx  = -1
        self._ref_path   = None

        # ── Object state ──────────────────────────────────────────────────────
        self.custom_objs  = []
        self._line_pending = None
        self._line_tmp_mk  = None
        self._sel_obj_idx  = None   # armed for "move here"

        # ── Measurement Way 2 state ───────────────────────────────────────────
        self._meas_mode  = False    # True = picking mode active
        self._meas_a     = None     # (lat, lon) of point A, or None
        self._meas_b     = None     # (lat, lon) of point B, or None
        self._meas_mk_a  = None     # map marker for A
        self._meas_mk_b  = None     # map marker for B

        apply_styles(self.root)
        self._build_ui()
        self.root.mainloop()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        tb = tk.Frame(self.root, bg=BG, height=46)
        tb.pack(fill="x"); tb.pack_propagate(False)
        tk.Label(tb, text="⬡  KENGURU PATH TOOLS", bg=BG, fg=ACCENT,
                 font=("Consolas", 12, "bold")).pack(side="left", padx=14)
        for txt, cmd in [("📂  Open .path", self.open_file),
                         ("📂+  Add .path",  self.add_file),
                         ("🗑   Reset map",   self.reset_map)]:
            ttk.Button(tb, text=txt, command=cmd,
                       style="Accent.TButton").pack(side="left", padx=4, pady=6)
        self._status = tk.StringVar(value="No file loaded")
        tk.Label(tb, textvariable=self._status,
                 bg=BG, fg=DIM, font=FONT_BODY).pack(side="right", padx=14)
        tk.Frame(self.root, bg=ACCENT2, height=1).pack(fill="x")

        pane = tk.PanedWindow(self.root, orient="horizontal", bg=BG,
                              sashwidth=4, sashrelief="flat",
                              sashpad=0, handlesize=0)
        pane.pack(fill="both", expand=True)
        sb_host  = tk.Frame(pane, bg=PANEL, width=345)
        map_host = tk.Frame(pane, bg=BG)
        pane.add(sb_host,  minsize=290)
        pane.add(map_host, minsize=480)

        self.sidebar   = Sidebar(sb_host)
        self.map_panel = MapPanel(map_host)
        self._wire_events()

    def _wire_events(self):
        sb = self.sidebar

        # Path list
        sb.btn_add.config(   command=self.add_file)
        sb.btn_toggle.config(command=self._toggle_visibility)
        sb.btn_remove.config(command=self._remove_path)
        sb.btn_fit.config(   command=self._fit_all)
        sb.path_tv.bind("<<TreeviewSelect>>", self._on_path_select)
        sb.path_tv.bind("<Double-1>",          self._toggle_visibility)

        # Transform
        sb.btn_apply_transform.config(command=self._apply_transform)
        sb.btn_reset_transform.config(command=self._reset_transform)

        # Object controls
        sb.obj_type_var.trace_add("write",
            lambda *_: self._on_obj_type_change(sb.obj_type_var.get()))
        sb.btn_cancel_line.config(command=self._cancel_line_pending)
        sb.btn_edit_obj.config(  command=self._edit_obj_btn)
        sb.btn_move_obj.config(  command=self._start_move_mode)
        sb.btn_remove_obj.config(command=self._remove_obj)
        sb.btn_clear_objs.config(command=self._clear_custom_objs)
        sb.obj_tv.bind("<Double-1>", self._edit_obj_table)

        # Measurement Way 1 — table selection
        sb.meas_tv.bind("<<TreeviewSelect>>", self._on_way1_select)

        # Measurement Way 2 — map pick
        sb.btn_map_measure.config(command=self._toggle_map_measure)
        sb.btn_clear_meas.config( command=self._clear_map_measure)

        # Map
        self.map_panel.map_w.add_right_click_menu_command(
            "📐  Add object here",
            self._rcm_add_obj, pass_coords=True)
        self.map_panel.map_w.add_right_click_menu_command(
            "✥   Move selected object here",
            self._rcm_move_obj, pass_coords=True)
        self.map_panel.map_w.add_left_click_map_command(
            self._on_map_left_click)

        self.root.bind("<Escape>", lambda _e: self._on_escape())

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_status(self, msg): self._status.set(msg)

    def _n_kp(self):
        return sum(len(pd["keypoints"]) for pd in self.paths if pd["visible"])

    def _all_meas_items(self):
        """All items shown in the Way-1 measurement table."""
        items = []
        for pd in self.paths:
            if pd["visible"]: items.extend(pd["keypoints"])
        items.extend(self.custom_objs)
        return items

    def _get_ref_path(self):
        name = self.sidebar.ref_origin_var.get()
        for pd in self.paths:
            if pd["name"] == name: return pd
        return self.paths[0] if self.paths else None

    def _active_pd(self):
        if 0 <= self.active_idx < len(self.paths):
            return self.paths[self.active_idx]
        return None

    def _result_text(self, la1, lo1, la2, lo2, label1="A", label2="B"):
        """Build a formatted distance result string."""
        geo_d = haversine(la1, lo1, la2, lo2)
        lines = [f"{label1}  ↔  {label2}",
                 f"  Geo distance :  {geo_d:.3f} m"]
        ref = self._get_ref_path()
        if ref:
            x1, y1 = latlon_to_local(la1, lo1,
                                     ref["lat0"], ref["lon0"], ref["bearing"])
            x2, y2 = latlon_to_local(la2, lo2,
                                     ref["lat0"], ref["lon0"], ref["bearing"])
            ld = math.sqrt((x2-x1)**2 + (y2-y1)**2)
            lines += [f"  Local XY dist :  {ld:.3f} m",
                      f"  ΔX = {x2-x1:+.3f} m   ΔY = {y2-y1:+.3f} m",
                      f"  (ref: {ref['name']})"]
        return "\n".join(lines)

    # ── File loading ──────────────────────────────────────────────────────────
    def _pick_file(self):
        return filedialog.askopenfilename(
            title="Open AB Dynamics .path file",
            filetypes=[("Path files","*.path"),
                       ("XML files","*.xml"),("All files","*.*")])

    def open_file(self):
        fp = self._pick_file()
        if not fp: return
        for pd in self.paths: self.map_panel.erase_path(pd)
        self.paths.clear(); self.active_idx = -1
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
        self.sidebar.show_path_fields(pd)

        cur = self.sidebar.ref_origin_var.get()
        self.sidebar.rebuild_ref_menu(self.paths, cur, self._on_ref_origin_change)
        if self._ref_path is None: self._ref_path = pd
        self.sidebar.show_ref_coords(self._ref_path)

        self.map_panel.draw_path(pd)
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)

        if fit:
            self.map_panel.fit_to_coords(
                [(kp["lat"], kp["lon"]) for kp in pd["keypoints"]])
        self._set_status(f"{len(self.paths)} path(s) loaded  |  {pd['name']}")

    def _on_ref_origin_change(self, name):
        for pd in self.paths:
            if pd["name"] == name:
                self._ref_path = pd; break
        self.sidebar.show_ref_coords(self._ref_path)

    # ── Path list management ──────────────────────────────────────────────────
    def _on_path_select(self, _e=None):
        sel = self.sidebar.path_tv.selection()
        if not sel: return
        try: idx = int(sel[0][1:])
        except (ValueError, IndexError): return
        if 0 <= idx < len(self.paths):
            self.active_idx = idx
            self.sidebar.show_path_fields(self.paths[idx])

    def _toggle_visibility(self, _e=None):
        sel = self.sidebar.path_tv.selection()
        if not sel: return
        try: idx = int(sel[0][1:])
        except (ValueError, IndexError): return
        pd = self.paths[idx]
        pd["visible"] = not pd["visible"]
        (self.map_panel.draw_path if pd["visible"]
         else self.map_panel.erase_path)(pd)
        self.sidebar.refresh_path_list(self.paths, self.active_idx)
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)

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
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)
        if self.active_idx >= 0:
            self.sidebar.show_path_fields(self.paths[self.active_idx])
        else:
            self.sidebar.clear_path_fields()
        self._set_status(
            f"{len(self.paths)} path(s) loaded" if self.paths else "No file loaded")

    def _fit_all(self):
        self.map_panel.fit_to_all_paths(self.paths)

    # ── Path transform ────────────────────────────────────────────────────────
    def _apply_transform(self):
        pd = self._active_pd()
        if pd is None:
            messagebox.showwarning("No path selected",
                                   "Select a path in the list first."); return
        sb = self.sidebar
        try:
            pd["lat0"]    = float(sb.var_sel_lat.get())
            pd["lon0"]    = float(sb.var_sel_lon.get())
            pd["bearing"] = float(sb.var_sel_bearing.get())
            pd["alt0"]    = float(sb.var_sel_alt.get())
            dx = float(sb.var_dx.get()); dy = float(sb.var_dy.get())
            if dx != 0 or dy != 0:
                pd["lat0"], pd["lon0"] = local_to_latlon(
                    dx, dy, pd["lat0"], pd["lon0"], pd["bearing"])
            dbrg = float(sb.var_dbrg.get())
            if dbrg != 0:
                pd["bearing"] = (pd["bearing"] + dbrg) % 360.0
        except ValueError:
            messagebox.showerror("Invalid value",
                                 "All transform fields must be numbers."); return
        self.sidebar.show_path_fields(pd)
        self.map_panel.draw_path(pd)
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)
        if self._ref_path and self._ref_path["name"] == pd["name"]:
            self.sidebar.show_ref_coords(pd)
        self._set_status(
            f"{pd['name']} — origin updated  "
            f"({pd['lat0']:.6f}°, {pd['lon0']:.6f}°  brg {pd['bearing']:.2f}°)")

    def _reset_transform(self):
        pd = self._active_pd()
        if pd is None: return
        pd["lat0"]    = pd["orig_lat0"]
        pd["lon0"]    = pd["orig_lon0"]
        pd["alt0"]    = pd["orig_alt0"]
        pd["bearing"] = pd["orig_bearing"]
        self.sidebar.show_path_fields(pd)
        self.map_panel.draw_path(pd)
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)
        if self._ref_path and self._ref_path["name"] == pd["name"]:
            self.sidebar.show_ref_coords(pd)
        self._set_status(f"{pd['name']} — reset to original file values")

    # ── Object type dropdown ──────────────────────────────────────────────────
    _OBJ_HINTS = {
        "Point":     "right-click map to place",
        "Line":      "right-click: 1st = start,  2nd = end",
        "Rectangle": "right-click map → set size",
    }

    def _on_obj_type_change(self, val):
        self._cancel_line_pending()
        self.sidebar.set_obj_hint(self._OBJ_HINTS.get(val, ""))

    # ── Right-click map ───────────────────────────────────────────────────────
    def _rcm_add_obj(self, coords):
        lat, lon = coords
        t = self.sidebar.obj_type_var.get()
        if   t == "Point":     self._add_point(lat, lon)
        elif t == "Line":      self._line_click(lat, lon)
        elif t == "Rectangle": self._open_rect_dialog(lat, lon)

    def _rcm_move_obj(self, coords):
        if self._sel_obj_idx is None:
            self._set_status("Select an object first"); return
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
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)
        self._sel_obj_idx = None
        self._set_status("Object moved  ✓")

    # ── Left-click map → Way 2 ────────────────────────────────────────────────
    def _on_map_left_click(self, coords):
        if not self._meas_mode:
            return
        lat, lon = coords
        if self._meas_a is None:
            # Place A
            self._meas_a   = (lat, lon)
            self._meas_mk_a = self.map_panel.set_measure_pin(lat, lon, "A", "A")
            self.sidebar.lbl_pt_a.config(
                text=f"  A :  {lat:.6f}°,  {lon:.6f}°",
                foreground=ACCENT)
            self._set_status("Map measure: left-click to set point B")
        elif self._meas_b is None:
            # Place B → compute result
            self._meas_b   = (lat, lon)
            self._meas_mk_b = self.map_panel.set_measure_pin(lat, lon, "B", "B")
            self.sidebar.lbl_pt_b.config(
                text=f"  B :  {lat:.6f}°,  {lon:.6f}°",
                foreground="#f5c518")
            la1, lo1 = self._meas_a
            self.sidebar.show_result(
                self._result_text(la1, lo1, lat, lon, "A", "B"),
                ACCENT, FONT_BOLD)
            self._set_status("Map measure: result shown  |  click to reset  |  Esc to exit")
        else:
            # Third click → clear and start over
            self._clear_meas_pins()
            self._meas_a   = (lat, lon)
            self._meas_mk_a = self.map_panel.set_measure_pin(lat, lon, "A", "A")
            self.sidebar.lbl_pt_a.config(
                text=f"  A :  {lat:.6f}°,  {lon:.6f}°",
                foreground=ACCENT)
            self.sidebar.lbl_pt_b.config(text="  B :  —", foreground=DIM)
            self.sidebar.show_result(
                "—  set 2 points or select 2 objects  —", DIM)
            self._set_status("Map measure: left-click to set point B")

    # ── Way 2 mode controls ───────────────────────────────────────────────────
    def _toggle_map_measure(self):
        if self._meas_mode:
            self._stop_map_measure()
        else:
            self._start_map_measure()

    def _start_map_measure(self):
        self._meas_mode = True
        self.sidebar.btn_map_measure.config(text="■ Stop picking")
        self._set_status("Map measure ON — left-click to set point A")

    def _stop_map_measure(self):
        self._meas_mode = False
        self.sidebar.btn_map_measure.config(text="📏 Start picking")
        self._set_status("Map measure off")

    def _clear_meas_pins(self):
        for mk in (self._meas_mk_a, self._meas_mk_b):
            if mk:
                try: mk.delete()
                except Exception: pass
        self._meas_mk_a = self._meas_mk_b = None
        self._meas_a    = self._meas_b    = None

    def _clear_map_measure(self):
        self._clear_meas_pins()
        self._stop_map_measure()
        self.sidebar.lbl_pt_a.config(text="  A :  —", foreground=DIM)
        self.sidebar.lbl_pt_b.config(text="  B :  —", foreground=DIM)
        self.sidebar.show_result(
            "—  set 2 points or select 2 objects  —", DIM)

    def _on_escape(self):
        if self._meas_mode:
            self._clear_map_measure()
        elif self._line_pending:
            self._cancel_line_pending()

    # ── Measurement Way 1 — table selection ───────────────────────────────────
    def _on_way1_select(self, _e=None):
        sel   = self.sidebar.meas_tv.selection()
        items = self._all_meas_items()
        rows  = list(self.sidebar.meas_tv.get_children())

        if len(sel) == 2:
            idx = [rows.index(s) for s in sel]
            if any(i >= len(items) for i in idx): return
            it1, it2 = items[idx[0]], items[idx[1]]
            la1, lo1 = item_rep(it1)
            la2, lo2 = item_rep(it2)
            self.sidebar.show_result(
                self._result_text(la1, lo1, la2, lo2,
                                  it1.get("name","?"), it2.get("name","?")),
                ACCENT, FONT_BOLD)
        elif len(sel) == 1:
            i = rows.index(sel[0])
            if i >= len(items): return
            it  = items[i]
            lat, lon = item_rep(it)
            ref = self._get_ref_path()
            lines = [f"{OBJ_ICON.get(it.get('type',''),'■')}  {it.get('name','?')}",
                     f"  Lat  {lat:.6f}°",
                     f"  Lon  {lon:.6f}°"]
            t = it.get("type")
            if t == "line":
                d = haversine(it["lat1"],it["lon1"],it["lat2"],it["lon2"])
                lines.append(f"  L = {d:.3f} m   hdg {it.get('heading',0):.1f}°")
            elif t == "rect":
                lines.append(
                    f"  {it['width_m']:.2f} × {it['height_m']:.2f} m"
                    f"   hdg {it.get('heading',0):.1f}°")
            if ref:
                x, y = latlon_to_local(lat, lon,
                                       ref["lat0"], ref["lon0"], ref["bearing"])
                lines += [f"  X = {x:+.3f} m     Y = {y:+.3f} m",
                          f"  (ref: {ref['name']})"]
            self.sidebar.show_result(
                "\n".join(l for l in lines if l), ACCENT, FONT_BODY)
        else:
            self.sidebar.show_result(
                "—  set 2 points or select 2 objects  —", DIM)

    # ── Object creation ───────────────────────────────────────────────────────
    def _default_name(self, typ):
        n = sum(1 for o in self.custom_objs if o["type"] == typ) + 1
        return f"{typ[0].upper()}{n}"

    def _add_point(self, lat, lon):
        obj = ask_point_params(self.root, lat, lon,
                               self._default_name("point"),
                               ref_path=self._get_ref_path())
        if obj is None: return
        self.custom_objs.append(obj)
        self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)
        self._set_status(f"Point '{obj['name']}' added")

    def _add_line(self, lat1, lon1, lat2, lon2):
        obj = ask_line_params(self.root, lat1, lon1, lat2, lon2,
                              self._default_name("line"),
                              ref_path=self._get_ref_path())
        if obj is None: return
        self.custom_objs.append(obj)
        self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)
        d = haversine(obj["lat1"],obj["lon1"],obj["lat2"],obj["lon2"])
        self._set_status(
            f"Line '{obj['name']}'  {d:.2f} m  hdg {obj['heading']:.1f}°")

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
        obj = ask_rect_params(self.root, clat, clon, self._default_name("rect"),
                              ref_path=self._get_ref_path())
        if obj is None: return
        self.custom_objs.append(obj)
        self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)
        self._set_status(
            f"Rectangle '{obj['name']}'  "
            f"{obj['width_m']}×{obj['height_m']} m  hdg {obj['heading']:.1f}°")

    # ── Object editing / removal ──────────────────────────────────────────────
    def _obj_marker_clicked(self, obj):
        """Select the object in the obj_tv when its map marker is clicked."""
        rows  = list(self.sidebar.obj_tv.get_children())
        try:
            ci = self.custom_objs.index(obj)
            if ci < len(rows):
                self.sidebar.obj_tv.selection_set(rows[ci])
                self.sidebar.obj_tv.see(rows[ci])
        except ValueError:
            pass
        self._sel_obj_idx = self.custom_objs.index(obj) if obj in self.custom_objs else None

    def _get_selected_obj(self):
        sel = self.sidebar.obj_tv.selection()
        if not sel: return None
        rows = list(self.sidebar.obj_tv.get_children())
        i    = rows.index(sel[0])
        return self.custom_objs[i] if i < len(self.custom_objs) else None

    def _edit_obj_btn(self):
        obj = self._get_selected_obj()
        if obj is None:
            messagebox.showinfo("Nothing to edit",
                                "Select an object in the Objects list."); return
        if edit_obj(self.root, obj, ref_path=self._get_ref_path()):
            self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
            self.sidebar.refresh_obj_table(self.paths, self.custom_objs)

    def _edit_obj_table(self, _e=None):
        obj = self._get_selected_obj()
        if obj and edit_obj(self.root, obj, ref_path=self._get_ref_path()):
            self.map_panel.draw_obj(obj, on_click=self._obj_marker_clicked)
            self.sidebar.refresh_obj_table(self.paths, self.custom_objs)

    def _start_move_mode(self):
        obj = self._get_selected_obj()
        if obj is None:
            messagebox.showinfo("Nothing selected",
                                "Select an object first."); return
        self._sel_obj_idx = self.custom_objs.index(obj)
        self._set_status(
            f"Move mode — right-click map to place  '{obj['name']}'")

    def _remove_obj(self):
        sel  = self.sidebar.obj_tv.selection()
        if not sel: return
        rows = list(self.sidebar.obj_tv.get_children())
        to_rm = sorted([rows.index(s) for s in sel], reverse=True)
        for ci in to_rm:
            if ci < len(self.custom_objs):
                self.map_panel.erase_obj(self.custom_objs[ci])
                self.custom_objs.pop(ci)
        if (self._sel_obj_idx is not None and
                self._sel_obj_idx >= len(self.custom_objs)):
            self._sel_obj_idx = None
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)

    def _clear_custom_objs(self):
        for obj in self.custom_objs: self.map_panel.erase_obj(obj)
        self.custom_objs.clear()
        self._sel_obj_idx = None
        self.sidebar.refresh_obj_table(self.paths, self.custom_objs)

    # ── Reset map ─────────────────────────────────────────────────────────────
    def reset_map(self):
        if self.paths or self.custom_objs:
            if not messagebox.askyesno(
                    "Reset map",
                    "Remove all loaded paths and measurement objects?"):
                return
        self._clear_map_measure()
        for obj in self.custom_objs: self.map_panel.erase_obj(obj)
        self.custom_objs.clear()
        for pd in self.paths: self.map_panel.erase_path(pd)
        self.paths.clear()
        self.active_idx  = -1
        self._ref_path   = None
        self._sel_obj_idx = None
        self._cancel_line_pending()
        self.sidebar.refresh_path_list([], -1)
        self.sidebar.clear_path_fields()
        self.sidebar.rebuild_ref_menu([], "— none —", lambda _: None)
        self.sidebar.show_ref_coords(None)
        self.sidebar.refresh_obj_table([], [])
        self.sidebar.show_result(
            "—  set 2 points or select 2 objects  —", DIM)
        self._set_status("Map reset")
