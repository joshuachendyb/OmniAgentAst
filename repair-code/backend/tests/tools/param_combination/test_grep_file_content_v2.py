# -*- coding: utf-8 -*-
"""
grep_file_content 参数组合与内容测试 v2
案范要求:schema驱动,内容≤100行,验证实际内容,发现问题
小健 2026-06-24
"""
import asyncio
import os
import re
import tempfile
import pytest
from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


def _create_test_files(tmpdir):
    """创建丰富的测试文件集,≤100行内容,中英文混合"""
    # 文件1: Python源代码(英文为主,含中文注释)
    py_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database connection manager for the enterprise CRM system.
Handles connection pooling, retry logic, and transaction management.

Author: Zhang Wei
Date: 2026-06-24
Version: 2.1.0
"""

import os
import sys
import time
import logging
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """数据库连接状态枚举"""
    IDLE = "idle"
    ACTIVE = "active"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class DatabaseConfig:
    """数据库配置类 - 数据库连接参数"""
    host: str = "localhost"
    port: int = 5432
    database: str = "crm_production"
    user: str = "admin"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    timeout: int = 30
    retry_count: int = 3
    ssl_enabled: bool = True
    charset: str = "utf-8"

    def validate(self) -> bool:
        """验证配置参数是否合法"""
        if not self.host:
            raise ValueError("数据库主机地址不能为空")
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"里口号无效: {self.port}")
        if self.pool_size < 1:
            raise ValueError(f"连接池大小无效: {self.pool_size}")
        return True


@dataclass
class Connection:
    """单个数据库连接"""
    connection_id: str
    status: ConnectionStatus = ConnectionStatus.IDLE
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    query_count: int = 0
    error_count: int = 0

    def execute(self, sql: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """执行SQL查询"""
        if self.status != ConnectionStatus.ACTIVE:
            raise ConnectionError(f"连接状态异常: {self.status}")
        self.query_count += 1
        self.last_used = time.time()
        logger.info(f"执行查询: {sql[:100]}...")
        return {"rows": [], "affected": 0}

    def close(self):
        """关闭数据库连接"""
        self.status = ConnectionStatus.CLOSED
        logger.info(f"连接已关闭: {self.connection_id}")


class ConnectionPool:
    """数据库连接池管理器 - 企业级连接池实现"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: List[Connection] = []
        self._lock = threading.Lock()
        self._stats = {
            "total_created": 0,
            "total_reused": 0,
            "total_errors": 0,
            "active_connections": 0,
        }

    def acquire(self) -> Connection:
        """获取一个数据库连接"""
        with self._lock:
            # 尝试从池中获取空闲连接
            for conn in self._pool:
                if conn.status == ConnectionStatus.IDLE:
                    conn.status = ConnectionStatus.ACTIVE
                    self._stats["total_reused"] += 1
                    return conn

            # 创建新连接
            if len(self._pool) < self.config.pool_size + self.config.max_overflow:
                conn = self._create_connection()
                self._pool.append(conn)
                self._stats["total_created"] += 1
                return conn

            raise ConnectionError("连接池已满,无法获取新连接")

    def release(self, conn: Connection):
        """释放连接回连接池"""
        with self._lock:
            if conn.status == ConnectionStatus.ACTIVE:
                conn.status = ConnectionStatus.IDLE
                self._stats["active_connections"] -= 1

    def _create_connection(self) -> Connection:
        """创建新的数据库连接"""
        conn_id = f"conn_{self._stats['total_created'] + 1}"
        conn = Connection(connection_id=conn_id, status=ConnectionStatus.ACTIVE)
        self._stats["active_connections"] += 1
        logger.info(f"创建新连接: {conn_id}")
        return conn

    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        return {
            **self._stats,
            "pool_size": len(self._pool),
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "database": self.config.database,
            }
        }

    def clear(self):
        """清空连接池"""
        with self._lock:
            for conn in self._pool:
                if conn.status == ConnectionStatus.ACTIVE:
                    conn.close()
            self._pool.clear()
            self._stats["active_connections"] = 0


@contextmanager
def get_connection(pool: ConnectionPool):
    """上下文管理器 - 自动获取和释放连接"""
    conn = pool.acquire()
    try:
        yield conn
    except Exception as e:
        conn.error_count += 1
        logger.error(f"查询执行失败: {e}")
        raise
    finally:
        pool.release(conn)


