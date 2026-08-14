# -*- coding: utf-8 -*-
"""微信群发 / 定时发送助手 —— 图形界面入口（支持微信 / QQ 双平台）。

运行方式：python main.py
界面风格：仿苹果官网 —— 浅灰底、白色卡片、苹果蓝强调色、大量留白。
"""
import json
import os
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

import core
import scheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACTS_FILE = os.path.join(BASE_DIR, "contacts.json")

STATUS_TEXT = {
    "running": "进行中", "paused": "已暂停", "waiting": "等待定时",
    "done": "完成", "cancelled": "已取消",
}

PLATFORM_NAMES = list(core.PLATFORMS.keys())   # ["微信", "QQ"]

# ---------- 苹果风配色 ----------
C_BG = "#f5f5f7"          # 页面浅灰底
C_CARD = "#ffffff"        # 卡片白
C_BORDER = "#e8e8ed"      # 卡片描边
C_TEXT = "#1d1d1f"        # 主文字
C_SUB = "#86868b"         # 次要文字
C_ACCENT = "#0071e3"      # 苹果蓝
C_ACCENT_HOVER = "#0077ed"
C_DANGER = "#ff3b30"      # 删除红
C_DANGER_BG = "#fff0ef"
C_FIELD_BG = "#fbfbfd"    # 输入框浅底

FONT = "Microsoft YaHei UI"


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

    def __init__(self, names, content, platform="微信", hour=None, minute=None, interval=1.5):
        self.id = Task._next_id
        Task._next_id += 1
        self.names = list(names)
        self.content = content
        self.platform = platform
        self.hour = hour
        self.minute = minute
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
        preview = self.content.replace("\n", " ")[:14]
        timeinfo = f" @ {self.hour:02d}:{self.minute:02d}" if self.hour is not None else ""
        return f"任务{self.id} [{self.platform}·{st}] {self.done}/{self.total}{timeinfo} - {preview}"


