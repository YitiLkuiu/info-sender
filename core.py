# -*- coding: utf-8 -*-
"""微信 / QQ PC 版自动化核心：搜索 → 进入会话 → 粘贴发送。

原理：模拟键盘操作桌面客户端（微信 / QQ），靠快捷键驱动。
中文无法用 typewrite 直接输入，统一用「剪贴板复制 + Ctrl+V」粘贴。
"""
import threading
import time

import pyautogui
import pyperclip

# 中断改用任务管理的「暂停/删除」按钮，不再用鼠标甩左上角（易误触）
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1

# 平台差异：目前微信 / QQ 只有窗口标题不同，搜索快捷键等一致。
# 若实测发现 QQ 有其它差异（搜索方式/进会话方式），在这里单独加配置项。
PLATFORMS = {
    # result_wait = 粘贴名字后，等搜索结果出现的秒数。微信约 0.3s；QQ 约 0.9s（等不到就回车会进错页）。
    "微信": {"title": "微信", "open_search": "hotkey", "search_offset": None,  "result_wait": 0.3},
    # QQ 没有可靠的搜索快捷键（脚本模拟 Ctrl+F 不触发），改用「点击顶部搜索框」。
    # search_offset = 搜索框中心相对窗口左上角的偏移(像素)，窗口移动/最大化都按此相对位置算。
    "QQ":   {"title": "QQ",   "open_search": "click",  "search_offset": (202, 83), "result_wait": 0.9},
}


class SendController:
    """发送任务控制器：暂停 / 继续 / 取消。"""

    def __init__(self):
        self._pause = threading.Event()
        self._pause.set()            # 默认不暂停
        self._cancelled = threading.Event()
        self.paused = False

    def pause(self):
        self.paused = True
        self._pause.clear()

    def resume(self):
        self.paused = False
        self._pause.set()

    def cancel(self):
        self._cancelled.set()
        self._pause.set()            # 解除暂停，让循环能退出

    @property
    def cancelled(self):
        return self._cancelled.is_set()

    def wait_if_paused(self):
        self._pause.wait()


def activate_window(title):
    """强激活指定标题的窗口（Win32 API 置前，绕过前台锁定）。成功返回 True。"""
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE：还原（若最小化）
    user32.keybd_event(0x12, 0, 0, 0)   # Alt down
    user32.keybd_event(0x12, 0, 2, 0)   # Alt up
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.6)
    return True


def _paste(text):
    """把文本复制到剪贴板并 Ctrl+V 粘贴（支持中文）。"""
    pyperclip.copy(text)
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "v")


def _press_enter():
    """发回车键（带扫描码 0x1C）。QQ NT 只认带扫描码的回车，pyautogui 发的无效。"""
    import ctypes
    user32 = ctypes.windll.user32
    user32.keybd_event(0x0D, 0x1C, 0, 0)   # 按下
    user32.keybd_event(0x0D, 0x1C, 2, 0)   # 松开


def _open_search(cfg):
    """打开搜索框。微信用 Ctrl+F；QQ 点击顶部搜索框（相对窗口坐标）。"""
    if cfg["open_search"] == "hotkey":
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.6)
    else:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, cfg["title"])
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        ox, oy = cfg["search_offset"]
        pyautogui.click(rect.left + ox, rect.top + oy)
        time.sleep(0.6)


def _search_and_enter(name, cfg):
    """打开搜索框，粘贴名字、立即回车进入会话。"""
    _open_search(cfg)
    _paste(name)
    time.sleep(cfg.get("result_wait", 0.3))   # 等搜索结果出现（QQ 比微信慢）
    _press_enter()                  # 进入会话
    time.sleep(0.8)                 # 等会话打开、输入框聚焦


def _verify_sent():
    """发送后检测是否成功：清空剪贴板 → 全选 + 复制当前焦点框。

    空 = 发送成功（输入框已清空）；非空 = 没发出去（焦点仍在搜索框）。
    """
    pyperclip.copy("")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.15)
    return pyperclip.paste() == ""


def copy_file_to_clipboard(path):
    """把文件以 CF_HDROP 格式复制到剪贴板，供聊天窗口 Ctrl+V 粘贴成附件。"""
    import ctypes
    import struct
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    CF_HDROP = 15
    GMEM_MOVEABLE = 0x0002

    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

    data = path.encode("utf-16-le") + b"\x00\x00"      # 宽字符路径，双 \0 结尾
    header = struct.pack("<IIIII", 20, 0, 0, 0, 1)     # DROPFILES 头：pFiles=20, fWide=1
    blob = header + data

    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(blob))
        if not hmem:
            return False
        p = kernel32.GlobalLock(hmem)
        if not p:
            kernel32.GlobalFree(hmem)
            return False
        ctypes.memmove(p, blob, len(blob))
        kernel32.GlobalUnlock(hmem)
        user32.SetClipboardData(CF_HDROP, hmem)
        return True
    finally:
        user32.CloseClipboard()


def send_one(name, content, interval=1.5, cfg=None, file_path=None):
    """给单个对象发一条消息（文字 / 文件 / 文字+文件），返回是否发送成功。"""
    cfg = cfg or PLATFORMS["微信"]
    _search_and_enter(name, cfg)
    if content:
        _paste(content)
        time.sleep(0.3)
        _press_enter()              # 发送文字
        time.sleep(0.35)
    if file_path:
        copy_file_to_clipboard(file_path)
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "v")   # 粘贴成文件附件（不走 _paste，避免覆盖剪贴板）
        time.sleep(1.2)                  # 等附件加载
        _press_enter()                   # 发送文件
        time.sleep(0.5)
    ok = _verify_sent() if (content and not file_path) else True
    time.sleep(interval)
    return ok


def send_many(names, content, interval=1.5, log=None, controller=None, on_progress=None, platform="微信", file_path=None):
    """给多个对象逐个发消息。

    controller: SendController，用于暂停/取消。
    on_progress: 回调(done, total, ok, failed)，每处理一条调用。
    返回 (成功数, 失败名单)。
    """
    names = [n.strip() for n in names if n and n.strip()]
    if log:
        log("正在激活窗口...")
    cfg = PLATFORMS.get(platform, PLATFORMS["微信"])
    if not activate_window(cfg["title"]):
        if log:
            log(f"⚠ 未找到「{platform}」窗口，请确认 {platform} 已打开且窗口未最小化到托盘。")
        return 0, list(names)

    ok, failed = 0, []
    total = len(names)
    for i, name in enumerate(names):
        if controller and controller.cancelled:
            break
        if controller:
            controller.wait_if_paused()
        if controller and controller.cancelled:
            break
        try:
            if log:
                log(f"[{i + 1}/{total}] 发送给：{name}")
            if send_one(name, content, interval, cfg, file_path=file_path):
                ok += 1
            else:
                failed.append(name)
                if log:
                    log(f"  ⚠ 未找到「{name}」或发送失败，已跳过")
        except Exception as e:
            failed.append(name)
            if log:
                log(f"  发送「{name}」时出错：{e}")
        if on_progress:
            on_progress(i + 1, total, ok, len(failed))
    return ok, failed