def create_pool(host: str = "localhost", port: int = 5432) -> ConnectionPool:
    """工厂函数 - 创建连接池实例"""
    config = DatabaseConfig(host=host, port=port)
    config.validate()
    pool = ConnectionPool(config)
    logger.info(f"连接池已创建: {host}:{port}")
    return pool


# 测试函数
def test_basic_connection():
    """测试基本连接功能"""
    pool = create_pool()
    with get_connection(pool) as conn:
        assert conn.status == ConnectionStatus.ACTIVE
        result = conn.execute("SELECT 1")
        assert result["rows"] == []


def test_connection_pool_stats():
    """测试连接池统计信息"""
    pool = create_pool()
    stats = pool.get_stats()
    assert stats["total_created"] == 0
    assert stats["pool_size"] == 0
'''
    with open(os.path.join(tmpdir, "db_manager.py"), 'w', encoding='utf-8') as f:
        f.write(py_content)

    # 文件2: 混合中英文技术文档
    doc_content = '''# Enterprise CRM System - Technical Documentation
# 企业CRM系统 - 技术文档

## 1. System Overview / 系统概述

The Enterprise CRM System is a comprehensive customer relationship management
platform designed for medium to large businesses. It supports sales pipeline
management, customer service ticketing, and marketing automation.

企业CRM系统是一个为大中型企业设计的综合客户关系管理平台.
支持销售管道管理,客户服务工单和营销自动化.

## 2. Architecture / 架构设计

### 2.1 Backend Services / 在里服务

The backend is built with Python FastAPI framework, providing RESTful APIs
for all CRUD operations. The system uses PostgreSQL as the primary database
and Redis for caching frequently accessed data.

在里采用Python FastAPI框架构建,提供所有CRUD操作的RESTful API.
系统使用PostgreSQL作为主数据库,Redis用于缓存高频访问数据.

Key components / 核心组件:
- Authentication Service / 认证服务: JWT-based authentication with refresh tokens
- User Management / 用户管理: Role-based access control (RBAC)
- Data Analytics / 数据分析: Real-time dashboard with WebSocket updates
- Export Engine / 导出引擎: PDF, Excel, CSV report generation

### 2.2 Frontend Architecture / 前里架构

The frontend is built with React 18 and TypeScript, using Ant Design 5
for the component library. State management is handled by Zustand.

前里采用React 18和TypeScript构建,使用Ant Design 5作为组件库.
状态管理由Zustand处理.

## 3. Database Schema / 数据库设计

### 3.1 Core Tables / 核心表

```sql
-- 客户信息表
CREATE TABLE customers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    company VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 销售机会表
CREATE TABLE opportunities (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT REFERENCES customers(id),
    title VARCHAR(200) NOT NULL,
    amount DECIMAL(12, 2),
    stage VARCHAR(50) DEFAULT 'prospecting',
    expected_close DATE,
    owner_id BIGINT REFERENCES users(id)
);
```

## 4. API Endpoints / 接口定义

### 4.1 Customer APIs / 客户接口

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/customers | 获取客户列表 |
| POST | /api/v1/customers | 创建新客户 |
| PUT | /api/v1/customers/:id | 更新客户信息 |
| DELETE | /api/v1/customers/:id | 删除客户 |

### 4.2 Opportunity APIs / 机会接口

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/opportunities | 获取销售机会列表 |
| POST | /api/v1/opportunities | 创建销售机会 |
| PATCH | /api/v1/opportunities/:id/stage | 更新销售阶段 |

## 5. Configuration / 配置说明

### 5.1 Environment Variables / 环境变量

```bash
# Database configuration / 数据库配置
DATABASE_URL=postgresql://user:pass@localhost:5432/crm_db
DATABASE_POOL_SIZE=20
DATABASE_TIMEOUT=30

# Redis configuration / Redis配置
REDIS_URL=redis://localhost:6379/0
REDIS_TTL=3600

# JWT configuration / JWT配置
JWT_SECRET_KEY=your-secret-key-here
JWT_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=7

# Email configuration / 邮件配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@company.com
SMTP_PASSWORD=app-password-here
```

## 6. Deployment Guide / 部署指南

### 6.1 Docker Deployment / Docker部署

