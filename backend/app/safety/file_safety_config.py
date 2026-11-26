# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 从 operation_record.py 独立(A2-内部环, 方案4.2.3步骤1): FileSafetyConfig 整体复制, 逻辑一字不改,
#   仅新增 from app.config import get_config / from pathlib import Path 依赖导入; operation_record.py 同步删除原类改为导入
# 2026-10-15 北京老陈裁定(名副其实) - models.py 更名 file_safety_config.py:
#   本文件全部内容只有 FileSafetyConfig 一个类, 且其自身 docstring 写"文件安全操作配置" ——
#   与泛化名 models("数据模型"泛指)毫无对应, 属命名即契约失守; 现名与职责一一对应。
#   类体一字未改, git mv 保留文件历史。
# 2026-11-21 小欧 - 回收站目录回归数据目录唯一解析点: 原 RECYCLE_BIN_PATH 硬编码 Path.home()/.omniagent,
#   绕过 resolve_db_dir(), 设了 OMNI_DATA_DIR 仍写真盘(测试够得到真实用户目录); 改为类方法惰性解析
#   (不在导入期冻结, 与 db.get_conn 同款惰性口径), 默认值不变仍是 ~/.omniagent/recycle_bin。
#   同时删除 PROJECT_ROOT/REPORT_PATH/ensure_directories: 全库零调用方(死代码), 一旦被调就在用户项目根建
#   reports/, 属目录污染 — 小欧-2026-11-21
"""
file_safety_config — 文件安全操作配置

职责: 文件安全操作配置(回收站路径/保留天数/容量上限), 供 operation_backup/
      operation_record/operation_maintenance 共用, 消除循环依赖。
      本模块只定义配置, 不含任何行为函数(回收站目录解析是纯派生, 不建目录)。
小欧 2026-08-12 A2-内部环拆分
"""
from pathlib import Path

from app.db.database import resolve_db_dir


class FileSafetyConfig:
    """文件安全操作配置 — 小欧 2026-07-10 从 config.py 合并至此"""

    BACKUP_RETENTION_DAYS: int = 5
    RECYCLE_BIN_MAX_SIZE_GB: int = 10

    @classmethod
    def recycle_bin_path(cls) -> Path:
        """回收站根目录: 数据目录唯一解析点派生(OMNI_DATA_DIR 生效) — 小欧-2026-11-21

        惰性解析(调用时才读 env), 不在导入期冻结; 只返回路径, 建目录由写入方负责。
        """
        return resolve_db_dir() / "recycle_bin"
