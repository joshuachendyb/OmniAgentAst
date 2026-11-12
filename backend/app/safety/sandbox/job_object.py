# -*- coding: utf-8 -*-
# job_object.py — 沙箱 Job Object 高级封装(SandboxJob) — 小欧 2026-08-25
# 编辑历史:
# 2026-08-25 - 小欧 - 新建: ctypes 封装 Job Object, 收编子进程及全部孙进程(替代 taskkill PID 枚举无逃逸窗口);
#   内存上限 2048MB(sandbox.process_memory_limit_mb); assign 失败非静默上抛(R3); kill_tree 走 TerminateJobObject; close 释放句柄。
# 2026-10-08 - 小欧 - 补两项内核限额(纵深防御, 事故驱动): KILL_ON_JOB_CLOSE(句柄一关即杀全树, 防 exec 器崩溃留孤儿)
#   + ACTIVE_PROCESS_LIMIT(默认 64, 堵 fork 炸弹); 实测 QueryInformationJobObject 读回 LimitFlags=0x2108 确认生效,
#  限 1 时孙进程创建被内核拒绝。注意二者均不阻止子进程杀宿主进程, 那类由 shell_readonly 静态判定负责。 — 小欧-2026-10-08
# 2026-11-07 - 小欧 - 底层 ctypes 封装提取到 app/utils/win_job_object.py(SRP: 沙箱目录只放沙箱功能);
#   本文件改为从公共库导入底层声明/结构体/常量, 只保留 SandboxJob 类。— 小欧-2026-11-07
import ctypes
import subprocess

from app.logger import logger
from app.utils.win_job_object import (
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOB_OBJECT_LIMIT_PROCESS_MEMORY,
    JobObjectExtendedLimitInformation,
    kernel32,
)


class SandboxJob:
    """ctypes 封装 Windows Job Object — 内核保证收编全部后代进程(替代 taskkill PID 枚举, 无逃逸窗口)"""

    def __init__(self, process_memory_limit_mb: int = 2048,
                 active_process_limit: int = 64) -> None:
        # 内存上限默认 2048MB, 经 sandbox.process_memory_limit_mb 配置(R8: 误杀提示调大)
        # 2026-10-08 小欧: 补 KILL_ON_JOB_CLOSE(句柄一关即杀全树, 防 exec 器崩溃留孤儿) + 进程数上限(堵 fork 炸弹);
        #   二者均**不阻止**子进程操作宿主(杀别的进程/改注册表), 那类由 shell_readonly 静态判定负责。
        self._handle = kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise OSError(f"CreateJobObjectW failed: {ctypes.GetLastError()}")
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | JOB_OBJECT_LIMIT_ACTIVE_PROCESS)
        info.ProcessMemoryLimit = process_memory_limit_mb * 1024 * 1024
        info.BasicLimitInformation.ActiveProcessLimit = active_process_limit
        if not kernel32.SetInformationJobObject(
                self._handle, JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise OSError(f"SetInformationJobObject failed: {ctypes.GetLastError()}")
        logger.info(f"[sandbox][job] JobObject 创建成功, 进程内存上限={process_memory_limit_mb}MB, "
                    f"进程数上限={active_process_limit}, KILL_ON_JOB_CLOSE=开")

    def assign(self, proc: subprocess.Popen) -> None:
        """收编子进程及其全部孙进程; R3: 返回值必校验, 失败上抛非静默(executor 转 HITL)"""
        if not kernel32.AssignProcessToJobObject(self._handle, int(proc._handle)):
            raise OSError(f"AssignProcessToJobObject failed(pids={proc.pid}): {ctypes.GetLastError()}")
        logger.info(f"[sandbox][job] 进程收编入 Job: pid={proc.pid}")

    def kill_tree(self) -> None:
        """TerminateJobObject 内核一键杀全树(8.2.1: 杀后须 poll 确认全树退出)"""
        if self._handle:
            logger.debug("[sandbox][job] TerminateJobObject 杀全树(清理契约)")
            kernel32.TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        """CloseHandle(8.2.1: 千次 create/close 句柄数守恒) — 小欧 2026-08-25
        2026-10-08 小欧: 因已置 KILL_ON_JOB_CLOSE, 此处 close 本身也会杀树, 故必须幂等且不吞异常。"""
        if self._handle:
            kernel32.CloseHandle(self._handle)
            logger.info("[sandbox][job] CloseHandle 释放 Job")
            self._handle = None
