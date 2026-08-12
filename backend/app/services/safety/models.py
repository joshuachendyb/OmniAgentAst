# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 从 operation_record.py 独立(A2-内部环, 方案4.2.3步骤1): FileSafetyConfig 整体复制, 逻辑一字不改,
#   仅新增 from app.config import get_config / from pathlib import Path 依赖导入; operation_record.py 同步删除原类改为导入
"""
models — safety 层共享数据模型

职责: 文件安全操作配置等共享数据类, 供 operation_backup/operation_record/operation_maintenance 共用, 消除循环依赖
小欧 2026-08-12 A2-内部环拆分
"""
from pathlib import Path

from app.config import get_config


class FileSafetyConfig:
    """文件安全操作配置 — 小欧 2026-07-10 从 config.py 合并至此 C-10"""
    RECYCLE_BIN_PATH: Path = Path.home() / ".omniagent" / "recycle_bin"
    BACKUP_RETENTION_DAYS: int = 5
    RECYCLE_BIN_MAX_SIZE_GB: int = 10
    PROJECT_ROOT: Path = Path(get_config().get_project_root())
    REPORT_PATH: Path = PROJECT_ROOT / "reports"

    @classmethod
    def ensure_directories(cls):
        cls.RECYCLE_BIN_PATH.mkdir(parents=True, exist_ok=True)
        cls.REPORT_PATH.mkdir(parents=True, exist_ok=True)
