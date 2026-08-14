# -*- coding: utf-8 -*-
"""定时等待：等到指定时刻触发，支持取消和暂停。"""
import datetime
import time


def wait_until(hour, minute, controller=None):
    """等待到当天 hour:minute；若时间已过则顺延到明天。

    controller.cancelled 时提前返回 False；到点返回 True。
    等待期间受 controller 暂停控制。
    """
    now = datetime.datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    while True:
        if controller:
            controller.wait_if_paused()
        if controller and controller.cancelled:
            return False
        if datetime.datetime.now() >= target:
            return True
        time.sleep(1)
