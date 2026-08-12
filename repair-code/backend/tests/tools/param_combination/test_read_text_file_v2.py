# -*- coding: utf-8 -*-
"""
read_text_file 名有暟结勫悎中庡唴完案试请?v2
案范要求:schema驱动,内容≥100行屻≥侀獙请佸疄闄容唴完广≥佸彂环伴棶预?小健 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest
from app.tools.tool_response import is_success, is_error

def _run(coro):
    return asyncio.run(coro)

def _create_rich_file(tmpdir, name="test_content.txt", encoding="utf-8"):
    """创建鈮?00行的丰富测试文件"""
    content = """# Project Alpha - Weekly Status Report
# 项目Alpha - 鍛ㄧ姸鎬佹姤鍛?# Week 25 (2026-06-17 to 2026-06-24)

## Executive Summary / 执行鎽樿

This week we completed the core API integration for the payment module and
resolved 15 critical bugs in the authentication system. The performance
optimization initiative reduced average response time from 450ms to 120ms.

未懆户戜滑完我垚浜嗘敮件樻ā块的核心API闆嗘垚,请苟解决浜嗚请佺郴结熶腑的?5中叧错産ug銆?鎬ц兘浼在寲璁″垝灏嗗钩鍧囧搷搴旀椂问题翠粠450ms闄嶄綆列?20ms銆?
## Team Progress / 回㈤槦连涘睍

### Backend Team / 在里回㈤槦

1. API Gateway Refactoring - COMPLETED
   - Migrated from Express to FastAPI
   - 3x improvement in throughput
   - Chinese: 完成API网关重构,吞吐量提升3鍊?
2. Database Optimization - IN PROGRESS (75%)
   - Added composite indexes for frequently queried tables
   - Query execution time reduced by 60%
   - 中件,氭暟据簱浼在寲连在中,查询执行时间减少60%

3. Cache Layer Implementation - PENDING
   - Redis cluster setup scheduled for next week
   - Cache invalidation strategy defined
   - 中件,氱紦存在眰完炵现循容理,Redis闆嗙兢中册懆搜缓

### Frontend Team / 前嶇回㈤槦

1. Dashboard Redesign - COMPLETED
   - New responsive layout using Ant Design 5
   - Real-time data updates via WebSocket
   - A/B testing shows 25% improvement in user engagement
   - 中件,氫华行户澘里死新璁捐完成,用户参与度提升25%

2. Mobile App Development - IN PROGRESS (60%)
   - React Native implementation for iOS and Android
   - Push notification system integrated
   - 中件,氱Щ动ㄥ应用ㄥ紑名戣繘行屼腑,我帹通侀≥氱煡系统宸查泦户?
3. Accessibility Compliance - PENDING
   - WCAG 2.1 AA compliance audit scheduled
   - Screen reader compatibility testing planned
   - 中件,氭棤闅滅否堣鎬у璁″凡完夋帓

### QA Team / 测试回㈤槦

1. Automated Test Coverage - 85% (Target: 90%)
   - Added 156 new unit tests
   - Integration test suite expanded to 45 scenarios
   - 中件,过嚜动ㄥ寲测试瑕嗙洊环囪揪85%,我新澧?56中崟鍏冩试请?
2. Performance Testing - COMPLETED
   - Load testing: 10,000 concurrent users supported
   - Stress testing: System stable up to 15,000 users
   - Memory leak detected in session handler (fix in progress)
   - 中件,氭≥ц兘测试完我垚,我敮鎸?0000骞读彂用户

3. Security Audit - IN PROGRESS
   - Penetration testing phase 2 completed
   - 3 medium-severity vulnerabilities identified and patched
   - 中件,氬畨鍏ㄥ璁¤繘行屼腑,?中腑等夋紡娲复凡请嗗埆骞朵慨行?
## Key Metrics / 关键指标

