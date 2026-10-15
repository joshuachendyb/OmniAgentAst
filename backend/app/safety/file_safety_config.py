# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 从 operation_record.py 独立(A2-内部环, 方案4.2.3步骤1): FileSafetyConfig 整体复制, 逻辑一字不改,
#   仅新增 from app.config import get_config / from pathlib import Path 依赖导入; operation_record.py 同步删除原类改为导入
# 2026-10-15 北京老陈裁定(名副其实) - models.py 更名 file_safety_config.py:
#   本文件全部内容只有 FileSafetyConfig 一个类, 且其自身 docstring 写"文件安全操作配置" ——
#   与泛化名 models("数据模型"泛指)毫无对应, 属命名即契约失守; 现名与职责一一对应。
#   类体一字未改, git mv 保留文件历史。
"""
file_safety_config — 文件安全操作配置

职责: 文件安全操作配置(回收站路径/保留天数/容量上限/报告路径), 供 operation_backup/
      operation_record/operation_maintenance 共用, 消除循环依赖。
      本模块只定义配置, 不含任何行为函数。
小欧 2026-08-12 A2-内部环拆分
"""
from pathlib import Path

from app.config import get_config


class FileSafetyConfig:
    """文件安全操作配置 — 小欧 2026-07-10 从 config.py 合并至此"""
    RECYCLE_BIN_PATH: Path = Path.home() / ".omniagent" / "recycle_bin"
    BACKUP_RETENTION_DAYS: int = 5
    RECYCLE_BIN_MAX_SIZE_GB: int = 10
    PROJECT_ROOT: Path = Path(get_config().get_project_root())
    REPORT_PATH: Path = PROJECT_ROOT / "reports"

    @classmethod
    def ensure_directories(cls):
        cls.RECYCLE_BIN_PATH.mkdir(parents=True, exist_ok=True)
        cls.REPORT_PATH.mkdir(parents=True, exist_ok=True)
