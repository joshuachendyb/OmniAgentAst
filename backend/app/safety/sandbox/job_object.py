# -*- coding: utf-8 -*-
# job_object.py — Windows Job Object ctypes 封装(真实实现, 非伪代码) — 小欧 2026-08-25
# 编辑历史:
# 2026-08-25 - 小欧 - 新建: ctypes 封装 Job Object, 收编子进程及全部孙进程(替代 taskkill PID 枚举无逃逸窗口);
#   内存上限 2048MB(sandbox.process_memory_limit_mb); assign 失败非静默上抛(R3); kill_tree 走 TerminateJobObject; close 释放句柄。
# 2026-10-08 - 小欧 - 补两项内核限额(纵深防御, 事故驱动): KILL_ON_JOB_CLOSE(句柄一关即杀全树, 防 exec 器崩溃留孤儿)
#   + ACTIVE_PROCESS_LIMIT(默认 64, 堵 fork 炸弹); 实测 QueryInformationJobObject 读回 LimitFlags=0x2108 确认生效,
#   限 1 时孙进程创建被内核拒绝。注意二者均不阻止子进程杀宿主进程, 那类由 shell_readonly 静态判定负责。 — 小欧-2026-10-08
import ctypes
import subprocess
from ctypes import wintypes

from app.logger import logger

_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000   # 2026-10-08 小欧 新增: Job 句柄一关即杀全树, 防 exec 器崩溃留孤儿
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008     # 2026-10-08 小欧 新增: 限制树内并发进程数, 堵 fork 炸弹
_JobObjectExtendedLimitInformation = 9   # JobObjectInformationClass 枚举值

# v1.21 Z7: 64位 HANDLE 截断防护 — ctypes 默认 restype=c_int 会截断 64 位句柄(经典坑), 全部显式声明
_kernel32 = ctypes.windll.kernel32
_kernel32.CreateJobObjectW.restype = wintypes.HANDLE
_kernel32.CreateJobObjectW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
_kernel32.SetInformationJobObject.restype = wintypes.BOOL
_kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
_kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
_kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
_kernel32.TerminateJobObject.restype = wintypes.BOOL
_kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)


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


class SandboxJob:
    """ctypes 封装 Windows Job Object — 内核保证收编全部后代进程(替代 taskkill PID 枚举, 无逃逸窗口)"""

    def __init__(self, process_memory_limit_mb: int = 2048,
                 active_process_limit: int = 64) -> None:
        # 内存上限默认 2048MB, 经 sandbox.process_memory_limit_mb 配置(R8: 误杀提示调大)
        # 2026-10-08 小欧: 补 KILL_ON_JOB_CLOSE(句柄一关即杀全树, 防 exec 器崩溃留孤儿) + 进程数上限(堵 fork 炸弹);
        #   二者均**不阻止**子进程操作宿主(杀别的进程/改注册表), 那类由 shell_readonly 静态判定负责。
        self._handle = _kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise OSError(f"CreateJobObjectW failed: {ctypes.GetLastError()}")
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_PROCESS_MEMORY | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | _JOB_OBJECT_LIMIT_ACTIVE_PROCESS)
        info.ProcessMemoryLimit = process_memory_limit_mb * 1024 * 1024
        info.BasicLimitInformation.ActiveProcessLimit = active_process_limit
        if not _kernel32.SetInformationJobObject(
                self._handle, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise OSError(f"SetInformationJobObject failed: {ctypes.GetLastError()}")
        logger.info(f"[sandbox][job] JobObject 创建成功, 进程内存上限={process_memory_limit_mb}MB, "
                    f"进程数上限={active_process_limit}, KILL_ON_JOB_CLOSE=开")

    def assign(self, proc: subprocess.Popen) -> None:
        """收编子进程及其全部孙进程; R3: 返回值必校验, 失败上抛非静默(executor 转 HITL)"""
        if not _kernel32.AssignProcessToJobObject(self._handle, int(proc._handle)):
            raise OSError(f"AssignProcessToJobObject failed(pids={proc.pid}): {ctypes.GetLastError()}")
        logger.info(f"[sandbox][job] 进程收编入 Job: pid={proc.pid}")

    def kill_tree(self) -> None:
        """TerminateJobObject 内核一键杀全树(8.2.1: 杀后须 poll 确认全树退出)"""
        if self._handle:
            logger.debug(f"[sandbox][job] TerminateJobObject 杀全树(清理契约)")
            _kernel32.TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        """CloseHandle(8.2.1: 千次 create/close 句柄数守恒) — 小欧 2026-08-25
        2026-10-08 小欧: 因已置 KILL_ON_JOB_CLOSE, 此处 close 本身也会杀树, 故必须幂等且不吞异常。"""
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            logger.info(f"[sandbox][job] CloseHandle 释放 Job")
            self._handle = None