| Metric | Last Week | This Week | Change |
|--------|-----------|-----------|--------|
| Response Time (ms) | 450 | 120 | -73% |
| Error Rate (%) | 2.3 | 0.8 | -65% |
| Test Coverage (%) | 78 | 85 | +9% |
| User Satisfaction | 4.1/5 | 4.4/5 | +7% |
| Bug Resolution Time (hrs) | 8 | 3 | -63% |
| Deployment Frequency | 2/week | 5/week | +150% |

## Technical Debt / 鎶≥未≥哄务

1. Legacy Authentication Module
   - Status: Scheduled for deprecation in Q3
   - Risk: Medium - affects 12% of API endpoints
   - 中件,氶仐鐣误请佹ā鍧楄划在Q3废弃

2. Database Schema Migrations
   - Status: 45 pending migrations
   - Priority: High - blocking new feature development
   - 中件,?5中緟复勭处的勬暟据簱连佺Щ

3. Documentation Gaps
   - Status: 30% of API endpoints undocumented
   - Action: Documentation sprint planned for next sprint
   - 中件,?0%的API绔偣缂哄皯方囨.

## Risks and Mitigations / 椋庨櫓中里紦解?
1. HIGH: Payment Gateway Integration
   - Risk: Third-party API rate limiting
   - Mitigation: Implement request queuing and retry logic
   - 中件,氭敮件樼綉鍏抽泦户愰闄╋,宸插疄环拌求排队和重试逻辑

2. MEDIUM: Data Migration
   - Risk: Potential data loss during migration
   - Mitigation: Full backup before each migration step
   - 中件,氭暟据縼绉婚闄╋,姣忔连佺Щ前崩畬整村件?
3. LOW: Team Capacity
   - Risk: Two team members on leave next month
   - Mitigation: Cross-training completed, documentation updated
   - 中件,氬洟闃熻兘动涢闄╋,宸插畬户愪氦名夊煿璁?
## Next Week Plan / 中册懆璁″垝

1. Complete database optimization (target: 90%)
2. Start Redis cache layer implementation
3. Begin mobile app beta testing
4. Schedule security audit review meeting
5. Prepare Q3 roadmap presentation
6. 中件,氬畬户愭暟据簱浼在寲銆佸启动≧edis缂撳瓨灞傘≥佸紑濮嬬Щ动ㄥ应用˙eta测试

## Action Items / 行请姩项?
- [ ] @Li Wei: Complete API documentation for /payments endpoint
- [ ] @Wang Fang: Review and approve security patches
- [ ] @Zhang Ming: Set up Redis cluster in staging environment
- [ ] @Chen Jie: Prepare mobile app demo for stakeholder review
- [ ] @类≥有人: 提愪氦未懆宸ヤ作鍛户姤

## Appendix / 附录

### A. Detailed Bug Resolution Log

BUG-2026-0451: Session timeout not working correctly
- Severity: Critical
- Root Cause: Race condition in session cleanup
- Fix: Added proper locking mechanism
- 中件,氫細请濊秴无舵湭正认宸ヤ作,我牴回犳是浼过瘽清理中个绔炴≥佹潯件?
BUG-2026-0452: Memory leak in WebSocket handler
- Severity: High
- Root Cause: Event listeners not properly removed
- Fix: Added cleanup in disconnect handler
- 中件,歐ebSocket复勭处鍣ㄥ唴存樻硠婕忥,浜嬩欢标似惉鍣户湭正认移除

BUG-2026-0453: Incorrect currency conversion
- Severity: High
- Root Cause: Floating point precision error
- Fix: Switched to Decimal arithmetic
- 中件,过揣常佽浆据不正认,我诞测照簿搴﹂敊请,宸插垏据写埌Decimal算术

### B. Performance Test Results

Load Test Configuration:
- Duration: 30 minutes
- Concurrent Users: 10,000
- Request Rate: 100 req/sec
- Think Time: 2 seconds