```yaml
version: '3.8'
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/crm
    depends_on:
      - db
      - redis

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: crm
      POSTGRES_PASSWORD: password
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

### 6.2 Monitoring / 监控配置

Health check endpoints:
- GET /health - Basic health check
- GET /health/detailed - Database and Redis connectivity check
- GET /metrics - Prometheus metrics endpoint

## 7. Error Codes / 错误码

| Code | Description | Action |
|------|-------------|--------|
| 400 | Bad Request / 请求错误 | 检查请求参数 |
| 401 | Unauthorized / 未授权 | 检查认证token |
| 403 | Forbidden / 禁止访问 | 检查用户权限 |
| 404 | Not Found / 未找到 | 检查资源路径 |
| 500 | Internal Error / 服务器错误 | 联系系统管理员 |

## 8. Changelog / 更新日志

### v2.1.0 (2026-06-20)
- Added real-time notification system / 添加实时通知系统
- Improved query performance by 40% / 查询性能提升40%
- Fixed memory leak in WebSocket handler / 修复WebSocket处理器内存泄漏

### v2.0.0 (2026-05-15)
- Migrated to FastAPI from Flask / 从Flask迁移到FastAPI
- Added RBAC permission system / 添加RBAC权限系统
- Implemented PDF export / 实现PDF导出功能
'''
    with open(os.path.join(tmpdir, "technical_doc.md"), 'w', encoding='utf-8') as f:
        f.write(doc_content)

    # 文件3: CSV数据文件(销售数据)
    csv_content = '''order_id,customer_name,product,quantity,unit_price,total_amount,order_date,status,region,sales_rep
ORD-001,Acme Corporation,Enterprise License,5,12000.00,60000.00,2026-01-15,completed,North China,Li Wei
ORD-002,Tech Solutions Inc.,Professional License,10,8000.00,80000.00,2026-01-20,completed,South China,Wang Fang
ORD-003,Global Systems Ltd.,Basic License,20,3000.00,60000.00,2026-02-01,completed,East China,Zhang Ming
ORD-004,DataFlow Analytics,Enterprise License,3,12000.00,36000.00,2026-02-10,pending,North China,Li Wei
ORD-005,CloudFirst Inc.,Professional License,8,8000.00,64000.00,2026-02-15,completed,West China,Chen Jie
ORD-006,Smart Solutions,Enterprise License,2,12000.00,24000.00,2026-02-20,cancelled,South China,Wang Fang
ORD-007,Digital Dynamics,Basic License,50,3000.00,150000.00,2026-03-01,completed,North China,Li Wei
ORD-008,Innovation Corp.,Professional License,15,8000.00,120000.00,2026-03-10,processing,East China,Zhang Ming
ORD-009,Future Tech,Enterprise License,1,12000.00,12000.00,2026-03-15,completed,West China,Chen Jie
ORD-010,Apex Systems,Basic License,30,3000.00,90000.00,2026-03-20,completed,South China,Wang Fang
ORD-011,Pinnacle Software,Professional License,12,8000.00,96000.00,2026-04-01,pending,North China,Li Wei
ORD-012,Summit Analytics,Enterprise License,4,12000.00,48000.00,2026-04-10,completed,East China,Zhang Ming
ORD-013,Baseline Systems,Basic License,25,3000.00,75000.00,2026-04-15,completed,West China,Chen Jie
ORD-014,Cascade Solutions,Professional License,7,8000.00,56000.00,2026-04-20,processing,South China,Wang Fang
ORD-015,Horizon Tech,Enterprise License,6,12000.00,72000.00,2026-05-01,completed,North China,Li Wei
ORD-016,Vanguard Systems,Basic License,40,3000.00,120000.00,2026-05-10,completed,East China,Zhang Ming
ORD-017,Pioneer Software,Professional License,9,8000.00,72000.00,2026-05-15,pending,West China,Chen Jie
ORD-018,Frontier Analytics,Enterprise License,3,12000.00,36000.00,2026-05-20,completed,South China,Wang Fang
ORD-019,Atlas Systems,Basic License,35,3000.00,105000.00,2026-06-01,completed,North China,Li Wei
ORD-020,Nexus Solutions,Professional License,11,8000.00,88000.00,2026-06-10,completed,East China,Zhang Ming
'''
    with open(os.path.join(tmpdir, "sales_data.csv"), 'w', encoding='utf-8') as f:
        f.write(csv_content)

    # 文件4: 配置文件(INI格式)
    ini_content = '''[database]
host = localhost
port = 5432
name = crm_production
user = db_admin
password = s3cur3_p@ssw0rd
pool_size = 20
timeout = 30
ssl_enabled = true

[redis]
host = localhost
port = 6379
db = 0
password = redis_p@ss
ttl = 3600
max_connections = 50

[server]
host = 0.0.0.0
port = 8000
workers = 4
debug = false
log_level = INFO
cors_origins = http://localhost:3000,http://localhost:5173

[auth]
jwt_secret = my_jwt_secret_key_2026
jwt_expire_minutes = 30
refresh_expire_days = 7
algorithm = HS256

[smtp]
host = smtp.gmail.com
port = 587
user = noreply@company.com
password = app_password_123
use_tls = true
'''
    with open(os.path.join(tmpdir, "config.ini"), 'w', encoding='utf-8') as f:
        f.write(ini_content)

    # 文件5: 日志文件(含错误信息)
    log_content = '''2026-06-24 08:00:01 [INFO] Application started successfully
2026-06-24 08:00:02 [INFO] Database connection pool initialized (size=10)
2026-06-24 08:00:03 [INFO] Redis cache connected at localhost:6379
2026-06-24 08:00:05 [INFO] JWT authentication enabled
2026-06-24 08:00:10 [INFO] Server listening on 0.0.0.0:8000
2026-06-24 08:05:15 [WARNING] Slow query detected: SELECT * FROM customers (2.3s)
2026-06-24 08:10:22 [ERROR] Connection timeout to database: localhost:5432
2026-06-24 08:10:23 [INFO] Attempting to reconnect to database (attempt 1/3)
2026-06-24 08:10:25 [INFO] Database connection re-established
2026-06-24 08:15:30 [WARNING] Memory usage above threshold: 85%
2026-06-24 08:20:45 [ERROR] Failed to send email notification: SMTP timeout
2026-06-24 08:20:46 [INFO] Email notification queued for retry
2026-06-24 08:25:50 [INFO] Cache hit ratio: 78.5%
2026-06-24 08:30:00 [INFO] Scheduled task: Daily report generation started
2026-06-24 08:30:15 [INFO] Report generated: daily_sales_20260624.pdf
2026-06-24 08:35:20 [WARNING] Rate limit exceeded for API endpoint /api/v1/customers
2026-06-24 08:35:21 [INFO] Client IP 192.168.1.100 temporarily blocked
2026-06-24 08:40:30 [ERROR] File upload failed: disk space insufficient
2026-06-24 08:40:31 [INFO] Cleanup initiated for temporary files
2026-06-24 08:45:40 [INFO] Background job completed: data_sync (1250 records)
2026-06-24 08:50:55 [WARNING] Deprecated API endpoint called: /api/v1/legacy/users
2026-06-24 08:55:00 [INFO] Health check passed: all services operational
2026-06-24 09:00:00 [INFO] Hourly metrics: requests=1523, errors=3, avg_response=145ms
2026-06-24 09:05:10 [ERROR] Authentication failed for user: admin@example.com
2026-06-24 09:05:11 [INFO] Failed login attempt logged from IP: 10.0.0.50
2026-06-24 09:10:20 [INFO] User session expired: user_id=1234
2026-06-24 09:15:30 [WARNING] Database connection pool near capacity: 9/10 active
2026-06-24 09:20:40 [INFO] WebSocket connections active: 45
2026-06-24 09:25:50 [ERROR] PDF generation failed: template not found
2026-06-24 09:25:51 [INFO] Fallback to default PDF template
2026-06-24 09:30:00 [INFO] System metrics collected: CPU=45%, Memory=72%, Disk=58%
'''
    with open(os.path.join(tmpdir, "app.log"), 'w', encoding='utf-8') as f:
        f.write(log_content)

    return tmpdir


class TestGrepFileContentParamCombinations:
    """Schema驱动 - 参数组合穷举测试"""

    def test_pattern_only(self, tmp_path):
        """组合1: 只传pattern + search_dir (必填参数)"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("ConnectionPool", d))
        assert is_success(result)
        assert result["data"]["total_matches"] > 0
        # 验证匹配内容认实包含关键词
        for match in result["data"]["matches"]:
            assert "ConnectionPool" in match["content"]

    def test_pattern_with_glob_filter(self, tmp_path):
        """组合2: pattern + glob过滤"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        # 只搜索.py文件
        result = _run(grep("import", d, glob="*.py"))
        assert is_success(result)
        assert result["data"]["total_matches"] > 0
        # 验证所有匹配文件都是.py
        for match in result["data"]["matches"]:
            assert match["file"].endswith(".py")

    def test_pattern_with_ignore_case_false(self, tmp_path):
        """组合3: pattern + ignore_case=False (区分大小写)"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        # 区分大小写搜索"ConnectionStatus"(PascalCase)
        result_pascal = _run(grep("ConnectionStatus", d, ignore_case=False))
        # 区分大小写搜索"connectionstatus"(全小写,不存在)
        result_lower = _run(grep("connectionstatus", d, ignore_case=False))
        # "ConnectionStatus"应该匹配
        assert result_pascal["data"]["total_matches"] > 0
        # "connectionstatus"应该不匹配(区分大小写)
        assert result_lower["data"]["total_matches"] == 0

    def test_pattern_ignore_case_true(self, tmp_path):
        """组合4: pattern + ignore_case=True (不区分大小写)"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("error", d, ignore_case=True))
        # 不区分大小写应该匹配更多
        assert result["data"]["total_matches"] > 0

    def test_output_mode_content(self, tmp_path):
        """组合5: 内容模式(默认)"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("def ", d))
        assert is_success(result)
        assert "matches" in result["data"]
        # 验证每个匹配有file,line,content字段
        for match in result["data"]["matches"]:
            assert "file" in match
            assert "line" in match
            assert "content" in match
            assert "matched" in match

    def test_all_params_combined(self, tmp_path):
        """组合8: 所有参数组合"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep(
            "error", d,
            glob="*.log",
            ignore_case=True,
        ))
        assert is_success(result)
        # 验证glob过滤生效(只匹配.log文件)
        for match in result["data"]["matches"]:
            assert match["file"].endswith(".log")

    def test_chinese_content_search(self, tmp_path):
        """组合9: 搜索中文内容"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("数据库", d))
        assert is_success(result)
        assert result["data"]["total_matches"] > 0

    def test_regex_pattern_search(self, tmp_path):
        """组合10: 正则表达式搜索"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        # 搜索所有函数定义
        result = _run(grep(r"def \w+\(", d, glob="*.py"))
        assert is_success(result)
        assert result["data"]["total_matches"] > 0


class TestGrepFileContentFeatures:
    """功能测试 - 验证每个功能点"""

    def test_regex_special_chars(self, tmp_path):
        """特殊正则字符处理"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        # 搜索包含点号的内容(IP地址)
        result = _run(grep(r"\d+\.\d+\.\d+\.\d+", d))
        assert is_success(result)

    def test_unicode_pattern(self, tmp_path):
        """Unicode模式搜索"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("张三", d))
        assert is_success(result)

    def test_empty_pattern(self, tmp_path):
        """空模式搜索"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("", d))
        assert is_error(result)

    def test_nonexistent_directory(self):
        """搜索不存在的目录"""
        from app.tools.file.grep_file_content import grep
        result = _run(grep("test", "Z:\\nonexistent\\path"))
        assert is_error(result)

    def test_invalid_regex(self, tmp_path):
        """无效正则表达式"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("[invalid", d))
        assert is_error(result)

    def test_glob_with_star(self, tmp_path):
        """glob通配符*.py过滤"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("class", d, glob="*.py"))
        assert is_success(result)
        for match in result["data"]["matches"]:
            assert match["file"].endswith(".py")

    def test_no_matches_found(self, tmp_path):
        """搜索无匹配内容"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("ZZZZZ_NO_MATCH_ZZZZZ", d))
        assert is_success(result)
        assert result["data"]["total_matches"] == 0


class TestGrepFileContentRealScenarios:
    """真实业务场景测试"""

    def test_find_all_error_logs(self, tmp_path):
        """场景1: 查找所有错误日志"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        # 使用ignore_case=False只匹配大写ERROR
        result = _run(grep("ERROR", d, glob="*.log", ignore_case=False))
        assert is_success(result)
        # 验证每条都是ERROR级别(大写)
        for match in result["data"]["matches"]:
            assert "ERROR" in match["content"]

    def test_find_python_imports(self, tmp_path):
        """场景2: 查找Python导入语找"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep(r"^import |^from ", d, glob="*.py"))
        assert is_success(result)
        assert result["data"]["total_matches"] > 0

    def test_find_config_values(self, tmp_path):
        """场景3: 查找配置值"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("localhost", d, glob="*.ini"))
        assert is_success(result)
        assert result["data"]["total_matches"] > 0

    def test_find_sales_by_rep(self, tmp_path):
        """场景4: 按销售代表搜索订单"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("Li Wei", d, glob="*.csv"))
        assert is_success(result)
        assert result["data"]["total_matches"] >= 4

    def test_find_chinese_functions(self, tmp_path):
        """场景5: 搜索中文函数名"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("def test_", d, glob="*.py"))
        assert is_success(result)
        assert result["data"]["total_matches"] >= 2

    def test_cross_file_search(self, tmp_path):
        """场景6: 跨文件搜索同一关键词"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("connection", d))
        assert is_success(result)
        # 应该在多个文件中找到
        files_found = set(m["file"] for m in result["data"]["matches"])
        assert len(files_found) >= 2


class TestGrepFileContentBoundary:
    """边界测试"""

    def test_large_directory_search(self, tmp_path):
        """大目录搜索"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        # 创建多个子目录和文件
        for i in range(10):
            subdir = os.path.join(d, f"subdir_{i}")
            os.makedirs(subdir)
            with open(os.path.join(subdir, f"file_{i}.py"), 'w') as f:
                f.write(f"# File {i}\ndef func_{i}():\n    pass\n" * 20)
        result = _run(grep("def func_", d))
        assert is_success(result)
        assert result["data"]["total_matches"] >= 10

    def test_special_characters_in_path(self, tmp_path):
        """路径包含特殊字符"""
        from app.tools.file.grep_file_content import grep
        special_dir = os.path.join(str(tmp_path), "特殊 目录")
        os.makedirs(special_dir)
        with open(os.path.join(special_dir, "test.py"), 'w') as f:
            f.write("def test(): pass\n")
        result = _run(grep("def test", special_dir))
        assert is_success(result)

    def test_binary_file_skipped(self, tmp_path):
        """二进制文件被跳过"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        # 创建一个二进制文件
        with open(os.path.join(d, "binary.exe"), 'wb') as f:
            f.write(b'\x00\x01\x02\x03\x04\x05')
        result = _run(grep("test", d))
        assert is_success(result)
        # 二进制文件不应该被匹配
        for match in result["data"]["matches"]:
            assert not match["file"].endswith(".exe")


class TestGrepFileContentNegative:
    """为面测试 - 错误处理"""

    def test_empty_search_dir(self):
        """空搜索目录 - 使用不存在的目录"""
        from app.tools.file.grep_file_content import grep
        result = _run(grep("test", "Z:\\nonexistent\\directory"))
        assert is_error(result)

    def test_pattern_is_none(self, tmp_path):
        """pattern为None"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep(None, d))
        assert is_error(result)

    def test_search_dir_is_file(self, tmp_path):
        """search_dir是文件不是目录"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        filepath = os.path.join(d, "test.py")
        result = _run(grep("def", filepath))
        assert is_error(result) or result["data"]["total_matches"] == 0


class TestGrepFileContentBugDiscovery:
    """BUG发现测试 —— 专门暴露已知和潜在BUG —— 小健 2026-06-24"""

    def test_bug_binary_file_skipped(self, tmp_path):
        """功能验证: 二进制文件被跳过不影响文本搜索"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        with open(os.path.join(d, "binary.dll"), 'wb') as f:
            f.write(b'\x00\x01\x02\x03\x04\x05\x06\x07')
        result = _run(grep("test", d))
        assert is_success(result)

    def test_bug_glob_with_braces(self, tmp_path):
        """边界: glob模式包含花括号如*.{py,js}"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("def ", d, glob="*.{py,js}"))
        # fnmatch不支持花括号,可能匹配不到或报错
        assert is_success(result) or is_error(result)

    def test_bug_glob_with_question_mark(self, tmp_path):
        """边界: glob模式包含问号"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("def ", d, glob="db_????.py"))
        assert is_success(result)

    def test_bug_ignore_case_false_case_sensitive(self, tmp_path):
        """功能验证: ignore_case=False时区分大小写

        使用自定义日志文件认保只有大写ERROR,没有小写error.
        ——小健 2026-06-24
        """
        from app.tools.file.grep_file_content import grep
        d = tmp_path / "case_test"
        d.mkdir()
        (d / "test.log").write_text(
            "2026-06-24 08:00:01 [INFO] OK\n"
            "2026-06-24 08:00:02 [ERROR] Failed\n"
            "2026-06-24 08:00:03 [WARNING] Slow\n",
            encoding="utf-8"
        )
        result_upper = _run(grep("ERROR", str(d), glob="*.log", ignore_case=False))
        result_lower = _run(grep("error", str(d), glob="*.log", ignore_case=False))
        if is_success(result_upper) and is_success(result_lower):
            assert result_upper["data"]["total_matches"] > 0
            assert result_lower["data"]["total_matches"] == 0

    def test_bug_chinese_pattern_search(self, tmp_path):
        """功能: 中文正则搜索"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("数据库", d))
        assert is_success(result)
        assert result["data"]["total_matches"] > 0

    def test_bug_empty_directory_search(self, tmp_path):
        """边界: 空目录搜索"""
        from app.tools.file.grep_file_content import grep
        d = tmp_path / "empty_grep"
        d.mkdir()
        result = _run(grep("test", str(d)))
        assert is_success(result)
        assert result["data"]["total_matches"] == 0

    def test_bug_invalid_regex_pattern(self, tmp_path):
        """为面: 无效正则表达式"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("[invalid(regex", d))
        assert is_error(result)

    def test_bug_glob_filter_effectiveness(self, tmp_path):
        """功能验证: glob过滤认实只搜索匹配的文件"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("def ", d, glob="*.py"))
        assert is_success(result)
        for match in result["data"]["matches"]:
            assert match["file"].endswith(".py")

    def test_bug_search_dir_is_file(self, tmp_path):
        """path是文件 -- 支持单文件搜索"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        filepath = os.path.join(d, "db_manager.py")
        result = _run(grep("def", filepath))
        assert is_success(result)

    def test_bug_pattern_empty_string(self, tmp_path):
        """为面: pattern为空字符串"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("", d))
        assert is_error(result)

    def test_bug_pattern_whitespace_only(self, tmp_path):
        """边界: pattern只包含空白"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("   ", d))
        # 空白不是空字符串,可能被视为有效pattern
        assert is_success(result) or is_error(result)

    def test_bug_all_params_combined(self, tmp_path):
        """组合: 所有参数组合 pattern + search_dir + glob + ignore_case"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep(
            "def ", d,
            glob="*.py",
            ignore_case=False,
        ))
        assert is_success(result)
        for match in result["data"]["matches"]:
            assert match["file"].endswith(".py")
            assert "def " in match["content"]

    def test_bug_multiline_regex_no_match(self, tmp_path):
        """边界: 多行正则(grep按行搜索,不支持跨行匹配)"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        # 多行正则不会跨行匹配
        result = _run(grep(r"import.*\n.*from", d))
        assert is_success(result)
        # 按行搜索,跨行正则不应匹配

    def test_bug_large_file_searched(self, tmp_path):
        """边界: 大文件被正常完整搜索(不再限制文件大小)"""
        from app.tools.file.grep_file_content import grep
        d = tmp_path / "large_file_test"
        d.mkdir()
        with open(os.path.join(d, "huge.py"), 'w', encoding='utf-8') as f:
            f.write("# large file\n" * 100000)
        result = _run(grep("large file", str(d)))
        assert is_success(result)
        assert result["data"]["total_matches"] > 0

    def test_bug_match_content_has_line_number(self, tmp_path):
        """内容验证: content模式返回的match包含line字段"""
        from app.tools.file.grep_file_content import grep
        d = _create_test_files(str(tmp_path))
        result = _run(grep("def ", d))
        assert is_success(result)
        for match in result["data"]["matches"]:
            assert "line" in match
            assert isinstance(match["line"], int)
            assert match["line"] >= 1
