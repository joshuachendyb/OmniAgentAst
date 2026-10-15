
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - 从 services/service_manager/lifecycle.py 迁入，背 path 管理
# 2026-07-26 - 小沈 - 合并 backup_to_recycle_bin 自 operation_record，成为真正备份职责文件
# 2026-08-11 - 小欧 - 长路径支持(北京老陈驱动): 源/目标加\\?\前缀绕过MAX_PATH(260)限制,
#   解决深嵌套目录(递归自复制套娃)备份WinError 206路径超长整体失败致"无备份删除"历史事故
# 2026-08-11 - 小欧 - _win_long_path 提为全局公用 app/utils/path_utils.to_win_long_path
#   (三堂会审: 清理链路 operation_cleanup 需同用长路径, 否则超长备份永远清不掉; 提公共层避免循环依赖)
# 2026-08-12 - 小欧 - A2-内部环(方案4.2.3步骤3): FileSafetyConfig 导入改 models.py, cleanup_expired_backups 导入改 operation_maintenance.py
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件内部 import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-10-15 北京老陈裁定(YAGNI·名副其实) - 删 set/get/clear_backup_paths 与 _backup_path/_config_path/_backup_lock 及 threading import:
#   实测三者【零调用方】(app+tests 全仓仅 config_routes.py 两处注释记载该 import 早已移除), 且与 backup_to_recycle_bin
#   职责无关(前者是模块级路径状态存取, 后者是备份动作), 属 SRP 违反 + backward 残留。
#   处置选【删除】而非拆到新模块 — 拆过去只是给死代码搬家(YAGNI)。
#   现本文件只剩一件事: 把文件/目录备份到回收站, 名实相符。
"""
operation_backup — 文件/目录备份到回收站

职责: 备份文件/目录到回收站(删除前的保险), 备份完成后触发过期清理。
      备份路径的配置存取已于 2026-10-15 删除(YAGNI, 零调用方), 本模块现无任何模块级可变状态。
小欧 2026-06-18
"""
import os
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.logger import logger
from app.utils.path_utils import to_win_long_path
from app.utils.time_utils import timestamp_for_filename
from app.safety.file_safety_config import FileSafetyConfig
from app.safety.operation_maintenance import cleanup_expired_backups


def backup_to_recycle_bin(source_path: Path) -> Optional[Path]:
    r"""备份文件到回收站 — 小欧 2026-08-11 长路径支持: 源/目标加\\?\前缀,
    解决深嵌套目录(递归自复制套娃)备份时 WinError 206 路径超长整体失败。
    """
    config = FileSafetyConfig()
    try:
        timestamp = timestamp_for_filename()
        backup_dir = config.RECYCLE_BIN_PATH / f"{timestamp}_{uuid4().hex[:8]}"
        os.makedirs(to_win_long_path(backup_dir), exist_ok=True)
        backup_path = backup_dir / source_path.name
        src_long = to_win_long_path(source_path)
        dst_long = to_win_long_path(backup_path)
        if os.path.isdir(src_long):
            shutil.copytree(src_long, dst_long)
        else:
            shutil.copy2(src_long, dst_long)
        logger.info(f"File backed up to recycle bin: {source_path} -> {backup_path}")
        cleanup_expired_backups()
        return backup_path
    except Exception as e:
        logger.warning(f"Failed to backup file to recycle bin: {e}")  # 2026-08-11 小欧 error→warning: 备份失败不阻断操作, 仅提示(北京老陈驱动)
        return None

