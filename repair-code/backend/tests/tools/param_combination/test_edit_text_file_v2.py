# -*- coding: utf-8 -*-
"""
edit_text_file parameter combination and content test v2
Schema-driven, content >= 100 lines, verify actual content, discover issues
XiaoJian 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest
from app.services.task.task_context import _current_task_id
from app.tools.tool_response import is_success, is_error


def _run_with_task_id(coro):
    """Run coroutine within task_id context"""
    token = _current_task_id.set("test-task-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def _get_rich_content():
    """Generate >= 100 lines of mixed Chinese/English content"""
    return """# Enterprise CRM System - Deployment Guide
# Enterprise CRM System - Deployment Guide

## 1. Overview / System Overview

This document provides comprehensive instructions for deploying the Enterprise
CRM System in production environments. It covers hardware requirements,
software dependencies, configuration steps, and post-deployment verification.

This document provides comprehensive instructions for deploying the Enterprise
CRM System in production environments. It covers hardware requirements,
software dependencies, configuration steps, and post-deployment verification.

## 2. Hardware Requirements / Hardware Requirements

### 2.1 Minimum Configuration / Minimum Configuration
| Component | Requirement | Recommended |
|-----------|-------------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Storage | 100 GB SSD | 500 GB SSD |
| Network | 100 Mbps | 1 Gbps |

### 2.2 Production Configuration / Production Configuration

For production environments with 1000+ concurrent users:
For production environments with 1000+ concurrent users:

- CPU: 16 cores (Intel Xeon or AMD EPYC)
- RAM: 64 GB ECC memory
- Storage: 2 TB NVMe SSD with RAID 10
- Network: 10 Gbps with redundant connections
- Backup: Dedicated backup server with 10 TB storage

## 3. Software Dependencies / Software Dependencies

### 3.1 Required Software / Required Software

```
Python 3.11+ / Python 3.11+
PostgreSQL 15+ / PostgreSQL 15+
Redis 7+ / Redis 7+
Nginx 1.24+ / Nginx 1.24+
Node.js 20 LTS / Node.js 20 LTS
```

### 3.2 Python Packages / Python Packages
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

## 4. Installation Steps / Installation Steps

### Step 1: Clone Repository / Clone Repository

```bash
git clone https://github.com/company/crm-system.git
cd crm-system
git checkout v2.1.0
```

### Step 2: Set Up Virtual Environment / Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\\Scripts\\activate  # Windows

pip install -r requirements.txt
```

### Step 3: Configure Database / Configure Database
```sql
-- Create database
CREATE DATABASE crm_production;
CREATE USER crm_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE crm_production TO crm_user;

-- Enable extensions
\\c crm_production
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

### Step 4: Environment Variables / Environment Variables

```bash
# .env file configuration
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

### Step 5: Run Migrations / Run Migrations

```bash
# Generate migration file
alembic revision --autogenerate -m "initial migration"

# Run migration
alembic upgrade head

# Verify migration
alembic current
alembic history
```

### Step 6: Initialize Data / Initialize Data
```bash
# Create admin user
python scripts/create_admin.py --email admin@company.com --password Admin123!

# Import sample data (optional)
python scripts/seed_data.py --env production
```

### Step 7: Start Services / Start Services

```bash
# Start API service
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Start Celery Worker
celery -A app.celery worker --loglevel=info --concurrency=4

# Start Celery Beat (scheduled tasks)
celery -A app.celery beat --loglevel=info
```

## 5. Nginx Configuration / Nginx Configuration

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

## 6. Post-Deployment Verification / Post-Deployment Verification
### 6.1 Health Check / Health Check
```bash
# Basic health check
curl -f http://localhost:8000/health

# Detailed health check
curl -f http://localhost:8000/health/detailed

# Prometheus metrics
curl http://localhost:8000/metrics
```

### 6.2 Functional Tests / Functional Tests

```bash
# Run API tests
pytest tests/api/ -v --tb=short

