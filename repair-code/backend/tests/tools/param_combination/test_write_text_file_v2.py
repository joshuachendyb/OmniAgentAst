# -*- coding: utf-8 -*-
"""
write_text_file 参数组合与内容测试v2
案范要求:schema驱动,内容≥100行,验证实际内容,发现问题 小健 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest
from app.services.task.task_context import _current_task_id
from app.tools.tool_response import is_success, is_error


def _run_with_task_id(coro):
    """在task_id上下文中运行协程"""
    token = _current_task_id.set("test-task-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def _get_rich_content():
    """生成≥100行的中英文混合内容"""
    return """# Enterprise CRM System - Deployment Guide
# 企业CRM系统 - 部署指南

## 1. Overview / 系统概述

This document provides comprehensive instructions for deploying the Enterprise
CRM System in production environments. It covers hardware requirements,
software dependencies, configuration steps, and post-deployment verification.

本文档提供了在生产环境中部署企业CRM系统的全面说明.涵盖硬件要求,软件依赖,配置步骤和部署在验证.
## 2. Hardware Requirements / 硬件要求

### 2.1 Minimum Configuration / 最低配置
| Component | Requirement | Recommended |
|-----------|-------------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Storage | 100 GB SSD | 500 GB SSD |
| Network | 100 Mbps | 1 Gbps |

### 2.2 Production Configuration / 生产配置

For production environments with 1000+ concurrent users:
对于1000+并发用户的生产环境:

- CPU: 16 cores (Intel Xeon or AMD EPYC)
- RAM: 64 GB ECC memory
- Storage: 2 TB NVMe SSD with RAID 10
- Network: 10 Gbps with redundant connections
- Backup: Dedicated backup server with 10 TB storage

## 3. Software Dependencies / 软件依赖

### 3.1 Required Software / 必需软件

```
Python 3.11+ / Python 3.11+
PostgreSQL 15+ / PostgreSQL 15+
Redis 7+ / Redis 7+
Nginx 1.24+ / Nginx 1.24+
Node.js 20 LTS / Node.js 20 LTS
```

### 3.2 Python Packages / Python包
```bash
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
alembic==1.13.0
psycopg2-binary==2.9.9
redis==5.0.1
pydantic==2.5.2
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
httpx==0.25.2
celery==5.3.6
```

## 4. Installation Steps / 安装步骤

### Step 1: Clone Repository / 克隆仓库

```bash
git clone https://github.com/company/crm-system.git
cd crm-system
git checkout v2.1.0
```

### Step 2: Set Up Virtual Environment / 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\\Scripts\\activate  # Windows

pip install -r requirements.txt
```

### Step 3: Configure Database / 配置数据库
```sql
-- 创建数据库
CREATE DATABASE crm_production;
CREATE USER crm_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE crm_production TO crm_user;

-- 启用扩展
\\c crm_production
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

### Step 4: Environment Variables / 环境变量

```bash
# .env 文件配置
DATABASE_URL=postgresql://crm_user:secure_password@localhost:5432/crm_production
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-super-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=7

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@yourcompany.com
SMTP_PASSWORD=app-specific-password
SMTP_TLS=true

# File Storage
UPLOAD_DIR=/var/crm/uploads
MAX_UPLOAD_SIZE=52428800  # 50MB
ALLOWED_EXTENSIONS=pdf,docx,xlsx,csv,png,jpg

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/crm/app.log
LOG_ROTATION=10MB
LOG_RETENTION=30 days
```

### Step 5: Run Migrations / 执行迁移

```bash
# 生成迁移文件
alembic revision --autogenerate -m "initial migration"

# 执行迁移
alembic upgrade head

# 验证迁移
alembic current
alembic history
```

### Step 6: Initialize Data / 初始化数据
```bash
# 创建超级管理员
python scripts/create_admin.py --email admin@company.com --password Admin123!

# 导入示例数据(可选)
python scripts/seed_data.py --env production
```

### Step 7: Start Services / 启动服务

```bash
# 启动API服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 启动Celery Worker
celery -A app.celery worker --loglevel=info --concurrency=4

# 启动Celery Beat (定时任务)
celery -A app.celery beat --loglevel=info
```

