"""
pv/styles.py
────────────
TTK theme setup. Call apply_styles(root) once before any widgets are created.
Edit here to change the look of every widget class in the application.
"""
from tkinter import ttk
from .constants import (BG, PANEL, CARD, BORDER, ACCENT, ACCENT2,
                        TEXT, DIM, WHITE, FONT_BODY, FONT_BOLD, FONT_HEAD)


def apply_styles(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    base = dict(background=PANEL, foreground=TEXT,
                fieldbackground=CARD, borderwidth=0, relief="flat")
    s.configure(".",             **base, font=FONT_BODY)
    s.configure("TFrame",        background=PANEL)
    s.configure("TLabel",        background=PANEL, foreground=TEXT,   font=FONT_BODY)
    s.configure("H.TLabel",      background=PANEL, foreground=ACCENT, font=FONT_HEAD)
    s.configure("Dim.TLabel",    background=PANEL, foreground=DIM,    font=FONT_BODY)
    s.configure("TEntry",
                fieldbackground=CARD, foreground=TEXT,
                insertcolor=ACCENT, borderwidth=1, relief="solid", padding=2)
    s.map("TEntry", fieldbackground=[("focus", "#251c4a")])
    s.configure("Accent.TButton",
                background=ACCENT2, foreground=WHITE,
                font=FONT_BOLD, borderwidth=0, padding=(8, 4))
    s.map("Accent.TButton",
          background=[("active", ACCENT), ("pressed", BG)],
          foreground=[("active", BG)])
    s.configure("TButton",
                background=CARD, foreground=TEXT,
                font=FONT_BODY, borderwidth=0, padding=(6, 3))
    s.map("TButton", background=[("active", BORDER)])
    s.configure("Treeview",
                background=CARD, foreground=TEXT, fieldbackground=CARD,
                rowheight=22, font=FONT_BODY, borderwidth=0)
    s.configure("Treeview.Heading",
                background=BORDER, foreground=ACCENT,
                font=FONT_BOLD, relief="flat")
    s.map("Treeview",
          background=[("selected", ACCENT2)],
          foreground=[("selected", WHITE)])
    s.configure("TScrollbar",
                background=CARD, troughcolor=BG, arrowcolor=DIM, borderwidth=0)
