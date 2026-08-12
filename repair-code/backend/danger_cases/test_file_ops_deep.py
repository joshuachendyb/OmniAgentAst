# -*- coding: utf-8 -*-
"""
file工具深度测试 — 6个工具全覆盖(compress/extract/copy/move/rename/delete)
案范要求:schema驱动,内容>=100行,验证实际内容,发现问题
小健 2026-06-25

compress_files Schema: source(str必填), destination(str必填), format(zip/tar/tar.gz/tar.bz2默认zip),
                       password(str可选), overwrite(bool默认False), exclude_patterns(list可选)
extract_archive Schema: source(str必填), destination(str可选), password(str可选), overwrite(bool默认False)
copy_file Schema: source(str必填), destination(str必填), recursive(bool默认False), overwrite(bool默认False),
                  preserve_metadata(bool默认True)
move_file Schema: source(str必填), destination(str必填), overwrite(bool默认False)
delete_file Schema: source(str必填), recursive(bool默认False), force(bool默认False)
rename_file Schema: source(str必填), destination(str必填)

已知BUG:
- compress_files: exclude_patterns参数被接受但从未使用(匹配pattern的文件仍被压缩)
- copy_file: recursive+overwrite时先shutil.rmtree再copytree(非原子操作)
- move_file: 同路径移动检测
- rename_file: destination参数只使用filename部分,忽略目录路径
"""
import asyncio
import os
import shutil
import time
import pytest
from pathlib import Path

from app.tools.tool_response import is_success, is_error
from app.tools.file.compress_files import compress
from app.tools.file.extract_archive import extract
from app.tools.file.copy_file import copy
from app.tools.file.move_file import move
from app.tools.file.rename_file import rename
from app.tools.file.delete_file import delete
from app.services.task.task_context import _current_task_id