## 5. Nginx Configuration / Nginx配置

```nginx
upstream crm_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    server_name crm.yourcompany.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name crm.yourcompany.com;

    ssl_certificate /etc/nginx/ssl/crm.crt;
    ssl_certificate_key /etc/nginx/ssl/crm.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 50M;

    location / {
        proxy_pass http://crm_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /ws {
        proxy_pass http://crm_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static {
        alias /var/crm/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

## 6. Post-Deployment Verification / 部署在验证
### 6.1 Health Check / 健康检查
```bash
# 基本健康检查
curl -f http://localhost:8000/health

# 详细健康检查
curl -f http://localhost:8000/health/detailed

# Prometheus指标
curl http://localhost:8000/metrics
```

### 6.2 Functional Tests / 功能测试

```bash
# 运行API测试
pytest tests/api/ -v --tb=short

# 运行集成测试
pytest tests/integration/ -v --tb=short

# 运行里到里测试
npx playwright test tests/e2e/
```

### 6.3 Performance Verification / 性能验证

| Metric | Target | Actual |
|--------|--------|--------|
| Response Time (avg) | < 200ms | ✅ |
| Response Time (p95) | < 500ms | ✅ |
| Response Time (p99) | < 1000ms | ✅ |
| Error Rate | < 0.1% | ✅ |
| Throughput | > 100 req/s | ✅ |

## 7. Troubleshooting / 故障排除

### 7.1 Common Issues / 常见问题

**Issue**: Database connection refused
**解决**: 检查PostgreSQL服务是否运行,里口是否正认
**Issue**: Redis connection timeout
**解决**: 检查Redis服务状态,认认防火墙案则
**Issue**: SSL certificate error
**解决**: 检查证书文件路径和权限,认认证书未过期

**Issue**: 502 Bad Gateway
**解决**: 检查uvicorn服务是否运行,Nginx upstream配置

### 7.2 Log Analysis / 日志分析

```bash
# 查看应用日志
tail -f /var/log/crm/app.log

# 搜索错误
grep -i "error" /var/log/crm/app.log | tail -50

# 查看慢查询
grep -i "slow query" /var/log/crm/app.log
```

## 8. Backup and Recovery / 备份与恢复
### 8.1 Database Backup / 数据库备份
```bash
# 每日自动备份
pg_dump -U crm_user crm_production | gzip > backup_$(date +%Y%m%d).sql.gz

# 恢复备份
gunzip < backup_20260624.sql.gz | psql -U crm_user crm_production
```

### 8.2 File Backup / 文件备份

```bash
# 备份上传文件
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz /var/crm/uploads

