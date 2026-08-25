# -*- coding: utf-8 -*-
# backend.py — 后端协议与唯一实现(v1.19 P2 真实实现, 非伪代码) — 小欧 2026-08-25
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from app.logger import logger
from app.safety.sandbox.job_object import SandboxJob

_TAIL_CHARS = 4096   # stdout/stderr 尾部截断口径(PreCheckResult.stdout_tail 同款)


@dataclass
class BackendResult:
    rc: int
    stdout_tail: str = ""
    stderr_tail: str = ""
    timed_out: bool = False   # run 被 timeout_sec 截断标志(4.2 判定分流算法规则2 数据来源; rc 无法区分截断与真失败)


class SandboxBackend(Protocol):
    def probe(self) -> bool:   # 探测可用性(协议扩展位; JobObjectBackend 恒True)
        ...
    def run(self, command: str, workspace: Path, timeout_sec: int) -> BackendResult:
        ...
    def cleanup(self) -> None:  # 统一清理契约: 杀树+释放句柄(executor finally 调用)
        ...


class JobObjectBackend:
    """当前唯一后端 — subprocess(pwsh -NoProfile -NoLogo -NonInteractive -ExecutionPolicy Bypass) + SandboxJob 包裹"""

    def __init__(self, process_memory_limit_mb: int = 2048) -> None:
        self._job: Optional[SandboxJob] = None
        self._proc: Optional[subprocess.Popen] = None

    def probe(self) -> bool:
        return True   # 唯一实现零依赖永远在线, 无运行时探测开销(2.5.1)

    def run(self, command: str, workspace: Path, timeout_sec: int) -> BackendResult:
        """命令落临时脚本执行(%TEMP% 属影响面豁免区 FP3, 不污染 workspace diff); R3: assign 失败上抛 OSError"""
        script = Path(tempfile.gettempdir()) / f"omniagent_sbx_{os.getpid()}_{uuid.uuid4().hex}.ps1"   # v1.21 Z8: uuid 免同命令并发碰撞
        script.write_text(command, encoding="utf-8-sig")   # BOM 头保 pwsh 正确解码中文命令(8.5 编码攻击向量)
        argv = ["pwsh", "-NoProfile", "-NoLogo", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", str(script)]
        timed_out = False
        _start = time.monotonic()
        logger.info(f"[sandbox][backend] run 启动: timeout={timeout_sec}s, workspace={workspace}, command_head={command[:120]!r}")
        try:
            self._job = SandboxJob()
            self._proc = subprocess.Popen(argv, cwd=str(workspace),
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._job.assign(self._proc)               # 提权进程收编失败 → 上抛(R3 非静默)
            out_b, err_b = self._proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True                            # 规则2 数据来源(N4)
            logger.warning(f"[sandbox][backend] run 超时截断(timed_out), 触发 kill_tree 防失控: timeout={timeout_sec}s")
            self.kill_tree()                            # 超时防失控第一道闸(4.1/M4)
            out_b, err_b = self._proc.communicate()
        finally:
            script.unlink(missing_ok=True)              # 临时脚本即用即删(自我指涉攻击面最小化)
        decode = lambda b: (b or b"").decode("utf-8", errors="replace")[-_TAIL_CHARS:]
        _elapsed = round(time.monotonic() - _start, 3)
        logger.info(f"[sandbox][backend] run 结束: rc={self._proc.returncode if not timed_out else -1}, "
                    f"timed_out={timed_out}, elapsed={_elapsed}s, stdout_len={len(out_b)}, stderr_len={len(err_b)}")
        return BackendResult(rc=self._proc.returncode if not timed_out else -1,
                             stdout_tail=decode(out_b), stderr_tail=decode(err_b),
                             timed_out=timed_out)

    def kill_tree(self) -> None:
        if self._job is not None:
            logger.info(f"[sandbox][backend] kill_tree 触发(清理契约/超时兜底)")
            self._job.kill_tree()

    def cleanup(self) -> None:
        """统一清理契约: TerminateJobObject 杀树 + CloseHandle 释放(8.7 三项守恒断言之句柄项)
        v1.21 Z4: R3 失败路径子进程未入 Job, 杀空 Job 无效 → 必须对 Popen 本体兜底 kill+wait, 杜绝孤儿进程"""
        if self._proc is not None:
            try:
                if self._proc.poll() is None:      # 仍在运行(含未入 Job 的孤儿) → 兜底击杀并收割
                    self._proc.kill()
                    self._proc.wait(timeout=5)
            except Exception as exc:               # 收割失败仅告警不阻断清理链
                logger.warning(f"[sandbox] proc reap failed: {exc}")
        if self._job is not None:
            self._job.kill_tree()
            self._job.close()
            self._job = None
