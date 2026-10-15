
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-11 - 小欧 - 创建文件: 长路径工具 to_win_long_path, 从 operation_backup._win_long_path 提为全局公用,
#   解决深嵌套目录(递归自复制套娃)备份/清理时 WinError 206 路径超长整体失败的历史事故闭环
#   (备份长路径已支持, 清理链路 operation_cleanup 同样需长路径, 否则超长备份永远清不掉→回收站永久膨胀)
# 2026-08-11 - 小欧 - 三堂会审复核落地: 补 is_absolute() 前置守卫, 相对路径不加 \\?\ 前缀,
#   与docstring"非绝对路径保持原样"承诺对齐(原代码相对路径会生成非法 \\?\relative 路径)
# 2026-10-15 北京老陈裁定(DRY) - 4 类目录判定收敛为 utils 唯一实现; _get_protected_roots 提为公开单源:
#   原根集合在 delete_safety._get_allowed_roots / path_safe_check 白名单构建 / 本文件三处各写一份同义逻辑,
#   且 .resolve() 用法不一致(str/Path 混流, 靠下游 realpath 兜底)。现三处统一调用本函数; 失败语义改 fail-closed。
# 2026-10-15 小欧 - 文档[35] 阶段五: SYSTEM_PROTECTED_DIR_NAMES / is_system_protected_path / is_disk_root /
#   is_code_root_path / is_protected_root_itself 五符号迁往 app.safety/path_guard.py(职责回归安全域)。
#   本文件不再持有任何安全判定, 只剩长路径与允许根两项通用工具; 旧名不保留转发(禁止 backward)。
"""
path_utils — 路径处理通用工具

职责: Windows 长路径支持、允许根集合构建。
不含任何安全判定 —— 目录属性判定见 app/safety/path_guard.py(2026-10-15 迁出)。

小欧 2026-08-11 建 / 2026-10-15 小欧 收敛
"""
import os
from pathlib import Path
from typing import Iterable, Optional

# 2026-10-06 小欧 - 从 path_safe_check.validate_path 函数体内提到模块级(常量归位): 原先定义在函数里,
#   每次调用重建一遍 frozenset; 展示层(security_docs)拿不到, 只能硬编码 \ProgramData 等 3 条。
def to_win_long_path(path: Path) -> str:
    r"""Windows长路径 \\?\ 前缀, 绕过MAX_PATH(260)限制 — 小欧 2026-08-11
    仅NT系统生效; 已带前缀或非绝对路径保持原样。
    """
    if os.name != "nt":
        return str(path)
    s = str(path)
    if s.startswith("\\\\?\\") or not Path(s).is_absolute():
        return s
    return "\\\\?\\" + s


def get_allowed_roots(extra_roots: Optional[Iterable[str]] = None) -> list:
    r"""允许根集合 = 项目根 + 授权目录 [+ 调用方传入的会话工作区] — **判定单源, 各层只调用**

    2026-10-15 北京老陈裁定(DRY 收敛): 此前 delete_safety._get_allowed_roots /
    path_safe_check 的白名单构建 / 本文件 _get_protected_roots 三处各写一份同义逻辑,
    且 .resolve() 用法不一致(str/Path 混流, 靠下游 realpath 兜底)。现收于本函数, 三处统一调用。

    extra_roots 参数化(去反向依赖): 会话工作区快照在 app/tools/context.py, 属上层。
      若本函数直接 import 即构成「utils 反向依赖上层」(架构守护测试 test_utils_does_not_depend_on_upper_layers 红)。
      改为由调用方传入 —— safety 层与 tools 层**均可** import app.tools.context
      (铁律只禁 tools→services/safety, safety→tools 本就合法; tools→tools 同层更合法),
      故此拆分**不损失任何保护**, 仅解开 utils 的分层依赖。

    失败语义(fail-closed): config 来源读取异常即整体抛 RuntimeError, 不用空列表静默降级 ——
    空列表会让"是否在允许根内"恒为 False, 把全部路径误判成区外, 属安全侧最坏的静默失败。
    """
    from app.config import get_config  # 延迟导入: utils 不反向依赖 app.config

    roots: list = []
    try:
        cfg = get_config()
        roots.append(Path(cfg.get_project_root()).resolve())
        roots.extend(Path(d).resolve() for d in cfg.get_allowed_dirs())
    except Exception as e:
        raise RuntimeError(f"读取允许根失败(config): {e}") from e
    if extra_roots:
        try:
            roots.extend(Path(p).resolve() for p in extra_roots)
        except Exception as e:
            raise RuntimeError(f"读取允许根失败(会话工作区): {e}") from e
    return roots


__all__ = ["to_win_long_path", "get_allowed_roots"]
