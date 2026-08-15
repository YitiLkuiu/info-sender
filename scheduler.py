# -*- coding: utf-8 -*-
"""定时等待：等到指定时刻触发，支持取消和暂停。"""
import datetime
import time


def wait_until(hour, minute, controller=None, month=None, day=None):
    """等待到指定时刻触发，支持取消和暂停。

    month/day 都给定时：等到该月该日的 hour:minute（该时刻已过则顺延到下一年）。
    未给定时：等到「最近的未来时刻」——今天该时刻已过就顺延到明天。
    controller.cancelled 时提前返回 False；到点返回 True；等待期间受暂停控制。
    """
    now = datetime.datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if month is not None and day is not None:
        try:
            target = target.replace(month=month, day=day)
        except ValueError:
            return False          # 无效日期（如 2-30）
        if target <= now:
            target = target.replace(year=now.year + 1)
    else:
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
