# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-21 小欧 - 新建: 日志保留期清理。原日志只按大小轮转、提示词日志只增不减,
#   实测 backend/logs 317 MB / prompt-logs 202 MB 且无任何清理; 保留期取 logging.retention_days
#   (默认 10 天), 启动扫一次, 按文件 mtime 删超期档。
# 2026-11-21 小欧 - 口径改为"日志目录整体": 原按 app_*/boot_*/prompt-logs 白名单匹配, 目录里
#   任何未被登记的文件(手工副本、早期格式、pyspy 转储)都永久残留, 白名单本身就是漏网的根源。
#   改为递归遍历 LOG_DIR 全树, 超期文件一律删, 清空后空目录一并删; 目录与文件的期限同一口径。
"""log_retention — 日志目录按保留天数整体清理 — 小欧-2026-11-21

职责(SRP): 只清 LOG_DIR 内的超期文件与空目录, 不碰业务数据、不碰任务记录。
口径: 日志目录是**可再生的观测产物集聚地**, 里面的一切(运行日志、启动日志、提示词快照、
  诊断转储、供应商报告、手工副本、早期格式残留)都按同一保留期处理 —— 不设白名单,
  新增任何日志形态都自动纳入清理, 不需要回来改这里。
判定: 文件 mtime 早于 now - retention_days 天即删; 子目录内容清空后一并删;
  LOG_DIR 本身不删(它是日志根, 删了 handler 无处落盘)。
  正在被 handler 写入的文件在 Windows 上删不掉(unlink 报占用), 直接跳过, 次日自然命中。
保留天数: retention_days <= 0 表示关闭清理。
"""
import os
import time
from pathlib import Path
from typing import Dict

from app.config import get_config
from app.logger import LOG_DIR, logger


def _purge_file(path: Path, cutoff: float) -> bool:
    try:
        if path.stat().st_mtime >= cutoff:
            return False
        path.unlink()
        return True
    except OSError as e:   # 占用/权限/竞态(并发轮转)都跳过, 不让单个文件挡住整轮清理
        logger.warning(f"[log_retention] 删除失败(跳过): {path} err={e}")
        return False


def sweep_old_logs(days: int = 0) -> Dict[str, int]:
    """按保留天数清理日志目录全树, 返回 {"files": n, "dirs": m, "total": n+m} — 小欧-2026-11-21

    days <= 0 时取配置 logging.retention_days(缺省 10); 仍 <= 0 则本次不清理。
    """
    if days <= 0:
        days = int(get_config().get("logging.retention_days", 10) or 0)
    if days <= 0:
        return {"files": 0, "dirs": 0, "total": 0}

    root = Path(LOG_DIR)
    if not root.is_dir():
        return {"files": 0, "dirs": 0, "total": 0}

    cutoff = time.time() - days * 86400
    removed_files = 0
    removed_dirs = 0
    # topdown=False: 先清子目录里的文件, 回到父层时再判空删子目录; 日志根自身永不出现在 rmdir 目标里
    for cur, subdirs, files in os.walk(root, topdown=False):
        cur_path = Path(cur)
        for name in files:
            if _purge_file(cur_path / name, cutoff):
                removed_files += 1
        for name in subdirs:
            sub = cur_path / name
            try:
                if not any(sub.iterdir()):
                    sub.rmdir()
                    removed_dirs += 1
            except OSError as e:          # 并发写入刚创建文件 → 不空, 跳过
                logger.debug(f"[log_retention] 目录保留: {sub} err={e}")

    if removed_files or removed_dirs:
        logger.info(f"[log_retention] 清理超期日志: 文件 {removed_files} 个, 空目录 {removed_dirs} 个"
                    f"(保留 {days} 天)")
    return {"files": removed_files, "dirs": removed_dirs, "total": removed_files + removed_dirs}
