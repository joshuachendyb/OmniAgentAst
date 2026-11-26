# -*- coding: utf-8 -*-
# win_job_object.py — Windows Job Object 底层 ctypes 封装(通用, 非沙箱专属) — 小欧 2026-11-07
# 编辑历史:
# 2026-11-07 - 小欧 - 从 sandbox/job_object.py 提取底层封装: ctypes 声明/结构体/常量是沙箱和打包版
#   共用的底层设施, 不应归属沙箱目录(SRP); assign_current_to_kill_on_close_job() 是通用进程管理,
#   非沙箱功能。提取到 app/utils/ 与 proc_utils.py 同层(通用进程工具)。— 小欧-2026-11-07
# 2026-11-12 - 小欧 - SetInformationJobObject 从 BasicLimitInformation(Class=2) 改用 ExtendedLimitInformation(Class=9):
#   KILL_ON_JOB_CLOSE 在 Basic 上返回 ERROR_INVALID_PARAMETER(87), 必须用 Extended 才能设置此标志
# 2026-11-22 - 小欧 - 误杀面收敛(不能误伤铁律): 新增 breakaway 基础设施常量
#   JOB_OBJECT_LIMIT_BREAKAWAY_OK(允许显式 breakaway) / JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK(子进程自动脱离)
#   / CREATE_BREAKAWAY_FROM_JOB(进程创建标志)。供沙箱 Job 豁免"用户显式启动、意图跨调用驻留的后台进程"
#   (Start-Process/Start-Job/&) 脱离 Job, 预检 cleanup 杀树不误杀。SILENT 与 BREAKAWAY 互斥(Windows 限制),
#   沙箱默认启用 SILENT(自动脱离覆盖任意 shell 后台), BREAKAWAY_OK 保留为显式控制基础设施。
#   新增 QueryInformationJobObject 声明(验证 LimitFlags 读回生效)。
# 2026-11-26 - 小欧 - 进程宿主([65] E1)复用: 新增 create_kill_on_close_job/assign_to_job/terminate_job/close_job
#   四个通用句柄操作(宿主用独立 Job 收编每条命令的子进程树, 超时/宿主退出整树杀净); logger 改函数内惰性导入,
#   使本模块 import 零副作用(轻量宿主进程导入不进 app.logger 控制台线程)。
import ctypes
import subprocess
from ctypes import wintypes

# ── 内核限额标志 ──
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008

# 2026-11-22 小欧 - breakaway 基础设施(不能误伤): 允许 Job 内进程创建的子进程脱离 Job。
#   SILENT=自动脱离(子进程无需标志, 覆盖任意 shell 后台); BREAKAWAY=需显式 CREATE_BREAKAWAY_FROM_JOB。
#   二者互斥(Windows 限制), 沙箱默认启用 SILENT, BREAKAWAY_OK 保留为显式控制基础设施。
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
# 进程创建标志: 配合 BREAKAWAY_OK, 新进程以显式 breakaway 脱离 Job(需 Job 先设 BREAKAWAY_OK)。
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


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

# 2026-11-22 小欧 - QueryInformationJobObject 声明: 读回 LimitFlags 验证 breakaway/KILL_ON_JOB_CLOSE 生效
kernel32.QueryInformationJobObject.restype = wintypes.BOOL
kernel32.QueryInformationJobObject.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))



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
    from app.logger import logger  # 惰性导入: 保持本模块 import 零副作用(见文件头 2026-11-26)
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        logger.warning(f"[job] CreateJobObjectW 失败: {ctypes.GetLastError()}")
        return 0
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
            handle, JobObjectExtendedLimitInformation,
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


def create_kill_on_close_job() -> int:
    """创建独立 Job 并仅设 KILL_ON_JOB_CLOSE, 返回内核句柄 — 2026-11-26 小欧

    供进程宿主按命令收编子进程树: 句柄关闭(含宿主退出)时内核杀净整棵树。
    失败抛 OSError(fail-closed: 调用方不得在无 Job 时裸跑子进程)。
    注意: 不设 SILENT_BREAKAWAY_OK —— 那会让孙进程逃离 Job 致杀树失效(沙箱场景另论)。
    """
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise OSError(ctypes.GetLastError(), "CreateJobObjectW 失败")
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
            handle, JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info)):
        err = ctypes.GetLastError()
        kernel32.CloseHandle(handle)
        raise OSError(err, "SetInformationJobObject(KILL_ON_JOB_CLOSE) 失败")
    return handle


def assign_to_job(job_handle: int, proc: "subprocess.Popen") -> None:
    """把已创建的子进程收编进 Job(应在子进程派生子进程前尽快执行) — 2026-11-26 小欧

    用 Popen 暴露的进程句柄(_handle); 失败抛 OSError, 调用方须 fail-closed。
    """
    proc_handle = getattr(proc, "_handle", None)
    if not proc_handle:
        raise OSError(0, "Popen 无进程句柄(_handle), 无法收编 Job")
    if not kernel32.AssignProcessToJobObject(job_handle, proc_handle):
        raise OSError(ctypes.GetLastError(), "AssignProcessToJobObject 失败")


def terminate_job(job_handle: int) -> None:
    """立即杀净 Job 内全部进程 — 2026-11-26 小欧

    失败抛 OSError(句柄已失效等), 由调用方按清理链容错。
    """
    if not kernel32.TerminateJobObject(job_handle, 1):
        raise OSError(ctypes.GetLastError(), "TerminateJobObject 失败")


def close_job(job_handle: int) -> None:
    """关闭 Job 句柄(KILL_ON_JOB_CLOSE 触发杀树; 空句柄/已关闭容错不抛) — 2026-11-26 小欧"""
    if job_handle:
        kernel32.CloseHandle(job_handle)
