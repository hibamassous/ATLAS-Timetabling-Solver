import math
import os
import random
import queue
import re
import statistics
import sys
import threading
import time
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from werkzeug.security import generate_password_hash, check_password_hash

import engine

sys.setswitchinterval(0.002)
APP_TITLE = "ATLAS Timetabling Solver"
APP_HEADER = "ATLAS Timetabling Solver"
APP_SUBTITLE = "Mohammed V University · Rabat"

LOT_SIZE = 25                              
ALL_LABEL = "★ All instances"              
QUICK_SIZES = (10, 25, 50, 75, 100, 150, 200)  
ROOM_MEDIUM_MIN_CAPACITY = 60    

C_BG = "#EEF2F7"
C_HEAD = "#2C3E50"
C_BLUE = "#13497B"
C_BLUE_H = "#1B62A3"
C_RED = "#B5202A"
C_HDR = "#DCE6F2"
C_OK = "#E8F5E9"       
C_EMPTY = "#FDECEA"     
CELL_COLORS = ['#FFB6C1', '#87CEEB', '#98FB98', '#FFD700', '#DDA0DD', '#F0E68C',
               '#FFA07A', '#20B2AA', '#B0C4DE', '#F08080', '#90EE90', '#FFDAB9',
               '#E6E6FA', '#AFEEEE', '#FFC0CB', '#C1FFC1', '#FFE4B5', '#D8BFD8']


def _nat(s):
    """Natural sort key: EDT_2 before EDT_10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def blue_titlebar(win, caption="#13497B", text="#FFFFFF"):
    """Blue Windows title bar (Windows 11 only — Windows 10 uses the drawn bar below)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())

        def bgr(h):
            h = h.lstrip("#")
            return int(h[0:2], 16) | (int(h[2:4], 16) << 8) | (int(h[4:6], 16) << 16)
        for attr, col in ((35, caption), (36, text), (34, caption)):   # background, text, border
            val = ctypes.c_int(bgr(col))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def style_window(win):
    """Apply the blue title bar to small dialogs."""
    blue_titlebar(win)
    try:
        win.after(150, lambda: blue_titlebar(win))
    except Exception:
        pass


def _workarea(win):
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            r = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)   # SPI_GETWORKAREA
            return r.left, r.top, r.right - r.left, r.bottom - r.top
        except Exception:
            pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight() - 40


def _taskbar_fix(win):
    """A window without a system frame vanishes from the taskbar: put it back."""
    if os.name != "nt":
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        st = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        st = (st & ~0x80) | 0x40000                      # remove TOOLWINDOW, add APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, st)
        win.withdraw()
        win.after(30, win.deiconify)
    except Exception:
        pass


def install_blue_titlebar(win, title, color=C_BLUE, hover=C_BLUE_H):
    """Replace the white title bar by a BLUE one: drag, double-click = maximize,
    minimize, maximize/restore, close. Call BEFORE building the window content."""
    win.overrideredirect(True)
    st = {"max": False, "geo": None, "min": False, "dx": 0, "dy": 0}

    bar = tk.Frame(win, bg=color, height=34)
    bar.pack(side="top", fill="x")
    bar.pack_propagate(False)
    ico = tk.Label(bar, text="🏫", bg=color, fg="white", font=("Segoe UI Emoji", 11))
    ico.pack(side="left", padx=(10, 4))
    lab = tk.Label(bar, text=title, bg=color, fg="white", font=("Segoe UI", 10))
    lab.pack(side="left")

    def toggle():
        if not st["max"]:
            st["geo"] = win.geometry()
            x, y, w, h = _workarea(win)
            win.geometry(f"{w}x{h}+{x}+{y}")
            st["max"] = True
            btn_max.config(text="❐")
        else:
            win.geometry(st["geo"])
            st["max"] = False
            btn_max.config(text="□")

    def minimize():
        win.overrideredirect(False)

        def go():
            st["min"] = True
            win.iconify()
        win.after(40, go)

    def on_map(e):
        if e.widget is win and st["min"] and win.state() == "normal":
            st["min"] = False

            def reshow():
                win.overrideredirect(True)
                _taskbar_fix(win)
            win.after(10, reshow)
    win.bind("<Map>", on_map, add="+")

    def mk(txt, cmd, hov):
        b = tk.Label(bar, text=txt, bg=color, fg="white", font=("Segoe UI", 11), width=5)
        b.pack(side="right", fill="y")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.config(bg=hov))
        b.bind("<Leave>", lambda e: b.config(bg=color))
        return b
    mk("✕", win.destroy, "#C42B1C")
    btn_max = mk("□", toggle, hover)
    mk("–", minimize, hover)

    def start(e):
        st["dx"], st["dy"] = e.x_root - win.winfo_x(), e.y_root - win.winfo_y()

    def move(e):
        if not st["max"]:
            win.geometry(f"+{e.x_root - st['dx']}+{max(0, e.y_root - st['dy'])}")
    for w in (bar, lab, ico):
        w.bind("<Button-1>", start)
        w.bind("<B1-Motion>", move)
        w.bind("<Double-Button-1>", lambda e: toggle())
    _taskbar_fix(win)


def add_grip(win, color=C_BLUE):
    """◢ grip at the bottom right to resize the window."""
    g = tk.Label(win, text="◢", fg=color, bg=C_BG, cursor="size_nw_se", font=("Segoe UI", 10))
    g.place(relx=1.0, rely=1.0, anchor="se")
    g.bind("<B1-Motion>", lambda e: win.geometry(
        f"{max(900, e.x_root - win.winfo_x())}x{max(560, e.y_root - win.winfo_y())}"))
    g.lift()


def center_window(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth() - w) // 2
    y = max(0, (win.winfo_screenheight() - h) // 2 - 20)
    win.geometry(f"{w}x{h}+{x}+{y}")


def fit_window(win, w, h):
    """Size the window so it ALWAYS fits on screen."""
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w, h = min(w, sw - 40), min(h, sh - 90)
    x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 2 - 20)
    win.geometry(f"{w}x{h}+{x}+{y}")

    def _clamp():
        try:
            win.geometry(f"+{max(0, win.winfo_x())}+{max(0, win.winfo_y())}")
        except Exception:
            pass
    win.after(300, _clamp)


def _pointer_in(ev, widget):
    """Is the mouse over `widget` (or one of its children)?"""
    try:
        w = widget.winfo_containing(ev.x_root, ev.y_root)
    except Exception:
        return False
    while w is not None:
        if w is widget:
            return True
        w = w.master
    return False


def set_icon(win):
    """Window icon (replaces Tk's default feather) — drawn in code."""
    img = tk.PhotoImage(width=32, height=32)
    img.put(C_BLUE, to=(0, 0, 32, 32))
    img.put(C_RED, to=(0, 0, 32, 4))
    img.put("#FFFFFF", to=(4, 10, 28, 30))      # building
    img.put("#FFFFFF", to=(8, 6, 24, 10))       # roof
    img.put("#FFFFFF", to=(14, 3, 18, 6))
    for x in (7, 13, 19):                        # windows
        for y in (13, 19):
            img.put(C_BLUE, to=(x, y, x + 4, y + 4))
    img.put(C_RED, to=(13, 25, 19, 30))          # door
    win.iconphoto(True, img)
    win._icon_ref = img


def setup_style(root):
    """Modern theme: blue tabs, colored buttons, dark-header tables."""
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    F = "Segoe UI"
    s.configure(".", font=(F, 9), background=C_BG)
    s.configure("TFrame", background=C_BG)
    s.configure("TLabel", background=C_BG)
    s.configure("TLabelframe", background=C_BG, bordercolor="#BFD0E3")
    s.configure("TLabelframe.Label", background=C_BG, foreground=C_BLUE, font=(F, 9, "bold"))
    s.configure("TButton", background=C_BLUE, foreground="white", padding=(6, 4),
                borderwidth=0, font=(F, 9, "bold"))
    s.map("TButton", background=[("disabled", "#B7C4D3"), ("active", "#1B62A3")],
          foreground=[("disabled", "#F4F4F4")])
    s.configure("Mini.TButton", padding=(3, 4), font=(F, 8, "bold"))
    s.configure("Go.TButton", background="#2E8B57")
    s.map("Go.TButton", background=[("disabled", "#B7C4D3"), ("active", "#3CA56C")])
    s.configure("Fast.TButton", background="#E08A00")
    s.map("Fast.TButton", background=[("disabled", "#B7C4D3"), ("active", "#F09A10")])
    s.configure("Stop.TButton", background=C_RED)
    s.map("Stop.TButton", background=[("disabled", "#B7C4D3"), ("active", "#D02A36")])
    s.configure("TNotebook", background=C_BG, borderwidth=0)
    s.configure("TNotebook.Tab", padding=(7, 5), background="#D6E0EC", foreground=C_HEAD, font=(F, 8, "bold"))
    s.map("TNotebook.Tab", background=[("selected", C_BLUE)], foreground=[("selected", "white")])
    s.configure("Treeview", rowheight=24, fieldbackground="white", font=(F, 9))
    s.configure("Treeview.Heading", background="#87CEEB", foreground="#0B3C5D", font=(F, 9, "bold"), padding=6)
    s.map("Treeview.Heading", background=[("active", "#5DB8E8")])
    s.configure("Horizontal.TProgressbar", troughcolor="#D6E0EC", background="#2E8B57", thickness=16)


