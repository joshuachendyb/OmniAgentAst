# -*- coding: utf-8 -*-
"""shell_parse.action — shell 解析的动作契约(解析层输出 / 判定层输入) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 数据契约落地。
  一条 shell 命令解析为若干 PathAction(动作级抽象, 非命令级单模式);
  kind 三值(read/write/delete), flags 随动作绑定, origin 标注来源语句/动词。

分层: 本文件只持契约, 不做任何解析、不判任何权限(解析与判定零耦合)。
"""
from dataclasses import dataclass, field
from typing import Dict

READ_KIND = "read"
WRITE_KIND = "write"
DELETE_KIND = "delete"
ACTION_KINDS = (READ_KIND, WRITE_KIND, DELETE_KIND)


@dataclass
class PathAction:
    """一次 shell 动作: 对某个路径做读/写/删 — 小欧 2026-10-18

    kind   : 动作性质, ∈ {read, write, delete}
    path   : 已归一/绝对化的目标路径(相对且无 cwd 者不入清单)
    flags  : {"recursive": bool, "force": bool, "append": bool, "wildcard": bool}
    origin : 来源语句/动词(如 "delete" / "move-src" / "pipe")
    """
    kind: str
    path: str
    flags: Dict[str, bool] = field(default_factory=dict)
    origin: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ACTION_KINDS:
            raise ValueError(f"非法动作性质: {self.kind!r}(仅 {'/'.join(ACTION_KINDS)})")
        if not isinstance(self.path, str) or not self.path:
            raise ValueError(f"动作路径必须是非空字符串: {self.path!r}")


__all__ = ["PathAction", "READ_KIND", "WRITE_KIND", "DELETE_KIND", "ACTION_KINDS"]
