# -*- coding: utf-8 -*-
"""微信群发 / 定时发送助手 —— 图形界面入口（支持微信 / QQ 双平台）。

运行方式：python main.py
界面风格：现代浅色设计 —— 圆角卡片、渐变横幅、药丸按钮、悬停反馈。
"""
import datetime
import json
import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, scrolledtext, filedialog

import core
import scheduler

# 打包成 exe 后 __file__ 指向临时解压目录，联系人/图标要放 exe 同目录，改用 sys.executable 定位
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACTS_FILE = os.path.join(BASE_DIR, "contacts.json")


def resource_path(rel):
    """资源文件（图标等）路径：打包后从 PyInstaller 解压目录读取。"""
    base = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(base, rel)

STATUS_TEXT = {
    "running": "进行中", "paused": "已暂停", "waiting": "等待定时",
    "done": "完成", "cancelled": "已取消",
}

PLATFORM_NAMES = list(core.PLATFORMS.keys())   # ["微信", "QQ"]

# ---------- 现代配色（参考苹果/谷歌/腾讯的浅色设计语言） ----------
C_BG = "#eef1f6"          # 页面浅灰底（带一点冷调）
C_CARD = "#ffffff"        # 卡片白
C_BORDER = "#e4e7ef"      # 卡片/输入框描边
C_TEXT = "#1a1d24"        # 主文字
C_SUB = "#6b7280"         # 次要文字
C_ACCENT = "#3b82f6"      # 主蓝（谷歌式）
C_DANGER = "#f04438"      # 删除红
C_FIELD_BG = "#f7f8fa"    # 输入框浅底
C_SUCCESS = "#16a34a"     # 成功绿

FONT = "Microsoft YaHei UI"

# 状态颜色（任务列表）
STATUS_COLOR = {
    "running": "#2563eb", "waiting": "#8b8fa3", "paused": "#d97706",
    "done": "#16a34a", "cancelled": "#9aa0ab",
}

# 按钮配色：fill 常态 / grad 渐变底(竖向) / hover 悬停 / press 按下 / fg 文字 / border 描边
BTN_STYLES = {
    "primary":   {"fill": "#3b82f6", "grad": "#2563eb", "hover": "#2f6feb", "press": "#1f5fd6", "fg": "#ffffff"},
    "secondary": {"fill": "#eaf1fe", "hover": "#dce8fe", "press": "#cfe0fd", "fg": "#2f6bff"},
    "ghost":     {"fill": "#ffffff", "hover": "#f3f4f6", "press": "#e9ebef", "fg": "#1a1d24", "border": "#e2e5ec"},
    "danger":    {"fill": "#ffffff", "hover": "#fef2f2", "press": "#fde8e8", "fg": "#f04438", "border": "#f6d9d8"},
    "seg":       {"fill": "#eef0f4", "hover": "#e6e9ef", "press": "#dde2ea", "fg": "#4b5563"},
}

# 平台品牌色（选中态）：微信绿 / QQ 蓝
PLATFORM_BRAND = {
    "微信": ("#07c160", "#05a954"),
    "QQ":   ("#12b7f5", "#0f9ede"),
}


# ---------- 绘制工具 ----------
def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb2hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def _round_pts(x1, y1, x2, y2, r):
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def _draw_rounded(cv, x1, y1, x2, y2, r, **kw):
    return cv.create_polygon(_round_pts(x1, y1, x2, y2, r), smooth=True, **kw)


def _draw_gradient_rounded(cv, x1, y1, x2, y2, r, c1, c2):
    """竖向渐变圆角矩形：逐行画线，两端按圆角收窄，模拟渐变。"""
    r1, g1, b1 = _hex2rgb(c1)
    r2, g2, b2 = _hex2rgb(c2)
    steps = max(12, int(y2 - y1))
    for i in range(steps):
        t = i / (steps - 1)
        y = y1 + (y2 - y1) * t
        col = _rgb2hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)
        inset = 0.0
        if y < y1 + r:
            dy = y1 + r - y
            inset = r - (r * r - dy * dy) ** 0.5
        elif y > y2 - r:
            dy = y - (y2 - r)
            inset = r - (r * r - dy * dy) ** 0.5
        cv.create_line(x1 + inset, y, x2 - inset, y, fill=col)


