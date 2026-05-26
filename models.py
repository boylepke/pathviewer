"""
pv/models.py
────────────
Data-model helpers: path dict factory, AB Dynamics XML parse / write-back,
and display utilities for custom measurement objects.
No tkinter dependency.
"""
import os
import xml.etree.ElementTree as ET
from .geo import heading_between, haversine

NS = "https://www.abdynamics.com/PathV3"

def _n(tag):
    """Fully-qualified XML tag for the AB Dynamics namespace."""
    return f"{{{NS}}}{tag}"


# ── Path dict ─────────────────────────────────────────────────────────────────

def new_path_dict(filepath, xml_tree, color):
    """Create a blank path data dict. Call parse_path() to populate it."""
    return {
        "filepath":           filepath,
        "xml_tree":           xml_tree,
        "color":              color,
        "visible":            True,
        "name":               "",
        "schema":             "",
        "lat0":               0.0,
        "lon0":               0.0,
        "alt0":               0.0,
        "bearing":            0.0,
        "origin_node":        "",
        "start_time_offset":  "0",
        "sync_code":          "0",
        "segments":           [],
        "keypoints":          [],   # filled by map_panel.draw_path()
        "_line":              None,
        "_markers":           [],
    }


def parse_path(pd):
    """Populate pd in-place by reading its xml_tree."""
    root = pd["xml_tree"].getroot()
    pd["name"]   = root.get("name",          os.path.basename(pd["filepath"]))
    pd["schema"] = root.get("schemaVersion", "?")

    hdr = root.find(_n("Header"))
    pd["origin_node"]       = hdr.get("originNode",      "?")
    pd["start_time_offset"] = hdr.get("startTimeOffset", "0")
    pd["sync_code"]         = hdr.get("syncCode",        "0")

    od = hdr.find(_n("OriginDatum"))
    pd["lat0"]    = float(od.get("latitude"))
    pd["lon0"]    = float(od.get("longitude"))
    pd["alt0"]    = float(od.get("altitude"))
    pd["bearing"] = float(od.get("bearing"))

    pd["segments"] = []
    for seg_el in root.findall(_n("SegmentList") + "/" + _n("Segment")):
        sp    = seg_el.find(_n("StartPoint"))
        ev_el = seg_el.find(_n("EndCriteria") + "/" + _n("EndVelocity"))
        end_v = float(ev_el.text) if ev_el is not None else 0.0
        x = float(sp.get("x",        0))
        y = float(sp.get("y",        0))
        t = float(sp.get("time",     0))
        v = float(sp.get("velocity", 0))
        h = float(sp.get("heading",  0))
        st       = seg_el.find(_n("SegmentType"))
        seg_type = "Unknown"
        length   = None
        if st is not None:
            straight = st.find(_n("Straight"))
            stop     = st.find(_n("StopPoint"))
            if straight is not None:
                seg_type = "Straight"
                length   = float(straight.get("length", 0))
            elif stop is not None:
                seg_type = "Stop"
        pd["segments"].append({
            "type": seg_type, "x": x, "y": y, "time": t,
            "velocity": v, "heading": h, "end_velocity": end_v,
            "length": length, "_el": seg_el,
        })


def write_path(pd):
    """Push all in-memory edits from pd back into its xml_tree (before save)."""
    root_el = pd["xml_tree"].getroot()
    od = root_el.find(_n("Header") + "/" + _n("OriginDatum"))
    od.set("latitude",  str(pd["lat0"]))
    od.set("longitude", str(pd["lon0"]))
    od.set("altitude",  str(pd["alt0"]))
    od.set("bearing",   str(pd["bearing"]))
    hdr = root_el.find(_n("Header"))
    hdr.set("startTimeOffset", pd["start_time_offset"])
    hdr.set("syncCode",        pd["sync_code"])
    for i, seg_el in enumerate(
            root_el.findall(_n("SegmentList") + "/" + _n("Segment"))):
        s = pd["segments"][i]
        ev = seg_el.find(_n("EndCriteria") + "/" + _n("EndVelocity"))
        if ev is not None:
            ev.text = str(s["end_velocity"])
        sp = seg_el.find(_n("StartPoint"))
        if sp is not None:
            sp.set("velocity", str(s["velocity"]))
            sp.set("heading",  str(s["heading"]))
        st = seg_el.find(_n("SegmentType") + "/" + _n("Straight"))
        if st is not None and s["length"] is not None:
            st.set("length", str(s["length"]))


# ── Custom measurement object helpers ─────────────────────────────────────────

def obj_info(obj):
    """One-line summary string for the measurement table Info column."""
    t = obj["type"]
    if t == "point":
        return f"{obj['lat']:.5f}°,  {obj['lon']:.5f}°"
    if t == "line":
        d   = haversine(obj["lat1"], obj["lon1"], obj["lat2"], obj["lon2"])
        hdg = obj.get("heading",
                      heading_between(obj["lat1"], obj["lon1"],
                                      obj["lat2"], obj["lon2"]))
        return f"L = {d:.2f} m   hdg {hdg:.1f}°"
    if t == "rect":
        return (f"{obj['width_m']:.2f} × {obj['height_m']:.2f} m"
                f"   hdg {obj.get('heading', 0.0):.1f}°")
    return "?"


def obj_rep(obj):
    """Representative (lat, lon) used as the distance-measurement anchor."""
    t = obj["type"]
    if t == "point":
        return obj["lat"], obj["lon"]
    if t == "line":
        return (obj["lat1"]+obj["lat2"])/2, (obj["lon1"]+obj["lon2"])/2
    if t == "rect":
        return obj["clat"], obj["clon"]


def item_rep(item):
    """Works for both path keypoints (no 'type' key) and custom objects."""
    if "type" in item:
        return obj_rep(item)
    return item["lat"], item["lon"]
