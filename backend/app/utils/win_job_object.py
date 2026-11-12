# -*- coding: utf-8 -*-
# win_job_object.py — Windows Job Object 底层 ctypes 封装(通用, 非沙箱专属) — 小欧 2026-11-07
# 编辑历史:
# 2026-11-07 - 小欧 - 从 sandbox/job_object.py 提取底层封装: ctypes 声明/结构体/常量是沙箱和打包版
#   共用的底层设施, 不应归属沙箱目录(SRP); assign_current_to_kill_on_close_job() 是通用进程管理,
#   非沙箱功能。提取到 app/utils/ 与 proc_utils.py 同层(通用进程工具)。— 小欧-2026-11-07
import ctypes
from ctypes import wintypes

from app.logger import logger

# ── 内核限额标志 ──
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008

# ── JobObjectInformationClass 枚举值 ──
JobObjectBasicLimitInformation = 2
JobObjectExtendedLimitInformation = 9

# ── kernel32 函数签名(64位 HANDLE 截断防护: ctypes 默认 restype=c_int 会截断, 全部显式声明) ──
kernel32 = ctypes.windll.kernel32
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.CreateJobObjectW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
kernel32.TerminateJobObject.restype = wintypes.BOOL
kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.GetCurrentProcess.restype = wintypes.HANDLE


# ── 结构体 ──
class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def assign_current_to_kill_on_close_job() -> int:
    """打包版 exe 顶层 Job Object: KILL_ON_JOB_CLOSE 保证主进程退出时子进程树自动终止。

    用途: 关 console 窗口时 shell 子进程等随主进程退出, 不留孤儿锁 DLL。
    机制: 当前进程 assign 入 Job → 子进程自动继承 → 主进程退出时 OS 回收句柄
          → KILL_ON_JOB_CLOSE 触发 → 内核杀全部子进程树。
    失败只 warning 不 crash(进程可能已在其他 Job Object 中, Windows 8+ 允许嵌套但旧版不允许)。
    返回 Job Object 句柄(内核句柄, Python GC 不关闭; 进程退出时 OS 自动回收句柄触发杀树)。— 小欧-2026-11-07
    """
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        logger.warning(f"[job] CreateJobObjectW 失败: {ctypes.GetLastError()}")
        return 0
    info = JOBOBJECT_BASIC_LIMIT_INFORMATION()
    info.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
            handle, JobObjectBasicLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info)):
        kernel32.CloseHandle(handle)
        logger.warning(f"[job] SetInformationJobObject 失败: {ctypes.GetLastError()}")
        return 0
    if not kernel32.AssignProcessToJobObject(handle, kernel32.GetCurrentProcess()):
        kernel32.CloseHandle(handle)
        logger.warning(f"[job] AssignProcessToJobObject 失败(可能已在其他 Job 中): {ctypes.GetLastError()}")
        return 0
    logger.info("[job] 当前进程已收编入 KILL_ON_JOB_CLOSE Job, 子进程将随主进程退出自动终止")
    return handle