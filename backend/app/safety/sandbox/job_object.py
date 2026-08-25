# -*- coding: utf-8 -*-
# job_object.py — Windows Job Object ctypes 封装(v1.19 P1 真实实现, 非伪代码) — 小欧 2026-08-25
import ctypes
import subprocess
from ctypes import wintypes

from app.logger import logger

_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
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

    def __init__(self, process_memory_limit_mb: int = 2048) -> None:
        # 内存上限默认 2048MB, 经 sandbox.process_memory_limit_mb 配置(R8: 误杀提示调大)
        self._handle = _kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise OSError(f"CreateJobObjectW failed: {ctypes.GetLastError()}")
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = process_memory_limit_mb * 1024 * 1024
        if not _kernel32.SetInformationJobObject(
                self._handle, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise OSError(f"SetInformationJobObject failed: {ctypes.GetLastError()}")
        logger.info(f"[sandbox][job] JobObject 创建成功, 进程内存上限={process_memory_limit_mb}MB")

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
        """CloseHandle(8.2.1: 千次 create/close 句柄数守恒)"""
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            logger.info(f"[sandbox][job] CloseHandle 释放 Job")
            self._handle = None