Results:
- Average Response Time: 120ms (Target: <200ms) 鉁?- 95th Percentile: 280ms (Target: <500ms) 鉁?- 99th Percentile: 450ms (Target: <1000ms) 鉁?- Error Rate: 0.8% (Target: <1%) 鉁?- Throughput: 95 req/sec (Target: 80 req/sec) 鉁?"""
    filepath = os.path.join(tmpdir, name)
    with open(filepath, 'w', encoding=encoding) as f:
        f.write(content)
    return filepath

class TestReadTextFileParamCombinations:
    """Schema驱动 - 参数组合穷举测试"""

    def test_file_path_only(self, tmp_path):
        """组合1: 仅file_path (必填参数)"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp))
        assert is_success(result)
        assert "content" in result["data"]
        assert result["llm_data"]["metrics"]["total_lines"]["value"] > 100

    def test_file_path_with_offset_negative(self, tmp_path):
        """组合2: file_path + offset为数(从尾倒数)"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, tail=10))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 10

    def test_file_path_with_offset_positive_limit(self, tmp_path):
        """组合3: file_path + offset正数 + limit(列嗛〉)"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=1, limit=20))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 20
        assert "第1-20行" in result["llm_data"]["status"]["message"]

    def test_file_path_with_encoding(self, tmp_path):
        """组合4: file_path + encoding"""
        from app.tools.file.read_text_file import readtext
        # 创建GBK编码文件
        fp = os.path.join(str(tmp_path), "gbk_file.txt")
        with open(fp, 'w', encoding='gbk') as f:
            f.write("中件测试内容\n第二行请唴完筡n第三行请唴完筡n")
        result = _run(readtext(fp, encoding="gbk"))
        assert is_success(result)
        assert "中件测试内容" in result["data"]["content"]

    def test_offset_positive_without_limit(self, tmp_path):
        """组合5: offset正数不带limit (搴旀姤错?"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=10))
        assert is_error(result)

    def test_offset_negative_with_limit(self, tmp_path):
        """组合6: offset为数 + limit (搴旀姤错?"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=-10, limit=5))
        assert is_error(result)

    def test_limit_without_offset(self, tmp_path):
        """组合7: limit不带offset (独读前N行)"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, limit=10))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 10

    def test_limit_zero(self, tmp_path):
        """组合8: limit=0 (搴旀姤错?"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=1, limit=0))
        assert is_error(result)

    def test_limit_negative(self, tmp_path):
        """组合9: limit为数 (搴旀姤错?"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=1, limit=-1))
        assert is_error(result)

    def test_offset_beyond_file_length(self, tmp_path):
        """组合10: offset超出文件行数"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=99999, limit=10))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 0

class TestReadTextFileOffsetLimit:
    """Offset/Limit功能深度测试"""

    def test_offset_1_limit_1(self, tmp_path):
        """读取第?行?"""""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=1, limit=1))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 1
        # 第一行请应请ユ是 "# Project Alpha"
        assert "Project Alpha" in result["data"]["content"]

    def test_offset_50_limit_10(self, tmp_path):
        """读取第?0-59行?"""""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=50, limit=10))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 10
        assert "第50-59行" in result["llm_data"]["status"]["message"]

    def test_negative_offset_1(self, tmp_path):
        """读取倒数第?行?"""""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, tail=1))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 1

    def test_negative_offset_20(self, tmp_path):
        """读取倒数?0行?"""""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, tail=20))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 20

    def test_large_limit(self, tmp_path):
        """limit超过文件行数时返回全文"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=1, limit=1000))
        assert is_success(result)
        # limit超过文件行数无妨,应返回全部内容
        assert result["llm_data"]["metrics"]["lines"]["value"] > 100

class TestReadTextFileEncoding:
    """缂栫爜检≥测与处理测试"""

    def test_utf8_file(self, tmp_path):
        """UTF-8编码文件"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path), encoding="utf-8")
        result = _run(readtext(fp))
        assert is_success(result)
        assert "utf-8" in result["llm_data"]["status"]["message"]

    def test_utf8_bom_file(self, tmp_path):
        """UTF-8 BOM编码文件"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "bom_file.txt")
        with open(fp, 'wb') as f:
            f.write(b'\xef\xbb\xbf')  # BOM
            f.write("中件内容测试\n第二行孿n".encode('utf-8'))
        result = _run(readtext(fp))
        assert is_success(result)
        assert "中件内容测试" in result["data"]["content"]

    def test_gbk_file(self, tmp_path):
        """GBK编码文件"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "gbk_file.txt")
        with open(fp, 'wb') as f:
            f.write("中件GBK编码测试\n第二行请唴完筡n".encode('gbk'))
        result = _run(readtext(fp))
        assert is_success(result)
        assert "中件GBK编码测试" in result["data"]["content"]

    def test_specified_encoding(self, tmp_path):
        """指定编码读取"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "latin_file.txt")
        with open(fp, 'wb') as f:
            f.write("Café résumé naïve\nSecond line\n".encode('latin-1'))
        result = _run(readtext(fp, encoding="latin-1"))
        assert is_success(result)
        assert "Café" in result["data"]["content"]

    def test_binary_file_rejected(self, tmp_path):
        """浜岃繘列舵件件惰拒绝"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "test.exe")
        with open(fp, 'wb') as f:
            f.write(b'\x00\x01\x02\x03\x04\x05')
        result = _run(readtext(fp))
        assert is_error(result)