# Run integration tests
pytest tests/integration/ -v --tb=short

# Run E2E tests
npx playwright test tests/e2e/
```

### 6.3 Performance Verification / Performance Verification

| Metric | Target | Actual |
|--------|--------|--------|
| Response Time (avg) | < 200ms | OK |
| Response Time (p95) | < 500ms | OK |
| Response Time (p99) | < 1000ms | OK |
| Error Rate | < 0.1% | OK |
| Throughput | > 100 req/s | OK |

## 7. Troubleshooting / Troubleshooting

### 7.1 Common Issues / Common Issues

**Issue**: Database connection refused
**Solution**: Check if PostgreSQL service is running, port is correct
**Issue**: Redis connection timeout
**Solution**: Check Redis service status, ensure firewall rules correct
**Issue**: SSL certificate error
**Solution**: Check certificate file path and permissions, ensure certificate not expired

**Issue**: 502 Bad Gateway
**Solution**: Check if uvicorn service is running, Nginx upstream configuration

### 7.2 Log Analysis / Log Analysis

```bash
# View application logs
tail -f /var/log/crm/app.log

# Search errors
grep -i "error" /var/log/crm/app.log | tail -50

# View slow queries
grep -i "slow query" /var/log/crm/app.log
```

## 8. Backup and Recovery / Backup and Recovery
### 8.1 Database Backup / Database Backup
```bash
# Daily auto backup
pg_dump -U crm_user crm_production | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore backup
gunzip < backup_20260624.sql.gz | psql -U crm_user crm_production
```

### 8.2 File Backup / File Backup

```bash
# Backup uploaded files
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz /var/crm/uploads

# Backup config files
tar -czf config_backup_$(date +%Y%m%d).tar.gz /etc/crm/
```

## 9. Security Checklist / Security Checklist
- [ ] Database password uses strong password
- [ ] SSL certificate correctly configured
- [ ] Firewall rules restrict access
- [ ] API keys rotated periodically
- [ ] Logs do not contain sensitive information
- [ ] File upload size limit configured
- [ ] CORS configuration correct
- [ ] Rate limiting enabled

## 10. Contact Information / Contact Information

- System Administrator: admin@company.com
- Database Admin: dba@company.com
- Security Team: security@company.com
- Emergency Hotline: +86-10-12345678

---
Document Version: 2.1.0
Last Updated: 2026-06-24
Author: DevOps Team
Translation: DevOps Team
"""


class TestEditTextFileParamCombinations:
    """Schema-driven - parameter combination exhaustive test"""

    def test_file_path_old_string_new_string_only(self, tmp_path):
        """Combination 1: file_path + old_string + new_string (required params only)"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit1.txt")
        content = _get_rich_content()
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "Enterprise", "Enterprise-Modified"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "Enterprise-Modified" in modified
        assert modified.count("Enterprise-Modified") == 1

    def test_replace_all(self, tmp_path):
        """Combination 2: file_path + old_string + new_string + replace_all=True"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit2.txt")
        content = "aaa bbb aaa ccc aaa ddd"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "aaa", "xxx", mode="all"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "aaa" not in modified
        assert modified == "xxx bbb xxx ccc xxx ddd"

    def test_replace_all_false(self, tmp_path):
        """Combination 3: file_path + old_string + new_string + replace_all=False (default)"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit3.txt")
        content = "aaa bbb aaa ccc aaa ddd"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "aaa", "xxx"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert modified == "xxx bbb aaa ccc aaa ddd"

    def test_encoding_param(self, tmp_path):
        """Combination 4: file_path + old_string + new_string + encoding"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit4.txt")
        content = "chinese content test chinese content"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "test", "replaced", encoding="utf-8"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "replaced" in modified

    def test_all_params_combined(self, tmp_path):
        """Combination 5: all parameters combined"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit5.txt")
        content = "Line1 test Line2 test Line3"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "test", "done", mode="all", encoding="utf-8"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "test" not in modified
        assert "done" in modified

    def test_replace_multiline_string(self, tmp_path):
        """Combination 6: multiline string replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit6.txt")
        content = """Line 1
Line 2
Line 3
Line 4
Line 5"""
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        old = "Line 2\nLine 3"
        new = "Line-2-Modified\nLine-3-Modified"
        result = _run_with_task_id(edittext(fp, old, new))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "Line-2-Modified" in modified
        assert "Line-3-Modified" in modified

    def test_replace_with_empty_string(self, tmp_path):
        """Combination 7: new_string is empty (delete content)"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit7.txt")
        content = "aaa bbb ccc"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, " bbb", ""))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "bbb" not in modified
        assert "aaa ccc" in modified

    def test_replace_special_characters(self, tmp_path):
        """Combination 8: special character replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit8.txt")
        content = "price = 100; // comment"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "100", "200"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "200" in modified
        assert "100" not in modified


class TestEditTextFileFeatures:
    """Feature tests - verify each feature point"""

    def test_chinese_content(self, tmp_path):
        """Chinese content replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_cn.txt")
        content = "This is Chinese content. Chinese is important."
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "Chinese", "English"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "English" in modified

    def test_code_block_replacement(self, tmp_path):
        """Code block replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_code.txt")
        content = """```python