class App:
    def __init__(self, root):
        self.root = root
        root.title("群发助手")
        root.geometry("980x720")
        root.minsize(900, 640)
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
        """白色圆角卡片容器（tkinter 无圆角，用白底 + 极淡描边模拟）。"""
        return tk.Frame(parent, bg=C_CARD, highlightbackground=C_BORDER,
                        highlightthickness=1, padx=padx, pady=pady)

    def _label(self, parent, text, size=10, color=C_SUB, weight="normal", **kw):
        return tk.Label(parent, text=text, font=self._f(size, weight), fg=color, bg=C_CARD, **kw)

    def _card_title(self, card, text, sub=None):
        """卡片标题：左侧蓝色竖条 + 标题 + 右侧可选副标题。"""
        bar = tk.Frame(card, bg=C_CARD)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        dot = tk.Frame(bar, bg=C_ACCENT, width=3, height=14)
        dot.pack_propagate(False)
        dot.pack(side="left", padx=(0, 8))
        tk.Label(bar, text=text, font=self._f(12, "bold"), fg=C_TEXT, bg=C_CARD).pack(side="left")
        if sub:
            tk.Label(bar, text=sub, font=self._f(9), fg=C_SUB, bg=C_CARD).pack(side="right")
        return bar

    def _button(self, parent, text, command, kind="primary", width=None):
        styles = {
            "primary":   dict(bg=C_ACCENT, fg="#ffffff", activebackground=C_ACCENT_HOVER, activeforeground="#ffffff"),
            "secondary": dict(bg="#e8f1fc", fg=C_ACCENT, activebackground="#d8e9fb", activeforeground=C_ACCENT),
            "ghost":     dict(bg=C_CARD, fg=C_TEXT, activebackground=C_BG, activeforeground=C_TEXT),
            "danger":    dict(bg=C_CARD, fg=C_DANGER, activebackground=C_DANGER_BG, activeforeground=C_DANGER),
        }
        s = styles[kind]
        return tk.Button(parent, text=text, command=command, font=self._f(10),
                         relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                         takefocus=0, padx=16, pady=7, width=width, **s)

    def _entry(self, parent, width=None, **kw):
        return tk.Entry(parent, font=self._f(11), relief="flat", bd=0, highlightthickness=1,
                        highlightbackground=C_BORDER, highlightcolor=C_ACCENT,
                        bg=C_FIELD_BG, fg=C_TEXT, insertbackground=C_TEXT, width=width, **kw)

    # ---------- 界面 ----------
    def _build_ui(self):
        root = self.root
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(1, weight=1, minsize=260)

        self._build_content_card()
        self._build_left_card()
        self._build_right_card()
        self._build_log_card()

    def _refresh_platform_buttons(self):
        for p, b in self.platform_btns.items():
            selected = (p == self.current_platform)
            b.configure(bg=C_ACCENT if selected else "#e8e8ed",
                        fg="#ffffff" if selected else C_TEXT,
                        activebackground=C_ACCENT if selected else "#dcdce1",
                        activeforeground="#ffffff" if selected else C_TEXT)

    def _build_content_card(self):
        card = self._card(self.root)
        card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(16, 8))
        card.grid_columnconfigure(0, weight=1)

        # 标题行：左侧标题 + 右侧平台切换
        head = tk.Frame(card, bg=C_CARD)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        dot = tk.Frame(head, bg=C_ACCENT, width=3, height=14)
        dot.pack_propagate(False)
        dot.pack(side="left", padx=(0, 8))
        tk.Label(head, text="发送内容", font=self._f(12, "bold"), fg=C_TEXT, bg=C_CARD).pack(side="left")

        seg = tk.Frame(head, bg="#e8e8ed", padx=3, pady=3)
        seg.pack(side="right")
        self.platform_btns = {}
        for p in PLATFORM_NAMES:
            b = tk.Button(seg, text=p, font=self._f(10), relief="flat", bd=0,
                          highlightthickness=0, cursor="hand2", takefocus=0, padx=18, pady=4,
                          command=lambda name=p: self._set_platform(name))
            b.pack(side="left")
            self.platform_btns[p] = b
        self._refresh_platform_buttons()

        self.content_text = tk.Text(card, height=2, font=self._f(11), relief="flat", bd=0,
                                    highlightthickness=1, highlightbackground=C_BORDER,
                                    highlightcolor=C_ACCENT, bg=C_FIELD_BG, fg=C_TEXT,
                                    insertbackground=C_TEXT, padx=10, pady=8, wrap="word")
        self.content_text.grid(row=1, column=0, sticky="ew")

        row2 = tk.Frame(card, bg=C_CARD)
        row2.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self._label(row2, "定时 HH:MM", size=10).pack(side="left")
        self.time_entry = self._entry(row2, width=7)
        self.time_entry.pack(side="left", padx=(6, 16))
        self._label(row2, "间隔(秒)", size=10).pack(side="left")
        self.interval_entry = self._entry(row2, width=5)
        self.interval_entry.insert(0, "1.5")
        self.interval_entry.pack(side="left", padx=(6, 0))

        self._button(row2, "立即发送", self.send_now, "primary").pack(side="right")
        self._button(row2, "定时发送", self.send_later, "secondary").pack(side="right", padx=(0, 8))

    def _build_left_card(self):
        card = self._card(self.root)
        card.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=8)
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        self._card_title(card, "通讯录", "Ctrl + 点击 多选")

        self.listbox = tk.Listbox(card, selectmode=tk.EXTENDED, exportselection=False,
                                  font=self._f(11), relief="flat", bd=0, highlightthickness=0,
                                  bg=C_FIELD_BG, fg=C_TEXT, selectbackground=C_ACCENT,
                                  selectforeground="#ffffff", activestyle="none")
        self.listbox.grid(row=1, column=0, sticky="nsew")

        addf = tk.Frame(card, bg=C_CARD)
        addf.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        addf.grid_columnconfigure(0, weight=1)
        self.entry_new = self._entry(addf)
        self.entry_new.grid(row=0, column=0, sticky="ew")
        self.entry_new.bind("<Return>", lambda e: self.add_contact())
        self._button(addf, "添加", self.add_contact, "secondary", width=6).grid(row=0, column=1, padx=(8, 0))

        self._button(card, "删除选中联系人", self.del_contact, "danger").grid(
            row=3, column=0, sticky="ew", pady=(8, 0))

    def _build_right_card(self):
        card = self._card(self.root)
        card.grid(row=1, column=1, sticky="nsew", padx=(8, 24), pady=8)
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        self._card_title(card, "任务", "选中后操作")

        self.task_listbox = tk.Listbox(card, exportselection=False, font=self._f(11),
                                       relief="flat", bd=0, highlightthickness=0,
                                       bg=C_FIELD_BG, fg=C_TEXT, selectbackground=C_ACCENT,
                                       selectforeground="#ffffff", activestyle="none")
        self.task_listbox.grid(row=1, column=0, sticky="nsew")

        btns = tk.Frame(card, bg=C_CARD)
        btns.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self._button(btns, "暂停/继续", self.toggle_pause, "ghost").pack(side="left")
        self._button(btns, "载入编辑", self.load_edit, "ghost").pack(side="left", padx=(8, 0))
        self._button(btns, "删除任务", self.delete_task, "danger").pack(side="left", padx=(8, 0))

    def _build_log_card(self):
        card = self._card(self.root, pady=12)
        card.grid(row=2, column=0, columnspan=2, sticky="ew", padx=24, pady=(8, 20))
        card.grid_columnconfigure(0, weight=1)

        self._card_title(card, "日志")
        self.log_text = scrolledtext.ScrolledText(
            card, height=3, font=self._f(10), relief="flat", bd=0,
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
        for tid in sorted(self.tasks):
            self.task_listbox.insert(tk.END, self.tasks[tid].label())

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

    def _get_interval(self):
        try:
            v = float(self.interval_entry.get().strip())
            return v if v >= 0.5 else 1.5
        except Exception:
            return 1.5

    def _create_task(self, names, content, hour, minute, interval):
        task = Task(names, content, platform=self.current_platform,
                    hour=hour, minute=minute, interval=interval)
        self.tasks[task.id] = task
        self._refresh_tasks()
        self.log("=" * 40)
        when = f"定时 {hour:02d}:{minute:02d}" if hour is not None else "立即"
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
                platform=task.platform)
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
                if scheduler.wait_until(task.hour, task.minute, controller=task.controller):
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
        self.interval_entry.delete(0, tk.END)
        self.interval_entry.insert(0, str(task.interval))
        # 移除旧任务
        task.controller.cancel()
        del self.tasks[task.id]
        self._refresh_tasks()
        self.log(f"任务{task.id} 已载入编辑区，修改后重新发送")

    # ---------- 发送入口 ----------
    def _collect(self, require_time):
        names = self._get_selected_names()
        content = self._get_content()
        if not names:
            messagebox.showwarning("提示", "请先在左侧勾选要发的人")
            return None
        if not content:
            messagebox.showwarning("提示", "请填写发送内容")
            return None
        interval = self._get_interval()
        hour = minute = None
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
        return names, content, hour, minute, interval

    def send_now(self):
        r = self._collect(require_time=False)
        if not r:
            return
        names, content, hour, minute, interval = r
        task = self._create_task(names, content, hour, minute, interval)
        self._start_task(task)

    def send_later(self):
        r = self._collect(require_time=True)
        if not r:
            return
        names, content, hour, minute, interval = r
        task = self._create_task(names, content, hour, minute, interval)
        self._start_task(task)
        self.log("⚠ 到点前请保持程序运行、电脑不睡眠、不合盖、微信/QQ 登录在线")


def main():
    root = tk.Tk()
    icon = os.path.join(BASE_DIR, "app_icon.ico")
    if os.path.exists(icon):
        try:
            root.iconbitmap(icon)
        except Exception:
            pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