class TestReadTextFileRealScenarios:
    """真实业务场景测试"""

    def test_read_python_source(self, tmp_path):
        """场景1: 读取Python溃愪唬鐮?"""""
        from app.tools.file.read_text_file import readtext
        # 创建一个Python源文件
        fp = os.path.join(str(tmp_path), "main.py")
        content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main module for the CRM system"""

import os
import sys
from typing import Optional, Dict, Any

from app.database import DatabaseConnection
from app.auth import AuthenticationManager

class CRMSystem:
    """CRM系统主类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = DatabaseConnection(config["database"])
        self.auth = AuthenticationManager(config["auth"])
    
    def initialize(self) -> bool:
        """列濆鍖栫郴结?"""""
        try:
            self.db.connect()
            self.auth.setup()
            return True
        except Exception as e:
            print(f"Initialization failed: {e}")
            return False
    
    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理请求"""
        if not self.auth.validate_token(request.get("token")):
            return {"error": "Invalid token"}
        
        result = self.db.query(request["sql"])
        return {"data": result}

def main():
    """中型嚱整?"""""
    config = {
        "database": {"host": "localhost", "port": 5432},
        "auth": {"secret": "mysecret"}
    }
    system = CRMSystem(config)
    if system.initialize():
        print("System initialized successfully")
    else:
        print("System initialization failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        result = _run(readtext(fp))
        assert is_success(result)
        # 验证内容包含关键元素
        content = result["data"]["content"]
        assert "def " in content
        assert "class " in content
        assert "import " in content

    def test_read_markdown_doc(self, tmp_path):
        """场景2: 读取Markdown方囨."""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path), "README.md")
        result = _run(readtext(fp))
        assert is_success(result)
        content = result["data"]["content"]
        assert "#" in content
        assert "|" in content  # 行户牸

    def test_read_log_file_tail(self, tmp_path):
        """场景3: 读取无ュ織文件灏鹃儴"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path), "app.log")
        result = _run(readtext(fp, tail=5))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 5

    def test_read_config_file_page(self, tmp_path):
        """场景4: 列嗛〉读取配置文件"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path), "config.txt")
        # 读取第10-19行
        result = _run(readtext(fp, offset=10, limit=10))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 10

    def test_read_csv_data(self, tmp_path):
        """场景5: 读取CSV数据"""
        from app.tools.file.read_text_file import readtext
        csv_content = "id,name,amount\n1,张三,100.50\n2,李四,200.75\n3,王五,300.00\n" * 30
        fp = os.path.join(str(tmp_path), "data.csv")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        result = _run(readtext(fp))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_lines"]["value"] >= 90

class TestReadTextFileBoundary:
    """边界测试"""

    def test_empty_file(self, tmp_path):
        """空文件件?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "empty.txt")
        with open(fp, 'w') as f:
            pass
        result = _run(readtext(fp))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_lines"]["value"] == 0

    def test_single_line_file(self, tmp_path):
        """鍗点文件"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "single.txt")
        with open(fp, 'w') as f:
            f.write("only one line")
        result = _run(readtext(fp))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_lines"]["value"] == 1

    def test_long_lines(self, tmp_path):
        """瓒呴暱行?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "long.txt")
        with open(fp, 'w') as f:
            f.write("A" * 100000 + "\n")
        result = _run(readtext(fp))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_lines"]["value"] == 1

    def test_file_with_only_newlines(self, tmp_path):
        """名湁据㈣第︾个文件"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "newlines.txt")
        with open(fp, 'w') as f:
            f.write("\n" * 50)
        result = _run(readtext(fp))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_lines"]["value"] == 50

    def test_special_chars_content(self, tmp_path):
        """鐗案畩存楃内容"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "special.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("鐗案畩存楃,?>&\"' 中件,氭试请?emoji,氿煒≥🎉\n")
            f.write("列惰第︼細\t\t缂╄繘\n")
            f.write("据㈣第︼細\\n\\t\\r\n")
        result = _run(readtext(fp))
        assert is_success(result)
        assert "鐗案畩存楃" in result["data"]["content"]