class RoundedCard(tk.Frame):
    """圆角卡片：Canvas 画圆角白底 + 柔和投影，内容放进 self.body（grid 布局）。"""

    def __init__(self, master, radius=14, padx=18, pady=16, bg=C_BG, card=C_CARD,
                 border=C_BORDER, shadow="#e3e7ef", **kw):
        super().__init__(master, bg=bg, **kw)
        self.radius = radius
        self.card = card
        self.border = border
        self._shadow = shadow
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=card)
        self.body.grid(row=0, column=0, sticky="nsew", padx=padx, pady=pady)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, e=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 6 or h < 6:
            return
        self.cv.delete("all")
        _draw_rounded(self.cv, 2, 4, w - 1, h - 1, self.radius, fill=self._shadow)
        _draw_rounded(self.cv, 0, 0, w - 2, h - 4, self.radius, fill=self.card,
                      outline=self.border, width=1)
        self.cv.lower()


class PillButton(tk.Canvas):
    """圆角药丸按钮：渐变/纯色填充 + 悬停/按下反馈。"""

    def __init__(self, master, text, command, kind="primary", height=34, padx=18,
                 font=None, bg=C_CARD, **kw):
        font = font or (FONT, 10)
        w = tkfont.Font(font=font).measure(text) + padx * 2
        super().__init__(master, width=w, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2", **kw)
        self.text = text
        self.command = command
        self.kind = kind
        self.font = font
        self.height = height
        self.radius = height // 2
        self._hover = False
        self._pressed = False
        self._selected = False
        self._brand = None
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def _on_press(self, e):
        self._pressed = True
        self._draw()

    def _on_release(self, e):
        was = self._pressed
        self._pressed = False
        self._draw()
        if was and self.command:
            self.command()

    def set_selected(self, sel, brand=None):
        self._selected = sel
        self._brand = brand
        self._draw()

    def _colors(self):
        if self._selected and self._brand:
            return self._brand[0], self._brand[1], "#ffffff", ""
        s = BTN_STYLES[self.kind]
        top = s["fill"]
        bottom = s.get("grad", s["fill"])
        fg = s["fg"]
        border = s.get("border", "")
        if self._pressed:
            top = bottom = s.get("press", s["fill"])
        elif self._hover:
            top = bottom = s.get("hover", s["fill"])
        return top, bottom, fg, border

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            w = int(self["width"])
        top, bottom, fg, border = self._colors()
        if top != bottom:
            _draw_gradient_rounded(self, 0, 0, w, self.height, self.radius, top, bottom)
        else:
            _draw_rounded(self, 0, 0, w, self.height, self.radius, fill=top)
        if border:
            _draw_rounded(self, 0, 0, w, self.height, self.radius, fill="", outline=border, width=1)
        self.create_text(w / 2, self.height / 2, text=self.text, fill=fg, font=self.font)


class WheelPicker(tk.Frame):
    """单列滚轮选择器（手机闹钟式）：中间值高亮，滚轮/点击/箭头切换，循环滚动。"""

    ROW_H = 28            # 每行高度
    VISIBLE = 5           # 可见行数（当前值居中）

    def __init__(self, master, values, index=0, bg=C_BG, width=64, **kw):
        super().__init__(master, bg=bg, **kw)
        self.values = list(values)
        self.index = index % len(self.values)
        self.bg = bg
        self.width = width
        self.height = self.VISIBLE * self.ROW_H

        self._up = tk.Label(self, text="▲", font=(FONT, 9), fg=C_SUB, bg=bg, cursor="hand2")
        self._up.pack(fill="x")
        self._up.bind("<Button-1>", lambda e: self._scroll(-1))

        self.cv = tk.Canvas(self, width=width, height=self.height, bg=C_CARD,
                            highlightthickness=0, bd=0, cursor="hand2")
        self.cv.pack()

        self._down = tk.Label(self, text="▼", font=(FONT, 9), fg=C_SUB, bg=bg, cursor="hand2")
        self._down.pack(fill="x")
        self._down.bind("<Button-1>", lambda e: self._scroll(1))

        for w in (self, self._up, self._down, self.cv):
            w.bind("<MouseWheel>", self._on_wheel)
        self.cv.bind("<Button-1>", self._on_click)

        self._draw()

    def _on_wheel(self, e):
        step = -e.delta // 120
        if step == 0:
            step = -1 if e.delta > 0 else 1
        self._scroll(step)

    def _on_click(self, e):
        self._scroll(-1 if e.y < self.height / 2 else 1)

    def _scroll(self, delta):
        self.index = (self.index + delta) % len(self.values)
        self._draw()

    def get(self):
        return self.values[self.index]

    def _draw(self):
        self.cv.delete("all")
        n = len(self.values)
        cx = self.width / 2
        half = self.VISIBLE // 2
        for row in range(self.VISIBLE):
            offset = row - half                 # -2..2
            idx = (self.index + offset) % n
            y = row * self.ROW_H + self.ROW_H / 2
            if offset == 0:
                top = row * self.ROW_H
                self.cv.create_rectangle(0, top, self.width, top + self.ROW_H, fill="#eaf1fe", outline="")
                self.cv.create_line(0, top, self.width, top, fill=C_BORDER)
                self.cv.create_line(0, top + self.ROW_H, self.width, top + self.ROW_H, fill=C_BORDER)
                fg, font = C_TEXT, (FONT, 14, "bold")
            elif abs(offset) == 1:
                fg, font = C_SUB, (FONT, 11)
            else:
                fg, font = "#b0b5c0", (FONT, 9)
            self.cv.create_text(cx, y, text=self.values[idx], fill=fg, font=font)


def load_contacts():
    """读取通讯录，返回 {"微信": [...], "QQ": [...]}。兼容旧的纯列表格式。"""
    empty = {p: [] for p in PLATFORM_NAMES}
    try:
        with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return empty
    if isinstance(data, dict):
        result = {p: [] for p in PLATFORM_NAMES}
        for p in PLATFORM_NAMES:
            raw = data.get(p, [])
            if isinstance(raw, list):
                result[p] = [x for x in raw if isinstance(x, str)]
        return result
    if isinstance(data, list):   # 旧格式：整体当作微信通讯录
        empty["微信"] = [x for x in data if isinstance(x, str)]
    return empty


def save_contacts(all_contacts):
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_contacts, f, ensure_ascii=False, indent=2)


