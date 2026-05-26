"""
pv/constants.py
───────────────
All visual constants: palette, fonts, path-colour wheel, tile servers, icons.
Edit this file to retheme the entire application.
"""

# ── Colour palette ────────────────────────────────────────────────────────────
BG      = "#0b0718"
PANEL   = "#130d24"
CARD    = "#1c1438"
BORDER  = "#2a1f4a"
ACCENT  = "#00d4ff"
ACCENT2 = "#6d28d9"
TEXT    = "#ddd6f3"
DIM     = "#6b5f8a"
GREEN   = "#10d9a0"
RED     = "#f87070"
YELLOW  = "#f5c518"
ORANGE  = "#fb923c"
WHITE   = "#ffffff"

# ── Multi-path colour wheel (cycles when > 8 paths are loaded) ────────────────
PATH_COLORS = [
    "#00d4ff",  # 1  cyan
    "#f5c518",  # 2  amber
    "#10d9a0",  # 3  emerald
    "#f87070",  # 4  coral
    "#a78bfa",  # 5  violet
    "#fb923c",  # 6  orange
    "#f472b6",  # 7  pink
    "#34d399",  # 8  mint
]

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_BODY  = ("Consolas", 9)
FONT_BOLD  = ("Consolas", 9, "bold")
FONT_HEAD  = ("Consolas", 10, "bold")

# ── Measurement-object type icons ─────────────────────────────────────────────
OBJ_ICON = {"point": "📍", "line": "📏", "rect": "▭"}

# ── Map tile servers ──────────────────────────────────────────────────────────
TILE_SERVERS = {
    "Satellite":  "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}",
    "Hybrid":     "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}",
    "Road":       "https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}",
    "OpenStreet": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
}