def old_function():
    pass
```"""
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "old_function", "new_function"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "new_function" in modified
        assert "old_function" not in modified

    def test_table_cell_replacement(self, tmp_path):
        """Table cell replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_table.txt")
        content = """| Name | Age | City |
|------|-----|------|
| Zhang San | 25 | Beijing |
| Li Si | 30 | Shanghai |"""
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "25", "26"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "26" in modified

    def test_replace_in_middle_of_file(self, tmp_path):
        """Middle-of-file replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_mid.txt")
        lines = [f"Line {i}" for i in range(50)]
        content = "\n".join(lines)
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "Line 25", "Line-25-Modified"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "Line-25-Modified" in modified
        assert "Line 0" in modified
        assert "Line 49" in modified

    def test_replace_at_start_of_file(self, tmp_path):
        """Start-of-file replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_start.txt")
        content = "START middle end"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "START", "BEGIN"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert modified.startswith("BEGIN")

    def test_replace_at_end_of_file(self, tmp_path):
        """End-of-file replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_end.txt")
        content = "start middle END"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "END", "FINISH"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert modified.endswith("FINISH")

    def test_consecutive_replacements(self, tmp_path):
        """Consecutive multiple replacements"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_consec.txt")
        content = "aaa bbb ccc"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result1 = _run_with_task_id(edittext(fp, "aaa", "xxx"))
        assert is_success(result1)
        result2 = _run_with_task_id(edittext(fp, "bbb", "yyy"))
        assert is_success(result2)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "xxx yyy ccc" in modified

    def test_replace_preserves_structure(self, tmp_path):
        """Replacement preserves file structure"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_struct.txt")
        content = """# Header

## Section 1
Content 1

## Section 2
Content 2

## Section 3
Content 3"""
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "Content 1", "Content-1-Modified"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "# Header" in modified
        assert "## Section 1" in modified
        assert "## Section 2" in modified
        assert "Content-1-Modified" in modified


class TestEditTextFileRealScenarios:
    """Real business scenario tests"""

    def test_edit_config_value(self, tmp_path):
        """Scenario 1: Edit config value"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "config.yaml")
        content = """app:
  name: CRM System
  version: 2.1.0
  debug: false

database:
  host: localhost
  port: 5432
"""
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "debug: false", "debug: true"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "debug: true" in modified

    def test_edit_log_line(self, tmp_path):
        """Scenario 2: Edit log line"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "app.log")
        lines = []
        for i in range(50):
            level = ["INFO", "WARNING", "ERROR"][i % 3]
            lines.append(f"2026-06-24 {8+i//6:02d}:{(i*10)%60:02d}:00 [{level}] Log message {i}")
        content = "\n".join(lines) + "\n"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "[ERROR] Log message 2", "[CRITICAL] Log message 2"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "[CRITICAL] Log message 2" in modified

    def test_edit_csv_row(self, tmp_path):
        """Scenario 3: Edit CSV row"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "data.csv")
        lines = ["id,name,amount,region"]
        for i in range(30):
            lines.append(f"{i+1},Customer_{i+1},{(i+1)*1000},Region_{i%5+1}")
        content = "\n".join(lines) + "\n"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "Customer_5,5000", "Customer_5,6000"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "Customer_5,6000" in modified

    def test_edit_markdown_heading(self, tmp_path):
        """Scenario 4: Edit Markdown heading"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "readme.md")
        content = """# Old Project Name

## Overview
This is the old description.

## Installation
Follow these steps.
"""
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "# Old Project Name", "# New Project Name"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "# New Project Name" in modified
        assert "## Overview" in modified

    def test_edit_json_value(self, tmp_path):
        """Scenario 5: Edit JSON value"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "config.json")
        content = """{
    "name": "CRM System",
    "version": "2.1.0",
    "debug": false,
    "database": {
        "host": "localhost",
        "port": 5432
    }
}"""
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, '"version": "2.1.0"', '"version": "2.2.0"'))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert '"version": "2.2.0"' in modified


class TestEditTextFileBoundary:
    """Boundary tests"""

    def test_replace_single_char(self, tmp_path):
        """Single character replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_single.txt")
        content = "a"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "a", "b"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert modified == "b"

    def test_replace_very_long_string(self, tmp_path):
        """Very long string replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_long.txt")
        old_str = "A" * 10000
        new_str = "B" * 10000
        content = f"start {old_str} end"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, old_str, new_str))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "B" * 10000 in modified

    def test_replace_unicode_content(self, tmp_path):
        """Unicode content replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_unicode.txt")
        content = "chinese japanese korean arabic emoji smile"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "japanese", "Japanese"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "Japanese" in modified

    def test_replace_with_newlines(self, tmp_path):
        """Replacement content contains newlines"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_newlines.txt")
        content = "line1 placeholder line2"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "placeholder", "new_line1\nnew_line2\nnew_line3"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "new_line1" in modified
        assert "new_line3" in modified

    def test_replace_identical_strings(self, tmp_path):
        """old_string and new_string identical"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_same.txt")
        content = "test content"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "test", "test"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert modified == content

    def test_large_file_edit(self, tmp_path):
        """Large file edit"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "edit_large.txt")
        lines = [f"Line {i}: {'x' * 100}" for i in range(1000)]
        content = "\n".join(lines)
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "Line 500:", "Line-500-Modified:"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "Line-500-Modified:" in modified


class TestEditTextFileNegative:
    """Negative tests - error handling"""

    def test_empty_file_path(self):
        """Empty file path"""
        from app.tools.file.edit_text_file import edittext
        result = _run_with_task_id(edittext("", "old", "new"))
        assert is_error(result)

    def test_invalid_path(self):
        """Invalid path"""
        from app.tools.file.edit_text_file import edittext
        result = _run_with_task_id(edittext("Z:\\nonexistent\\file.txt", "old", "new"))
        assert is_error(result)

    def test_empty_old_string(self):
        """old_string empty"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(tempfile.gettempdir(), "test_empty_old.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("content")
        result = _run_with_task_id(edittext(fp, "", "new"))
        assert is_error(result)

    def test_file_not_exists(self):
        """File does not exist"""
        from app.tools.file.edit_text_file import edittext
        result = _run_with_task_id(edittext("Z:\\nonexistent\\file.txt", "old", "new"))
        assert is_error(result)

    def test_old_string_not_found(self):
        """old_string not found in file"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(tempfile.gettempdir(), "test_not_found.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("content")
        result = _run_with_task_id(edittext(fp, "nonexistent", "new"))
        assert is_error(result)


class TestEditTextFileBugDiscovery:
    """BUG discovery tests - expose known and potential BUGs - XiaoJian 2026-06-24"""

    def test_bug_ignore_case_replace_all_hardcoded_flag(self, tmp_path):
        """BUG#11: _apply_replacement uses hardcoded flags=2 instead of re.IGNORECASE

        edit_text_file.py:99 - flags = 0 if not ignore_case else 2
        Hardcodes re.IGNORECASE=2 instead of using re_mod.IGNORECASE.
        Although CPython re.IGNORECASE==2 is a fact, this is an implementation detail.
        - XiaoJian 2026-06-24
        """
        from app.tools.file.edit_text_file import edittext
        import re
        fp = os.path.join(str(tmp_path), "ignore_case_test.txt")
        content = "Hello HELLO hello HeLLo"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "hello", "REPLACED", mode="all", ignore_case=True))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "REPLACED" in modified
        assert "hello" not in modified.lower() or modified.count("REPLACED") == 4

    def test_bug_ignore_case_single_replace(self, tmp_path):
        """ignore_case + replace_all=False: replace first match only"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "ignore_single.txt")
        content = "Hello HELLO hello HeLLo"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "hello", "REPLACED", ignore_case=True))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert modified.count("REPLACED") == 1
        assert "HELLO" in modified or "hello" in modified or "HeLLo" in modified

    def test_bug_ignore_case_with_chinese(self, tmp_path):
        """ignore_case + Chinese content (Chinese has no case, should replace normally)"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "ignore_cn.txt")
        content = "content A content B content C"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "content", "modified", mode="all", ignore_case=True))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "modified" in modified
        assert "content" not in modified

    def test_bug_ignore_case_regex_special_chars(self, tmp_path):
        """ignore_case + old_string contains regex special chars (should escape)"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "regex_chars.txt")
        content = "price = $100; PRICE = $200;"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "price = $100", "cost = $100", ignore_case=True))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "cost = $100" in modified

    def test_bug_replace_all_count_verification(self, tmp_path):
        """replace_all=True: verify applied_edits count correct"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "count_verify.txt")
        content = "aaa bbb aaa ccc aaa ddd aaa eee"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "aaa", "xxx", mode="all"))
        assert is_success(result)
        # applied_edits 已迁移至 llm_data.metrics.applied.value - 小欧 2026-07-11
        assert result["llm_data"]["metrics"]["applied"]["value"] == 4
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert modified == "xxx bbb xxx ccc xxx ddd xxx eee"

    def test_bug_replace_all_false_count_is_one(self, tmp_path):
        """replace_all=False: verify applied_edits=1"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "count_one.txt")
        content = "aaa bbb aaa ccc aaa"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "aaa", "xxx"))
        assert is_success(result)
        # applied_edits 已迁移至 llm_data.metrics.applied.value - 小欧 2026-07-11
        assert result["llm_data"]["metrics"]["applied"]["value"] == 1

    def test_bug_edit_binary_extension_rejected(self, tmp_path):
        """File type: editing .exe file should be rejected"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "test.exe")
        with open(fp, 'wb') as f:
            f.write(b'\x00\x01\x02')
        result = _run_with_task_id(edittext(fp, "old", "new"))
        assert is_error(result)

    def test_bug_edit_image_extension_rejected(self, tmp_path):
        """File type: editing .png file should be rejected"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "test.png")
        with open(fp, 'wb') as f:
            f.write(b'\x89PNG')
        result = _run_with_task_id(edittext(fp, "old", "new"))
        assert is_error(result)

    def test_bug_edit_pdf_extension_rejected(self, tmp_path):
        """File type: editing .pdf file should be rejected"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "test.pdf")
        with open(fp, 'wb') as f:
            f.write(b'%PDF-1.4')
        result = _run_with_task_id(edittext(fp, "old", "new"))
        assert is_error(result)

    def test_bug_edit_docx_extension_rejected(self, tmp_path):
        """File type: editing .docx file should be rejected"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "test.docx")
        with open(fp, 'wb') as f:
            f.write(b'PK\x03\x04')
        result = _run_with_task_id(edittext(fp, "old", "new"))
        assert is_error(result)

    def test_bug_no_task_id(self, tmp_path):
        """Security: no task_id should error"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "no_task.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("content")
        token = _current_task_id.set(None)
        try:
            result = asyncio.run(edittext(fp, "content", "modified"))
            assert is_error(result)
        finally:
            _current_task_id.reset(token)

    def test_bug_old_string_none(self, tmp_path):
        """Negative: old_string=None"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "none_old.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("content")
        result = _run_with_task_id(edittext(fp, None, "new"))
        assert is_error(result)

    def test_bug_new_string_none(self, tmp_path):
        """Negative: new_string=None"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "none_new.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("content")
        result = _run_with_task_id(edittext(fp, "content", None))
        assert is_error(result)

    def test_bug_edit_gbk_file_with_encoding(self, tmp_path):
        """Encoding: edit GBK encoded file with explicit encoding"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "gbk_edit.txt")
        with open(fp, 'w', encoding='gbk') as f:
            f.write("GBK encoded content test GBK encoded content")
        result = _run_with_task_id(edittext(fp, "test", "replaced", encoding="gbk"))
        assert is_success(result)
        with open(fp, 'r', encoding='gbk') as f:
            modified = f.read()
        assert "replaced" in modified

    def test_bug_edit_preserves_encoding(self, tmp_path):
        """Encoding: file encoding preserved after edit"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "enc_preserve.txt")
        with open(fp, 'w', encoding='gbk') as f:
            f.write("content old content")
        result = _run_with_task_id(edittext(fp, "old", "new", encoding="gbk"))
        assert is_success(result)
        with open(fp, 'rb') as f:
            raw = f.read()
        assert "new".encode('gbk') in raw

    def test_bug_edit_multiline_with_ignore_case(self, tmp_path):
        """ignore_case + multiline replacement"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "multiline_ic.txt")
        content = "Function A\nfunction A\nFUNCTION A\n"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "function a", "def main", mode="all", ignore_case=True))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert modified.count("def main") == 3

    def test_bug_edit_overlapping_matches(self, tmp_path):
        """Boundary: overlapping matches (e.g. "aaa" in "aaaa")"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "overlap.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("aaaa")
        result = _run_with_task_id(edittext(fp, "aaa", "bbb"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "bbb" in modified

    def test_bug_edit_empty_old_string(self, tmp_path):
        """Negative: old_string empty string"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "empty_old.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("content")
        result = _run_with_task_id(edittext(fp, "", "new"))
        assert is_error(result)

    def test_bug_edit_file_not_found(self, tmp_path):
        """Negative: file not found"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "nonexistent.txt")
        result = _run_with_task_id(edittext(fp, "old", "new"))
        assert is_error(result)

    def test_bug_edit_content_verification_rich_file(self, tmp_path):
        """Content verification: precise replacement in rich content file"""
        from app.tools.file.edit_text_file import edittext
        fp = os.path.join(str(tmp_path), "rich_edit.txt")
        lines = [f"Line {i}: content with keyword_{i % 5}" for i in range(100)]
        content = "\n".join(lines)
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run_with_task_id(edittext(fp, "keyword_0", "REPLACED_0", mode="all"))
        assert is_success(result)
        with open(fp, 'r', encoding='utf-8') as f:
            modified = f.read()
        assert "REPLACED_0" in modified
        assert "keyword_0" not in modified