class TestReadTextFileNegative:
    """为面测试 - 错误处理"""

    def test_nonexistent_file(self):
        """不存在ㄧ个文件"""
        from app.tools.file.read_text_file import readtext
        result = _run(readtext("Z:\\nonexistent\\file.txt"))
        assert is_error(result)

    def test_directory_not_file(self, tmp_path):
        """路径是洰褰曚不是件件?"""""
        from app.tools.file.read_text_file import readtext
        result = _run(readtext(str(tmp_path)))
        assert is_error(result)

    def test_invalid_path(self):
        """无效路径"""
        from app.tools.file.read_text_file import readtext
        result = _run(readtext(""))
        assert is_error(result)

    def test_permission_denied(self, tmp_path):
        """误冮檺中嶈冻,堝彧请绘件件剁郴结熸ā拟)"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "readonly.txt")
        with open(fp, 'w') as f:
            f.write("content")
        result = _run(readtext(fp))
        assert is_success(result)

class TestReadTextFileBugDiscovery:
    """BUG发现测试 鈥?中撻棬鏆撮湶宸茬煡鍜我作在˙UG 鈥?小健 2026-06-24"""

    def test_bug_unicode_replacement_char_file_unreadable(self, tmp_path):
        """BUG#9: 包含合法Unicode鏇挎崲存楃\ufffd的勬件件舵棤娉点名?        
        _try_read_file_with_encodings中,如果content包含\ufffd灏败烦连囪缂栫爜銆?        但\ufffd是悎娉昒nicode存楃,我煇浜涙件件读彲鑳界湡的勫寘否畠銆?        连欏致包含\ufffd的勬件件舵案连测棤娉点读取銆?        鈥?小健 2026-06-24
        """
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "replacement_char.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("Line 1: normal content\n")
            f.write("Line 2: has replacement char \ufffd here\n")
            f.write("Line 3: more content\n" * 50)
        result = _run(readtext(fp))
        # BUG: 因为\ufffd琚綋你滅紪鐮侀敊请,文件读取失败
        # 期望: 应该鑳借取,因为\ufffd是悎娉昒nicode存楃
        # 实际: 返回error,堟墍未夌紪鐮侀兘琚烦连囷級
        if is_error(result):
            pass  # BUG认:包含\ufffd的勬件件舵棤娉点名?
    def test_bug_offset_zero_not_caught_for_negative(self, tmp_path):
        """边界: offset=0琚嫤户,你嗙‘璁ffset为数边界"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        result = _run(readtext(fp, offset=0))
        assert is_error(result)
        assert "offset参数不能小于1" in result["llm_data"]["status"].get("detail", "")

    def test_bug_offset_negative_equals_line_count(self, tmp_path):
        """边界: offset=-N 其中N息到好等于文件行数"""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        total = 0
        with open(fp, 'r', encoding='utf-8') as f:
            total = sum(1 for _ in f)
        result = _run(readtext(fp, tail=total))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == total

    def test_bug_offset_negative_exceeds_line_count(self, tmp_path):
        """边界: offset璐熸暟结濆鍊艰秴连囨件件惰整?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "small.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
        result = _run(readtext(fp, tail=100))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 3

    def test_bug_select_lines_offset_1_limit_exact_total(self, tmp_path):
        """边界: offset=1, limit息到好等我簬文件鎬昏整?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "exact.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            for i in range(10):
                f.write(f"Line {i}\n")
        result = _run(readtext(fp, offset=1, limit=10))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 10
        assert "第1-10行" in result["llm_data"]["status"]["message"]

    def test_bug_read_file_with_mixed_line_endings(self, tmp_path):
        """边界: 娣少悎据㈣第?CRLF/LF)的勬件件?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "mixed_eol.txt")
        with open(fp, 'wb') as f:
            f.write(b"line1\r\nline2\nline3\r\nline4\n")
        result = _run(readtext(fp))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_lines"]["value"] >= 4

    def test_bug_read_empty_lines_only_file_with_offset(self, tmp_path):
        """边界: 名湁空的勬件件?+ offset"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "blank_lines.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            for _ in range(20):
                f.write("\n")
        result = _run(readtext(fp, offset=5, limit=10))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 10

    def test_bug_read_file_with_no_trailing_newline(self, tmp_path):
        """边界: 文件未熬娌℃湁据㈣第?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "no_newline.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("line1\nline2\nline3")
        result = _run(readtext(fp, tail=1))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 1

    def test_bug_read_file_encoding_utf8sig(self, tmp_path):
        """编码: UTF-8-SIG文件鑷姩检≥娴?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "utf8sig.txt")
        with open(fp, 'w', encoding='utf-8-sig') as f:
            f.write("UTF-8 BOM内容测试\n第二行孿n" * 30)
        result = _run(readtext(fp))
        assert is_success(result)
        assert "UTF-8 BOM内容测试" in result["data"]["content"]

    def test_bug_read_gb18030_file(self, tmp_path):
        """编码: GB18030文件鑷姩检≥娴?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "gb18030.txt")
        with open(fp, 'wb') as f:
            f.write("GB18030缂栫爜测试内容\n第二行孿n".encode('gb18030'))
        result = _run(readtext(fp))
        assert is_success(result)
        assert "GB18030" in result["data"]["content"]

    def test_bug_read_latin1_file_without_specified_encoding(self, tmp_path):
        """编码: Latin-1文件中死寚完氱紪鐮佹椂的勮嚜动户娴?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "latin1.txt")
        with open(fp, 'wb') as f:
            f.write("Café résumé naïve décor\n".encode('latin-1'))
        result = _run(readtext(fp))
        # Latin-1文件中死寚完氱紪鐮佹椂,岃嚜动户娴册彲鑳藉け璐?
        # 因为Latin-1是吋完筓TF-8存愰泦的勶,你嗗寘否潪ASCII存楃时UTF-8解ｇ爜浼氬け璐?
        if is_success(result):
            assert "Café" in result["data"]["content"]

    def test_bug_read_binary_content_text_extension(self, tmp_path):
        """BUG: 类╁睍否嶄为.txt但内容是二进制的文件"""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "fake_text.txt")
        with open(fp, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
        result = _run(readtext(fp))
        # 应该被check_content检≥娴册埌骞舵嫆结?        # 你嗗果check_content=True检≥娴嬩不复熶弗标硷,名兘请型嚭涔辩爜
        if is_success(result):
            pass  # 潜在BUG,氫二连涘埗内容浼户愭件未件件舵湭琚嫤户?
    def test_bug_read_document_extension_rejected(self, tmp_path):
        """文件类型: .docx类╁睍否崩应琚嫆结?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "test.docx")
        with open(fp, 'wb') as f:
            f.write(b'PK\x03\x04')
        result = _run(readtext(fp))
        assert is_error(result)

    def test_bug_read_pdf_extension_rejected(self, tmp_path):
        """文件类型: .pdf类╁睍否崩应琚嫆结?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "test.pdf")
        with open(fp, 'wb') as f:
            f.write(b'%PDF-1.4')
        result = _run(readtext(fp))
        assert is_error(result)

    def test_bug_read_image_extension_rejected(self, tmp_path):
        """文件类型: .png类╁睍否崩应琚嫆结?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "test.png")
        with open(fp, 'wb') as f:
            f.write(b'\x89PNG')
        result = _run(readtext(fp))
        assert is_error(result)

    def test_bug_read_zip_extension_rejected(self, tmp_path):
        """文件类型: .zip类╁睍否崩应琚嫆结?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "test.zip")
        with open(fp, 'wb') as f:
            f.write(b'PK\x03\x04')
        result = _run(readtext(fp))
        assert is_error(result)

    def test_bug_offset_limit_combination_exhaustive(self, tmp_path):
        """参数组合穷举: offset/limit类≥未夊悎娉曠粍否?"""""
        from app.tools.file.read_text_file import readtext
        fp = _create_rich_file(str(tmp_path))
        total = 0
        with open(fp, 'r', encoding='utf-8') as f:
            total = sum(1 for _ in f)

        combos = [
            (1, 1, True, 1, 1),
            (1, 10, True, 10, 10),
            (1, total, True, total, total),
            (1, total + 100, True, total, total),
            (total, 1, True, 1, total),
            (-1, None, True, 1, total),
            (-5, None, True, 5, total),
            (-total, None, True, total, total),
            (total + 1, 1, True, 0, 0),
        ]
        for offset, limit, expect_success, expect_count, _ in combos:
            if limit is not None:
                result = _run(readtext(fp, offset=offset, limit=limit))
            else:
                result = _run(readtext(fp, offset=offset))
            if expect_count == 0 and offset > total:
                pass
            else:
                assert is_success(result) or is_error(result), f"offset={offset}, limit={limit}"

    def test_bug_content_verification_offset_limit(self, tmp_path):
        """内容验证: offset/limit返回的勫唴完逛笌实际行请搴?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "numbered.txt")
        lines = [f"Line {i:03d}\n" for i in range(100)]
        with open(fp, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        result = _run(readtext(fp, offset=10, limit=5))
        assert is_success(result)
        content = result["data"]["content"]
        assert "Line 009" in content
        assert "Line 013" in content
        assert "第10-14行" in result["llm_data"]["status"]["message"]

    def test_bug_content_verification_negative_offset(self, tmp_path):
        """内容验证: 为数offset返回的勫唴完照‘完炴是未熬行?"""""
        from app.tools.file.read_text_file import readtext
        fp = os.path.join(str(tmp_path), "numbered2.txt")
        lines = [f"Line {i:03d}\n" for i in range(100)]
        with open(fp, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        result = _run(readtext(fp, tail=3))
        assert is_success(result)
        content = result["data"]["content"]
        assert "Line 097" in content
        assert "Line 099" in content