class Header(tk.Canvas):
    """Blue gradient banner with CENTERED title and subtitle."""
    def __init__(self, parent, title, subtitle, c1="#0F2E4F", c2="#1B62A3", h=60):
        super().__init__(parent, height=h, highlightthickness=0, bd=0)
        self.t, self.st, self.c1, self.c2, self.h = title, subtitle, c1, c2, h
        self.bind("<Configure>", self._draw)

    def _draw(self, e):
        self.delete("all")
        w = e.width
        a = [v >> 8 for v in self.winfo_rgb(self.c1)]
        b = [v >> 8 for v in self.winfo_rgb(self.c2)]
        for x in range(0, w, 4):
            t = x / max(1, w)
            col = "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
            self.create_rectangle(x, 0, x + 4, self.h, fill=col, outline="")
        self.create_rectangle(0, self.h - 4, w, self.h, fill=C_RED, outline="")
        self.create_text(w // 2, 23, text="🏫  " + self.t, fill="white", font=("Segoe UI", 14, "bold"))
        self.create_text(w // 2, 44, text=self.st, fill="#CFE0F3", font=("Segoe UI", 9))


P_BG, P_CARD, P_BORDER = "#FCF9F2", "#F2F2EC", "#E4DFD0"
P_TXT, P_LBL = "#12283D", "#2C4A66"
PILL = {"ok": ("#DDF3E6", "#1E7B4A"), "ko": ("#FBE3E1", "#B5202A"),
        "warn": ("#FFF1CC", "#8A6100"), "na": ("#E9E9E4", "#666666")}

SKY, SKY_D, SKY_L, SKY_LL = "#87CEEB", "#5DB8E8", "#D9F0FC", "#F4FAFE"
GRID_LINE, SKY_TXT = "#B5D8EE", "#0B3C5D"


class ScheduleGrid(ttk.Frame):
    """Timetable-style grid drawn on a Canvas: perfectly aligned columns, each course = ONE block
    covering its whole duration (e.g. 3 h = 3 columns). Overlapping courses in the same row are
    stacked (lanes) and marked ⚠ in red, without ever modifying the data."""
    LABEL_W, COL_W, LANE_H, HEAD_H = 190, 88, 50, 36

    def __init__(self, parent):
        super().__init__(parent)
        self.hc = tk.Canvas(self, height=self.HEAD_H, bg=SKY, highlightthickness=0, xscrollincrement=20)
        self.cv = tk.Canvas(self, bg="white", highlightthickness=0, xscrollincrement=20, yscrollincrement=20)
        self.sy = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.sx = ttk.Scrollbar(self, orient="horizontal", command=self._xview)
        self.cv.configure(yscrollcommand=self.sy.set, xscrollcommand=self.sx.set)
        self.hc.grid(row=0, column=0, sticky="ew")
        self.cv.grid(row=1, column=0, sticky="nsew")
        self.sy.grid(row=1, column=1, sticky="ns")
        self.sx.grid(row=2, column=0, sticky="ew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.cv.bind("<Enter>", lambda e: self.cv.focus_set())
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-3 if e.delta > 0 else 3, "units"))
        self.cv.bind("<Shift-MouseWheel>", lambda e: self._xview("scroll", -3 if e.delta > 0 else 3, "units"))
        self.cv.bind("<Button-4>", lambda e: self.cv.yview_scroll(-3, "units"))
        self.cv.bind("<Button-5>", lambda e: self.cv.yview_scroll(3, "units"))

    def _xview(self, *a):
        self.cv.xview(*a)
        self.hc.xview_moveto(self.cv.xview()[0])

    def clear(self):
        self.cv.delete("all")
        self.hc.delete("all")

    @staticmethod
    def _fit(s, n):
        s = str(s)
        return s if len(s) <= n else s[:max(1, n - 1)] + "…"

    def render(self, hours, rows, corner="Room \\ Hour"):
        """rows = [dict(label, sub, bg, items=[dict(start, end, lines[], color, over, cb)])]
        Returns the number of overlapping courses."""
        cv, hc = self.cv, self.hc
        self.clear()
        if not hours:
            return 0
        LW, CW, LH, HH = self.LABEL_W, self.COL_W, self.LANE_H, self.HEAD_H
        h0, h1 = hours[0], hours[-1] + 1
        W = LW + (h1 - h0) * CW
        # ── sky-blue header
        hc.create_rectangle(0, 0, LW, HH, fill=SKY, outline="white", width=2)
        hc.create_text(LW / 2, HH / 2, text=corner, font=("Segoe UI", 9, "bold"), fill=SKY_TXT)
        for i, h in enumerate(hours):
            x = LW + i * CW
            hc.create_rectangle(x, 0, x + CW, HH, fill=SKY, outline="white", width=2)
            hc.create_text(x + CW / 2, HH / 2, text=f"{h}h – {h + 1}h", font=("Segoe UI", 9, "bold"), fill=SKY_TXT)
        hc.create_rectangle(0, HH - 3, W, HH, fill=SKY_D, outline="")
        hc.configure(scrollregion=(0, 0, W, HH))

        y, total_conf, n_tag = 0, 0, 0
        for row in rows:
            items = sorted((dict(it) for it in row.get("items", [])), key=lambda it: (it["start"], it["end"]))
            lane_end = []
            for it in items:
                for li, e in enumerate(lane_end):
                    if e <= it["start"]:
                        it["lane"], lane_end[li] = li, it["end"]
                        break
                else:
                    it["lane"] = len(lane_end)
                    lane_end.append(it["end"])
            for a in items:
                a["conf"] = any(b is not a and a["start"] < b["end"] and b["start"] < a["end"] for b in items)
            nconf = sum(1 for a in items if a["conf"])
            total_conf += nconf
            rh = max(1, len(lane_end)) * LH

            # label cell
            cv.create_rectangle(0, y, LW, y + rh, fill=row.get("bg", SKY_L), outline=GRID_LINE)
            txts = [(self._fit(row["label"], 26), ("Segoe UI", 9, "bold"), "#1a1a1a")]
            if row.get("sub"):
                txts.append((row["sub"], ("Segoe UI", 8), "#444444"))
            if nconf:
                txts.append((f"⚠ {nconf} overlapping courses", ("Segoe UI", 8, "bold"), "#B5202A"))
            for k, (t, f, c) in enumerate(txts):
                cv.create_text(LW / 2, y + rh / 2 + (k - (len(txts) - 1) / 2) * 15, text=t, font=f, fill=c)

            # empty squares (background)
            for i in range(h1 - h0):
                x = LW + i * CW
                cv.create_rectangle(x, y, x + CW, y + rh, fill=SKY_LL, outline=GRID_LINE)

            # course blocks (full duration)
            for it in items:
                s, e = max(it["start"], h0), min(it["end"], h1)
                if e <= s:
                    continue
                x0, x1 = LW + (s - h0) * CW + 2, LW + (e - h0) * CW - 2
                y0 = y + it["lane"] * LH + 2
                y1 = y0 + LH - 4
                tag = f"it{n_tag}"
                n_tag += 1
                cv.create_rectangle(x0, y0, x1, y1, fill=it.get("color", "#CCE"),
                                    outline="#C0392B" if it["conf"] else "#6C8EA4",
                                    width=2 if it["conf"] else 1, tags=(tag,))
                maxc = max(6, int((x1 - x0 - 10) / 6.2))
                lines = [l for l in it.get("lines", []) if l]
                fg = "#B5202A" if it.get("over") else "#1a1a1a"
                for k, l in enumerate(lines[:3]):
                    cy = (y0 + y1) / 2 + (k - (min(3, len(lines)) - 1) / 2) * 12.5
                    cv.create_text((x0 + x1) / 2, cy, text=self._fit(l, maxc), fill=fg, tags=(tag,),
                                   font=("Segoe UI", 8, "bold") if k == 0 else ("Segoe UI", 7))
                if it["conf"]:
                    cv.create_text(x1 - 9, y0 + 8, text="⚠", fill="#C0392B", font=("Segoe UI", 9, "bold"), tags=(tag,))
                cb = it.get("cb")
                if cb:
                    cv.tag_bind(tag, "<Button-1>", lambda ev, cb=cb: cb())
                    cv.tag_bind(tag, "<Enter>", lambda ev: cv.config(cursor="hand2"))
                    cv.tag_bind(tag, "<Leave>", lambda ev: cv.config(cursor=""))
            y += rh
        cv.configure(scrollregion=(0, 0, W, y + 2))
        hc.xview_moveto(0)
        cv.xview_moveto(0)
        return total_conf



def _span(c):
    d = int(c["debut"])
    e = int(c["fin"]) if c.get("fin") not in (None, "") else 0
    if e <= d:
        e = d + int(c.get("duree", 1) or 1)
    return d, e


class _Planning:
    """Occupation par (salle, jour) : masque de bits pour tester la disponibilité en O(1)."""
    def __init__(self):
        self.busy = defaultdict(list)          # (room, day) -> [(s, e, idx)]
        self.mask = defaultdict(int)

    @staticmethod
    def _bits(s, e):
        return ((1 << (e - s)) - 1) << s

    def is_free(self, room, day, s, e, ignore=None):
        return not (self.mask[(room, day)] & self._bits(s, e))

    def blockers(self, room, day, s, e):
        return [i for bs, be, i in self.busy[(room, day)] if s < be and bs < e]

    def add(self, room, day, s, e, i):
        self.busy[(room, day)].append((s, e, i))
        self.mask[(room, day)] |= self._bits(s, e)

    def remove(self, room, day, i):
        k = (room, day)
        self.busy[k] = [t for t in self.busy[k] if t[2] != i]
        m = 0
        for bs, be, _ in self.busy[k]:
            m |= self._bits(bs, be)
        self.mask[k] = m


def fast_assign(cours, caps, rooms=None, seed=None, sweeps=4):
    """Affectation rapide des salles. seed=None -> déterministe ; seed=int -> variante aléatoire
    reproductible (même graine = même résultat). Renvoie stats + historique de fitness (par balayage).
    fitness = -pénalité (plus haut = meilleur)."""
    rng = random.Random(seed) if seed is not None else None
    noise = 0.35 if rng else 0.0
    rooms = list(rooms or caps.keys())
    cap = {r: float(caps.get(r, 0) or 0) for r in rooms}
    n = len(cours)
    sp = [_span(c) for c in cours]
    eff = [float(c.get("effectif", 0) or 0) for c in cours]
    day = [c["jour"] for c in cours]
    grp = defaultdict(list)
    for i, c in enumerate(cours):
        grp[(c.get("num_edt", ""), c["jour"])].append(i)
        c["salle"] = None
    room = [None] * n
    plan = _Planning()
    _cc = {}
    def cand_of(i):
        v = eff[i]
        if v not in _cc:
            _cc[v] = [r for r in rooms if cap[r] >= v]
        return _cc[v]

    def neighbour_rooms(i):
        s, e = sp[i]
        near, other = set(), set()
        for j in grp[(cours[i].get("num_edt", ""), day[i])]:
            if j == i or room[j] is None:
                continue
            (near if (sp[j][1] == s or sp[j][0] == e) else other).add(room[j])
        return near, other

    def cost(i, r, nb):
        c = cap[r]
        k = (c - eff[i]) / max(c, 1.0)
        if eff[i] > 0 and c > 2 * eff[i]:
            k += 1.0
        near, other = nb
        if r in near:
            k -= 0.8
        elif r in other:
            k -= 0.3
        if noise:
            k += rng.random() * noise
        return k

    def place(i, r):
        room[i] = r
        plan.add(r, day[i], sp[i][0], sp[i][1], i)

    def unplace(i):
        plan.remove(room[i], day[i], i)
        room[i] = None

    def best_free_room(i, exclude=None, need_cap=True):
        s, e = sp[i]
        best, bk = None, None
        nb = neighbour_rooms(i)
        for r in (cand_of(i) if need_cap else rooms):
            if r == exclude:
                continue
            if not plan.is_free(r, day[i], s, e):
                continue
            k = cost(i, r, nb) if need_cap else -cap[r]
            if bk is None or k < bk:
                best, bk = r, k
        return best

    def penalty():
        un = oc = big = chg = 0
        for i in range(n):
            r = room[i]
            if r is None:
                un += 1
            elif cap[r] < eff[i]:
                oc += 1
            elif eff[i] > 0 and cap[r] > 2 * eff[i]:
                big += 1
        for idxs in grp.values():
            lst = sorted((j for j in idxs if room[j] is not None), key=lambda j: sp[j][0])
            chg += sum(1 for a, b in zip(lst, lst[1:]) if room[a] != room[b])
        return 1000 * (un + oc) + 3 * big + chg

    # 1) construction (ordre légèrement perturbé si graine)
    if rng:
        keyv = [(-eff[i] * (1 + noise * rng.random()), -(sp[i][1] - sp[i][0]), sp[i][0]) for i in range(n)]
        order = sorted(range(n), key=lambda i: keyv[i])
    else:
        order = sorted(range(n), key=lambda i: (-eff[i], -(sp[i][1] - sp[i][0]), sp[i][0]))
    pending = []
    for i in order:
        r = best_free_room(i)
        if r is None:
            pending.append(i)
        else:
            place(i, r)

    # 2) chaîne d'éjection
    still = []
    for i in pending:
        done = False
        s, e = sp[i]
        cands = sorted((r for r in rooms if cap[r] >= eff[i]),
                       key=lambda r: len(plan.blockers(r, day[i], s, e)))
        for r in cands:
            blk = plan.blockers(r, day[i], s, e)
            if len(blk) > 3:
                continue
            moved, ok = [], True
            for b in blk:
                old = room[b]
                unplace(b)
                nr = best_free_room(b, exclude=r)
                if nr is None:
                    place(b, old)
                    ok = False
                    break
                place(b, nr)
                moved.append((b, old))
            if ok and plan.is_free(r, day[i], s, e):
                place(i, r)
                done = True
                break
            for b, old in reversed(moved):
                unplace(b)
                place(b, old)
        if not done:
            still.append(i)
    for i in still:
        r = best_free_room(i, need_cap=False)
        if r is not None:
            place(i, r)

    # 3) balayages d'amélioration + historique (meilleur-jusqu'ici)
    best_pen = penalty()
    best_room = room[:]
    hist = [-best_pen]
    idle = False
    for _ in range(sweeps):
        if not idle:
            idx = list(range(n))
            if rng:
                rng.shuffle(idx)
            changed = 0
            for i in idx:
                if room[i] is None or cap[room[i]] < eff[i]:
                    continue
                cur = room[i]
                nb = neighbour_rooms(i)
                best, bk = cur, cost(i, cur, nb)
                s, e = sp[i]
                for r in cand_of(i):
                    if r == cur or not plan.is_free(r, day[i], s, e):
                        continue
                    k = cost(i, r, nb)
                    if k < bk - 1e-9:
                        best, bk = r, k
                if best != cur:
                    unplace(i)
                    place(i, best)
                    changed += 1
            if not changed and not rng:
                idle = True
            p = penalty()
            if p < best_pen:
                best_pen, best_room = p, room[:]
        hist.append(-best_pen)

    for i, c in enumerate(cours):
        c["salle"] = best_room[i]
    unassigned = sum(1 for r in best_room if r is None)
    over = sum(1 for i in range(n) if best_room[i] and cap[best_room[i]] < eff[i])
    return dict(total=n, assigned=n - unassigned, unassigned=unassigned, over_capacity=over,
                penalty=best_pen, fitness=-best_pen, history=hist)


def fast_assign_multi(cours, caps, rooms=None, runs=30, base_seed=0, sweeps=4):
    """Lance `runs` variantes (run 1 = déterministe, run r>1 = graine base_seed+r).
    Garde la MEILLEURE affectation dans cours. Renvoie (stats_du_meilleur, historiques, finals)."""
    best_stats, best_rooms = None, None
    hists, finals = [], []
    for r in range(max(1, runs)):
        seed = None if r == 0 else (base_seed + r if base_seed is not None else random.randrange(1 << 30))
        st = fast_assign(cours, caps, rooms, seed=seed, sweeps=sweeps)
        hists.append(st["history"])
        finals.append(st["fitness"])
        if best_stats is None or st["fitness"] > best_stats["fitness"]:
            best_stats, best_rooms = st, [c["salle"] for c in cours]
    for c, r in zip(cours, best_rooms):
        c["salle"] = r
    return best_stats, hists, finals


def _first_key(cours, keys):
    for c in cours:
        for k in keys:
            if c.get(k) not in (None, "", [], ()):
                return k
    return None


def room_types():
    """{room name: lowercase type} from engine.rooms_payload()."""
    out = {}
    try:
        rooms = engine.rooms_payload()
        if not rooms:
            return out
        keys = list(rooms[0].keys())
        kn = next((k for k in keys if k.lower() in ("name", "nom", "salle")), keys[0])
        kt = next((k for k in keys if "type" in k.lower()), None)
        if kt:
            out = {str(r[kn]): str(r[kt]).strip().lower() for r in rooms}
    except Exception:
        pass
    return out


def check_constraints(cours, caps, rtypes):
    """Returns (hard, soft, prof_conflicts).
    hard/soft: lists of (label, n_violations | None if not applicable, detail).
    prof_conflicts: list of dicts describing each REAL professor double-booking."""
    placed = [c for c in cours if c.get("salle")]

    n_cap = sum(1 for c in placed if c["effectif"] > caps.get(c["salle"], 0))

    by = defaultdict(list)
    for c in placed:
        by[(c["salle"], c["jour"])].append(c)
    n_ov = 0
    for lst in by.values():
        for i in range(len(lst)):
            a0, a1 = _span(lst[i])
            for j in range(i + 1, len(lst)):
                b0, b1 = _span(lst[j])
                if a0 < b1 and b0 < a1:
                    n_ov += 1

    byg = defaultdict(list)
    for c in placed:
        byg[(c.get("num_edt", ""), c["jour"])].append(c)
    n_group_ov = 0
    group_conf = []
    for lst in byg.values():
        for i in range(len(lst)):
            a0, a1 = _span(lst[i])
            for j in range(i + 1, len(lst)):
                b0, b1 = _span(lst[j])
                if a0 < b1 and b0 < a1:
                    n_group_ov += 1
                    a, b = lst[i], lst[j]
                    group_conf.append(dict(
                        edt=a.get("num_edt", ""), jour=a["jour"],
                        a=f"{a.get('module', '')} {a0}h-{a1}h",
                        b=f"{b.get('module', '')} {b0}h-{b1}h"))

   
    byp = defaultdict(list)
    for c in placed:
        if str(c.get("prof", "")).strip():
            byp[(str(c["prof"]).strip().lower(), c["jour"])].append(c)
    n_prof, n_joint, prof_conf = 0, 0, []
    for lst in byp.values():
        for i in range(len(lst)):
            a0, a1 = _span(lst[i])
            for j in range(i + 1, len(lst)):
                b0, b1 = _span(lst[j])
                if a0 < b1 and b0 < a1:
                    a, b = lst[i], lst[j]
                    same_mod = str(a.get("module", "")).strip().lower() == str(b.get("module", "")).strip().lower()
                    if same_mod and (a0, a1) == (b0, b1):
                        n_joint += 1
                        continue
                    n_prof += 1
                    prof_conf.append(dict(
                        prof=a.get("prof", ""), jour=a["jour"],
                        a=f"{a.get('module', '')} [{a.get('num_edt', '')}] {a0}h-{a1}h",
                        b=f"{b.get('module', '')} [{b.get('num_edt', '')}] {b0}h-{b1}h"))
    prof_detail = "same professor, 2 simultaneous sessions"
    if n_joint:
        prof_detail += f"  ({n_joint} joint session(s) ignored)"

    hard = [("Room capacity", n_cap, "students > room capacity"),
            ("Room / time-slot overlap", n_ov, "2 courses in the same room at the same time"),
            ("Group overlap (same EDT, same time slot)", n_group_ov,
             "2 courses of the same group at the same time"),
            ("Professor availability", n_prof, prof_detail)]

   
    n_un = len(cours) - len(placed)
    n_big = sum(1 for c in placed if c["effectif"] > 0 and caps.get(c["salle"], 0) > 2 * c["effectif"])
    byg2 = defaultdict(list)
    for c in placed:
        byg2[(c.get("num_edt"), c["jour"])].append(c)
    n_chg = 0
    for lst in byg2.values():
        lst.sort(key=lambda c: _span(c)[0])
        n_chg += sum(1 for a, b in zip(lst, lst[1:]) if a["salle"] != b["salle"])
    soft = [("All courses are assigned", n_un, "courses without a room"),
            ("Well-sized room (capacity ≤ 2 × students)", n_big, "oversized rooms"),
            ("Few room changes during the day (same EDT)", n_chg, "room changes")]
    return hard, soft, prof_conf


def _fmt(v, nd=3):
    s = f"{v:.{nd}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


class StatsPanel(tk.Frame):
    """Statistics panel: constraint tables + statistic cards."""
    COLS = 5

    def __init__(self, parent):
        super().__init__(parent, bg=P_BG)
        self._wrap_labels = []
        self.cv = tk.Canvas(self, bg=P_BG, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.cv, bg=P_BG)
        self._win_id = self.cv.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", self._on_resize)
        self.bind_all("<MouseWheel>", self._wheel, add="+")

    def _on_resize(self, e):
        self.cv.itemconfigure(self._win_id, width=e.width)
        for lb in self._wrap_labels:               # long texts follow the panel width (no more cut-off)
            try:
                lb.config(wraplength=max(200, e.width - 70))
            except tk.TclError:
                pass

    def _wheel(self, e):
        if _pointer_in(e, self):
            self.cv.yview_scroll(-3 if e.delta > 0 else 3, "units")

    def clear(self):
        self._wrap_labels = []
        for w in self.body.winfo_children():
            w.destroy()

    @staticmethod
    def _pill(parent, text, kind):
        bg, fg = PILL[kind]
        return tk.Label(parent, text=text, bg=bg, fg=fg, font=("Segoe UI", 9, "bold"), padx=12, pady=3)

    def _wrapped(self, parent, text, **kw):
        lb = tk.Label(parent, text=text, anchor="w", justify="left",
                      wraplength=max(200, self.cv.winfo_width() - 70), **kw)
        self._wrap_labels.append(lb)
        return lb

    def _title(self, text, sub=None):
        tk.Label(self.body, text=text, bg=P_BG, fg=P_LBL, font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x", padx=22, pady=(18, 2))
        if sub:
            self._wrapped(self.body, sub, bg=P_BG, fg="#6B6B60",
                          font=("Segoe UI", 9)).pack(fill="x", padx=22, pady=(0, 8))

    def _table(self, title, rows, soft=False):
        box = tk.Frame(self.body, bg=P_BG, highlightbackground=P_BORDER, highlightthickness=1)
        box.pack(fill="x", padx=22, pady=6)
        inner = tk.Frame(box, bg=P_BG)
        inner.pack(fill="x", padx=22, pady=16)
        inner.columnconfigure(0, weight=1)
        applicable = [r for r in rows if r[1] is not None]
        ok = sum(1 for r in applicable if r[1] == 0)
        head_kind = "ok" if ok == len(applicable) else ("warn" if soft else "ko")
        tk.Label(inner, text=title, bg=P_BG, fg=P_TXT, font=("Segoe UI", 11, "bold"),
                 anchor="w").grid(row=0, column=0, sticky="w")
        self._pill(inner, f"{ok}/{len(applicable)} satisfied", head_kind).grid(row=0, column=1, sticky="e")
        tk.Label(inner, text="CONSTRAINT", bg=P_BG, fg=P_LBL, font=("Segoe UI", 8, "bold"),
                 anchor="w").grid(row=1, column=0, sticky="w", pady=(14, 6))
        tk.Label(inner, text="STATUS", bg=P_BG, fg=P_LBL, font=("Segoe UI", 8, "bold"),
                 anchor="w").grid(row=1, column=1, sticky="w", pady=(14, 6), padx=(0, 60))
        r = 2
        for label, n, detail in rows:
            tk.Frame(inner, bg=P_BORDER, height=1).grid(row=r, column=0, columnspan=2, sticky="ew")
            cell = tk.Frame(inner, bg=P_BG)
            cell.grid(row=r + 1, column=0, sticky="w", pady=8)
            tk.Label(cell, text=label, bg=P_BG, fg=P_TXT, font=("Segoe UI", 11), anchor="w").pack(anchor="w")
            if detail:
                tk.Label(cell, text=detail, bg=P_BG, fg="#8A8A80", font=("Segoe UI", 8), anchor="w").pack(anchor="w")
            if n is None:
                pill = self._pill(inner, "— Not applicable", "na")
            elif n == 0:
                pill = self._pill(inner, "✔ Satisfied", "ok")
            else:
                pill = self._pill(inner, f"⚠ {n}" if soft else f"✖ {n} violation(s)", "warn" if soft else "ko")
            pill.grid(row=r + 1, column=1, sticky="w", padx=(0, 20))
            r += 2

    def _conflicts(self, conflicts):
        """List of the REAL professor conflicts (they come from the input data)."""
        box = tk.Frame(self.body, bg=P_BG, highlightbackground=P_BORDER, highlightthickness=1)
        box.pack(fill="x", padx=22, pady=6)
        inner = tk.Frame(box, bg=P_BG)
        inner.pack(fill="x", padx=22, pady=14)
        tk.Label(inner, text=f"PROFESSOR CONFLICTS — {len(conflicts)} found", bg=P_BG, fg=P_TXT,
                 font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        self._wrapped(inner, "Days and hours come from the Excel file and are never modified; the algorithm only "
                             "chooses rooms. These conflicts are already in the source data: correct the timetable "
                             "file (move one of the two courses).",
                      bg=P_BG, fg="#6B6B60", font=("Segoe UI", 9)).pack(fill="x", pady=(2, 8))
        for cf in conflicts[:40]:
            tk.Frame(inner, bg=P_BORDER, height=1).pack(fill="x")
            self._wrapped(inner, f"{cf['prof']}  ·  {cf['jour']}:   {cf['a']}   ⟷   {cf['b']}",
                          bg=P_BG, fg=P_TXT, font=("Segoe UI", 9)).pack(fill="x", pady=4)
        if len(conflicts) > 40:
            tk.Label(inner, text=f"… and {len(conflicts) - 40} more", bg=P_BG, fg="#8A8A80",
                     font=("Segoe UI", 9, "italic"), anchor="w").pack(fill="x", pady=4)

    def _cards(self, items):
        box = tk.Frame(self.body, bg=P_BG, highlightbackground=P_BORDER, highlightthickness=1)
        box.pack(fill="x", padx=22, pady=6)
        g = tk.Frame(box, bg=P_BG)
        g.pack(fill="x", padx=18, pady=16)
        for i in range(self.COLS):
            g.columnconfigure(i, weight=1, uniform="c")
        for i, (lab, val) in enumerate(items):
            card = tk.Frame(g, bg=P_CARD, highlightbackground=P_BORDER, highlightthickness=1)
            card.grid(row=i // self.COLS, column=i % self.COLS, padx=6, pady=6, sticky="nsew")
            tk.Label(card, text=lab, bg=P_CARD, fg=P_LBL, font=("Segoe UI", 8), justify="left", anchor="w",
                     wraplength=170).pack(fill="x", padx=14, pady=(12, 2))
            tk.Label(card, text=val, bg=P_CARD, fg=P_TXT, font=("Consolas", 19, "bold"),
                     anchor="w").pack(fill="x", padx=14, pady=(0, 14))

    def render_empty(self, msg):
        self.clear()
        tk.Label(self.body, text=msg, bg=P_BG, fg="#888", font=("Segoe UI", 11)).pack(padx=30, pady=40)

    def render(self, summary, hard, soft, cards, prof_conf=()):
        self.clear()
        self._title("CONSTRAINT VERIFICATION (HARD & SOFT)",
                    "Each constraint is checked on the final result of this run — the number of violations "
                    "and the status correspond to the assignment actually obtained.")
        self._table("HARD CONSTRAINTS — FULL VERIFICATION", hard)
        if prof_conf:
            self._conflicts(list(prof_conf))
        self._table("SOFT CONSTRAINTS", soft, soft=True)
        self._title("STATISTICS PANEL", summary)
        self._cards(cards)
        tk.Frame(self.body, bg=P_BG, height=20).pack()
        self.cv.update_idletasks()
        self._on_resize(type("E", (), {"width": self.cv.winfo_width()})())


USERS = {
    "admin": {"h": generate_password_hash("Admin@2026"), "role": "Administrator"},
    "responsable": {"h": generate_password_hash("Salles@2026"), "role": "Room manager"},
}



class LoginDialog:
    def __init__(self, root):
        self.result = None
        self.win = tk.Toplevel(root)
        self.win.title("Login")
        center_window(self.win, 360, 260)
        set_icon(self.win)
        style_window(self.win)
        self.win.configure(bg="#f0f0f0")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", root.destroy)
        top = tk.Frame(self.win, bg=C_HEAD)
        top.pack(fill="x")
        tk.Label(top, text="🏫 ATLAS Timetabling Solver", font=("Arial", 13, "bold"),
                 bg=C_HEAD, fg="white").pack(pady=(12, 2))
        tk.Label(top, text="Mohammed V University — Rabat", font=("Arial", 9),
                 bg=C_HEAD, fg="#dce6f2").pack(pady=(0, 10))
        f = ttk.Frame(self.win, padding=15)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Username:").grid(row=0, column=0, sticky="w", pady=4)
        self.u = ttk.Entry(f, width=24)
        self.u.grid(row=0, column=1, pady=4)
        ttk.Label(f, text="Password:").grid(row=1, column=0, sticky="w", pady=4)
        self.p = ttk.Entry(f, width=24, show="•")
        self.p.grid(row=1, column=1, pady=4)
        ttk.Button(f, text="🔐 Sign in", command=self.ok).grid(row=2, column=0, columnspan=2, pady=12, sticky="ew")
        self.p.bind("<Return>", lambda e: self.ok())
        self.u.focus_set()

    def ok(self):
        user = USERS.get(self.u.get().strip())
        if user and check_password_hash(user["h"], self.p.get()):
            self.result = (self.u.get().strip(), user["role"])
            self.win.destroy()
        else:
            messagebox.showerror("Error", "Incorrect username or password.", parent=self.win)



class App:
    def __init__(self, root, user, role):
        self.root, self.user, self.role = root, user, role
        self.is_admin = role == "Administrator"
        root.title(APP_TITLE)
        set_icon(root)
        fit_window(root, 1400, 800)
        root.configure(bg=C_BG)

        self.all_cours = []         
        self.cours = []              
        self.inst_map = {}           
        self.inst_nums = None        
        self.inst_uids = None        
        self.custom_inst = {}        
        self._inst_cache = {}       
        self._run_info = {}         
        self._cur_label = ""
        self.stats = None
        self.history = []
        self.moteur = None
        self.running = False
        self.warnings = []
        self._t0 = time.time()
        self._dirty = set()          
        self._sal = self._rt = None  
        self._q = queue.Queue()      
        self._last_plot = 0.0
        self._stop_requested = False
        self._current_run = 1
        self.n_gen = 1
        # ── multi-run state
        self._run_target = 0         
        self._run_done = 0          
        self._all_histories = []    
        self._batch_seed = 0        

        install_blue_titlebar(root, APP_TITLE)     
        self._build()
        add_grip(root)
        self.log(f"✅ Signed in: {user} ({role}). Load an Excel file to get started.")

    # ─────────── construction ───────────
    def _build(self):
        Header(self.root, APP_HEADER,
               f"{APP_SUBTITLE}  ·  👤 {self.user} ({self.role})").pack(fill="x")

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=5, pady=5)
        left = ttk.Frame(paned, width=300, relief=tk.SUNKEN, borderwidth=2)
        right = ttk.Frame(paned, relief=tk.SUNKEN, borderwidth=2)
        paned.add(left, weight=1)
        paned.add(right, weight=4)
        lc = tk.Canvas(left, bg=C_BG, highlightthickness=0, width=290)
        lsb = ttk.Scrollbar(left, orient="vertical", command=lc.yview)
        lc.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        lc.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(lc)
        wid = lc.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: lc.configure(scrollregion=lc.bbox("all")))
        lc.bind("<Configure>", lambda e: lc.itemconfigure(wid, width=e.width))
        self.root.bind_all("<MouseWheel>", lambda e: lc.yview_scroll(-2 if e.delta > 0 else 2, "units")
                           if _pointer_in(e, lc) else None, add="+")
        self._controls(inner)
        self._tabs(right)

    def _controls(self, p):
        f = ttk.LabelFrame(p, text="📂 FILES", padding=5)
        f.pack(fill="x", padx=5, pady=5)
        ttk.Button(f, text="📥 Load courses (Excel)", command=self.load_file).pack(fill="x", pady=2)
        if self.is_admin:
            ttk.Button(f, text="🏢 Load rooms (Excel)", command=self.load_rooms_excel).pack(fill="x", pady=2)
        if self.is_admin:
            ttk.Button(f, text="🆕 Empty session (manual entry)", command=self.new_session).pack(fill="x", pady=2)
        self.lbl_file = ttk.Label(f, text="No file", foreground="gray")
        self.lbl_file.pack(anchor="w")

        f = ttk.LabelFrame(p, text="🎯 WORKING INSTANCE", padding=5)
        f.pack(fill="x", padx=5, pady=5)
        ttk.Label(f, text="Work on:").pack(anchor="w")
        self.inst_var = tk.StringVar()
        self.inst_cb = ttk.Combobox(f, textvariable=self.inst_var, values=[], state="readonly")
        self.inst_cb.pack(fill="x", pady=(2, 0))
        self.inst_cb.bind("<<ComboboxSelected>>", self.on_instance_change)

        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.inst_cb.bind(ev, lambda e: "break")
        self.lbl_inst = ttk.Label(f, text="Load a file to choose an instance.", foreground="gray")
        self.lbl_inst.pack(anchor="w", pady=(4, 0))


        ttk.Separator(f).pack(fill="x", pady=6)
        ttk.Label(f, text="Create an instance of N courses:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        line = ttk.Frame(f)
        line.pack(fill="x", pady=3)
        self.n_var = tk.StringVar(value="50")
        ent = ttk.Entry(line, textvariable=self.n_var, width=7)
        ent.pack(side="left")
        ent.bind("<Return>", lambda e: self.create_custom_instance())
        ttk.Label(line, text=" courses").pack(side="left")
        self.rand_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(line, text="Random", variable=self.rand_var).pack(side="left", padx=8)
        ttk.Button(f, text="🎯 Create instance", style="Mini.TButton",
                   command=self.create_custom_instance).pack(fill="x", pady=2)
        pal = ttk.Frame(f)
        pal.pack(fill="x", pady=(2, 0))
        for n in QUICK_SIZES:
            ttk.Button(pal, text=str(n), width=4, style="Mini.TButton",
                       command=lambda n=n: self.create_custom_instance(n)).pack(side="left", fill="x",
                                                                                expand=True, padx=1)

        f = ttk.LabelFrame(p, text="⚙️ PARAMETERS (genetic algorithm)", padding=5)
        f.pack(fill="x", padx=5, pady=5)
        self.params = {}
        for key, label, default in [("pop", "Population", 60), ("gen", "Generations", 300),
                                     ("pc", "Crossover (0-1)", 0.8), ("pm", "Mutation (0-1)", 0.05),
                                     ("seed", "Seed (empty = random)", 42),
                                     ("runs", "Runs per click", 30)]:
            line = ttk.Frame(f)
            line.pack(fill="x", pady=2)
            ttk.Label(line, text=label + ":", width=18).pack(side="left")
            v = tk.StringVar(value=str(default))
            ttk.Entry(line, textvariable=v, width=9).pack(side="left")
            self.params[key] = v

        f = ttk.LabelFrame(p, text="🚀 ACTIONS", padding=5)
        f.pack(fill="x", padx=5, pady=5)
        line = ttk.Frame(f)
        line.pack(fill="x", pady=2)
        self.btn_run = ttk.Button(line, text="▶️ Run GA", command=self.run, style="Go.TButton")
        self.btn_run.pack(side="left", fill="x", expand=True, padx=1)
        self.btn_stop = ttk.Button(line, text="⏹️ Stop", command=self.stop, state=tk.DISABLED, style="Stop.TButton")
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=1)
        line = ttk.Frame(f)
        line.pack(fill="x", pady=2)
        self.btn_x1 = ttk.Button(line, text="📅 Export timetable", command=lambda: self.export("edt"), state=tk.DISABLED)
        self.btn_x1.pack(side="left", fill="x", expand=True, padx=1)
        self.btn_x2 = ttk.Button(line, text="🏢 Export rooms", command=lambda: self.export("salles"), state=tk.DISABLED)
        self.btn_x2.pack(side="left", fill="x", expand=True, padx=1)
        self.btn_x3 = ttk.Button(f, text="📋 Export details (full list)", command=self.export_details,
                                 state=tk.DISABLED)
        self.btn_x3.pack(fill="x", pady=(4, 0), padx=1)

        f = ttk.LabelFrame(p, text="📊 PROGRESS", padding=5)
        f.pack(fill="x", padx=5, pady=5)
        self.pb = tk.DoubleVar()
        ttk.Progressbar(f, variable=self.pb, maximum=100).pack(fill="x", pady=2)
        self.status = ttk.Label(f, text="Ready", foreground="green")
        self.status.pack(pady=2)
        self.lbl_time = ttk.Label(f, text="⏱ Execution time: —",
                                  font=("Segoe UI", 10, "bold"), foreground=C_BLUE)
        self.lbl_time.pack(pady=2)
        self.lbl_run = ttk.Label(f, text="🔁 Run: — / —",
                                 font=("Segoe UI", 10, "bold"), foreground="#8A6100")
        self.lbl_run.pack(pady=2)

        f = ttk.LabelFrame(p, text="📝 LOG", padding=5)
        f.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_log = tk.Text(f, height=6, wrap="word", font=("Consolas", 8))
        sb = ttk.Scrollbar(f, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        ttk.Button(p, text="🚪 Log out", command=self.logout).pack(fill="x", padx=5, pady=5)

    def _scroll_area(self, parent):
        cont = ttk.Frame(parent)
        cont.pack(fill="both", expand=True, padx=5, pady=5)
        cv = tk.Canvas(cont, bg="white", highlightthickness=0)
        sy = ttk.Scrollbar(cont, orient="vertical", command=cv.yview)
        sx = ttk.Scrollbar(cont, orient="horizontal", command=cv.xview)
        fr = ttk.Frame(cv)
        fr.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=fr, anchor="nw")
        cv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        cv.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")
        return fr

    def _tabs(self, p):
        self.nb = ttk.Notebook(p)
        self.nb.pack(fill="both", expand=True)
        self.t_occ, self.t_edt, self.t_list = ttk.Frame(self.nb), ttk.Frame(self.nb), ttk.Frame(self.nb)
        self.t_stats, self.t_evo, self.t_rooms = ttk.Frame(self.nb), ttk.Frame(self.nb), ttk.Frame(self.nb)
        self.nb.add(self.t_occ, text="📅 ROOM OCCUPANCY")
        self.nb.add(self.t_edt, text="📚 TIMETABLE (PROGRAM)")
        self.nb.add(self.t_list, text="📋 DETAILED LIST")
        self.nb.add(self.t_stats, text="📊 STATISTICS")
        self.nb.add(self.t_evo, text="📈 FITNESS EVOLUTION")
        self.nb.add(self.t_rooms, text="🏢 ROOM MANAGEMENT")
        self._occ_ui()
        self._edt_ui()
        self._list_ui()
        self._stats_ui()
        self._evo_ui()
        self._rooms_ui()
        self.nb.bind("<<NotebookTabChanged>>", self._refresh_visible)


    def _in_inst(self, c):
        """Does course c belong to the current instance?"""
        if self.inst_uids is not None:
            return c.get("_uid") in self.inst_uids
        return self.inst_nums is None or c.get("num_edt") in self.inst_nums

    def _build_instances(self, reset=False):
        """List of instances: "All", the "N courses" selections, batches of LOT_SIZE EDT,
        then each EDT alone."""
        order, fil = [], {}
        for c in self.all_cours:
            n = c.get("num_edt", "")
            if n not in fil:
                fil[n] = c.get("filiere", "")
                order.append(n)
        order.sort(key=_nat)
        m = {}
        if self.all_cours:
            m[ALL_LABEL] = None
            for lab in self.custom_inst:
                m[lab] = None
            if len(order) > LOT_SIZE:
                for i in range(0, len(order), LOT_SIZE):
                    part = order[i:i + LOT_SIZE]
                    m[f"Batch {i // LOT_SIZE + 1} · {part[0]} → {part[-1]}"] = part
            for n in order:
                m[f"{n} · {fil[n]}"] = [n]
        prev = self.inst_var.get()
        self.inst_map = m
        self.inst_cb["values"] = list(m)
        self.inst_var.set(prev if (not reset and prev in m) else (ALL_LABEL if m else ""))

    def _load_instance(self):
        """Put the courses of the chosen instance in self.cours and refresh all tabs."""
        label = self.inst_var.get()
        if label in self.custom_inst:
            self.inst_uids, self.inst_nums = set(self.custom_inst[label]), None
        else:
            self.inst_uids = None
            nums = self.inst_map.get(label)
            self.inst_nums = set(nums) if nums else None
        self._cur_label = label
        self.cours = [c for c in self.all_cours if self._in_inst(c)]
        st, hist = self._inst_cache.get(label, (None, []))
        self.stats, self.history = st, list(hist)
        self._all_histories = []
        self.pb.set(0)
        self.edt_var.set("")
        self.edt_grid.clear()
        self.edt_info.config(text="")
        self.f_fil.set("All")
        self._update_export_buttons()
        t = self._run_info.get(label, {}).get("time")          
        self.lbl_time.config(text=self._fmt_time(t) if t else "⏱ Execution time: —")
        self.lbl_run.config(text="🔁 Run: — / —")
        self.refresh_all()

    @staticmethod
    def _fmt_time(t):
        """Human-readable execution time (ms for very fast runs)."""
        return f"⏱ Execution time: {t * 1000:.1f} ms" if t < 1 else f"⏱ Execution time: {t:.2f} s"

    def _sync_back(self):
        """Write the work of the current instance (assignments, additions, deletions)
        back into the full data set — other courses are never touched."""
        nxt = max([c.get("_uid", -1) for c in self.all_cours + self.cours] + [-1]) + 1
        for c in self.cours:                              
            if "_uid" not in c:
                c["_uid"] = nxt
                nxt += 1
        if self.inst_uids is None and self.inst_nums is None:
            self.all_cours = list(self.cours)
        else:
            rest = [c for c in self.all_cours if not self._in_inst(c)]
            if self.inst_uids is not None:
                self.inst_uids |= {c["_uid"] for c in self.cours}
                self.custom_inst[self._cur_label] = set(self.inst_uids)
            self.all_cours = rest + list(self.cours)
            self.all_cours.sort(key=lambda c: _nat(c.get("num_edt", "")))   

    def _set_all(self, cours):
        """New full data set (Excel load or empty session)."""
        self.all_cours = list(cours)
        for i, c in enumerate(self.all_cours):
            c["_uid"] = i
        self._inst_cache, self._run_info, self.custom_inst = {}, {}, {}
        self.inst_uids = self.inst_nums = None
        self._build_instances(reset=True)
        self._load_instance()

    def create_custom_instance(self, n=None):
        """Create an instance of N courses (the first N, or N random) and switch to it."""
        if not self.all_cours:
            messagebox.showwarning("Warning", "Load the courses first.")
            return
        if self.running:
            return
        try:
            n = int(n if n is not None else self.n_var.get())
        except ValueError:
            messagebox.showerror("Error", "Enter an integer number of courses.")
            return
        if n < 1:
            messagebox.showerror("Error", "The number of courses must be ≥ 1.")
            return
        self.n_var.set(str(n))
        self._sync_back()                                
        n = min(n, len(self.all_cours))
        rnd = self.rand_var.get()
        s = self.params["seed"].get().strip()          
        rng = random.Random(int(s)) if s.lstrip("-").isdigit() else random
        pool = rng.sample(self.all_cours, n) if rnd else self.all_cours[:n]
        base = f"✂ {n} courses ({'random' if rnd else 'first'})"
        label, k = base, 2
        while label in self.custom_inst:
            label, k = f"{base} #{k}", k + 1
        self.custom_inst[label] = {c["_uid"] for c in pool}
        self._build_instances()
        self.inst_var.set(label)
        self.on_instance_change()

    def on_instance_change(self, _e=None):
        if self.running:                              
            self.inst_var.set(self._cur_label)
            return
        self._sync_back()                             
        self._inst_cache[self._cur_label] = (self.stats, list(self.history))
        self._load_instance()
        placed = sum(1 for c in self.cours if c.get("salle"))
        self.log(f"🎯 Instance “{self._cur_label}”: {len(self.cours)} courses ({placed} already assigned).")
        self.status.config(text=f"Instance: {len(self.cours)} courses")

    def _salles(self):
        if self._sal is None:
            self._sal = engine.get_salles()
        return self._sal

    def _room_types(self):
        if self._rt is None:
            self._rt = room_types()
        return self._rt

    def _update_export_buttons(self):
        st = tk.NORMAL if any(c.get("salle") for c in self.cours) else tk.DISABLED
        for b in (self.btn_x1, self.btn_x2, self.btn_x3):
            b.config(state=st)

    def _occ_ui(self):
        b = ttk.Frame(self.t_occ)
        b.pack(fill="x", padx=5, pady=5)
        ttk.Label(b, text="Filter by:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        ttk.Label(b, text="Day:").pack(side="left", padx=(8, 2))
        self.f_day = ttk.Combobox(b, values=list(engine.JOURS), width=12, state="readonly")
        self.f_day.set(engine.JOURS[0])
        self.f_day.pack(side="left")
        ttk.Label(b, text="Room:").pack(side="left", padx=(8, 2))
        self.f_room = ttk.Combobox(b, values=["All"], width=22, state="readonly")
        self.f_room.set("All")
        self.f_room.pack(side="left")
        ttk.Label(b, text="Program:").pack(side="left", padx=(8, 2))
        self.f_fil = ttk.Combobox(b, values=["All"], width=22, state="readonly")
        self.f_fil.set("All")
        self.f_fil.pack(side="left")
        for c in (self.f_day, self.f_room, self.f_fil):
            c.bind("<<ComboboxSelected>>", lambda e: self.refresh_occ())
        ttk.Button(b, text="🔄 Refresh", command=self.refresh_occ).pack(side="left", padx=8)
        ttk.Button(b, text="❌ Reset", command=self.reset_filters).pack(side="left")
        ttk.Label(self.t_occ, text="💡 Click a course to change its room.",
                  foreground="#777", font=("Arial", 8)).pack(anchor="w", padx=8)
        self.occ_info = ttk.Label(self.t_occ, text="", font=("Segoe UI", 10, "bold"), foreground=C_BLUE)
        self.occ_info.pack(pady=4)
        self.occ_leg = ttk.Frame(self.t_occ)
        self.occ_leg.pack(side="bottom", fill="x", pady=4)
        self.occ_grid = ScheduleGrid(self.t_occ)
        self.occ_grid.pack(fill="both", expand=True, padx=5, pady=5)

    def reset_filters(self):
        self.f_room.set("All")
        self.f_fil.set("All")
        self.refresh_occ()

    def _mod_color(self, m):
        if not hasattr(self, "_mc"):
            self._mc = {}
        if m not in self._mc:
            self._mc[m] = CELL_COLORS[len(self._mc) % len(CELL_COLORS)]
        return self._mc[m]

    @staticmethod
    def _end(c):
        """Real end of the course (Excel data, e.g. 3 h) — never modified."""
        d = int(c["debut"])
        e = int(c["fin"]) if c.get("fin") not in (None, "") else 0
        if e <= d:
            e = d + int(c.get("duree", 1) or 1)
        return e

    def refresh_occ(self):
        for w in self.occ_leg.winfo_children():
            w.destroy()
        placed = [c for c in self.cours if c.get("salle")]
        if not placed:
            self.occ_grid.clear()
            self.occ_info.config(text="No data. Run the assignment first.")
            return
        _a, _m, _p, salles_all, caps = self._salles()
        day, rsel, fsel = self.f_day.get(), self.f_room.get(), self.f_fil.get()
        rooms = [rsel] if rsel != "All" else list(salles_all)
        jour_c = [c for c in placed if c["jour"] == day and (fsel == "All" or c.get("filiere") == fsel)]
        counts = {r: sum(1 for c in jour_c if c["salle"] == r) for r in rooms}
        rows = []
        for r in sorted(rooms, key=lambda x: counts[x], reverse=True):
            items = [dict(start=int(c["debut"]), end=self._end(c),
                          lines=[c["module"], c["filiere"], c["prof"]],
                          color=self._mod_color(c["module"]), over=c["effectif"] > caps.get(r, 0),
                          cb=(lambda c=c: self.reassign_dialog(c)))
                     for c in jour_c if c["salle"] == r]
            rows.append(dict(label=r, sub=f"{counts[r]} courses · cap.{caps.get(r, '?')}",
                             bg=C_OK if counts[r] else C_EMPTY, items=items))
        nconf = self.occ_grid.render(list(engine.HEURES), rows, "Room \\ Hour")
        used = sum(1 for r in rooms if counts[r])
        self.occ_info.config(text=f"📅 Day: {day}  |  Program: {fsel}  |  Courses shown: {len(jour_c)}  |  "
                                  f"Rooms used: {used}/{len(rooms)}  |  ⚠ Overlapping: {nconf}")
        ttk.Label(self.occ_leg, text="Legend:", font=("Segoe UI", 8, "bold")).pack(side="left", padx=5)
        for m in list(dict.fromkeys(c["module"] for c in jour_c))[:10]:
            tk.Label(self.occ_leg, text=m[:14], font=("Segoe UI", 7), bg=self._mod_color(m), relief="solid",
                     borderwidth=1, padx=4).pack(side="left", padx=2)

    def reassign_dialog(self, c):
        _a, _m, _p, salles_all, caps = self._salles()
        d = tk.Toplevel(self.root)
        d.title("Reassign room")
        d.geometry("380x200")
        d.transient(self.root)
        d.grab_set()
        style_window(d)
        f = ttk.Frame(d, padding=12)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=f"{c['module']} — {c['prof']}\n{c['jour']} {int(c['debut'])}h-{int(c['fin'])}h · "
                          f"{int(c['effectif'])} students", font=("Arial", 9, "bold")).pack(anchor="w", pady=4)
        ttk.Label(f, text=f"Current room: {c['salle']}").pack(anchor="w")
        cb = ttk.Combobox(f, values=[f"{s}  ({caps[s]} seats)" for s in salles_all], state="readonly", width=34)
        cb.pack(pady=8)

        def apply():
            if not cb.get():
                return
            new = cb.get().split("  (")[0]
            msg = self._try_reassign(c, new, caps)
            if msg:
                messagebox.showerror("Reassignment impossible", msg, parent=d)
            else:
                self.log(f"🔁 {c['module']} → {new}")
                d.destroy()
                self.refresh_all()
        ttk.Button(f, text="✔ Apply", command=apply).pack(fill="x")

    def _try_reassign(self, cible, new, caps):
        if caps[new] < cible["effectif"]:
            return f"Insufficient capacity: {new} ({caps[new]} seats) for {int(cible['effectif'])} students."
        for c in self.cours:
            if c is cible or c.get("salle") != new or c.get("jour") != cible["jour"]:
                continue
            if int(c["debut"]) < int(cible["fin"]) and int(cible["debut"]) < int(c["fin"]):
                return f"Conflict: {new} is already occupied by {c['module']} ({c['prof']}) in this time slot."
        cible["salle"] = new
        return None

    def _edt_ui(self):
        b = ttk.Frame(self.t_edt)
        b.pack(fill="x", padx=5, pady=5)
        ttk.Label(b, text="Program / Timetable:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        self.edt_var = tk.StringVar()
        self.edt_cb = ttk.Combobox(b, textvariable=self.edt_var, width=30, state="readonly")
        self.edt_cb.pack(side="left", padx=5)
        self.edt_cb.bind("<<ComboboxSelected>>", lambda e: self.show_edt())
        self.edt_info = ttk.Label(self.t_edt, text="", font=("Segoe UI", 11, "bold"), foreground=C_BLUE)
        self.edt_info.pack(pady=4)
        self.edt_grid = ScheduleGrid(self.t_edt)
        self.edt_grid.pack(fill="both", expand=True, padx=5, pady=5)

    def show_edt(self):
        num = self.edt_var.get().split(" — ")[0]
        mine = [c for c in self.cours if c.get("num_edt") == num and c.get("salle")]
        if not mine:
            self.edt_grid.clear()
            self.edt_info.config(text="No course assigned.")
            return
        rows = []
        for day in engine.JOURS:
            items = [dict(start=int(c["debut"]), end=self._end(c), lines=[c["module"], c["prof"], c["salle"]],
                          color=self._mod_color(c["module"])) for c in mine if c["jour"] == day]
            rows.append(dict(label=day, sub=f"{len(items)} courses", bg=C_OK if items else "#F0F0F0", items=items))
        nconf = self.edt_grid.render(list(engine.HEURES), rows, "Day \\ Hour")
        self.edt_info.config(text=f"📚 Timetable — {mine[0]['filiere']}"
                                  + (f"   ·   ⚠ {nconf} overlapping courses" if nconf else ""))

    def _list_ui(self):
        if self.is_admin:
            b = ttk.Frame(self.t_list)
            b.pack(fill="x", padx=5, pady=5)
            ttk.Button(b, text="➕ Add", command=lambda: self.course_dialog(None)).pack(side="left", padx=2)
            ttk.Button(b, text="✏️ Edit", command=self.edit_course).pack(side="left", padx=2)
            ttk.Button(b, text="🗑️ Delete", command=self.del_course).pack(side="left", padx=2)
        f = ttk.Frame(self.t_list)
        f.pack(fill="both", expand=True, padx=5, pady=5)
        cols = ("EDT", "Program", "Day", "Time", "Module", "Professor", "Students", "Room", "Cap.", "Status")
        self.tree = ttk.Treeview(f, columns=cols, show="headings", height=22)
        for col, w in zip(cols, [70, 150, 80, 80, 220, 150, 70, 130, 55, 90]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")
        sy = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sy.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        self.tree.tag_configure("over", background="#ffe0e0")
        self.tree.tag_configure("none", background="#fff6d6")

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        _a, _m, _p, _all, caps = self._salles()
        for i, c in enumerate(self.cours):
            s = c.get("salle")
            cap = caps.get(s, "") if s else ""
            over = bool(s) and cap != "" and c["effectif"] > cap
            status = "⚠️ capacity" if over else ("—" if not s else "OK")
            self.tree.insert("", "end", iid=str(i), tags=("over",) if over else (() if s else ("none",)),
                             values=(c.get("num_edt", ""), c.get("filiere", ""), c.get("jour", ""),
                                     f"{int(c['debut'])}h-{int(c['fin'])}h", c.get("module", ""),
                                     c.get("prof", ""), int(c.get("effectif", 0)), s or "", cap, status))

    def _selected_course(self):
        sel = self.tree.selection()
        return self.cours[int(sel[0])] if sel else None

    def edit_course(self):
        c = self._selected_course()
        if c:
            self.course_dialog(c)
        else:
            messagebox.showinfo("Info", "Select a course.")

    def del_course(self):
        c = self._selected_course()
        if not c:
            return
        if messagebox.askyesno("Confirm", f"Delete “{c['module']}”?"):
            try:
                engine.remove_course(self.cours, c.get("id"))
                self.after_manual_change()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def course_dialog(self, c):
        if self.cours is None:
            return
        d = tk.Toplevel(self.root)
        d.title("Course")
        d.transient(self.root)
        d.grab_set()
        style_window(d)
        f = ttk.Frame(d, padding=12)
        f.pack()
        fields = [("num_edt", "EDT No."), ("filiere", "Program"), ("module", "Module"), ("prof", "Professor"),
                  ("jour", "Day"), ("debut", "Start (h)"), ("duree", "Duration (h)"), ("effectif", "Students")]
        vars_ = {}
        for r, (k, lab) in enumerate(fields):
            ttk.Label(f, text=lab + ":").grid(row=r, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=str(c.get(k, "")) if c else "")
            if k == "jour":
                ttk.Combobox(f, textvariable=v, values=list(engine.JOURS), state="readonly", width=24).grid(row=r, column=1)
            else:
                ttk.Entry(f, textvariable=v, width=27).grid(row=r, column=1)
            vars_[k] = v

        def save():
            data = {k: v.get().strip() for k, v in vars_.items()}
            try:
                if c:
                    engine.update_course(self.cours, c.get("id"), data)
                else:
                    engine.add_course(self.cours, data)
                d.destroy()
                self.after_manual_change()
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=d)
        ttk.Button(f, text="💾 Save", command=save).grid(row=len(fields), column=0, columnspan=2,
                                                          pady=10, sticky="ew")

    def after_manual_change(self):
        self.stats, self.history = None, []
        self._inst_cache.pop(self._cur_label, None)
        self._run_info.pop(self._cur_label, None)
        self._sync_back()                            
        old = self.inst_var.get()
        self._build_instances()                     
        if self.inst_var.get() != old:                
            self._load_instance()
        else:
            self.refresh_all()
        self.lbl_time.config(text="⏱ Execution time: —")
        self.log("✏️ Courses modified — run the assignment again.")

    def _stats_ui(self):
        self.stats_panel = StatsPanel(self.t_stats)
        self.stats_panel.pack(fill="both", expand=True)

    def refresh_stats(self):
        P = self.stats_panel
        if not self.cours:
            P.render_empty("Load a file, then run the assignment.")
            return
        placed = [c for c in self.cours if c.get("salle")]
        if not placed:
            P.render_empty("Run the assignment to see the statistics of this instance.")
            return
        _a, _m, _p, allr, caps = self._salles()
        hard, soft, prof_conf = check_constraints(self.cours, caps, self._room_types())
        hist = list(self.history)
        info = self._run_info.get(self._cur_label, {})
        var = statistics.pvariance(hist) if len(hist) > 1 else 0.0
        finals = info.get("finals", [])
        tvar = statistics.pvariance(finals) if len(finals) > 1 else 0.0
        if "time" in info:
            t = info["time"]
            time_txt = f"{t * 1000:.1f}ms" if t < 1 else f"{t:.2f}s"
        else:
            time_txt = "—"
        cards = [("FITNESS FUNCTION (BEST)", _fmt(hist[-1], 1) if hist else "—"),
                 ("EXECUTION TIME", time_txt),
                 ("FITNESS VARIANCE", _fmt(var)),
                 ("FITNESS STANDARD DEVIATION", _fmt(math.sqrt(var))),
                 ("TRAJECTORY VARIANCE", _fmt(tvar)),
                 ("TRAJECTORY STANDARD DEVIATION", _fmt(math.sqrt(tvar))),
                 ("GENERATIONS EXECUTED", str(len(hist)) if hist else "—")]
        summary = (f"Instance: {self._cur_label}   ·   {len(placed)}/{len(self.cours)} courses assigned   ·   "
                   f"{len(set(c['salle'] for c in placed))}/{len(allr)} rooms used   ·   "
                   f"{len(finals)} run(s) recorded")
        P.render(summary, hard, soft, cards, prof_conf)

    def _evo_ui(self):
        self.fig = Figure(figsize=(10, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.cv = FigureCanvasTkAgg(self.fig, master=self.t_evo)
        self.cv.get_tk_widget().pack(fill="both", expand=True)
        self.draw_evo()

    def draw_evo(self):
        self.ax.clear()

        curves = [h for h in self._all_histories if h]
        if curves:
            L = max(len(h) for h in curves)
            avg = []
            for i in range(L):
                vals = [h[i] for h in curves if i < len(h)]
                avg.append(sum(vals) / len(vals))
            g = list(range(1, len(avg) + 1))
            self.ax.axis("on")
            for h in curves[:30]:                       
                self.ax.plot(range(1, len(h) + 1), h, color="#9DB8D2", lw=0.6, alpha=0.5)
            self.ax.plot(g, avg, color=C_BLUE, lw=2.5, label=f"Average of {len(curves)} run(s)")
            self.ax.set_title("Fitness evolution — average over runs", fontweight="bold")
            self.ax.set_xlabel("Generation")
            self.ax.set_ylabel("Fitness")
            self.ax.grid(True, ls="--", alpha=0.35)
            self.ax.legend(loc="lower right")
        elif self.history:
            g = list(range(1, len(self.history) + 1))
            self.ax.axis("on")
            self.ax.plot(g, self.history, color=C_BLUE, lw=2.2, label="Best fitness")
            self.ax.fill_between(g, self.history, min(self.history), color=C_BLUE, alpha=0.1)
            self.ax.set_title("Fitness evolution — Genetic algorithm", fontweight="bold")
            self.ax.set_xlabel("Generation")
            self.ax.set_ylabel("Fitness")
            self.ax.grid(True, ls="--", alpha=0.35)
            self.ax.legend(loc="lower right")
        else:
            self.ax.text(0.5, 0.5, "Run the GA to see the convergence\n(the ⚡ fast solver has no evolution curve)",
                         ha="center", va="center", transform=self.ax.transAxes, color="#888", fontsize=12)
            self.ax.axis("off")
        self.fig.tight_layout()
        self.cv.draw_idle()

    def _rooms_ui(self):
        b = ttk.Frame(self.t_rooms)
        b.pack(fill="x", padx=5, pady=5)
        if self.is_admin:
            ttk.Button(b, text="➕ Add / edit", command=self.room_dialog).pack(side="left", padx=2)
            ttk.Button(b, text="🗑️ Delete", command=self.del_room).pack(side="left", padx=2)
        else:
            ttk.Label(b, text="Read-only (administrator only).", foreground="gray").pack(side="left")
        ttk.Button(b, text="🔄 Refresh", command=self.refresh_rooms).pack(side="left", padx=8)
        self.rooms_tree = ttk.Treeview(self.t_rooms, show="headings", height=22)
        self.rooms_tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.refresh_rooms()

    def refresh_rooms(self):
        self._sal = self._rt = None                    
        rooms = engine.rooms_payload()
        self.rooms_data = rooms
        keys = list(rooms[0].keys()) if rooms else ["name", "capacity", "type"]
        self.room_keys = keys
        t = self.rooms_tree
        t.delete(*t.get_children())
        t["columns"] = keys
        for k in keys:
            t.heading(k, text=k.capitalize())
            t.column(k, width=130, anchor="center")
        for r in rooms:
            t.insert("", "end", values=[r.get(k, "") for k in keys])
        self._update_room_filter()

    def room_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Room")
        d.transient(self.root)
        d.grab_set()
        style_window(d)
        f = ttk.Frame(d, padding=12)
        f.pack()
        sel = self.rooms_tree.selection()
        cur = dict(zip(self.room_keys, self.rooms_tree.item(sel[0])["values"])) if sel else {}
        vars_ = {}
        for r, k in enumerate(self.room_keys):
            ttk.Label(f, text=k.capitalize() + ":").grid(row=r, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=str(cur.get(k, "")))
            ttk.Entry(f, textvariable=v, width=26).grid(row=r, column=1)
            vars_[k] = v

        def save():
            try:
                engine.upsert_room({k: v.get().strip() for k, v in vars_.items()})
                d.destroy()
                self.refresh_rooms()
                self.refresh_occ()
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=d)
        ttk.Button(f, text="💾 Save", command=save).grid(row=len(self.room_keys), column=0,
                                                          columnspan=2, pady=10, sticky="ew")

    def del_room(self):
        sel = self.rooms_tree.selection()
        if not sel:
            return
        name = str(self.rooms_tree.item(sel[0])["values"][0])
        if messagebox.askyesno("Confirm", f"Delete room “{name}”?"):
            try:
                engine.remove_room(name)
                self.refresh_rooms()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def _update_room_filter(self):
        try:
            _a, _m, _p, allr, _c = self._salles()
            self.f_room["values"] = ["All"] + list(allr)
        except Exception:
            pass

    def load_file(self):
        path = filedialog.askopenfilename(title="Courses file",
                                          filetypes=[("Excel", "*.xlsx *.xlsm *.xls"), ("All", "*.*")])
        if not path:
            return
        try:
            cours, self.warnings = engine.charger_cours(path)
        except Exception as e:
            self.log(f"❌ {e}")
            messagebox.showerror("Error", str(e))
            return
        self.lbl_file.config(text=os.path.basename(path), foreground=C_BLUE)
        self._set_all(cours)          # full data set + instance list (default: "All")
        n_edt = len(set(c["num_edt"] for c in self.all_cours))
        self.log(f"✅ {len(self.all_cours)} courses · {n_edt} EDT · {len(self.warnings)} warning(s)")
        for w in self.warnings[:8]:
            self.log(f"   ⚠ {w}")
        self.log("🎯 Choose the working instance in the “WORKING INSTANCE” box (left).")
        self.status.config(text=f"{len(self.all_cours)} courses loaded")

    def new_session(self):
        self.warnings = []
        self.lbl_file.config(text="Empty session", foreground=C_BLUE)
        self._set_all([])
        self.log("🆕 Empty session created — add courses in the LIST tab.")

    def run_fast(self):
        """⚡ Fast solver: N runs (parameter "Runs per click") in a fraction of a second.
        Run 1 is deterministic, run r>1 uses seed+r (same seed => same results). The BEST run is kept."""
        if not self.cours:
            messagebox.showwarning("Warning", "Load the courses first.")
            return
        if self.running:
            return
        try:
            runs = max(1, min(int(self.params["runs"].get()), 1000))
            seed_txt = self.params["seed"].get().strip()
            base = int(seed_txt) if seed_txt else None
        except ValueError:
            messagebox.showerror("Error", "Invalid parameters (runs / seed).")
            return
        try:
            _a, _m, _p, allr, caps = self._salles()
            t0 = time.perf_counter()
            st, hists, finals = fast_assign_multi(self.cours, caps, list(allr), runs=runs, base_seed=base)
            dt = time.perf_counter() - t0
        except Exception as e:
            self.log(f"❌ {e}")
            messagebox.showerror("Error", str(e))
            return
        self.history = list(st["history"])               
        self._all_histories = [list(h) for h in hists]    
        self.stats = st
        info = self._run_info.setdefault(self._cur_label, {"finals": []})
        info["time"] = dt
        info["finals"] = list(finals)                   
        self._sync_back()
        self._inst_cache[self._cur_label] = (self.stats, list(self.history))
        self.lbl_time.config(text=self._fmt_time(dt))
        self.lbl_run.config(text=f"🔁 Run: {runs} / {runs} ✓  (⚡ fast)")
        self.pb.set(0)
        self.status.config(text=f"Done — {st['assigned']}/{st['total']} courses assigned")
        self._update_export_buttons()
        self.log(f"⚡ Fast solve · instance “{self._cur_label}” · {runs} run(s) · best fitness {st['fitness']} · "
                 f"{st['assigned']}/{st['total']} assigned · {st['over_capacity']} over capacity · "
                 f"{dt * 1000:.0f} ms total")
        if st["unassigned"] or st["over_capacity"]:
            self.log("   ⚠ Some courses could not be placed correctly (not enough rooms of sufficient "
                     "capacity at that time): see the STATISTICS tab.")
        self.refresh_all()

    def run(self):
        """Launch the GA multiple times in a row (N = 'Runs per click' parameter).
        Each run uses seed+0, seed+1, seed+2, … (or random seeds if seed is empty)."""
        if not self.cours:
            messagebox.showwarning("Warning", "Load the courses first.")
            return
        try:
            pop = max(10, min(int(self.params["pop"].get()), 400))
            gen = max(10, min(int(self.params["gen"].get()), 3000))
            pc = min(max(float(self.params["pc"].get()), 0.0), 1.0)
            pm = min(max(float(self.params["pm"].get()), 0.0), 1.0)
            seed_txt = self.params["seed"].get().strip()
            base = int(seed_txt) if seed_txt else None
            runs = max(1, min(int(self.params["runs"].get()), 1000))
        except ValueError:
            messagebox.showerror("Error", "Invalid parameters.")
            return

        self.running = True
        self._t0 = time.time()
        self.n_gen = gen
        self._run_target = runs
        self._run_done = 0
        self._all_histories = []
        self._batch_seed = base if base is not None else 0
        self.history = []
        self.inst_cb.config(state="disabled")
        self.btn_run.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_x1.config(state=tk.DISABLED)
        self.btn_x2.config(state=tk.DISABLED)
        self.btn_x3.config(state=tk.DISABLED)
        self.lbl_time.config(text="⏱ Execution time: 0.0 s")
        self.lbl_run.config(text=f"🔁 Run: 0 / {runs}")
        self.log(f"🚀 Starting batch of {runs} run(s) — Instance “{self._cur_label}” ({len(self.cours)} courses) — "
                 f"Pop={pop} Gen={gen} Pc={pc} Pm={pm} "
                 f"Seed_base={base if base is not None else 'random'}")
        work = [dict(c) for c in self.cours]

        self._batch_params = dict(pop=pop, gen=gen, pc=pc, pm=pm, base=base, runs=runs, work=work)

        def worker():
            try:
                for r in range(self._batch_params["runs"]):
                    if self._stop_requested:
                        break
                    seed = None if self._batch_params["base"] is None else self._batch_params["base"] + r
                    if seed is not None:
                        random.seed(seed)
                        try:
                            import numpy as np
                            np.random.seed(seed)
                        except ImportError:
                            pass
                    work_copy = [dict(c) for c in self._batch_params["work"]]
                    self._q.put(("run_start", r + 1, self._batch_params["runs"]))
                    self.moteur = engine.Moteur(
                        work_copy, self._batch_params["pop"], self._batch_params["gen"],
                        self._batch_params["pc"], self._batch_params["pm"],
                        cb_log=lambda m, r=r: self._q.put(("log", f"[run {r+1}] {m}")),
                        cb_progress=lambda g, f, s, r=r: self._q.put(("prog", g, f, s, r + 1)),
                        cb_done=lambda c, st, h, r=r: self._q.put(("run_done", c, st, h, r + 1)))
                    self.moteur.run()
                    if self._stop_requested:
                        break
                self._q.put(("batch_done",))
            except Exception as e:
                self._q.put(("err", str(e)))
        self._stop_requested = False
        self._q = queue.Queue()
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._poll)
        self._tick()

    def _tick(self):
        if self.running:
            self.lbl_time.config(text=f"⏱ Execution time: {time.time() - self._t0:.1f} s")
            self.root.after(200, self._tick)

    def stop(self):
        self._stop_requested = True
        if self.moteur:
            self.moteur.stop()
        self.log("⏹️ Stop requested…")
        self.btn_stop.config(state=tk.DISABLED)

    def on_progress(self, g, f, s):
        r = getattr(self, "_current_run", 1)
        overall = ((r - 1) + g / max(1, self.n_gen)) / max(1, self._run_target) * 100
        self.pb.set(min(100, overall))
        self.status.config(text=f"Run {r}/{self._run_target} | Gen {g}/{self.n_gen} | Fitness {f:.1f} | Stag {s}")
        now = time.time()
        if now - self._last_plot > 1.0 and self.nb.index(self.nb.select()) == 4:
            self._last_plot = now
            self.draw_evo()

    def _poll(self):
        last, n = None, 0
        try:
            while n < 500:
                item = self._q.get_nowait()
                n += 1
                k = item[0]
                if k == "log":
                    self.log(item[1])
                elif k == "run_start":
                    self._current_run = item[1]
                    self.lbl_run.config(text=f"🔁 Run: {item[1]} / {item[2]}")
                    self.log(f"— Run {item[1]}/{item[2]} —")
                elif k == "prog":
                    g, f, s, r = item[1], item[2], item[3], item[4]
                    self.history.append(f)
                    last = (g, f, s)
                elif k == "run_done":
                    cours, stats, hist, r = item[1], item[2], item[3], item[4]
                    if hist:
                        self._all_histories.append(list(hist))
                    if cours and any(c.get("salle") for c in cours):
                        self.cours = cours
                        self.stats = stats
                elif k == "batch_done":
                    if last:
                        self.on_progress(*last)
                    self.on_done()
                    return
                elif k == "err":
                    self.on_error(item[1])
                    return
        except queue.Empty:
            pass
        if last:
            self.on_progress(*last)
        if self.running:
            self.root.after(100, self._poll)

    def on_done(self):
        """Called when the whole batch is finished."""
        self.running = False
        self._sync_back()                              # store the last result in the full data set
        self._inst_cache[self._cur_label] = (self.stats, list(self.history))
        info = self._run_info.setdefault(self._cur_label, {"finals": []})
        info["time"] = time.time() - self._t0
        self.lbl_time.config(text=f"⏱ Execution time: {info['time']:.2f} s")
        # store the final fitness of each run in the batch
        info["finals"] = [h[-1] for h in self._all_histories if h]     # last batch only (no accumulation)
        self.pb.set(0)
        self.inst_cb.config(state="readonly")
        self.btn_run.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_x1.config(state=tk.NORMAL)
        self.btn_x2.config(state=tk.NORMAL)
        self.btn_x3.config(state=tk.NORMAL)
        placed = sum(1 for c in self.cours if c.get("salle"))
        self.status.config(text=f"Done — {placed}/{len(self.cours)} courses assigned")
        n_runs = len(self._all_histories)
        self.log(f"✅ Batch done · {n_runs} run(s) · {placed}/{len(self.cours)} courses assigned · "
                 f"instance “{self._cur_label}” · {info['time']:.2f}s")
        self.lbl_run.config(text=f"🔁 Run: {n_runs} / {self._run_target} ✓")
        self.refresh_all()
        messagebox.showinfo("Success", f"Batch of {n_runs} run(s) completed.\n"
                                        f"{placed}/{len(self.cours)} courses assigned.")

    def on_error(self, msg):
        self.running = False
        self.inst_cb.config(state="readonly")
        self.btn_run.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.lbl_time.config(text="⏱ Execution time: —")
        self.log(f"❌ {msg}")
        messagebox.showerror("Error", msg)

    def refresh_all(self):
        placed_n = sum(1 for c in self.cours if c.get("salle"))
        n_edt = len(set(c.get("num_edt") for c in self.cours))
        self.lbl_inst.config(text=(f"{len(self.cours)} courses · {n_edt} EDT · {placed_n} assigned"
                                   if self.all_cours else "Load a file to choose an instance."),
                             foreground=C_BLUE if self.all_cours else "gray")
        edts = sorted(set((c["num_edt"], c["filiere"]) for c in self.cours if c.get("salle")), key=lambda t: _nat(t[0]))
        self.edt_cb["values"] = [f"{n} — {f}" for n, f in edts]
        if edts and not self.edt_var.get():
            self.edt_cb.current(0)
        fils = sorted(set(c["filiere"] for c in self.cours if c.get("filiere")))
        self.f_fil["values"] = ["All"] + fils
        self._update_room_filter()
        self._dirty = {"occ", "edt", "list", "stats", "evo"}
        t0 = time.time()
        self._refresh_visible()
        dt = time.time() - t0
        if dt > 0.5:
            self.log(f"⏱ Display: {dt:.2f}s")

    TAB_KEYS = ("occ", "edt", "list", "stats", "evo", "rooms")

    def _refresh_visible(self, _e=None):
        try:
            key = self.TAB_KEYS[self.nb.index(self.nb.select())]
        except Exception:
            key = "occ"
        if key not in self._dirty:
            return
        self._dirty.discard(key)
        if key == "occ":
            self.refresh_occ()
        elif key == "edt":
            if self.edt_var.get():
                self.show_edt()
        elif key == "list":
            self.refresh_list()
        elif key == "stats":
            self.refresh_stats()
        elif key == "evo":
            self.draw_evo()

    def export(self, kind):
        if not self.cours:
            return
        wb1, wb2, ts = engine.build_workbooks(self.cours)
        wb = wb1 if kind == "edt" else wb2
        pre = "EDT" if kind == "edt" else "Rooms"
        fp = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"{pre}_{ts}.xlsx",
                                          filetypes=[("Excel", "*.xlsx")])
        if fp:
            wb.save(fp)
            self.log(f"✅ Export: {os.path.basename(fp)}")
            messagebox.showinfo("Success", fp)

    def load_rooms_excel(self):
        """Import rooms from Excel — the file REPLACES the current room list.
        Recognised columns (any order, accents/case ignored):
          Lieu | Type | Numéro | Capacité      -> room name = "Lieu Type Numéro" (e.g. "ENS Amphi 1")
          or  Name/Nom | Capacity/Capacité | Type | Category | Location
        Nothing is changed if the file is not recognised."""
        import unicodedata
        import pandas as pd
        path = filedialog.askopenfilename(title="Rooms file",
                                          filetypes=[("Excel", "*.xlsx *.xlsm *.xls"), ("All", "*.*")])
        if not path:
            return
        try:
            df = pd.read_excel(path)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        def norm(s):                  
            s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
            return re.sub(r"[^a-z0-9]+", "", s)
        aliases = {"loc": {"lieu", "location", "site", "etablissement", "batiment"},
                   "type": {"type", "categorie", "category"},
                   "num": {"numero", "num", "no", "n", "number"},
                   "name": {"name", "nom", "salle", "room"},
                   "cap": {"capacite", "capacity", "places", "nbplaces"}}
        cols = {}
        for c in df.columns:
            h = norm(c)
            for role, al in aliases.items():
                if role not in cols and h in al:
                    cols[role] = c
        if "cap" not in cols or ("name" not in cols and "num" not in cols):
            msg = ("Columns not recognised.\nExpected: Lieu | Type | Numéro | Capacité\n"
                   "(or Name | Capacity).\nFound: " + ", ".join(str(c) for c in df.columns))
            self.log("❌ Rooms file: " + msg.replace("\n", " "))
            messagebox.showerror("Rooms", msg + "\n\nNothing was changed.")
            return

        def val(row, role):
            c = cols.get(role)
            if c is None or pd.isna(row[c]):
                return ""
            v = row[c]
            v = v.item() if hasattr(v, "item") else v
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            return v

        new_rows = []
        for i, row in df.iterrows():
            loc, typ, num, cap = (str(val(row, "loc")).strip(), str(val(row, "type")).strip(),
                                  str(val(row, "num")).strip(), val(row, "cap"))
            name = str(val(row, "name")).strip() or " ".join(p for p in (loc, typ, num) if p)
            if not name and cap == "":
                continue                                             # blank line in the file
            t = typ.lower()
            try:
                capn = float(cap)
            except (TypeError, ValueError):
                capn = 0.0
            if "amphi" in t:
                cat = "amphi"
            elif "moyen" in t:
                cat = "moyenne"
            elif "petit" in t:
                cat = "petite"
            else:                                       
                cat = "moyenne" if capn >= ROOM_MEDIUM_MIN_CAPACITY else "petite"
            new_rows.append((i, dict(name=name, category=cat, capacity=cap, location=loc, features="")))

       
        try:
            old = [str(r.get("name", "")) for r in (engine.rooms_payload() or [])]
        except Exception:
            old = []
        ok, errs = 0, []
        for i, data in new_rows:
            try:
                engine.upsert_room(data)
                ok += 1
            except ValueError as e:
                errs.append(f"row {i + 2}: {e}")
        if ok == 0:                                                 
            self.log("❌ No valid room in the file: the room list was NOT changed.")
            for e in errs[:8]:
                self.log(f"   ⚠ {e}")
            messagebox.showerror("Rooms", "No valid room found in the file.\nThe room list was not changed.")
            return

        new_names = {d["name"].strip().lower() for _, d in new_rows}
        kept = []
        for n in old:
            if n.strip().lower() in new_names:
                continue
            try:
                engine.remove_room(n)
            except Exception:
                kept.append(n)

        self.refresh_rooms()
        _a, _m, _p, allr, _c = self._salles()

        valid, seen, dropped = set(allr), set(), 0
        for c in list(self.all_cours) + list(self.cours):
            if id(c) in seen:
                continue
            seen.add(id(c))
            if c.get("salle") and c["salle"] not in valid:
                c["salle"] = None
                dropped += 1
        self.refresh_occ()
        if dropped:
            self._update_export_buttons()
            self.refresh_all()

        self.log(f"🏢 {ok} room(s) read from {os.path.basename(path)} → {len(allr)} room(s) now in the system")
        if kept:
            self.log(f"   ⚠ {len(kept)} old room(s) could not be removed: {', '.join(kept[:8])}")
        if dropped:
            self.log(f"   ⚠ {dropped} course(s) were assigned to a removed room: run the assignment again.")
        for e in errs[:8]:
            self.log(f"   ⚠ {e}")
        note = f"\n{len(errs)} error(s)." if errs else ""
        if len(allr) != ok:
            note += "\n(Rooms with the same name in the file are merged into one.)"
        messagebox.showinfo("Rooms", f"{ok} room(s) imported.\nRooms in the system: {len(allr)}." + note)

    def export_details(self):
        """Export the full list of assigned courses (colored Excel sheet)."""
        import pandas as pd
        from openpyxl.styles import Alignment, Font, PatternFill
        if not self.cours:
            return
        _a, _m, _p, _all, caps = self._salles()
        rows = [{"EDT": c.get("num_edt", ""), "Program": c.get("filiere", ""), "Day": c.get("jour", ""),
                 "Start": int(c["debut"]), "End": int(c["fin"]), "Module": c.get("module", ""),
                 "Professor": c.get("prof", ""), "Students": int(c.get("effectif", 0)),
                 "Room": c.get("salle") or "", "Capacity": caps.get(c.get("salle"), ""),
                 "Over capacity": "YES" if c.get("salle") and c["effectif"] > caps.get(c["salle"], 0) else "no"}
                for c in self.cours]
        fp = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="Assignment_details.xlsx",
                                          filetypes=[("Excel", "*.xlsx")])
        if not fp:
            return
        try:
            with pd.ExcelWriter(fp, engine="openpyxl") as w:
                pd.DataFrame(rows).to_excel(w, sheet_name="Details", index=False)
                ws = w.sheets["Details"]
                for cell in ws[1]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", start_color="13497B", end_color="13497B")
                    cell.alignment = Alignment(horizontal="center")
                for col in ws.columns:
                    ws.column_dimensions[col[0].column_letter].width = max(12, min(34, max(len(str(c.value or "")) for c in col) + 2))
                red = PatternFill("solid", start_color="FFE0E0", end_color="FFE0E0")
                for r in ws.iter_rows(min_row=2):
                    if r[-1].value == "YES":
                        for c in r:
                            c.fill = red
            self.log(f"✅ Export: {os.path.basename(fp)}")
            messagebox.showinfo("Success", fp)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def logout(self):
        self.root.destroy()
        main()

    def log(self, msg):
        from datetime import datetime
        self.txt_log.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
        self.txt_log.see("end")


def main():
    root = tk.Tk()

    def _show_err(exc, val, tb):
        import traceback
        messagebox.showerror("Error", "".join(traceback.format_exception(exc, val, tb))[-1500:])
    root.report_callback_exception = _show_err
    setup_style(root)
    set_icon(root)
    root.withdraw()
    dlg = LoginDialog(root)
    root.wait_window(dlg.win)
    if not dlg.result:
        root.destroy()
        return
    root.deiconify()
    try:
        App(root, *dlg.result)
    except Exception:
        import traceback
        messagebox.showerror("Startup error", traceback.format_exc()[-1500:])
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
