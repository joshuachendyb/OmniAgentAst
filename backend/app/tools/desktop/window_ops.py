# -*- coding: utf-8 -*-
"""window_ops — 窗口状态查询与前台切换共用件(Windows 平台)

只收"多个窗口工具都要用"的句柄级操作, 各工具自己管业务逻辑。
编辑历史:
2026-10-19 小欧 - 新建: is_zoomed 收口 IsZoomed 缺失(当前 pywin32 build 无此属性);
  focus_window 走 ShowWindow+BringWindowToTop+SetActiveWindow+SetForegroundWindow 组合。
  AttachThreadInput 经实测排除: ①pywin32 该函数不返 BOOL(返 None), 无法判成败;
  ②常见场景下目标与前台同线程, attach 对无效对直接被系统拒(error 5), 徒增异常分支。
"""

import time

import win32api
import win32con
import win32gui

from app.logger import logger


def is_zoomed(hwnd: int) -> bool:
    """窗口是否最大化 — 小欧 2026-10-19

    当前 pywin32 build 的 win32gui 缺 IsZoomed 属性(实测 hasattr=False, 调用即
    AttributeError), 故改判 GetWindowPlacement 的 showCmd 是否 SW_SHOWMAXIMIZED。
    set_window_state 与 window_resize 共用本函数, 勿各写一遍。
    """
    return bool(win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED)


def focus_window(hwnd: int, attempts: int = 3, interval: float = 0.2) -> bool:
    """把窗口切到前台 — 小欧 2026-10-19

    Windows 前台锁: 非前台进程调 SetForegroundWindow 会被系统拒, 属系统策略而非参数错误。
    故按下列顺序逐级尝试, 每次都以 GetForegroundWindow() 实测是否真切换(不靠返回值):
      ① Alt 解锁      —— 释放前台资格, Windows 惯用解法;
      ② 还原窗口      —— 最小化窗口无法直接切前台;
      ③ 提升+激活     —— BringWindowToTop/SetActiveWindow 提升 Z 序并激活;
      ④ 置前台        —— 终选, 前三步已放宽系统限制;
      ⑤ 轮询          —— 窗口切换是异步的, 最多 attempts 次 × interval 秒。
    全部尝试仍失败即确为系统拒绝, 返回 False 由调用方如实报错, 不吞。

    ⚠ keybd_event 是**全局输入注入**, 会真实按下 Alt 键: 目标窗口若把 Alt 作快捷键前缀
    会连带触发; 运行在无活动桌面会话(服务/RDP 已断开)时注入无效。故仅作首选尝试,
    失败后靠 ②③④ 兜底, 不重复注入。
    """
    for _ in range(attempts):
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetActiveWindow(hwnd)
        except Exception as exc:
            # 跨进程时 SetActiveWindow 必失败(Windows 设计), 不终止, 留日志供排查
            logger.debug(f"[window_ops] 提升激活失败(可接受): hwnd={hwnd}, {exc!r}")
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception as exc:
            logger.debug(f"[window_ops] SetForegroundWindow 异常: hwnd={hwnd}, {exc!r}")
        if win32gui.GetForegroundWindow() == hwnd:
            return True
        time.sleep(interval)
    # 末次判定非冗余: 捕捉"最后一次 SetForegroundWindow 之后、sleep 期间才完成"的异步切换
    return win32gui.GetForegroundWindow() == hwnd


__all__ = ["is_zoomed", "focus_window"]