class Task:
    _next_id = 1

    def __init__(self, names, content, platform="微信", hour=None, minute=None, interval=1.5,
                 month=None, day=None, file=None):
        self.id = Task._next_id
        Task._next_id += 1
        self.names = list(names)
        self.content = content
        self.file = file
        self.platform = platform
        self.hour = hour
        self.minute = minute
        self.month = month
        self.day = day
        self.interval = interval
        self.controller = core.SendController()
        self.status = "waiting" if hour is not None else "running"
        self.done = 0
        self.total = len(names)
        self.ok = 0
        self.failed = 0
        self.thread = None

    def label(self):
        st = STATUS_TEXT.get(self.status, self.status)
        if self.file:
            preview = "[文件] " + os.path.basename(self.file)
        else:
            preview = self.content.replace("\n", " ")[:14]
        timeinfo = ""
        if self.hour is not None:
            if self.month is not None:
                timeinfo = f" @ {self.month:02d}-{self.day:02d} {self.hour:02d}:{self.minute:02d}"
            else:
                timeinfo = f" @ {self.hour:02d}:{self.minute:02d}"
        return f"任务{self.id} [{self.platform}·{st}] {self.done}/{self.total}{timeinfo} - {preview}"


class App:
    def __init__(self, root):
        self.root = root
        root.title("信息发送助手")
        root.geometry("980x780")
        root.minsize(920, 700)
        root.configure(bg=C_BG)
        self.all_contacts = load_contacts()
        self.current_platform = PLATFORM_NAMES[0]   # 默认微信
        self.tasks = {}
        self._build_ui()
        self._refresh_contacts()

    # ---------- 样式 / 控件工具 ----------
    def _f(self, size, weight="normal"):
        return (FONT, size, weight)

    def _card(self, parent, padx=18, pady=16):
        """白色圆角卡片（Canvas 画圆角 + 柔和投影）。"""
        return RoundedCard(parent, padx=padx, pady=pady)

    def _label(self, parent, text, size=10, color=C_SUB, weight="normal", **kw):
        return tk.Label(parent, text=text, font=self._f(size, weight), fg=color, bg=C_CARD, **kw)

    def _card_title(self, card, text, sub=None):
        """卡片标题：左侧蓝色竖条 + 标题 + 右侧可选副标题。"""
        bar = tk.Frame(card.body, bg=C_CARD)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        dot = tk.Frame(bar, bg=C_ACCENT, width=4, height=16)
        dot.pack_propagate(False)
        dot.pack(side="left", padx=(0, 9))
        tk.Label(bar, text=text, font=self._f(13, "bold"), fg=C_TEXT, bg=C_CARD).pack(side="left")
        if sub:
            tk.Label(bar, text=sub, font=self._f(9), fg=C_SUB, bg=C_CARD).pack(side="right")
        return bar

    def _button(self, parent, text, command, kind="primary", width=None, **kw):
        return PillButton(parent, text=text, command=command, kind=kind, **kw)

    def _entry(self, parent, width=None, **kw):
        return tk.Entry(parent, font=self._f(11), relief="flat", bd=0, highlightthickness=1,
                        highlightbackground=C_BORDER, highlightcolor=C_ACCENT,
                        bg=C_FIELD_BG, fg=C_TEXT, insertbackground=C_TEXT, width=width, **kw)

    # ---------- 界面 ----------
    def _build_ui(self):
        root = self.root
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(2, weight=1, minsize=260)

        self._build_header()
        self._build_content_card()
        self._build_left_card()
        self._build_right_card()
        self._build_log_card()

    def _build_header(self):
        """顶部渐变横幅：应用名 + 副标题 + 版本号。"""
        h = tk.Frame(self.root, bg=C_BG)
        h.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(16, 8))
        cv = tk.Canvas(h, bg=C_BG, height=86, highlightthickness=0, bd=0)
        cv.pack(fill="x")

        def draw(e=None):
            w = cv.winfo_width()
            if w < 10:
                return
            cv.delete("all")
            _draw_gradient_rounded(cv, 0, 2, w, 84, 16, "#3b82f6", "#6a5cff")
            cv.create_text(26, 30, anchor="w", text="信息发送助手",
                           fill="#ffffff", font=(FONT, 19, "bold"))
            cv.create_text(26, 56, anchor="w", text="微信 / QQ · 批量群发 · 定时发送 · 文件消息",
                           fill="#e8ecff", font=(FONT, 10))
            cv.create_text(w - 26, 44, anchor="e", text="v1.5",
                           fill="#ffffff", font=(FONT, 12, "bold"))

        cv.bind("<Configure>", draw)
        draw()

    def _refresh_platform_buttons(self):
        for p, b in self.platform_btns.items():
            selected = (p == self.current_platform)
            b.set_selected(selected, PLATFORM_BRAND.get(p))

    def _build_content_card(self):
        card = self._card(self.root)
        card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=24, pady=8)
        card.body.grid_columnconfigure(0, weight=1)

        # 标题行：左侧标题 + 右侧平台切换
        head = tk.Frame(card.body, bg=C_CARD)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        dot = tk.Frame(head, bg=C_ACCENT, width=4, height=16)
        dot.pack_propagate(False)
        dot.pack(side="left", padx=(0, 9))
        tk.Label(head, text="📋 发送内容", font=self._f(13, "bold"), fg=C_TEXT, bg=C_CARD).pack(side="left")

        seg = tk.Frame(head, bg="#eef0f4", padx=3, pady=3)
        seg.pack(side="right")
        self.platform_btns = {}
        for p in PLATFORM_NAMES:
            b = PillButton(seg, text=p, command=lambda name=p: self._set_platform(name),
                           kind="seg", bg="#eef0f4", height=28, padx=16)
            b.pack(side="left")
            self.platform_btns[p] = b
        self._refresh_platform_buttons()

        self.content_text = tk.Text(card.body, height=2, font=self._f(11), relief="flat", bd=0,
                                    highlightthickness=1, highlightbackground=C_BORDER,
                                    highlightcolor=C_ACCENT, bg=C_FIELD_BG, fg=C_TEXT,
                                    insertbackground=C_TEXT, padx=10, pady=8, wrap="word")
        self.content_text.grid(row=1, column=0, sticky="ew")

        rowf = tk.Frame(card.body, bg=C_CARD)
        rowf.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self._label(rowf, "📁 文件", size=10).pack(side="left")
        self.file_entry = self._entry(rowf)
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(6, 8))
        self._button(rowf, "选择文件", self.pick_file, "secondary").pack(side="left")
        self._button(rowf, "清除", self.clear_file, "ghost").pack(side="left", padx=(6, 0))

        row2 = tk.Frame(card.body, bg=C_CARD)
        row2.grid(row=3, column=0, sticky="ew", pady=(12, 0))

        self._label(row2, "📅 日期(可选)", size=10).pack(side="left")
        self.date_entry = self._entry(row2, width=9)
        self.date_entry.pack(side="left", padx=(6, 4))
        self.date_entry.config(cursor="hand2")
        self.date_entry.bind("<Button-1>", lambda e: self._pick_date())
        self._button(row2, "选择", self._pick_date, "secondary", height=28, padx=12).pack(side="left")
        self._label(row2, "🕐 定时", size=10).pack(side="left", padx=(12, 0))
        self.time_entry = self._entry(row2, width=9)
        self.time_entry.pack(side="left", padx=(6, 4))
        self.time_entry.config(cursor="hand2")
        self.time_entry.bind("<Button-1>", lambda e: self._pick_time())
        self._button(row2, "选择", self._pick_time, "secondary", height=28, padx=12).pack(side="left")
        self._label(row2, "⏱ 间隔(秒)", size=10).pack(side="left", padx=(12, 0))
        self.interval_entry = self._entry(row2, width=5)
        self.interval_entry.insert(0, "1.5")
        self.interval_entry.pack(side="left", padx=(6, 0))

        self._button(row2, "立即发送", self.send_now, "primary").pack(side="right")
        self._button(row2, "定时发送", self.send_later, "secondary").pack(side="right", padx=(0, 8))

    def _build_left_card(self):
        card = self._card(self.root)
        card.grid(row=2, column=0, sticky="nsew", padx=(24, 8), pady=8)
        card.body.grid_rowconfigure(1, weight=1)
        card.body.grid_columnconfigure(0, weight=1)

        self._card_title(card, "👥 通讯录", "Ctrl + 点击 多选")

        self.listbox = tk.Listbox(card.body, selectmode=tk.EXTENDED, exportselection=False,
                                  font=self._f(11), relief="flat", bd=0, highlightthickness=0,
                                  bg=C_FIELD_BG, fg=C_TEXT, selectbackground=C_ACCENT,
                                  selectforeground="#ffffff", activestyle="none")
        self.listbox.grid(row=1, column=0, sticky="nsew")

        addf = tk.Frame(card.body, bg=C_CARD)
        addf.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        addf.grid_columnconfigure(0, weight=1)
        self.entry_new = self._entry(addf)
        self.entry_new.grid(row=0, column=0, sticky="ew")
        self.entry_new.bind("<Return>", lambda e: self.add_contact())
        self._button(addf, "添加", self.add_contact, "secondary").grid(row=0, column=1, padx=(8, 0))

        self._button(card.body, "删除选中联系人", self.del_contact, "danger").grid(
            row=3, column=0, sticky="ew", pady=(10, 0))

    def _build_right_card(self):
        card = self._card(self.root)
        card.grid(row=2, column=1, sticky="nsew", padx=(8, 24), pady=8)
        card.body.grid_rowconfigure(1, weight=1)
        card.body.grid_columnconfigure(0, weight=1)

        self._card_title(card, "📦 任务", "选中后操作")

        self.task_listbox = tk.Listbox(card.body, exportselection=False, font=self._f(11),
                                       relief="flat", bd=0, highlightthickness=0,
                                       bg=C_FIELD_BG, fg=C_TEXT, selectbackground=C_ACCENT,
                                       selectforeground="#ffffff", activestyle="none")
        self.task_listbox.grid(row=1, column=0, sticky="nsew")

        btns = tk.Frame(card.body, bg=C_CARD)
        btns.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self._button(btns, "暂停/继续", self.toggle_pause, "ghost").pack(side="left")
        self._button(btns, "载入编辑", self.load_edit, "ghost").pack(side="left", padx=(8, 0))
        self._button(btns, "删除任务", self.delete_task, "danger").pack(side="left", padx=(8, 0))

    def _build_log_card(self):
        card = self._card(self.root, pady=12)
        card.grid(row=3, column=0, columnspan=2, sticky="ew", padx=24, pady=(8, 18))
        card.body.grid_columnconfigure(0, weight=1)

        self._card_title(card, "📜 日志")
        self.log_text = scrolledtext.ScrolledText(
            card.body, height=3, font=self._f(10), relief="flat", bd=0,
            highlightthickness=0, bg=C_FIELD_BG, fg=C_TEXT, padx=10, pady=8, wrap="word")
        self.log_text.grid(row=1, column=0, sticky="ew")
        self.log_text.configure(state="disabled")

    # ---------- 平台切换 ----------
    def _set_platform(self, platform):
        if platform == self.current_platform:
            return
        self.current_platform = platform
        self._refresh_platform_buttons()
        self._refresh_contacts()
        self.log(f"已切换到「{self.current_platform}」平台")

    @property
    def contacts(self):
        return self.all_contacts[self.current_platform]

    # ---------- 通讯录 ----------
    def _refresh_contacts(self):
        self.listbox.delete(0, tk.END)
        for name in self.contacts:
            self.listbox.insert(tk.END, name)

    def add_contact(self):
        name = self.entry_new.get().strip()
        if not name:
            return
        if name in self.contacts:
            messagebox.showinfo("提示", f"「{name}」已在通讯录中")
            return
        self.contacts.append(name)
        save_contacts(self.all_contacts)
        self._refresh_contacts()
        self.entry_new.delete(0, tk.END)

    def del_contact(self):
        selected = list(self.listbox.curselection())
        if not selected:
            return
        for idx in reversed(selected):
            del self.contacts[idx]
        save_contacts(self.all_contacts)
        self._refresh_contacts()

    # ---------- 任务 ----------
    def _refresh_tasks(self):
        self.task_listbox.delete(0, tk.END)
        for i, tid in enumerate(sorted(self.tasks)):
            t = self.tasks[tid]
            self.task_listbox.insert(tk.END, t.label())
            self.task_listbox.itemconfig(i, fg=STATUS_COLOR.get(t.status, C_TEXT))

    def _selected_task(self):
        sel = self.task_listbox.curselection()
        if not sel:
            return None
        ids = sorted(self.tasks)
        idx = sel[0]
        if idx >= len(ids):
            return None
        return self.tasks[ids[idx]]

    def log(self, msg):
        def _update():
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")
        self.root.after(0, _update)

    def _get_selected_names(self):
        return [self.contacts[i] for i in self.listbox.curselection()]

    def _get_content(self):
        return self.content_text.get("1.0", "end").rstrip("\n")

    def pick_file(self):
        path = filedialog.askopenfilename(title="选择要发送的文件")
        if path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, path)

    def clear_file(self):
        self.file_entry.delete(0, tk.END)

    def _pick_date(self):
        """弹出日历窗口选日期，选中后填回 date_entry（格式 MM-DD）。"""
        import calendar as _cal
        now = datetime.datetime.now()
        y, m = now.year, now.month

        # 若已选过月份，定位到该月；否则默认当前月
        cur = self.date_entry.get().strip()
        if cur:
            try:
                parts = [int(x) for x in cur.replace("/", "-").split("-") if x.strip()]
                if len(parts) == 2:
                    m = parts[0]
            except Exception:
                pass

        win = tk.Toplevel(self.root)
        win.title("选择日期")
        win.configure(bg=C_BG)
        win.resizable(False, False)
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass

        bar = tk.Frame(win, bg=C_BG)
        bar.pack(padx=12, pady=(12, 4))
        prev = PillButton(bar, text="‹ 上月", command=None, kind="ghost", height=26, padx=10, bg=C_BG)
        prev.pack(side="left")
        month_label = tk.Label(bar, text="", font=self._f(12, "bold"), fg=C_TEXT, bg=C_BG, width=12)
        month_label.pack(side="left", padx=10)
        nxt = PillButton(bar, text="下月 ›", command=None, kind="ghost", height=26, padx=10, bg=C_BG)
        nxt.pack(side="left")

        week_row = tk.Frame(win, bg=C_BG)
        week_row.pack(padx=12, pady=(4, 0))
        for i, wd in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            tk.Label(week_row, text=wd, font=self._f(9), fg=C_SUB, bg=C_BG, width=3).grid(row=0, column=i, padx=2)

        grid = tk.Frame(win, bg=C_BG)
        grid.pack(padx=12, pady=4)

        def choose(d):
            self.date_entry.delete(0, tk.END)
            self.date_entry.insert(0, f"{m:02d}-{d:02d}")
            win.destroy()

        def render():
            for wdg in grid.winfo_children():
                wdg.destroy()
            month_label.config(text=f"{y} 年 {m} 月")
            for r, week in enumerate(_cal.monthcalendar(y, m)):
                for c, day in enumerate(week):
                    if day == 0:
                        tk.Label(grid, text="", bg=C_BG, width=3).grid(row=r, column=c, padx=2, pady=2)
                    else:
                        tk.Button(grid, text=str(day), font=self._f(10), relief="flat", bd=0,
                                  bg=C_CARD, fg=C_TEXT, activebackground=C_ACCENT,
                                  activeforeground="#ffffff", cursor="hand2", width=3,
                                  highlightthickness=1, highlightbackground=C_BORDER,
                                  command=lambda d=day: choose(d)).grid(row=r, column=c, padx=2, pady=2)

        def go(delta):
            nonlocal y, m
            m += delta
            if m < 1:
                y -= 1
                m = 12
            elif m > 12:
                y += 1
                m = 1
            render()

        prev.command = lambda: go(-1)
        nxt.command = lambda: go(1)

        footer = tk.Frame(win, bg=C_BG)
        footer.pack(padx=12, pady=(4, 12), fill="x")
        PillButton(footer, text="清除日期",
                   command=lambda: (self.date_entry.delete(0, tk.END), win.destroy()),
                   kind="danger", height=26, padx=12).pack(side="right")

        render()

    def _pick_time(self):
        """弹出手机闹钟式滚轮选时间，填回 time_entry（格式 HH:MM）。"""
        hh, mm = 8, 0
        cur = self.time_entry.get().strip()
        if cur:
            try:
                h, mi = cur.split(":")
                hh, mm = int(h), int(mi)
                if not (0 <= hh <= 23 and 0 <= mm <= 59):
                    raise ValueError
            except Exception:
                hh, mm = 8, 0

        win = tk.Toplevel(self.root)
        win.title("选择时间")
        win.configure(bg=C_BG)
        win.resizable(False, False)
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass

        tk.Label(win, text="选择时间", font=self._f(14, "bold"), fg=C_TEXT, bg=C_BG).pack(pady=(14, 6))

        row = tk.Frame(win, bg=C_BG)
        row.pack(padx=20, pady=4)
        hours = WheelPicker(row, [f"{i:02d}" for i in range(24)], index=hh)
        hours.pack(side="left")
        tk.Label(row, text=":", font=self._f(18, "bold"), fg=C_TEXT, bg=C_BG).pack(side="left", padx=10)
        minutes = WheelPicker(row, [f"{i:02d}" for i in range(60)], index=mm)
        minutes.pack(side="left")

        footer = tk.Frame(win, bg=C_BG)
        footer.pack(padx=20, pady=(6, 14), fill="x")

        def confirm():
            self.time_entry.delete(0, tk.END)
            self.time_entry.insert(0, f"{hours.get()}:{minutes.get()}")
            win.destroy()

        PillButton(footer, text="确定", command=confirm,
                   kind="primary", height=30, padx=18).pack(side="right")
        PillButton(footer, text="清除时间",
                   command=lambda: (self.time_entry.delete(0, tk.END), win.destroy()),
                   kind="danger", height=30, padx=14).pack(side="right", padx=(8, 0))

    def _get_interval(self):
        try:
            v = float(self.interval_entry.get().strip())
            return v if v >= 0.5 else 1.5
        except Exception:
            return 1.5

    def _create_task(self, names, content, hour, minute, interval, month=None, day=None, file_path=None):
        task = Task(names, content, platform=self.current_platform,
                    hour=hour, minute=minute, interval=interval, month=month, day=day, file=file_path)
        self.tasks[task.id] = task
        self._refresh_tasks()
        self.log("=" * 40)
        if hour is not None:
            if month is not None:
                when = f"定时 {month:02d}-{day:02d} {hour:02d}:{minute:02d}"
            else:
                when = f"定时 {hour:02d}:{minute:02d}（若已过则顺延到明天）"
        else:
            when = "立即"
        self.log(f"任务{task.id} 已创建：[{self.current_platform}] {len(names)} 人，{when}，间隔 {interval} 秒")
        return task

    def _run_task(self, task):
        """在后台线程执行发送。"""
        def progress(done, total, ok, failed):
            task.done = done
            task.ok = ok
            task.failed = failed
            self.root.after(0, self._refresh_tasks)

        def worker():
            ok, failed = core.send_many(
                task.names, task.content, interval=task.interval,
                log=self.log, controller=task.controller, on_progress=progress,
                platform=task.platform, file_path=task.file)
            task.status = "cancelled" if task.controller.cancelled else "done"
            self.root.after(0, self._refresh_tasks)
            self.log(f"任务{task.id} 结束：成功 {ok} 条，失败 {len(failed)} 条")
            if failed:
                self.log("失败名单（请手动补发）：" + "、".join(failed))

        task.thread = threading.Thread(target=worker, daemon=True)
        task.thread.start()

    def _start_task(self, task):
        if task.hour is not None:
            def wait_then_run():
                if scheduler.wait_until(task.hour, task.minute, controller=task.controller,
                                        month=task.month, day=task.day):
                    if task.controller.cancelled:
                        return
                    task.status = "running"
                    self.root.after(0, self._refresh_tasks)
                    self.log(f"任务{task.id} 到点，开始发送...")
                    self._run_task(task)
                else:
                    task.status = "cancelled"
                    self.root.after(0, self._refresh_tasks)
            task.thread = threading.Thread(target=wait_then_run, daemon=True)
            task.thread.start()
        else:
            self._run_task(task)

    def toggle_pause(self):
        task = self._selected_task()
        if not task:
            messagebox.showinfo("提示", "请先在任务列表选中一个任务")
            return
        if task.status == "paused":
            task.controller.resume()
            task.status = "running" if task.hour is None or task.done else "waiting"
            self.log(f"任务{task.id} 已继续")
        elif task.status in ("running", "waiting"):
            task.controller.pause()
            task.status = "paused"
            self.log(f"任务{task.id} 已暂停")
        else:
            messagebox.showinfo("提示", "该任务已结束，无法暂停")
            return
        self._refresh_tasks()

    def delete_task(self):
        task = self._selected_task()
        if not task:
            messagebox.showinfo("提示", "请先在任务列表选中一个任务")
            return
        task.controller.cancel()
        del self.tasks[task.id]
        self._refresh_tasks()
        self.log(f"任务{task.id} 已删除")

    def load_edit(self):
        task = self._selected_task()
        if not task:
            messagebox.showinfo("提示", "请先在任务列表选中一个任务")
            return
        # 切到该任务所在平台
        if task.platform in PLATFORM_NAMES and task.platform != self.current_platform:
            self._set_platform(task.platform)
        # 内容
        self.content_text.delete("1.0", "end")
        self.content_text.insert("1.0", task.content)
        # 名单：勾选通讯录里能匹配到的
        self.listbox.selection_clear(0, tk.END)
        for name in task.names:
            if name in self.contacts:
                self.listbox.selection_set(self.contacts.index(name))
        # 时间 + 间隔
        self.time_entry.delete(0, tk.END)
        if task.hour is not None:
            self.time_entry.insert(0, f"{task.hour:02d}:{task.minute:02d}")
        self.date_entry.delete(0, tk.END)
        if task.month is not None:
            self.date_entry.insert(0, f"{task.month:02d}-{task.day:02d}")
        self.interval_entry.delete(0, tk.END)
        self.interval_entry.insert(0, str(task.interval))
        # 文件
        self.file_entry.delete(0, tk.END)
        if task.file:
            self.file_entry.insert(0, task.file)
        # 移除旧任务
        task.controller.cancel()
        del self.tasks[task.id]
        self._refresh_tasks()
        self.log(f"任务{task.id} 已载入编辑区，修改后重新发送")

    # ---------- 发送入口 ----------
    def _collect(self, require_time):
        names = self._get_selected_names()
        content = self._get_content()
        file_path = self.file_entry.get().strip() or None
        if not names:
            messagebox.showwarning("提示", "请先在左侧勾选要发的人")
            return None
        if not content and not file_path:
            messagebox.showwarning("提示", "请填写发送内容或选择文件")
            return None
        interval = self._get_interval()
        hour = minute = month = day = None
        t = self.time_entry.get().strip()
        if require_time or t:
            if not t:
                messagebox.showwarning("提示", "定时发送需要填写时间（HH:MM）")
                return None
            try:
                h, m = t.split(":")
                hour, minute = int(h), int(m)
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError
            except Exception:
                messagebox.showwarning("提示", "时间格式错误，请用 HH:MM，例如 23:30")
                return None
        # 日期（可选）：MM-DD，不填则默认「最近的未来时刻」
        d = self.date_entry.get().strip()
        if d:
            if hour is None:
                messagebox.showwarning("提示", "填了日期就必须同时填时间（HH:MM）")
                return None
            try:
                s = d.replace("/", "-").replace("月", "-").replace("日", "")
                parts = [int(x) for x in s.split("-") if x.strip() != ""]
                if len(parts) != 2:
                    raise ValueError
                month, day = parts
                datetime.date(2024, month, day)   # 2024 闰年，能校验 2-29 及所有无效月日
            except Exception:
                messagebox.showwarning("提示", "日期格式错误，请用 MM-DD，例如 08-16")
                return None
        return names, content, hour, minute, interval, month, day, file_path

    def send_now(self):
        r = self._collect(require_time=False)
        if not r:
            return
        names, content, hour, minute, interval, month, day, file_path = r
        task = self._create_task(names, content, hour, minute, interval, month, day, file_path)
        self._start_task(task)

    def send_later(self):
        r = self._collect(require_time=True)
        if not r:
            return
        names, content, hour, minute, interval, month, day, file_path = r
        task = self._create_task(names, content, hour, minute, interval, month, day, file_path)
        self._start_task(task)
        self.log("⚠ 到点前请保持程序运行、电脑不睡眠、不合盖、微信/QQ 登录在线")


def main():
    root = tk.Tk()
    icon = resource_path("app_icon.ico")
    if os.path.exists(icon):
        try:
            root.iconbitmap(icon)
        except Exception:
            pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
