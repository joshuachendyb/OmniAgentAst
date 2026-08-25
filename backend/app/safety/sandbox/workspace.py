# -*- coding: utf-8 -*-
# workspace.py — 沙箱工作区管理(v1.19 P3 真实实现, 非伪代码) — 小欧 2026-08-25
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

_MAX_UNLINK_RETRY = 5        # 销毁重试次数(复用 shell_engine _safe_unlink 同款思路)
_RETRY_INTERVAL_SEC = 0.2


@dataclass
class FileImpact:
    """影响文件清单条目(3.1.4 FileImpact 结构的正式定义)。
    一期在 blocked_reason 中拼纯文本下发, 二期结构化 JSON 数组(见 5.2 二期增强)。"""
    path: str
    change_type: str         # added / modified / removed
    size_bytes: int


class SandboxWorkspace:
    """沙箱工作区: %TEMP%/omniagent_sandbox/{uuid4hex}_{ts}/(uuid 免跨任务同名冲突)"""

    def __init__(self, max_workspace_mb: int = 500, max_shadow_mb: int = 100) -> None:
        self.path: Optional[Path] = None            # create 后可用(v1.17 N9 口径统一)
        self._snapshot: Dict[str, int] = {}          # 执行前快照: path -> size_bytes
        self._max_ws_bytes = max_workspace_mb * 1024 * 1024
        self._max_shadow_bytes = max_shadow_mb * 1024 * 1024

    def create(self) -> Path:
        self.path = Path(tempfile.gettempdir()) / "omniagent_sandbox" / f"{uuid.uuid4().hex}_{int(time.time() * 1000)}"
        self.path.mkdir(parents=True)
        return self.path

    def shadow_copy(self, target: Path) -> Path:
        """影子副本(保留相对结构); 单文件超上限返回原路径仅统计影响面(降级不阻断, 3.1.1 规则)"""
        dest = self.path / target.name
        if target.is_file():
            if target.stat().st_size > self._max_shadow_bytes:
                return target
            shutil.copy2(target, dest)
        else:
            shutil.copytree(target, dest, dirs_exist_ok=True)
        return dest

    def snapshot_files(self) -> None:
        """执行前快照(diff 的基线)"""
        self._snapshot = {str(p): p.stat().st_size for p in self.path.rglob("*") if p.is_file()}

    def diff_impacts(self) -> List[FileImpact]:
        """执行后 diff → 影响清单三态判定(新增/修改/删除), 抓漏报用例见 8.2.2"""
        current = {str(p): p.stat().st_size for p in self.path.rglob("*") if p.is_file()}
        impacts: List[FileImpact] = []
        for p, sz in current.items():
            if p not in self._snapshot:
                impacts.append(FileImpact(path=p, change_type="added", size_bytes=sz))
            elif self._snapshot[p] != sz:
                impacts.append(FileImpact(path=p, change_type="modified", size_bytes=sz))
        for p, sz in self._snapshot.items():
            if p not in current:
                impacts.append(FileImpact(path=p, change_type="removed", size_bytes=sz))
        return impacts

    def check_capacity(self, used_bytes: int) -> bool:
        """工作区大小上限判定(超限拒绝预检转 HITL 强确认, 3.1.1 规则; 边界翻转点见 8.2.2)"""
        return used_bytes <= self._max_ws_bytes

    def destroy(self) -> None:
        """_safe_unlink 重试销毁(R5): 重试后最终成功或明确报错"""
        if self.path is None:
            return
        last_err: OSError = None
        for _ in range(_MAX_UNLINK_RETRY):
            try:
                shutil.rmtree(self.path)
                self.path = None
                return
            except OSError as exc:
                last_err = exc
                time.sleep(_RETRY_INTERVAL_SEC)
        raise OSError(f"sandbox workspace destroy failed after {_MAX_UNLINK_RETRY} retries: {last_err}")