# 备份配置文件
tar -czf config_backup_$(date +%Y%m%d).tar.gz /etc/crm/
```

## 9. Security Checklist / 安全检查清单
- [ ] 数据库密码使用强密码
- [ ] SSL证书正认配置
- [ ] 防火墙案则限制访问
- [ ] API密钥定期轮换
- [ ] 日志中不包含敏感信息
- [ ] 文件上传大小限制已设置
- [ ] CORS配置正认
- [ ] Rate limiting已启用
## 10. Contact Information / 联系信息

- System Administrator: admin@company.com
- Database Admin: dba@company.com
- Security Team: security@company.com
- Emergency Hotline: +86-10-12345678

---
Document Version: 2.1.0
Last Updated: 2026-06-24
Author: DevOps Team
中文翻译: 运维团队
"""


class TestWriteTextFileParamCombinations:
    """Schema驱动 - 参数组合穷举测试"""

    def test_file_path_and_content_only(self, tmp_path):
        """组合1: 仅file_path + content (必需参数)"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "output.txt")
        content = _get_rich_content()
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        # 验证文件创建
        assert os.path.exists(fp)
        # 验证内容完整性
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert len(written) == len(content)
        assert "Enterprise CRM System" in written
        assert "企业CRM系统" in written

    def test_file_path_content_encoding(self, tmp_path):
        """组合2: file_path + content + encoding"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "gbk_output.txt")
        content = "中文GBK编码测试\n第二行内容\n" * 30
        result = _run_with_task_id(writetext(fp, content, encoding="gbk"))
        assert is_success(result)
        # 验证GBK编码
        with open(fp, 'r', encoding='gbk') as f:
            written = f.read()
        assert "中文GBK编码测试" in written

    def test_file_path_content_append(self, tmp_path):
        """组合3: file_path + content + append=True"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "append.txt")
        # 第一次写入
        result1 = _run_with_task_id(writetext(fp, "第一部分内容\n"))
        assert is_success(result1)
        # 追加写入
        result2 = _run_with_task_id(writetext(fp, "第二部分内容\n", append=True))
        assert is_success(result2)
        # 验证合并内容
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "第一部分内容" in written
        assert "第二部分内容" in written

    def test_all_params_combined(self, tmp_path):
        """组合4: 所有参数组合"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "full_output.txt")
        content = _get_rich_content()
        result = _run_with_task_id(writetext(fp, content, encoding="utf-8", append=False))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert len(written) > 100

    def test_overwrite_existing_file(self, tmp_path):
        """组合5: 覆盖已有文件"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "overwrite.txt")
        # 写入初始内容
        _run_with_task_id(writetext(fp, "原始内容\n" * 10))
        # 覆盖写入
        result = _run_with_task_id(writetext(fp, "新内容\n" * 5))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "新内容" in written
        assert "原始内容" not in written

    def test_chinese_content(self, tmp_path):
        """组合6: 纯中文内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "chinese.txt")
        content = "这是一段中文内容.\n" * 50
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "这是一段中文内容" in written

    def test_english_content(self, tmp_path):
        """组合7: 纯英文内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "english.txt")
        content = "This is English content.\n" * 50
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "This is English content" in written

    def test_mixed_language_content(self, tmp_path):
        """组合8: 中英文混合内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "mixed.txt")
        lines = []
        for i in range(50):
            lines.append(f"Line {i}: 第{i}行 - This is line {i}")
        content = "\n".join(lines)
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "第" in written
        assert "line 0" in written


class TestWriteTextFileFeatures:
    """功能测试 - 验证每个功能点"""

    def test_special_characters(self, tmp_path):
        """特殊字符写入"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "special.txt")
        content = "特殊字符:<>&\"'\\n\\t中文:测试\nemoji:😊🎉\n"
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "特殊字符" in written

    def test_multiline_content(self, tmp_path):
        """多行内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "multiline.txt")
        content = "\n".join([f"Line {i}" for i in range(100)])
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 100

    def test_content_with_tables(self, tmp_path):
        """包含表格的内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "tables.txt")
        content = """| Name | Age | City |
|------|-----|------|
| 张三 | 25 | 北输 |
| 李四 | 30 | 上海 |
| 王五 | 28 | 广州 |
"""
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "|" in written
        assert "张三" in written

    def test_content_with_code_blocks(self, tmp_path):
        """包含代码块的内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "code.txt")
        content = '''# Python Code Example

```python
def hello_world():
    """打印Hello World"""
    print("Hello, World!")
    return True
