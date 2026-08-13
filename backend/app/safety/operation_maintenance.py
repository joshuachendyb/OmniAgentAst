
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 从 operation_cleanup.py 承接清理职责(A2-内部环, 方案4.2.3步骤2): cleanup_expired_backups/_get_folder_size/_cleanup_by_size 整体复制,
#   FileSafetyConfig 导入改 app.services.safety.models(原 operation_record, 已独立); 其余逻辑一字不改
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件内部 import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-13 - 小沈 - P1: remove_readonly 延迟导入改从 app.utils.file_utils 直接导入(消除 safety→tools 实现依赖)
# 2026-08-13 - 小欧 - 三堂会审修复#14: cleanup_expired_backups 删完过期备份(形态 backup_dir时间戳uuid/源名)后,
#   父时间戳目录若空则顺手删除(原仅靠超限清理 _cleanup_by_size 兜底, 空时间戳目录残留); 长路径+空判定
# 2026-08-13 - 小沈 - 三堂会审修复#15: E2E p0_08 发现并发竞态(多工具并行各自 backup→各自 cleanup 同批过期记录):
#   (1)加进程内锁 _cleanup_lock 串行化 cleanup, 锁内重查DB, 后进线程见文件已删→exists=False跳过, 天然幂等
#   (2)FileNotFoundError(目标已删=目标达成) 降为 debug, 不再报 ERROR
#   (3)PermissionError(文件被占用/只读残留) 降为 warning, 下次再清; 与 backup_to_recycle_bin 备份失败降warning策略一致
"""
operation_maintenance — 备份回收站维护

职责: 清理过期备份文件 + 回收站超限清理(归口维护职责, 与备份职责 operation_backup 解耦)
小欧 2026-08-12 承接原 operation_cleanup.py
"""
import os
import shutil
import threading
from pathlib import Path

_cleanup_lock = threading.Lock()  # #15: 并发串行化清理, 防多工具并行 backup 各自 cleanup 竞态 — 小沈 2026-08-13

from app.db import db
from app.logger import logger
from app.utils.path_utils import to_win_long_path
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区
from app.utils.file_utils import remove_readonly  # P1: 从 utils 导入 — 小沈 2026-08-13


def _get_folder_size(path: Path) -> int:
    """递归计算文件夹总字节数（长路径支持: 深嵌套子项普通Path无法遍历, 需\\?\前缀）"""
    total = 0
    try:
        for entry in Path(to_win_long_path(path)).rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def _cleanup_by_size() -> int:
    """总大小超过上限时，从最旧的备份开始删"""
    from app.safety.models import FileSafetyConfig
    config = FileSafetyConfig()
    max_bytes = config.RECYCLE_BIN_MAX_SIZE_GB * 1024 ** 3
    recycle_path = config.RECYCLE_BIN_PATH
    if not recycle_path.exists():
        return 0

    total = _get_folder_size(recycle_path)
    if total <= max_bytes:
        return 0

    folders = sorted(
        [p for p in recycle_path.iterdir() if p.is_dir()],
        key=lambda p: p.name,
    )
    count = 0
    for folder in folders:
        if total <= max_bytes:
            break
        try:
            folder_size = _get_folder_size(folder)
            # onerror解决Windows下只读文件被copy2备份后属性锁死的问题; 长路径rmtree带\\?\前缀递归删内部超长子项
            shutil.rmtree(to_win_long_path(folder), onerror=remove_readonly)
            total -= folder_size
            count += 1
            logger.info(f"Size cleanup: removed {folder.name} (saved {folder_size / 1024**3:.2f}GB)")
        except Exception as e:
            logger.error(f"Failed to size-cleanup {folder}: {e}")
    return count


def cleanup_expired_backups() -> int:
    """清理过期的备份文件 + 超出大小上限时清理最旧的
    
    shutil.rmtree加onerror是因为Windows下只读文件+备份文件属性继承会导致[WinError 5]
    #15: 加锁串行化, 防多工具并行 backup 各自 cleanup 同批过期记录竞态(见文件头编辑历史) — 小沈 2026-08-13
    """
    with _cleanup_lock:
        return _cleanup_expired_backups_locked()


def _cleanup_expired_backups_locked() -> int:
    count = 0
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT backup_path FROM file_operations WHERE backup_expires_at < ? AND backup_path IS NOT NULL',
                (get_local_iso_timestamp(),),
            )
            rows = cursor.fetchall()
            for (backup_path,) in rows:
                try:
                    path = Path(backup_path)
                    long_path = to_win_long_path(path)
                    if os.path.exists(long_path):
                        if os.path.isdir(long_path):
                            # onerror解决Windows下只读文件备份后无法删除的问题; 长路径rmtree递归删内部超长子项
                            shutil.rmtree(long_path, onerror=remove_readonly)
                        else:
                            # 只读文件: chmod加写权限后再删(同remove_readonly逻辑) — 小欧 2026-07-26
                            os.chmod(long_path, os.stat(long_path).st_mode | 0o200)
                            try:
                                os.unlink(long_path)
                            except PermissionError:
                                # 首次chmod可能不够(Windows只读属性), 再试一次更激进
                                os.chmod(long_path, 0o666)
                                os.unlink(long_path)
                        count += 1
                        logger.info(f"Cleaned up expired backup: {backup_path}")
                        # #14修复: 备份形态为 backup_dir(时间戳uuid)/源名, 删完源后父时间戳目录可能变空,
                        #   原仅靠超限清理(_cleanup_by_size)兜底才清 → 此处删空父目录, 不留空壳 — 小欧 2026-08-13
                        _parent_lp = to_win_long_path(path.parent)
                        try:
                            if os.path.isdir(_parent_lp) and not os.listdir(_parent_lp):
                                os.rmdir(_parent_lp)
                                logger.info(f"Cleaned up empty backup dir: {path.parent}")
                        except Exception as _e:
                            logger.debug(f"Empty backup dir cleanup skipped: {_e}")
                except FileNotFoundError:
                    # #15: 目标已不存在 = 清理目标已达成(并发其他线程已删/上次已删), 幂等视为成功 — 小沈 2026-08-13
                    logger.debug(f"Backup already gone (idempotent skip): {backup_path}")
                except PermissionError as e:
                    # #15: 文件被占用/只读残留, 本次删不动, 留待下次清理; 不视为严重错误 — 小沈 2026-08-13
                    logger.warning(f"Backup cleanup deferred (access denied): {backup_path}: {e}")
                except Exception as e:
                    logger.error(f"Failed to cleanup backup {backup_path}: {e}")
        count += _cleanup_by_size()
        return count
    except Exception as e:
        logger.error(f"Failed to cleanup expired backups: {e}")
        return count