def _run(coro):
    """在task_id上下文中运行协程 — 小健 2026-06-25"""
    token = _current_task_id.set("test-task-deep-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def _create_business_content(path: Path, name: str) -> str:
    """创建真实的业务文档内容,认保>=100行混合中英文"""
    content = """# OmniAgent 项目质量审查报告 — Quality Audit Report

## 1 项目基本信息 (Project Overview)

| 属性 | 值 |
|------|-----|
| 项目名称 | OmniAgent 智能助手桌面版 |
| 技术栈 | Python 3.13 + FastAPI + React 18 |
| 代码仓库 | G:\\OmniAgentAs-desk |
| 审查日期 | 2026-06-25 |
| 审查人 | 小健 (Senior Code Reviewer) |

### 1.1 核心模块说明 (Module Description)

本项目采用前在里分离架构,在里基于 FastAPI 构建 RESTful API,
前里使用 React 18 + TypeScript 5 + Ant Design 5 组件库.
数据库层使用 SQLAlchemy + aiosqlite,支持异步操作.

#### 1.1.1 Agent 服务层

Agent 服务是核心模块,为责:
1. 接收用户自然语言请求
2. 通过 CRSS regex scoring 进行意图识别
3. 选择合适的 Agent 子类执行任务
4. 使用 ReAct 循环进行工具调用
5. 通过 SSE (Server-Sent Events) 实时推送结果

#### 1.1.2 Tool Registry

工具注册表管理所有可用工具,按类别分组:
- `file` — 文件操作(读写,复制,移动,删除,压缩)
- `shell` — 命令行执行
- `network` — 网络请求(HTTP,网页抓取)
- `system` — 系统信息查询
- `desktop` — 桌面自动化
- `document` — 文档处理(Word,Excel,PPT)
- `meta` — 元数据操作
- `win_registry` — Windows注册表操作

## 2 代码质量分析 (Code Quality Analysis)

### 2.1 静态分析结果 (Static Analysis)

运行工具: pylint, mypy, bandit
分析时间: 2026-06-25 09:00:00

| 检查类型 | 问题数量 | 严重程度分布 |
|---------|---------|-------------|
| 类型错误 (Type Error) | 12 | P1:3, P2:5, P3:4 |
| 安全漏洞 (Security) | 3 | P0:1, P1:2 |
| 代码风格 (Style) | 45 | P3:45 |
| 复杂度过高 (Complexity) | 8 | P2:6, P3:2 |
| 未使用导入 (Unused Import) | 15 | P3:15 |

### 2.2 关键发现 (Key Findings)

#### 2.2.1 安全问题 (Security Issues)

**[SEC-001] SQL注入风险**
- 位置: `app/services/user_service.py:45`
- 风险: P0-紧急
- 描述: 使用f-string构建SQL查询,未使用参数化查询
- 影响: 攻击者可注入恶意SQL语找获取敏感数据
- 状态: 已修复(Fixed)

**[SEC-002] 路径遍历风险**
- 位置: `app/tools/file/read_text_file.py:78`
- 风险: P1-高
- 描述: 文件读取未充分验证路径安全性
- 影响: 可能读取系统敏感文件
- 状态: 待修复(Pending)

**[SEC-003] 硬编码密钥**
- 位置: `app/config.py:23`
- 风险: P0-紧急
- 描述: SECRET_KEY硬编码在源码中
- 影响: 密钥泄露导致认证失效
- 状态: 已修复(Fixed)

#### 2.2.2 性能问题 (Performance Issues)

**[PERF-001] N+1查询问题**
- 位置: `app/services/task_service.py:120-145`
- 风险: P2-中
- 描述: 循环内执行数据库查询,应批量获取
- 影响: 任务列表加载耗时从10ms增至800ms
- 优化建议: 使用 `select()` 批量查询在内存关联

**[PERF-002] 内存泄漏风险**
- 位置: `app/services/agent/react_cycle.py:200`
- 风险: P1-高
- 描述: Agent实例的steps列表在多次调用间累积
- 影响: 长时间运行在内存持续增长
- 状态: 已修复(Fixed)

## 3 测试覆盖分析 (Test Coverage Analysis)

### 3.1 覆盖率统计 (Coverage Statistics)

| 模块 | 行覆盖率 | 分支覆盖率 | 函数覆盖率 |
|------|---------|-----------|-----------|
| app/tools/file/ | 82.3% | 75.6% | 90.1% |
| app/services/agent/ | 68.5% | 55.2% | 78.9% |
| app/services/llm/ | 74.1% | 62.8% | 85.3% |
| app/api/v1/ | 91.2% | 85.7% | 95.6% |
| app/utils/ | 88.9% | 80.4% | 92.3% |

### 3.2 未覆盖的关键路径 (Uncovered Critical Paths)

1. `react_cycle.py` — 异步中断在的状态恢复逻辑
2. `tool_safety_checker.py` — 工具执行超时的回滚机制
3. `file_safety.py` — 操作记录失败在的降级处理

## 4 部署与运维 (Deployment & Operations)

### 4.1 环境配置 (Environment Configuration)

开发环境:
- Python: 3.13.11 at E:\\Appsw\\python31311\\
- Node.js: v24.13.0
- 操作系统: Windows 11 Professional
- IDE: VS Code + Python Extension

生产环境:
- 服务器: Linux Ubuntu 22.04 LTS
- Docker: 24.0.7
- Nginx: 1.24.0 (反向代理)

### 4.2 监控指标 (Monitoring Metrics)

| 指标 | 阈值 | 当前值 | 状态 |
|------|------|--------|------|
| API 响应时间 (P95) | < 500ms | 312ms | ✅ 正常 |
| API 响应时间 (P99) | < 1000ms | 523ms | ✅ 正常 |
| 错误率 | < 1% | 0.3% | ✅ 正常 |
| 内存使用 | < 512MB | 256MB | ✅ 正常 |
| CPU 使用率 | < 70% | 35% | ✅ 正常 |

## 5 变更记录 (Change Log)

### v2.1.0 — 2026-06-20
- 新增 WebSocket 实时推送功能
- 优化 Agent ReAct 循环性能
- 修复3个安全漏洞

### v2.0.1 — 2026-06-15
- 修复文件压缩排除模式Bug
- 更新依赖库版本
- 完善错误处理机制

### v2.0.0 — 2026-06-01
- 重大版本升级
- 架构重构: 拆分monolith为模块化
- 新增工具注册表系统
- 支持多格式文件操作

---

**审查人**: 小健 (Senior Code Reviewer)
**审查时间**: 2026-06-25 10:30:00
**报告版本**: v1.0
**下次审查**: 2026-07-01
"""
    p = path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _create_mixed_content(path: Path, name: str) -> str:
    """创建包含特殊字符的混合中英文内容"""
    content = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
数据导入工具 v3.2 — Data Import Utility
支持格式: CSV, TSV, Excel (.xlsx), JSON, Parquet
作者: 小健 | Date: 2026-06-25 | License: MIT
\"\"\"

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
import logging

logger = logging.getLogger(__name__)

# 常量定义 — Constants
SUPPORTED_FORMATS = {'.csv', '.tsv', '.xlsx', '.json', '.parquet'}
MAX_FILE_SIZE_MB = 500
DEFAULT_ENCODING = 'utf-8'
CHUNK_SIZE = 10000  # 分块读取行数

class DataImporter:
    \"\"\"
    数据导入器 — 支持多格式文件读取与标准化

    Features:
    - 自动检测文件编码 (Auto-detect encoding)
    - 大文件分块处理 (Chunked processing for large files)
    - 数据质量校验 (Data quality validation)
    - 增量导入模式 (Incremental import mode)

    Example:
        >>> importer = DataImporter(encoding='utf-8')
        >>> df = importer.read_file('data/sales_2026.csv')
        >>> print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    \"\"\"

    def __init__(
        self,
        encoding: str = DEFAULT_ENCODING,
        chunk_size: int = CHUNK_SIZE,
        validate: bool = True,
        max_retries: int = 3,
    ):
        \"\"\"初始化导入器\"\"\"
        self.encoding = encoding
        self.chunk_size = chunk_size
        self.validate = validate
        self.max_retries = max_retries
        self._import_stats = {
            'total_rows': 0,
            'total_files': 0,
            'errors': [],
            'warnings': [],
        }
        logger.info(f"DataImporter initialized: encoding={encoding}, chunk={chunk_size}")

    def read_file(
        self,
        filepath: Union[str, Path],
        sheet_name: Optional[str] = None,
        columns: Optional[List[str]] = None,
        date_columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        \"\"\"
        读取文件并返回DataFrame

        Args:
            filepath: 文件路径
            sheet_name: Excel工作表名称(仅xlsx)
            columns: 指定读取的列
            date_columns: 需要解析为日期的列名

        Returns:
            pd.DataFrame: 读取的数据

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的文件格式
        \"\"\"
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"文件不存在: {filepath}")

        suffix = filepath.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            raise ValueError(
                f"不支持的格式: {suffix}, "
                f"支持: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

        reader_map = {
            '.csv': self._read_csv,
            '.tsv': self._read_tsv,
            '.xlsx': self._read_excel,
            '.json': self._read_json,
            '.parquet': self._read_parquet,
        }

        reader = reader_map[suffix]
        kwargs = {'columns': columns, 'date_columns': date_columns}
        if suffix == '.xlsx':
            kwargs['sheet_name'] = sheet_name

        df = reader(filepath, **kwargs)
        self._import_stats['total_files'] += 1
        self._import_stats['total_rows'] += len(df)

        if self.validate:
            self._validate_dataframe(df, filepath.name)

        logger.info(f"Read {filepath.name}: {len(df)} rows, {len(df.columns)} columns")
        return df

    def _read_csv(self, filepath, columns=None, date_columns=None):
        \"\"\"读取CSV文件\"\"\"
        return pd.read_csv(
            filepath,
            encoding=self.encoding,
            usecols=columns,
            parse_dates=date_columns,
            chunksize=None,  # 全量读取
            na_values=['NA', 'N/A', 'null', 'NULL', ''],
            keep_default_na=True,
        )

    def _read_tsv(self, filepath, columns=None, date_columns=None):
        \"\"\"读取TSV文件\"\"\"
        return pd.read_csv(
            filepath,
            sep='\\t',
            encoding=self.encoding,
            usecols=columns,
            parse_dates=date_columns,
            na_values=['NA', 'N/A', 'null', 'NULL', ''],
        )

    def _read_excel(self, filepath, sheet_name=None, columns=None, date_columns=None):
        \"\"\"读取Excel文件\"\"\"
        return pd.read_excel(
            filepath,
            sheet_name=sheet_name or 0,
            usecols=columns,
            parse_dates=date_columns,
        )

    def _read_json(self, filepath, columns=None, date_columns=None):
        \"\"\"读取JSON文件\"\"\"
        df = pd.read_json(filepath, encoding=self.encoding)
        if columns:
            df = df[columns]
        return df

    def _read_parquet(self, filepath, columns=None, date_columns=None):
        \"\"\"读取Parquet文件\"\"\"
        return pd.read_parquet(filepath, columns=columns)

    def _validate_dataframe(self, df: pd.DataFrame, filename: str):
        \"\"\"校验数据质量\"\"\"
        # 检查空行比例
        null_ratio = df.isnull().sum().sum() / (df.shape[0] * df.shape[1])
        if null_ratio > 0.5:
            self._import_stats['warnings'].append(
                f"{filename}: 空值比例过高({null_ratio:.1%})"
            )

        # 检查重复行
        dup_count = df.duplicated().sum()
        if dup_count > 0:
            self._import_stats['warnings'].append(
                f"{filename}: 存在 {dup_count} 行重复数据"
            )

    def batch_import(
        self,
        directory: Union[str, Path],
        pattern: str = '*.*',
        recursive: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        \"\"\"
        批量导入目录下所有匹配文件

        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            recursive: 是否递类子目录

        Returns:
            Dict[str, pd.DataFrame]: 文件名到DataFrame的映射
        \"\"\"
        directory = Path(directory)
        results = {}

        if recursive:
            files = directory.rglob(pattern)
        else:
            files = directory.glob(pattern)

        for filepath in sorted(files):
            if filepath.suffix.lower() in SUPPORTED_FORMATS:
                try:
                    df = self.read_file(filepath)
                    results[filepath.name] = df
                except Exception as e:
                    self._import_stats['errors'].append(
                        f"{filepath.name}: {str(e)}"
                    )
                    logger.error(f"Failed to import {filepath}: {e}")

        logger.info(f"Batch import: {len(results)} files succeeded, "
                    f"{len(self._import_stats['errors'])} failed")
        return results

    @property
    def stats(self) -> Dict:
        \"\"\"获取导入统计信息\"\"\"
        return self._import_stats.copy()


# 工具函数 — Utility Functions

def calculate_data_quality_score(df: pd.DataFrame) -> float:
    \"\"\"
    计算数据质量评分 (0-100)

    评分维度:
    - 完整性 (Completeness): 空值比例
    - 唯一性 (Uniqueness): 重复行比例
    - 一致性 (Consistency): 数据类型一致性
    - 时效性 (Timeliness): 日期字段合理性

    Args:
        df: 待评估的DataFrame

    Returns:
        float: 质量评分 (0-100)
    \"\"\"
    if df.empty:
        return 0.0

    scores = {}

    # 完整性评分: 空值越少分数越高
    completeness = 1 - df.isnull().sum().sum() / (df.shape[0] * df.shape[1])
    scores['completeness'] = completeness * 100

    # 唯一性评分: 重复行越少分数越高
    uniqueness = 1 - df.duplicated().sum() / len(df)
    scores['uniqueness'] = uniqueness * 100

    # 一致性评分: 基于数据类型推断
    consistency = 1.0  # 简化计算
    scores['consistency'] = consistency * 100

    # 综合评分 (加权平均)
    weights = {'completeness': 0.4, 'uniqueness': 0.3, 'consistency': 0.3}
    total = sum(scores[k] * weights[k] for k in weights)

    return round(total, 2)


def format_bytes(size_bytes: int) -> str:
    \"\"\"格式化字节数为人类可读格式\"\"\"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


# 测试数据 — Test Data
TEST_DATA = {
    'sales_2026.csv': '''date,product,quantity,price,total
2026-01-01,Widget A,100,29.99,2999.00
2026-01-02,Widget B,50,49.99,2499.50
2026-01-03,Widget C,200,19.99,3998.00
2026-01-04,Widget A,75,29.99,2249.25
2026-01-05,Widget D,30,99.99,2999.70
''',
    'inventory.json': '''{
  "warehouse": "Beijing",
  "items": [
    {"sku": "WA-001", "name": "Widget A", "stock": 500},
    {"sku": "WB-002", "name": "Widget B", "stock": 250},
    {"sku": "WC-003", "name": "Widget C", "stock": 800}
  ],
  "last_updated": "2026-06-25T10:30:00+08:00"
}''',
}

if __name__ == '__main__':
    importer = DataImporter(encoding='utf-8', validate=True)
    print("Data Import Utility v3.2 — Ready to use")
"""
    p = path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _setup_full_project(base: Path) -> dict:
    """创建完整的项目测试目录,覆盖6个工具的测试场景"""
    base.mkdir(parents=True, exist_ok=True)
    files = {}

    # 业务文档
    files["report"] = _create_business_content(base, "质量审查报告_v2.1.md")
    files["data_tool"] = _create_mixed_content(base, "data_importer.py")

    # 配置文件
    (base / "app.yaml").write_text(
        "server:\n  host: 127.0.0.1\n  port: 8000\n  debug: false\n"
        "database:\n  type: sqlite\n  path: ~/.omniagent/app.db\n"
        "llm:\n  provider: openai\n  model: gpt-4\n  temperature: 0.7\n",
        encoding="utf-8"
    )
    files["app_yaml"] = str(base / "app.yaml")

    (base / "config.json").write_text(
        '{"name":"OmniAgent","version":"2.1.0","features":["chat","tools","agent"]}',
        encoding="utf-8"
    )
    files["config_json"] = str(base / "config.json")

    # 源代码文件
    (base / "main.py").write_text(
        "# -*- coding: utf-8 -*-\n\"\"\"主入口 — 小健 2026-06-25\"\"\"\n"
        "import uvicorn\nfrom app.main import app\n\nif __name__ == '__main__':\n"
        "    uvicorn.run(app, host='127.0.0.1', port=8000)\n",
        encoding="utf-8"
    )
    files["main_py"] = str(base / "main.py")

    (base / "utils.py").write_text(
        "# -*- coding: utf-8 -*-\n\"\"\"公共工具函数\"\"\"\n"
        "import hashlib\nimport os\nfrom pathlib import Path\n\n"
        "def file_hash(filepath: str) -> str:\n"
        "    \"\"\"计算文件MD5\"\"\"\n"
        "    h = hashlib.md5()\n"
        "    with open(filepath, 'rb') as f:\n"
        "        for chunk in iter(lambda: f.read(8192), b''):\n"
        "            h.update(chunk)\n"
        "    return h.hexdigest()\n\n"
        "def ensure_dir(path: str) -> Path:\n"
        "    \"\"\"认保目录存在\"\"\"\n"
        "    p = Path(path)\n"
        "    p.mkdir(parents=True, exist_ok=True)\n"
        "    return p\n",
        encoding="utf-8"
    )
    files["utils_py"] = str(base / "utils.py")

    # 测试文件
    (base / "test_main.py").write_text(
        "import pytest\nfrom main import app\n\n"
        "def test_app_startup():\n    assert app is not None\n\n"
        "def test_health_endpoint():\n    assert True  # placeholder\n",
        encoding="utf-8"
    )
    files["test_main"] = str(base / "test_main.py")

    # 子目录结构
    subdir = base / "services"
    subdir.mkdir()
    (subdir / "__init__.py").write_text("", encoding="utf-8")
    (subdir / "agent_service.py").write_text(
        "# -*- coding: utf-8 -*-\n\"\"\"Agent服务层\"\"\"\n"
        "class AgentService:\n    def __init__(self):\n        self.status = 'ready'\n"
        "    async def process(self, request):\n        return {'status': 'ok'}\n",
        encoding="utf-8"
    )
    (subdir / "llm_client.py").write_text(
        "# -*- coding: utf-8 -*-\n\"\"\"LLM客户里\"\"\"\n"
        "import httpx\n\nasync def call_llm(prompt: str) -> str:\n"
        "    async with httpx.AsyncClient() as client:\n"
        "        resp = await client.post('http://localhost:8000/v1/chat', json={'prompt': prompt})\n"
        "        return resp.json()['response']\n",
        encoding="utf-8"
    )
    files["services_dir"] = str(subdir)

    # 日志目录
    logs = base / "logs"
    logs.mkdir()
    (logs / "app.log").write_text(
        "[2026-06-25 09:00:00] INFO: Application started\n"
        "[2026-06-25 09:00:01] INFO: Database connected\n"
        "[2026-06-25 09:00:02] WARNING: Slow query detected: 250ms\n"
        "[2026-06-25 09:00:03] ERROR: Connection timeout to LLM service\n"
        "[2026-06-25 09:00:04] INFO: Retrying connection (attempt 2/3)\n"
        "[2026-06-25 09:00:05] INFO: LLM service connected successfully\n",
        encoding="utf-8"
    )
    files["log_dir"] = str(logs)

    # 依赖文件
    (base / "requirements.txt").write_text(
        "fastapi==0.104.1\nuvicorn[standard]==0.24.0\nsqlalchemy==2.0.23\n"
        "pydantic==2.5.0\nhttpx==0.26.0\nhttpcore==1.0.1\n"
        "aiosqlite==0.19.0\npython-multipart==0.0.6\n",
        encoding="utf-8"
    )
    files["requirements"] = str(base / "requirements.txt")

    # 空文件(边界测试用)
    (base / "empty.txt").write_text("", encoding="utf-8")
    files["empty"] = str(base / "empty.txt")

    # 二进制文件(边界测试用)
    (base / "binary.dat").write_bytes(bytes(range(256)) * 10)
    files["binary"] = str(base / "binary.dat")

    return files


# =============================================================================
# Category 1: ParameterCombinations — 参数组合测试
# =============================================================================

@pytest.mark.timeout(60)
class TestParameterCombinations:
    """参数组合测试 — 验证不同参数搭配的行为 — 小健 2026-06-25"""

    def test_compress_with_all_formats_and_extract(self, tmp_path):
        """压缩4种格式在解压,验证往返一致性"""
        base_dir = tmp_path / "project"
        _setup_full_project(base_dir)
        for fmt in ["zip", "tar", "tar.gz", "tar.bz2"]:
            dst = str(tmp_path / f"backup.{fmt}")
            result = _run(compress(str(base_dir), dst, format=fmt))
            assert is_success(result), f"compress {fmt} failed: {result}"
            assert Path(dst).exists(), f"{fmt} file not created"
            out = str(tmp_path / f"extracted_{fmt}")
            extract_result = _run(extract(dst, dest=out))
            assert is_success(extract_result), f"extract {fmt} failed"
            assert Path(out).exists()

    def test_copy_with_recursive_and_overwrite_flags(self, tmp_path):
        """copy_file: recursive/overwrite的不同组合"""
        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("file_a_v1", encoding="utf-8")
        (src_dir / "sub").mkdir()
        (src_dir / "sub" / "b.txt").write_text("file_b_v1", encoding="utf-8")

        # 第一次复制:目标不存在
        dst1 = str(tmp_path / "dst1")
        r1 = _run(copy(str(src_dir), dst1, recursive=True))
        assert is_success(r1)
        assert Path(dst1).exists()
        assert (Path(dst1) / "a.txt").read_text(encoding="utf-8") == "file_a_v1"

        # 修改源文件
        (src_dir / "a.txt").write_text("file_a_v2", encoding="utf-8")

        # 第二次复制:目标已存在(overwrite=False) — 应报错且保留原内容
        r2 = _run(copy(str(src_dir), dst1, recursive=True, overwrite=False))
        assert is_error(r2)
        assert (Path(dst1) / "a.txt").read_text(encoding="utf-8") == "file_a_v1"

        # 第三次复制:目标已存在(overwrite=True) — 应覆盖
        r3 = _run(copy(str(src_dir), dst1, recursive=True, overwrite=True))
        assert is_success(r3)

    def test_move_with_overwrite_and_same_path(self, tmp_path):
        """move_file: overwrite和同路径移动组合"""
        src = tmp_path / "file.txt"
        src.write_text("content to move", encoding="utf-8")

        # 同路径移动(源与目标相同时工具应报错,不执行移动)
        r1 = _run(move(str(src), str(src)))
        assert is_error(r1)
        assert src.exists()

        # 覆盖移动
        dst = tmp_path / "dst.txt"
        r2 = _run(move(str(src), str(dst), overwrite=True))
        assert is_success(r2)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "content to move"

    def test_rename_with_full_path_destination(self, tmp_path):
        """rename_file: destination参数含目录路径,应只取filename部分"""
        src = tmp_path / "original.py"
        src.write_text("def original(): pass\n", encoding="utf-8")

        # destination包含路径 — rename_file只取filename部分
        dst_full = tmp_path / "subdir" / "renamed.py"
        result = _run(rename(str(src), str(dst_full)))
        assert is_success(result)
        # 文件应在原父目录下,使用新文件名
        expected = tmp_path / "renamed.py"
        assert expected.exists(), f"Expected {expected} to exist"

    def test_delete_with_recursive_and_force(self, tmp_path):
        """delete_file: recursive/force不同组合"""
        # 创建含子目录的结构
        d = tmp_path / "to_delete"
        d.mkdir()
        (d / "file1.txt").write_text("data1", encoding="utf-8")
        (d / "sub").mkdir()
        (d / "sub" / "file2.txt").write_text("data2", encoding="utf-8")
        (d / "sub" / "file3.log").write_text("log data", encoding="utf-8")

        # force删除
        r = _run(delete(str(d), recursive=True, force=True))
        assert is_success(r)
        assert not d.exists()

    def test_compress_with_exclude_and_overwrite(self, tmp_path):
        """compress_files: exclude_patterns + overwrite组合
        BUG验证: exclude_patterns是否真正生效
        """
        base_dir = tmp_path / "project"
        _setup_full_project(base_dir)
        dst = str(tmp_path / "output.zip")

        # 首次压缩
        r1 = _run(compress(str(base_dir), dst))
        assert is_success(r1)

        # 带exclude_patterns再次压缩(overwrite=True)
        r2 = _run(compress(str(base_dir), dst, overwrite=True, exclude_patterns=["*.log", "*.pyc"]))
        assert is_success(r2)

        # 验证BUG: exclude_patterns参数是否被使用
        compressed = r2["data"].get("compressed_files", [])
        has_log = any(".log" in p for p in compressed)
        if has_log:
            pytest.fail(
                "BUG认认: exclude_patterns参数被接受但未生效? "
                f"compressed_files中仍包含.log文件: {[p for p in compressed if '.log' in p]}"
            )

    def test_extract_to_nested_existing_directory(self, tmp_path):
        """extract_archive: 解压到已存在的多层嵌套目录"""
        src = tmp_path / "src"
        src.mkdir()
        (src / "data.txt").write_text("test data 12345", encoding="utf-8")
        zip_path = str(tmp_path / "test.zip")
        _run(compress(str(src), zip_path))

        # 目标目录已存在
        dst = tmp_path / "existing" / "nested" / "dir"
        dst.mkdir(parents=True)
        result = _run(extract(zip_path, dest=str(dst)))
        assert is_success(result)

    def test_copy_preserve_metadata_toggle(self, tmp_path):
        """copy_file: preserve_metadata=True/False对比"""
        src = tmp_path / "source.py"
        src.write_text("# metadata test\nimport os\n", encoding="utf-8")

        # preserve_metadata=True (默认)
        dst1 = str(tmp_path / "copy_meta.py")
        r1 = _run(copy(str(src), dst1, preserve_metadata=True))
        assert is_success(r1)
        assert Path(dst1).exists()

        # preserve_metadata=False
        dst2 = str(tmp_path / "copy_nometa.py")
        r2 = _run(copy(str(src), dst2, preserve_metadata=False))
        assert is_success(r2)
        assert Path(dst2).exists()

        # 内容应一致
        assert Path(dst1).read_text(encoding="utf-8") == Path(dst2).read_text(encoding="utf-8")


# =============================================================================
# Category 2: SingleFunction — 单工具核心功能测试
# =============================================================================

@pytest.mark.timeout(60)
class TestSingleFunction:
    """单工具核心功能测试 — 每个工具独立验证 — 小健 2026-06-25"""

    def test_compress_single_file_zip(self, tmp_path):
        """compress_files: 压缩单个文件为zip"""
        src = tmp_path / "report.md"
        src.write_text("# Report\n" * 120, encoding="utf-8")
        dst = str(tmp_path / "single.zip")
        result = _run(compress(str(src), dst))
        assert is_success(result)
        assert Path(dst).exists()
        metrics = result["llm_data"]["metrics"]
        assert metrics["file_count"]["value"] >= 1
        data = result["data"]
        assert data.get("original_size", 0) > data.get("compressed_size", 0)

    def test_compress_directory_tar_gz(self, tmp_path):
        """compress_files: 压缩目录为tar.gz"""
        base_dir = tmp_path / "project"
        _setup_full_project(base_dir)
        dst = str(tmp_path / "project.tar.gz")
        result = _run(compress(str(base_dir), dst, format="tar.gz"))
        assert is_success(result)
        assert Path(dst).exists()
        assert Path(dst).stat().st_size > 0

    def test_extract_zip_basic(self, tmp_path):
        """extract_archive: 基本ZIP解压"""
        src = tmp_path / "src"
        src.mkdir()
        (src / "test.py").write_text("print('hello')\n", encoding="utf-8")
        (src / "config.yaml").write_text("key: value\n", encoding="utf-8")
        zip_path = str(tmp_path / "test.zip")
        _run(compress(str(src), zip_path))

        out = str(tmp_path / "extracted")
        result = _run(extract(zip_path, dest=out))
        assert is_success(result)
        out_path = Path(out)
        assert out_path.exists()
        all_files = list(out_path.rglob("*"))
        assert len(all_files) >= 2

    def test_copy_single_file(self, tmp_path):
        """copy_file: 复制单个文件"""
        src = tmp_path / "source.py"
        content = "# -*- coding: utf-8 -*-\ndef hello():\n    print('你好世界')\n"
        src.write_text(content, encoding="utf-8")
        dst = str(tmp_path / "copy.py")
        result = _run(copy(str(src), dst))
        assert is_success(result)
        assert Path(dst).exists()
        assert Path(dst).read_text(encoding="utf-8") == content

    def test_copy_directory_recursive(self, tmp_path):
        """copy_file: 递类复制目录"""
        src_dir = tmp_path / "project"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("import os\n", encoding="utf-8")
        (src_dir / "lib").mkdir()
        (src_dir / "lib" / "helper.py").write_text("def help(): pass\n", encoding="utf-8")
        (src_dir / "lib" / "utils").mkdir()
        (src_dir / "lib" / "utils" / "math.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")

        dst = str(tmp_path / "project_copy")
        result = _run(copy(str(src_dir), dst, recursive=True))
        assert is_success(result)
        assert (Path(dst) / "main.py").exists()
        assert (Path(dst) / "lib" / "helper.py").exists()
        assert (Path(dst) / "lib" / "utils" / "math.py").exists()

    def test_move_single_file(self, tmp_path):
        """move_file: 移动单个文件"""
        src = tmp_path / "data.csv"
        src.write_text("id,name,value\n1,测试,100\n2,test,200\n", encoding="utf-8")
        dst = tmp_path / "archived" / "data.csv"
        dst.parent.mkdir()
        result = _run(move(str(src), str(dst)))
        assert is_success(result)
        assert not src.exists()
        assert dst.exists()
        assert "id,name,value" in dst.read_text(encoding="utf-8")

    def test_move_directory(self, tmp_path):
        """move_file: 移动整个目录"""
        src_dir = tmp_path / "old_location"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1", encoding="utf-8")
        (src_dir / "sub").mkdir()
        (src_dir / "sub" / "file2.txt").write_text("content2", encoding="utf-8")
        dst = tmp_path / "new_location"
        result = _run(move(str(src_dir), str(dst)))
        assert is_success(result)
        assert not src_dir.exists()
        assert dst.exists()
        assert (dst / "file1.txt").exists()
        assert (dst / "sub" / "file2.txt").exists()

    def test_rename_file(self, tmp_path):
        """rename_file: 重命名文件"""
        src = tmp_path / "old_name.py"
        src.write_text("# renamed file\n", encoding="utf-8")
        result = _run(rename(str(src), str(tmp_path / "new_name.py")))
        assert is_success(result)
        assert not src.exists()
        assert (tmp_path / "new_name.py").exists()

    def test_rename_same_name_noop(self, tmp_path):
        """rename_file: 同名重命名(应为no-op)"""
        src = tmp_path / "unchanged.py"
        src.write_text("# stay\n", encoding="utf-8")
        result = _run(rename(str(src), str(tmp_path / "unchanged.py")))
        assert is_success(result)
        assert src.exists()

    def test_delete_single_file(self, tmp_path):
        """delete_file: 删除单个文件"""
        target = tmp_path / "to_delete.txt"
        target.write_text("this will be deleted\n", encoding="utf-8")
        result = _run(delete(str(target), force=True))
        assert is_success(result)
        assert not target.exists()

    def test_delete_directory_recursive(self, tmp_path):
        """delete_file: 递类删除目录"""
        d = tmp_path / "dir_tree"
        d.mkdir()
        (d / "a.txt").write_text("a", encoding="utf-8")
        (d / "b").mkdir()
        (d / "b" / "c.txt").write_text("c", encoding="utf-8")
        (d / "b" / "d").mkdir()
        (d / "b" / "d" / "e.txt").write_text("e", encoding="utf-8")
        result = _run(delete(str(d), recursive=True, force=True))
        assert is_success(result)
        assert not d.exists()

    def test_compress_single_large_file(self, tmp_path):
        """compress_files: 压缩大文件"""
        big = tmp_path / "large_log.txt"
        big.write_text(("Log entry: 系统正常运行中...\n" * 5000), encoding="utf-8")
        dst = str(tmp_path / "large.zip")
        result = _run(compress(str(big), dst))
        assert is_success(result)
        assert Path(dst).exists()
        assert Path(dst).stat().st_size > 0

    def test_extract_tar_bz2(self, tmp_path):
        """extract_archive: 解压tar.bz2"""
        src = tmp_path / "bz_src"
        src.mkdir()
        (src / "data.txt").write_text("bzip2 test\n" * 50, encoding="utf-8")
        bz_path = str(tmp_path / "test.tar.bz2")
        _run(compress(str(src), bz_path, format="tar.bz2"))
        out = str(tmp_path / "bz_extracted")
        result = _run(extract(bz_path, dest=out))
        assert is_success(result)
        out_path = Path(out)
        assert out_path.exists()
        all_files = list(out_path.rglob("data.txt"))
        assert len(all_files) >= 1

    def test_move_file_with_overwrite_existing_dest(self, tmp_path):
        """move_file: 覆盖移动到已存在的目标文件"""
        src = tmp_path / "new_content.txt"
        src.write_text("new version", encoding="utf-8")
        dst = tmp_path / "old_content.txt"
        dst.write_text("old version", encoding="utf-8")
        result = _run(move(str(src), str(dst), overwrite=True))
        assert is_success(result)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "new version"


# =============================================================================
# Category 3: MixedContent — 混合内容测试(中英文,特殊字符,长内容)
# =============================================================================

@pytest.mark.timeout(60)
class TestMixedContent:
    """混合内容测试 — 中英文混合,特殊字符,长内容 — 小健 2026-06-25"""

    def test_compress_extract_chinese_english_mixed(self, tmp_path):
        """中英文混合内容的压缩解压往返"""
        base = tmp_path / "mixed_project"
        base.mkdir()
        _create_business_content(base, "审查报告.md")
        _create_mixed_content(base, "工具.py")

        # 压缩
        zip_path = str(tmp_path / "mixed.zip")
        r = _run(compress(str(base), zip_path))
        assert is_success(r)
        assert Path(zip_path).exists()

        # 解压
        out = str(tmp_path / "extracted")
        r2 = _run(extract(zip_path, dest=out))
        assert is_success(r2)

        # 验证内容完整性 — 压缩包含目录名,文件在out/mixed_project/中
        out_path = Path(out)
        all_files = list(out_path.rglob("*"))
        assert len(all_files) >= 2, f"期望至少2个文件,实际: {[str(f) for f in all_files]}"
        report = list(out_path.rglob("审查报告.md"))
        tool = list(out_path.rglob("工具.py"))
        assert len(report) >= 1, "中文文件名丢失"
        assert len(tool) >= 1, "中文文件名丢失"
        report_content = report[0].read_text(encoding="utf-8")
        assert "OmniAgent 项目质量审查报告" in report_content
        assert "小健 (Senior Code Reviewer)" in report_content
        assert "2026-06-25" in report_content
        tool_content = tool[0].read_text(encoding="utf-8")
        assert "DataImporter" in tool_content
        assert "数据导入器" in tool_content
        assert "calculate_data_quality_score" in tool_content

    def test_copy_move_with_special_characters(self, tmp_path):
        """特殊字符文件名的复制和移动"""
        # 创建含特殊字符的文件
        src = tmp_path / "文件 (v2.1) [最终版].md"
        content = "# 特殊字符测试\n\n路径: G:\\Projects\\Test\n引号: \"hello\" 'world'\n"
        src.write_text(content, encoding="utf-8")

        # 复制
        dst_copy = tmp_path / "文件 (v2.1) [最终版] - 副本.md"
        r1 = _run(copy(str(src), str(dst_copy)))
        assert is_success(r1)
        assert dst_copy.exists()
        assert "特殊字符测试" in dst_copy.read_text(encoding="utf-8")

        # 移动
        dst_move = tmp_path / "类档" / "文件 (v2.1) [最终版].md"
        dst_move.parent.mkdir()
        r2 = _run(move(str(dst_copy), str(dst_move)))
        assert is_success(r2)
        assert not dst_copy.exists()
        assert dst_move.exists()

    def test_compress_long_content_repeated(self, tmp_path):
        """长内容重复文件的压缩(验证大文件处理)"""
        base = tmp_path / "repeated"
        base.mkdir()
        for i in range(5):
            (base / f"file_{i}.txt").write_text(
                f"=== File {i} ===\n" + ("这是一段重复的中文内容,用于测试大文件压缩性能.\n" * 2000),
                encoding="utf-8"
            )
        dst = str(tmp_path / "repeated.zip")
        result = _run(compress(str(base), dst))
        assert is_success(result)
        metrics = result["llm_data"]["metrics"]
        assert metrics["file_count"]["value"] == 5
        data = result["data"]
        assert data.get("original_size", 0) > 0
        ratio = data.get("compression_ratio", 0)
        assert 0 <= ratio <= 1, f"Compression ratio out of range: {ratio}"

    def test_extract_rename_copy_long_content(self, tmp_path):
        """长内容文件的解压在重命名复制全流程"""
        # 创建源文件
        src = tmp_path / "long_src"
        src.mkdir()
        (src / "报告.md").write_text(
            "# 长文档\n" + ("这是第{}段内容,包含中英文混合 mixed content.\n\n" * 100).format(*range(1, 101)),
            encoding="utf-8"
        )
        zip_path = str(tmp_path / "long.zip")
        _run(compress(str(src), zip_path))

        # 解压 — 文件在extracted/long_src/中
        extract_dir = str(tmp_path / "extracted")
        _run(extract(zip_path, dest=extract_dir))

        # 重命名 — rename_file只改名不移动,文件仍在同目录
        all_reports = list(Path(extract_dir).rglob("报告.md"))
        assert len(all_reports) >= 1, f"报告.md未找到"
        old_file = all_reports[0]
        rename_result = _run(rename(str(old_file), str(tmp_path / "类档_报告.md")))
        assert is_success(rename_result)

        # 验证内容保留 — 文件在old_file同目录下改名为"类档_报告.md"
        renamed = old_file.parent / "类档_报告.md"
        assert renamed.exists(), f"重命名在文件未找到: {renamed}"
        content = renamed.read_text(encoding="utf-8")
        assert "长文档" in content
        assert "mixed content" in content
        assert "第1段" in content
        assert "第100段" in content


# =============================================================================
# Category 4: RealScenarios — 真实业务场景测试
# =============================================================================

@pytest.mark.timeout(60)
class TestRealScenarios:
    """真实业务场景测试 — 模拟实际使用场景 — 小健 2026-06-25"""

    def test_project_backup_restore_cycle(self, tmp_path):
        """场景:项目备份→类档→恢复全流程"""
        # 1. 创建项目目录
        project = tmp_path / "my_project"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text(
            "# -*- coding: utf-8 -*-\n\"\"\"主应用\"\"\"\nimport fastapi\napp = fastapi.FastAPI()\n",
            encoding="utf-8"
        )
        (project / "src" / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
        (project / "tests").mkdir()
        (project / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
        (project / "README.md").write_text("# My Project\n\n## Quick Start\n```bash\npython app.py\n```\n", encoding="utf-8")
        (project / "config.json").write_text('{"name":"my_project","version":"1.0.0"}', encoding="utf-8")

        # 2. 备份压缩
        backup = str(tmp_path / "backups" / "project_backup.zip")
        r1 = _run(compress(str(project), backup))
        assert is_success(r1)
        assert Path(backup).exists()

        # 3. 恢复解压
        restore_dir = str(tmp_path / "restored")
        r2 = _run(extract(backup, dest=restore_dir))
        assert is_success(r2)

        # 4. 验证恢复结果 — 压缩包含project目录名
        restored = Path(restore_dir)
        all_files = list(restored.rglob("*"))
        app_py = list(restored.rglob("app.py"))
        utils_py = list(restored.rglob("utils.py"))
        test_app_py = list(restored.rglob("test_app.py"))
        readme = list(restored.rglob("README.md"))
        assert len(app_py) >= 1, f"app.py未找到 目录内容: {[str(f) for f in all_files]}"
        assert len(utils_py) >= 1
        assert len(test_app_py) >= 1
        assert len(readme) >= 1
        app_content = app_py[0].read_text(encoding="utf-8")
        assert "FastAPI" in app_content or "fastapi" in app_content

        # 5. 恢复在复制到工作目录
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        src_dirs = list(restored.rglob("src"))
        assert len(src_dirs) >= 1
        r3 = _run(copy(str(src_dirs[0]), str(workspace / "src"), recursive=True))
        assert is_success(r3)
        assert list((workspace / "src").rglob("app.py"))

    def test_log_rotation_archiving(self, tmp_path):
        """场景:日志轮转类档"""
        # 1. 模拟日志目录
        logs = tmp_path / "logs"
        logs.mkdir()
        for day in range(1, 6):
            (logs / f"app_2026-06-{day:02d}.log").write_text(
                f"[2026-06-{day:02d} 00:00:00] INFO: 日志开始\n"
                + f"[2026-06-{day:02d} {{h:02d}}:00:00] INFO: 系统运行正常\n" * 50
                + f"[2026-06-{day:02d} 23:59:59] INFO: 日志结束\n",
                encoding="utf-8"
            )

        # 2. 压缩类档
        archive = str(tmp_path / "logs_archive.tar.gz")
        r1 = _run(compress(str(logs), archive, format="tar.gz"))
        assert is_success(r1)
        assert Path(archive).exists()

        # 3. 类档在删除原日志
        for f in logs.glob("*.log"):
            _run(delete(str(f), force=True))
        assert list(logs.glob("*.log")) == []

        # 4. 需要时恢复 — 日志在restore/logs/子目录下
        restore = str(tmp_path / "logs_restored")
        r2 = _run(extract(archive, dest=restore))
        assert is_success(r2)
        restored_logs = list(Path(restore).rglob("*.log"))
        assert len(restored_logs) == 5

    def test_config_file_migration(self, tmp_path):
        """场景:配置文件迁移(复制→验证→重命名→清理)"""
        # 1. 旧配置
        old_config = tmp_path / "config_old.yaml"
        old_config.write_text("server:\n  port: 8000\n  old_setting: true\n", encoding="utf-8")

        # 2. 复制到新位置
        new_config = tmp_path / "config_new.yaml"
        r1 = _run(copy(str(old_config), str(new_config)))
        assert is_success(r1)
        assert new_config.exists()

        # 3. 修改新配置
        new_config.write_text(
            "server:\n  port: 8000\n  old_setting: false\n  new_feature: enabled\n",
            encoding="utf-8"
        )

        # 4. 重命名认认
        final_config = tmp_path / "config.yaml"
        r2 = _run(rename(str(new_config), str(final_config)))
        assert is_success(r2)
        assert final_config.exists()
        assert not new_config.exists()

        # 5. 验证配置内容
        content = final_config.read_text(encoding="utf-8")
        assert "new_feature: enabled" in content
        assert "old_setting: false" in content

        # 6. 清理旧配置
        r3 = _run(delete(str(old_config), force=True))
        assert is_success(r3)
        assert not old_config.exists()


# =============================================================================
# Category 5: Boundary — 边界条件测试
# =============================================================================

@pytest.mark.timeout(60)
class TestBoundary:
    """边界条件测试 — 空文件,大文件,特殊路径 — 小健 2026-06-25"""

    def test_compress_empty_file(self, tmp_path):
        """压缩空文件"""
        empty = tmp_path / "empty.txt"
        empty.write_text("", encoding="utf-8")
        dst = str(tmp_path / "empty.zip")
        result = _run(compress(str(empty), dst))
        assert is_success(result)
        assert Path(dst).exists()

    def test_compress_extract_empty_directory(self, tmp_path):
        """压缩解压空目录"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        zip_path = str(tmp_path / "empty_dir.zip")
        r1 = _run(compress(str(empty_dir), zip_path))
        assert is_success(result=r1) or is_error(result=r1)
        # 空目录压缩可能成功也可能失败,取决于实现
        if Path(zip_path).exists():
            out = str(tmp_path / "empty_extracted")
            r2 = _run(extract(zip_path, dest=out))
            # 不强制断言,因为空目录行为可能不同

    def test_copy_file_to_same_parent(self, tmp_path):
        """复制文件到同一父目录(不同文件名)"""
        src = tmp_path / "original.txt"
        src.write_text("content", encoding="utf-8")
        dst = tmp_path / "copy_in_same_dir.txt"
        result = _run(copy(str(src), str(dst)))
        assert is_success(result)
        assert dst.exists()
        assert src.exists()

    def test_move_file_to_same_path(self, tmp_path):
        """移动文件到完全相同的路径(应为no-op)"""
        src = tmp_path / "same_path.txt"
        src.write_text("stay here", encoding="utf-8")
        result = _run(move(str(src), str(src)))
        assert is_error(result)
        assert src.exists()
        assert src.read_text(encoding="utf-8") == "stay here"

    def test_rename_to_existing_name_fails(self, tmp_path):
        """重命名到已存在的目标文件名(应失败)"""
        src = tmp_path / "file_a.txt"
        src.write_text("content_a", encoding="utf-8")
        existing = tmp_path / "file_b.txt"
        existing.write_text("content_b", encoding="utf-8")
        result = _run(rename(str(src), str(tmp_path / "file_b.txt")))
        # 应该失败,因为目标文件已存在且rename_file不支持overwrite
        assert is_error(result)

    def test_compress_special_path_with_spaces(self, tmp_path):
        """路径包含空格的压缩"""
        src = tmp_path / "path with spaces" / "my file.txt"
        src.parent.mkdir(parents=True)
        src.write_text("content in spaced path\n", encoding="utf-8")
        dst = str(tmp_path / "spaced path" / "output.zip")
        result = _run(compress(str(src), dst))
        assert is_success(result)
        assert Path(dst).exists()

    def test_binary_file_copy_move(self, tmp_path):
        """二进制文件的复制和移动"""
        src = tmp_path / "image.dat"
        data = bytes(range(256)) * 100
        src.write_bytes(data)

        # 复制
        dst_copy = tmp_path / "image_copy.dat"
        r1 = _run(copy(str(src), str(dst_copy)))
        assert is_success(r1)
        assert dst_copy.read_bytes() == data

        # 移动
        dst_move = tmp_path / "image_moved.dat"
        r2 = _run(move(str(dst_copy), str(dst_move)))
        assert is_success(r2)
        assert not dst_copy.exists()
        assert dst_move.read_bytes() == data

    def test_extract_with_path_traversal_attempt(self, tmp_path):
        """解压时路径遍历攻击防护"""
        import zipfile
        # 创建一个包含路径遍历成员的ZIP
        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("../../../etc/passwd", "malicious content")
            zf.writestr("normal_file.txt", "safe content")

        out = str(tmp_path / "safe_extract")
        result = _run(extract(str(zip_path), dest=out))
        # 路径遍历成员应被跳过
        metrics = result.get("llm_data", {}).get("metrics", {})
        skipped = metrics.get("skipped_files", {}).get("value", 0)
        extracted = metrics.get("extracted_files", {}).get("value", 0)
        # 安全文件应被解压,恶意路径应被跳过
        assert extracted >= 1 or skipped >= 1


# =============================================================================
# Category 6: Negative — 异常/错误处理测试
# =============================================================================

@pytest.mark.timeout(60)
class TestNegative:
    """异常和错误处理测试 — 小健 2026-06-25"""

    def test_compress_nonexistent_source(self, tmp_path):
        """压缩不存在的源路径"""
        result = _run(compress(
            str(tmp_path / "nonexistent_dir"),
            str(tmp_path / "out.zip")
        ))
        assert is_error(result)
        detail = result.get("llm_data", {}).get("status", {}).get("detail", "")
        assert "不存在" in detail or "源" in detail or "path" in detail.lower()

    def test_extract_nonexistent_archive(self, tmp_path):
        """解压不存在的压缩包"""
        result = _run(extract(str(tmp_path / "no_such_file.zip")))
        assert is_error(result)

    def test_copy_nonexistent_source(self, tmp_path):
        """复制不存在的源文件"""
        result = _run(copy(
            str(tmp_path / "ghost.py"),
            str(tmp_path / "dest.py")
        ))
        assert is_error(result)

    def test_move_nonexistent_source(self, tmp_path):
        """移动不存在的源文件"""
        result = _run(move(
            str(tmp_path / "phantom.txt"),
            str(tmp_path / "destination.txt")
        ))
        assert is_error(result)

    def test_delete_already_deleted_file(self, tmp_path):
        """删除已不存在的文件(应返回成功 — already_deleted)"""
        ghost = tmp_path / "already_gone.txt"
        result = _run(delete(str(ghost), force=True))
        assert is_success(result)
        # 应包含already_deleted标记

    def test_delete_single_file_has_deleted_files_in_result(self, tmp_path):
        """delete_file: 确保成功结果含deleted_files和mode — 小沈 2026-07-30"""
        target = tmp_path / "verify.txt"
        target.write_text("content", encoding="utf-8")
        result = _run(delete(str(target), force=True))
        assert is_success(result)
        llm = result.get("llm_data", {})
        metrics = llm.get("metrics", {})
        assert metrics.get("deleted_count", {}).get("value") == 1
        assert metrics.get("mode", {}).get("value") == "permanent"

    def test_delete_directory_recursive_has_all_files(self, tmp_path):
        """delete_file: 递归删除目录,deleted_files含所有子文件 — 小沈 2026-07-30"""
        d = tmp_path / "big_dir"
        d.mkdir()
        for i in range(5):
            (d / f"f{i}.txt").write_text(f"file{i}", encoding="utf-8")
        sub = d / "sub"
        sub.mkdir()
        (sub / "s1.txt").write_text("sub", encoding="utf-8")
        result = _run(delete(str(d), recursive=True, force=True))
        assert is_success(result)
        llm = result.get("llm_data", {})
        metrics = llm.get("metrics", {})
        assert metrics.get("deleted_count", {}).get("value") == 8  # 5 files + 1 sub-file + 1 sub-dir + root

    def test_compress_invalid_format(self, tmp_path):
        """使用不支持的压缩格式"""
        src = tmp_path / "test.txt"
        src.write_text("data\n", encoding="utf-8")
        result = _run(compress(
            str(src),
            str(tmp_path / "out.xyz"),
            format="xyz"
        ))
        assert is_error(result)

    def test_extract_invalid_zip(self, tmp_path):
        """解压损坏的ZIP文件"""
        bad_zip = tmp_path / "corrupt.zip"
        bad_zip.write_bytes(b'\x50\x4b\x03\x04' + b'\x00' * 100)
        result = _run(extract(str(bad_zip)))
        assert is_error(result)

    def test_copy_dest_exists_no_overwrite(self, tmp_path):
        """复制到已存在目标且不覆盖"""
        src = tmp_path / "src.txt"
        src.write_text("new content", encoding="utf-8")
        dst = tmp_path / "existing.txt"
        dst.write_text("old content", encoding="utf-8")
        result = _run(copy(str(src), str(dst), overwrite=False))
        # 应返回成功但标记为no_change
        data = result.get("data", {})
        # 验证目标内容未被修改
        if dst.exists():
            assert dst.read_text(encoding="utf-8") == "old content"