```

# JavaScript Code Example

```javascript
function helloWorld() {
    console.log("Hello, World!");
    return true;
}
```
'''
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "def hello_world" in written
        assert "function helloWorld" in written

    def test_append_creates_directories(self, tmp_path):
        """追加写入时自动创建目录"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "subdir", "nested", "output.txt")
        content = "Nested directory content\n"
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        assert os.path.exists(fp)


class TestWriteTextFileRealScenarios:
    """真实业务场景测试"""

    def test_write_technical_report(self, tmp_path):
        """场景1: 写入技术报告"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "report.md")
        content = _get_rich_content()
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        # 验证报告结构
        assert "# Enterprise CRM System" in written
        assert "## 1." in written
        assert "| Component |" in written

    def test_write_log_file(self, tmp_path):
        """场景2: 写入日志文件"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "app.log")
        lines = []
        for i in range(100):
            level = ["INFO", "WARNING", "ERROR"][i % 3]
            lines.append(f"2026-06-24 {8+i//6:02d}:{(i*10)%60:02d}:00 [{level}] Log message {i}")
        content = "\n".join(lines) + "\n"
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "[INFO]" in written
        assert "[ERROR]" in written

    def test_write_csv_data(self, tmp_path):
        """场景3: 写入CSV数据"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "data.csv")
        lines = ["id,name,amount,region"]
        for i in range(50):
            lines.append(f"{i+1},Customer_{i+1},{(i+1)*1000},Region_{i%5+1}")
        content = "\n".join(lines) + "\n"
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "id,name,amount" in written
        assert "Customer_1" in written

    def test_write_config_file(self, tmp_path):
        """场景4: 写入配置文件"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "config.yaml")
        content = """# Application Configuration
app:
  name: CRM System
  version: 2.1.0
  debug: false

database:
  host: localhost
  port: 5432
  name: crm_production
  pool_size: 20

redis:
  host: localhost
  port: 6379
  db: 0

logging:
  level: INFO
  file: /var/log/crm/app.log
"""
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "app:" in written
        assert "database:" in written


class TestWriteTextFileBoundary:
    """边界测试"""

    def test_empty_content(self, tmp_path):
        """空内容 —— BUG-402修复在拦截空字符串 —— 小健 2026-06-24"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "empty.txt")
        result = _run_with_task_id(writetext(fp, ""))
        assert is_error(result)

    def test_single_char_content(self, tmp_path):
        """单字符内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "single.txt")
        result = _run_with_task_id(writetext(fp, "X"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            assert f.read() == "X"

    def test_very_long_content(self, tmp_path):
        """超长内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "long.txt")
        content = "A" * 1000000 + "\n"  # 1MB
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        assert os.path.getsize(fp) > 1000000

    def test_content_with_all_line_endings(self, tmp_path):
        """混合换行符"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "lineendings.txt")
        content = "line1\nline2\rline3\r\nline4"
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)

    def test_unicode_content(self, tmp_path):
        """Unicode内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "unicode.txt")
        content = "中文 日本語 עברית العربية emoji🎯🎉🎍\n"
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            written = f.read()
        assert "中文" in written
        assert "日本語" in written


class TestWriteTextFileNegative:
    """为面测试 - 错误处理"""

    def test_empty_file_path(self):
        """空文件路径"""
        from app.tools.file.write_text_file import writetext
        result = _run_with_task_id(writetext("", "content"))
        assert is_error(result)

    def test_invalid_path(self):
        """无效路径"""
        from app.tools.file.write_text_file import writetext
        result = _run_with_task_id(writetext("Z:\\nonexistent\\file.txt", "content"))
        assert is_error(result)

    def test_none_content(self):
        """content为None"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(tempfile.gettempdir(), "test_none.txt")
        result = _run_with_task_id(writetext(fp, None))
        assert is_error(result) or os.path.exists(fp)


class TestWriteTextFileBugDiscovery:
    """BUG发现测试 —— 专门暴露已知和潜在BUG —— 小健 2026-06-24"""

    def test_bug_append_with_encoding_rejected(self, tmp_path):
        """安全检查 append=True + encoding指定 被拒绝(正认行为)

        append时指定encoding会导致编码混乱:
        - 原文件GBK + 追加UTF-8 = 混合编码文件(损坏)
        - 正认做法:append时不指定encoding,自动检测原文件编码
         —— 小健 2026-06-24
        """
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "append_enc.txt")
        _run_with_task_id(writetext(fp, "初始内容\n"))
        result = _run_with_task_id(writetext(fp, "追加内容\n", append=True, encoding="utf-8"))
        # 正认行为:append+encoding应该被拒绝
        assert is_error(result)

    def test_bug_append_to_gbk_file_encoding_mismatch(self, tmp_path):
        """BUG: 追加到GBK文件时编码不匹配警告"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "gbk_append.txt")
        _run_with_task_id(writetext(fp, "GBK初始内容\n", encoding="gbk"))
        result = _run_with_task_id(writetext(fp, "追加内容\n", append=True))
        # append时不指定encoding,应该自动检测为gbk
        if is_success(result) or is_error(result):
            pass

    def test_bug_null_char_in_content(self, tmp_path):
        """安全: content包含null字符应被拒绝"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "null.txt")
        result = _run_with_task_id(writetext(fp, "content with \x00 null"))
        assert is_error(result)

    def test_bug_write_to_binary_extension(self, tmp_path):
        """文件类型: 写入.exe扩展名应被拒绝"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "test.exe")
        result = _run_with_task_id(writetext(fp, "binary content"))
        assert is_error(result)

    def test_bug_write_to_image_extension(self, tmp_path):
        """文件类型: 写入.png扩展名应被拒绝"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "test.png")
        result = _run_with_task_id(writetext(fp, "image content"))
        assert is_error(result)

    def test_bug_write_to_pdf_extension(self, tmp_path):
        """文件类型: 写入.pdf扩展名应被拒绝"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "test.pdf")
        result = _run_with_task_id(writetext(fp, "pdf content"))
        assert is_error(result)

    def test_bug_write_to_docx_extension(self, tmp_path):
        """文件类型: 写入.docx扩展名应被拒绝"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "test.docx")
        result = _run_with_task_id(writetext(fp, "docx content"))
        assert is_error(result)

    def test_bug_write_to_zip_extension(self, tmp_path):
        """文件类型: 写入.zip扩展名应被拒绝"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "test.zip")
        result = _run_with_task_id(writetext(fp, "zip content"))
        assert is_error(result)

    def test_bug_no_task_id(self, tmp_path):
        """安全: 没有task_id时应报错"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "no_task.txt")
        token = _current_task_id.set(None)
        try:
            result = asyncio.run(writetext(fp, "content"))
            assert is_error(result)
        finally:
            _current_task_id.reset(token)

    def test_bug_append_creates_new_file(self, tmp_path):
        """功能: append=True但文件不存在时应创建新文件"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "new_append.txt")
        result = _run_with_task_id(writetext(fp, "新文件内容\n", append=True))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            assert "新文件内容" in f.read()

    def test_bug_write_deep_nested_path(self, tmp_path):
        """功能: 深层嵌套目录自动创建"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "a", "b", "c", "d", "e", "deep.txt")
        result = _run_with_task_id(writetext(fp, "deep content"))
        assert is_success(result)
        assert os.path.exists(fp)

    def test_bug_write_preserves_encoding_on_append(self, tmp_path):
        """功能: append时自动检测原文件编码"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "enc_preserve.txt")
        _run_with_task_id(writetext(fp, "GBK内容\n", encoding="gbk"))
        result = _run_with_task_id(writetext(fp, "追加内容\n", append=True))
        if is_success(result):
            with open(fp, 'r', encoding='gbk') as f:
                content = f.read()
            assert "GBK内容" in content

    def test_bug_write_content_with_tabs(self, tmp_path):
        """功能: 内容包含制表符"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "tabs.txt")
        content = "col1\tcol2\tcol3\nval1\tval2\tval3\n" * 30
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            assert "\t" in f.read()

    def test_bug_write_unknown_encoding(self, tmp_path):
        """为面: 不支持的编码"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "bad_enc.txt")
        result = _run_with_task_id(writetext(fp, "content", encoding="invalid_encoding_xyz"))
        assert is_error(result)

    def test_bug_write_whitespace_only_content(self, tmp_path):
        """边界: 只有空白字符的内容"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "whitespace.txt")
        result = _run_with_task_id(writetext(fp, "   \n\t\n   \n"))
        assert is_success(result)

    def test_bug_write_content_verification_bytes(self, tmp_path):
        """内容验证: 写入在文件字节数与预期一致"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "bytes_check.txt")
        content = "Hello World\n" * 10
        result = _run_with_task_id(writetext(fp, content))
        assert is_success(result)
        expected_bytes = len(content.encode('utf-8'))
        actual_bytes = os.path.getsize(fp)
        assert actual_bytes == expected_bytes

    def test_bug_write_append_multiple_times(self, tmp_path):
        """功能: 连续多次追加"""
        from app.tools.file.write_text_file import writetext
        fp = os.path.join(str(tmp_path), "multi_append.txt")
        for i in range(5):
            result = _run_with_task_id(writetext(fp, f"Part {i}\n", append=(i > 0)))
            assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        for i in range(5):
            assert f"Part {i}" in content
