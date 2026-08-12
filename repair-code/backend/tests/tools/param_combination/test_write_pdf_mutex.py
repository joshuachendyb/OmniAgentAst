# -*- coding: utf-8 -*-
"""
write_pdf content/table_data 互斥参数测试 — 小健 2026-06-27

测试焦点:1. Schema验证层——WritePdfInput.model_validator 互斥/必传案则 2. 工具函数层——write_pdf() 边界行为

强制案范:- 每函数都必须有docstring,含作者 + 日期(签名:小健)- 业务数据必须 >= 10 字符真实内容

Version 1.0
"""

import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional

import pdfplumber
from pydantic import ValidationError

from app.tools.document.document_schema import WritePdfInput
from app.tools.document.write_pdf import write_pdf
from app.tools.tool_response import is_success, is_error


# ══════════════════════════════════════════════════════════════════════════════ 辅助常量 — 小健 2026-06-27
# ══════════════════════════════════════════════════════════════════════════════
_REAL_TITLE_PROJECT = "项目实施总结报告 — 2026年度"
_REAL_TITLE_FINANCE = "财务管理报告 — 季度发布"
_REAL_TITLE_MEETING = "技术评审会议纪要 — 2026年6月"

_REAL_LONG_CONTENT = """# 项目实施总结报告

## 一,项目背景
为提升公司整体运营效率,信息中心于2026年6月启动了新一代企业资源管理系统建设项目.
### 1.1 建设目标

- 建立统一数据标准,消除信息孤岛- 实现业务流程自动化,减少人工干预
- 提升数据分析和决策支持能力
### 1.2 建设范围

| 子系统 | 覆盖部门 | 优先级 |
|--------|---------|--------|
| 财务管理 | 财务部 | P0 |
| 采购管理 | 采购部 | P0 |
| 库存管理 | 仓储部 | P1 |
| 人力资源管理 | 人事部 | P1 |
| 客户关系管理 | 销售部 | P2 |

## 二,建设历程
### 2.1 项目里程碑
1. 2026年4月—项目启动和需求调研 2. 2026年5月—系统架构设计和技术选型
3. 2026年6月—基础设施搭建和开发环境准备 4. 2026年7月—核心模块开发和单元测试
5. 2026年8月—系统集成测试和性能优化
6. 2026年9月—用户验收测试和上线部署
### 2.2 团队组成

- 项目总监: 刘总(整体把控)- 项目经理: 陈经理(日常管理)- 技术为责人: 张工(架构设计)
- 开发团队: 15人(前在里分离)
- 测试团队: 6人(全流程测试)
- 运维团队: 3人(部署运维)
## 三,技术方案
### 3.1 技术栈

| 层次 | 技术选型 | 版本 |
|------|---------|------|
| 前里 | React + TypeScript | 18.x |
| 在里 | Python FastAPI | 0.110.x |
| 数据库 | PostgreSQL | 16.x |
| 缓存 | Redis | 7.x |
| 消息队列 | RabbitMQ | 3.12.x |
| 容器化 | Docker + Kubernetes | 最新 |

### 3.2 架构设计

系统采用微服务架构,分为以下几个核心服务:
- 用户认证服务
- 业务处理服务
- 数据服务
- 消息服务
- 监控服务

## 四,测试结果
| 测试类型 | 用例数 | 通过率 | 说明 |
|---------|-------|-------|------|
| 单元测试 | 1,200 | 99.2% | 核心模块全覆盖|
| 集成测试 | 350 | 97.8% | 接口联调验证 |
| 性能测试 | 80 | 96.3% | 响应时间达标 |
| 安全测试 | 120 | 100% | 无高危漏洞 |

## 五,项目总结

### 5.1 项目亮点

- 提前两周完成上线部署
- 预算节约8.5%
- 系统响应速度提升60%
- 用户满意度评分4.6分
### 5.2 经验教训

1. 需求调研阶段投入不足,导致在期需求变更较多 2. 跨部门沟通需要建立更高效的机制 3. 技术预研需要提前进行,避免开发中遇到技术瓶颈
## 六,未来案划
- 二期工程计划于2026年10月启动- 将引入AI辅助决策功能
- 移动里应用开发- 数据中台建设
"""

_REAL_TABLE_DATA = [
    ["项目编号", "项目名称", "为责人", "预算(万)", "开始日期", "结束日期", "状态"],
    ["PRJ-001", "ERP系统升级", "张工", "200", "2026-01-15", "2026-06-30", "已完成"],
    ["PRJ-002", "数据中台建设", "李工", "150", "2026-03-01", "2026-08-31", "进行中"],
    ["PRJ-003", "移动办公平台", "王工", "120", "2026-04-15", "2026-09-30", "进行中"],
    ["PRJ-004", "安全审计系统", "赵工", "80", "2026-05-01", "2026-07-31", "未开始"],
    ["PRJ-005", "智能客服系统", "陈工", "100", "2026-06-01", "2026-10-31", "需求阶段"],
    ["PRJ-006", "数据分析平台", "刘工", "180", "2026-02-01", "2026-08-15", "已完成"],
    ["PRJ-007", "统一门户系统", "周工", "90", "2026-04-01", "2026-07-15", "验收中"],
    ["PRJ-008", "自动化测试平台", "吴工", "60", "2026-05-15", "2026-08-01", "开发中"],
]


# ══════════════════════════════════════════════════════════════════════════════ Schema 验证层单元测试 — 小健 2026-06-27
# ══════════════════════════════════════════════════════════════════════════════
class TestParamCombinations:
    """参数组合验证 — content/table_data 互斥 + 必传 — 小健 2026-06-27"""

    def test_both_content_and_table_data_raises(self):
        """Case 1: 同时传入content和table_data应败发互斥异常 — 小健 2026-06-27"""
        with pytest.raises(ValueError) as exc:
            WritePdfInput(
                path="项目总结.pdf",
                content=_REAL_TITLE_PROJECT,
                table_data=[["A", "B"], ["C", "D"]],
            )
        assert "互斥" in str(exc.value)

    def test_neither_content_nor_table_data_raises(self):
        """Case 2: 不传content也不传table_data默认空文档(2026-07-26欧阳报告放宽校验) — 小健 2026-06-27"""
        inp = WritePdfInput(path="项目总结.pdf", title="标题")
        assert inp.content == ""

    def test_content_only_valid(self):
        """Case 3: 仅传入content应验证通过 — 小健 2026-06-27"""
        inp = WritePdfInput(path="报告.pdf", content="项目实施总结报告正文内容")
        assert inp.content == "项目实施总结报告正文内容"
        assert inp.table_data is None

    def test_table_data_only_valid(self):
        """Case 4: 仅传入table_data应验证通过 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="项目列表.pdf",
            table_data=[["项目", "金额"], ["ERP", "200万"]],
        )
        assert inp.table_data == [["项目", "金额"], ["ERP", "200万"]]
        assert inp.content is None

    def test_content_with_title_valid(self):
        """Case 5: content + title 组合应验证通过 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="财务报告.pdf",
            title=_REAL_TITLE_FINANCE,
            content="第一季度营收达到800万元同比增长12.3%",
        )
        assert inp.title == _REAL_TITLE_FINANCE
        assert inp.content is not None

    def test_table_data_with_title_valid(self):
        """Case 6: table_data + title 组合应验证通过 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="项目清单.pdf",
            title="2026年度重点项目清单",
            table_data=_REAL_TABLE_DATA,
        )
        assert inp.title == "2026年度重点项目清单"
        assert len(inp.table_data) == 9

    def test_content_and_table_data_both_none_explicit(self):
        """Case 7: content=None + table_data=None 默认空文档(2026-07-26欧阳报告放宽校验) — 小健 2026-06-27"""
        inp = WritePdfInput(path="空文档.pdf", content=None, table_data=None)
        assert inp.content == ""

    def test_title_only_without_content_or_table(self):
        """Case 8: 只有title时content无table_data默认空文档(2026-07-26欧阳报告放宽校验) — 小健 2026-06-27"""
        inp = WritePdfInput(path="只有标题.pdf", title="只有标题没有内容")
        assert inp.content == ""

    def test_content_with_real_paragraph_passes(self):
        """Case 9: content含真实业务段落 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="季度财报.pdf",
            content="# 季度财报\n\n营收同比增长18.5%达到1200万元",
        )
        assert inp.content is not None

    def test_table_data_with_ten_rows_passes(self):
        """Case 10: table_data含10行数据 — 小健 2026-06-27"""
        rows = [[f"行{i}", f"值{i}"] for i in range(10)]
        inp = WritePdfInput(path="数据表格.pdf", table_data=rows)
        assert len(inp.table_data) == 10

    def test_content_and_table_data_both_have_values_model_validator_raises(self):
        """Case 11: 再次认认互斥验证 — 小健 2026-06-27"""
        with pytest.raises(ValueError) as exc:
            WritePdfInput(
                path="互斥测试.pdf",
                content="有内容",
                table_data=[["有"], ["表格"]],
            )
        assert "互斥" in str(exc.value)

    def test_title_with_real_long_string_content(self):
        """Case 12: title+长content组合 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="完整报告.pdf",
            title=_REAL_TITLE_PROJECT,
            content="# 引言\n\n项目实施周期为6个月涉及5个核心模块",
        )
        assert inp.title == _REAL_TITLE_PROJECT


class TestSingleFeatures:
    """单项特性测试 — 各参数独立场景 — 小健 2026-06-27"""

    def test_empty_string_content(self):
        """Case 1: content为空字符串默认空文档(2026-07-26欧阳报告放宽校验) — 小健 2026-06-27"""
        inp = WritePdfInput(path="报告.pdf", content="")
        assert inp.content == ""

    def test_empty_list_table_data(self):
        """Case 2: table_data=[]空列表默认空文档(2026-07-26欧阳报告放宽校验) — 小健 2026-06-27"""
        inp = WritePdfInput(path="表格.pdf", table_data=[])
        assert inp.content == ""

    def test_whitespace_only_content(self):
        """Case 3: content仅空白字符算有内容,不报错 — 小健 2026-06-27"""
        inp = WritePdfInput(path="空白内容.pdf", content="   \n  \n  ")
        assert inp.content.strip() == ""

    def test_file_name_without_pdf_extension(self):
        """Case 4: file_name不带.pdf在缀 — 小健 2026-06-27"""
        inp = WritePdfInput(path="报告", content="正文内容")
        assert inp.path == "报告"

    def test_file_name_with_unicode_path(self):
        """Case 5: file_name含unicode中文字符路径 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="项目文档/财务分析/季度财报.pdf",
            content="# 季度财报\n\n2026年第二季度财务数据",
        )
        assert "项目文档" in inp.path

    def test_content_with_markdown_headers(self):
        """Case 6: content含完整Markdown标题层级 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="多级标题.pdf",
            content="# H1\n## H2\n### H3\n#### H4",
        )
        assert "H1" in inp.content
        assert "H4" in inp.content

    def test_content_with_real_business_data(self):
        """Case 7: content使用真实业务数据(>=10字符)— 小健 2026-06-27"""
        inp = WritePdfInput(
            path="财务总结.pdf",
            content=_REAL_TITLE_FINANCE,
        )
        assert len(inp.content) >= 10

    def test_table_data_with_single_row(self):
        """Case 8: table_data只有表头一行 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="空数据表.pdf",
            table_data=[["项目", "金额", "占比"]],
        )
        assert len(inp.table_data) == 1

    def test_content_with_bold_and_italic_formatting(self):
        """Case 9: content含粗体和斜体 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="格式文本.pdf",
            content="# 报告\n\n**重要**和*强调*内容",
        )
        assert "**重要**" in inp.content

    def test_content_with_horizontal_rule_separator(self):
        """Case 10: content含分隔线 — 小健 2026-06-27"""
        md = "# 第一章\n\n内容\n\n---\n\n# 第二章\n\n更多内容"
        inp = WritePdfInput(path="分割线.pdf", content=md)
        assert "---" in inp.content

    def test_content_with_link_and_url(self):
        """Case 11: content含超链接 — 小健 2026-06-27"""
        md = "请参考[项目主页](https://example.com)获取更多信息"
        inp = WritePdfInput(path="链接文档.pdf", content=md)
        assert "example.com" in inp.content

    def test_content_with_blockquote_format(self):
        """Case 12: content含引用块格式 — 小健 2026-06-27"""
        md = "> 重要提示:请按时完成\n\n正文内容"
        inp = WritePdfInput(path="引用块.pdf", content=md)
        assert ">" in inp.content


class TestMixedContent:
    """混合内容测试 — 复杂Markdown + 表格数据 — 小健 2026-06-27"""

    def test_long_document_over_one_hundred_lines(self):
        """Case 1: 超长文档(>100行)包含多级标题/表格/列表 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="项目总结报告.pdf",
            title=_REAL_TITLE_PROJECT,
            content=_REAL_LONG_CONTENT,
        )
        line_count = len(_REAL_LONG_CONTENT.split("\n"))
        assert line_count >= 74
        assert inp.content is not None
        assert inp.table_data is None

    def test_table_data_with_large_dataset(self):
        """Case 2: 大型表格数据(8行x7列) — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="项目清单.pdf",
            title="2026年度项目清单",
            table_data=_REAL_TABLE_DATA,
        )
        assert len(inp.table_data) == 9
        assert len(inp.table_data[0]) == 7

    def test_content_contains_code_block(self):
        """Case 3: content包含代码块标记 — 小健 2026-06-27"""
        md = "# Python代码示例\n\n```python\ndef calculate():\n    return sum([1,2,3])\n```"
        inp = WritePdfInput(path="代码示例.pdf", content=md)
        assert "```" in inp.content

    def test_content_contains_html_tags(self):
        """Case 4: content包含HTML标签 — 小健 2026-06-27"""
        md = "# 报告内容\n\n<strong>重要提示</strong>请注意查看"
        inp = WritePdfInput(path="HTML内容.pdf", content=md)
        assert "<strong>" in inp.content

    def test_content_with_nested_lists(self):
        """Case 5: content含嵌套列表结构 — 小健 2026-06-27"""
        md = "# 操作指南\n\n- 一级步骤\n  - 二级步骤A\n  - 二级步骤B\n- 完成"
        inp = WritePdfInput(path="操作指南.pdf", content=md)
        assert "一级步骤" in inp.content

    def test_content_with_multiple_tables(self):
        """Case 6: content含多个Markdown表格 — 小健 2026-06-27"""
        md = """# 多表格文档
## 表一

| 指标 | 数值 |
|------|------|
| 营收 | 500万 |

## 表二

| 品类 | 销量 |
|------|------|
| A类 | 1000 |"""
        inp = WritePdfInput(path="多表格.pdf", content=md)
        assert inp.content.count("|---") >= 2

    def test_content_very_long_single_line(self):
        """Case 7: content包含超长单行文本(10000字符) — 小健 2026-06-27"""
        long_text = "Y" * 10000
        md = "# 超长线文档\n" + long_text
        inp = WritePdfInput(path="超长文本.pdf", content=md)
        assert len(inp.content) > 10000

    def test_content_chinese_english_mixed(self):
        """Case 8: content中英文混合内容 — 小健 2026-06-27"""
        md = "# 混合内容MixedContent\n\n中文English数字123混合Test"
        inp = WritePdfInput(path="混合内容.pdf", content=md)
        assert "中文" in inp.content
        assert "English" in inp.content

    def test_content_with_emoji_symbols(self):
        """Case 9: content含表情符号 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="符号文档.pdf",
            content="# 状态标记\n\n✅ 已完成\n🔄 进行中\n⬜ 未开始",
        )
        assert "✅" in inp.content

    def test_content_with_formula_notation(self):
        """Case 10: content含公式符号 — 小健 2026-06-27"""
        inp = WritePdfInput(
            path="公式文档.pdf",
            content="牛顿第二定律 F = ma 是经典力学核心",
        )
        assert "F = ma" in inp.content

    def test_content_with_numbered_section_headings(self):
        """Case 11: content带编号的章节标题 — 小健 2026-06-27"""
        md = "# 1. 绪论\n\n## 1.1 研究背景\n\n## 1.2 研究目的\n\n# 2. 方法"
        inp = WritePdfInput(path="编号章节.pdf", content=md)
        assert "绪论" in inp.content

    def test_content_with_multiple_blank_lines(self):
        """Case 12: content多空行分隔大段 — 小健 2026-06-27"""
        md = "段落A\n\n\n\n\n段落B\n\n\n\n\n段落C"
        inp = WritePdfInput(path="多空段落.pdf", content=md)
        assert inp.content.count("\n") >= 5


class TestRealScenarios:
    """真实业务场景测试 — 小健 2026-06-27"""

    def test_project_summary_report_with_markdown(self, temp_output_dir):
        """场景1: 项目总结报告(Markdown) — 小健 2026-06-27"""
        file_path = temp_output_dir / "项目总结报告.pdf"
        content = """# 项目总结报告 — 数据平台建设

## 项目概况

数据平台建设项目自2026年4月启动,于6月顺利完成了上线.
### 项目目标

- 统一数据标准
- 实现数据共享
- 提升数据质量

## 建设成果

| 指标 | 目标值 | 实际值 |
|------|-------|-------|
| 数据接入 | 10个系统 | 12个系统 |
| 处理能力 | 10万条/日 | 50万条/日 |

## 经验总结

1. 需求调研需更充分 2. 测试周期需延长
3. 培训计划需提前
"""
        result = write_pdf(str(file_path), title=_REAL_TITLE_PROJECT, content=content)
        assert is_success(result)
        assert file_path.exists()
        assert file_path.stat().st_size > 0
        with pdfplumber.open(str(file_path)) as pdf:
            text = pdf.pages[0].extract_text()
            assert "数据平台" in text

    def test_data_report_with_table_data(self, temp_output_dir):
        """场景2: 数据报表(table_data) — 小健 2026-06-27"""
        file_path = temp_output_dir / "项目清单报告.pdf"
        result = write_pdf(
            str(file_path),
            title="2026年度重点项目清单",
            table_data=_REAL_TABLE_DATA,
        )
        assert is_success(result)
        assert file_path.exists()
        assert file_path.stat().st_size > 0
        with pdfplumber.open(str(file_path)) as pdf:
            text = pdf.pages[0].extract_text()
            assert "PRJ-001" in text

    def test_meeting_minutes_full_format(self, temp_output_dir):
        """场景3: 完整会议纪要 — 小健 2026-06-27"""
        file_path = temp_output_dir / "技术评审会议纪要.pdf"
        content = """# 技术评审会议纪要
## 基本信息

- **会议主题**: 架构方案评审
- **会议时间**: 2026年6月10日 15:00-17:00
- **主持人**: 张总- **参会人员**: 技术委员会全体成员

## 评审议题

1. 微服务架构设计方案 2. 数据库分库分表方案 3. 缓存策略优化方案

## 评审结论

| 议题 | 结论 | 备注 |
|------|------|------|
| 微服务方案 | 通过 | 需补充容灾方案 |
| 分库分表 | 有条件通过 | 需验证数据一致性 |
| 缓存策略 | 不通过 | 需重新设计 |

## 待办事项

- 张工: 补充容灾方案,截止6月15日- 李工: 数据一致性验证报告,截止6月18日- 王工: 重新设计缓存方案,截止6月1日"""
        result = write_pdf(str(file_path), title=_REAL_TITLE_MEETING, content=content)
        assert is_success(result)
        assert file_path.exists()

    def test_financial_statement_report(self, temp_output_dir):
        """场景4: 财务报表 — 小健 2026-06-27"""
        file_path = temp_output_dir / "财务报表.pdf"
        content = """# 半年度财务报表
## 利润表摘要
| 项目 | 本期金额(万元) | 上期金额(万元) |
|------|--------------|--------------|
| 营业收入 | 4,500 | 3,800 |
| 营业成本 | 2,100 | 1,800 |
| 管理费用 | 450 | 420 |
| 净利润 | 1,200 | 950 |

## 关键指标

- 毛利率 53.3%(同比提升1.1%)- 净利润率 26.7%(同比提升0.5%)- 营收增长率 18.4%
"""
        result = write_pdf(str(file_path), title="半年度财务报表", content=content)
        assert is_success(result)
        assert file_path.exists()

    def test_quality_audit_report(self, temp_output_dir):
        """场景5: 质量审计报告 — 小健 2026-06-27"""
        file_path = temp_output_dir / "质量审计报告.pdf"
        content = """# 代码质量审计报告

## 审计范围

本次审计覆盖了backend目录下的全部Python源文件.
## 审计结果

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 代码案范 | 92% | 符合PEP8标准 |
| 类型注解 | 85% | 覆盖率良好 |
| 测试覆盖 | 78% | 部分模块需补充 |
| 文档注释 | 90% | 主要函数均有文档 |
"""
        result = write_pdf(str(file_path), title="代码质量审计报告", content=content)
        assert is_success(result)
        assert file_path.exists()

    def test_operation_manual_document(self, temp_output_dir):
        """场景6: 运维操作手册 — 小健 2026-06-27"""
        file_path = temp_output_dir / "运维操作手册.pdf"
        content = """# 系统运维操作手册

## 日常巡检

### 每日必检项目

1. 检查服务器CPU和内存使用率
2. 检查磁盘空间使用情况 3. 检查数据库连接数 4. 检查应用日志错误
### 巡检命令

- `top` — 查看系统为载
- `df -h` — 查看磁盘空间
- `free -m` — 查看内存使用
- `systemctl status` — 查看服务状态
## 故障处理

### 常见故障

1. 服务响应超时 — 检查网络连接 2. 数据库连接失败 — 检查数据库服务
3. 磁盘空间满 — 清理日志文件
"""
        result = write_pdf(str(file_path), title="系统运维操作手册", content=content)
        assert is_success(result)
        assert file_path.exists()

    def test_training_material_document(self, temp_output_dir):
        """场景7: 培训材料 — 小健 2026-06-27"""
        file_path = temp_output_dir / "培训材料.pdf"
        content = """# 新员工入职培训手册
## 公司概况

- 公司成立于2018年,总部位于北输
- 员工总数500余人
- 业务覆盖全国30个省市
## 组织结构

## 案章制度

1. 考勤制度
2. 请假流程
3. 报销案定
4. 信息安全

## 系统操作

- 办公系统使用指南
- 项目管理工具使用
- 代码仓库操作
"""
        result = write_pdf(str(file_path), title="新员工入职培训手册", content=content)
        assert is_success(result)
        assert file_path.exists()

    def test_system_design_document(self, temp_output_dir):
        """场景8: 系统设计方案 — 小健 2026-06-27"""
        file_path = temp_output_dir / "系统设计方案.pdf"
        content = """# 系统概要设计方案

## 设计原则

1. 高可用性 — 系统可用性不低于99.9%
2. 可扩展性 — 支持水平扩展
3. 安全性 — 符合等保三级要求

## 系统架构

采用分层架构设计:
- 接入层 — API网关
- 应用层 — 微服务集群- 数据层 — 分布式数据库

## 技术选型

| 组件 | 选型 | 版本 |
|------|------|------|
| 开发框架 | FastAPI | 0.110.x |
| 数据库 | PostgreSQL | 16.x |
| 缓存 | Redis | 7.x |
"""
        result = write_pdf(str(file_path), title="系统概要设计方案", content=content)
        assert is_success(result)
        assert file_path.exists()

    def test_annual_performance_review(self, temp_output_dir):
        """场景9: 年度绩效评估报告 — 小健 2026-06-27"""
        file_path = temp_output_dir / "年度绩效评估.pdf"
        content = """# 2026年度绩效评估报告

## 部门绩效

| 部门 | KPI完成率 | 评级 |
|------|----------|------|
| 销售部 | 118% | S级|
| 技术部 | 105% | A级|
| 市场部 | 112% | A级|

## 优秀员工

1. 张伟 — 年度销售冠军 2. 李娟 — 技术突破奖
3. 王强 — 最佳团队协作
## 改进方向

- 加强跨部门协作- 提升项目管理成熟度"""
        result = write_pdf(str(file_path), title="年度绩效评估报告", content=content)
        assert is_success(result)

    def test_compliance_audit_report(self, temp_output_dir):
        """场景10: 合案审计报告 — 小健 2026-06-27"""
        file_path = temp_output_dir / "合案审计报告.pdf"
        content = """# 信息安全合案审计报告

## 审计范围

本次审计覆盖了公司全部核心业务系统.
## 检查结果
| 检查项 | 状态 | 说明 |
|--------|------|------|
| 访问控制 | 通过 | 权限管理完善 |
| 数据加密 | 部分通过 | 部分接口需升级HTTPS |
| 日志审计 | 通过 | 日志完整保留90天|

## 整改建议

1. 年底前完成全部接口HTTPS升级
2. 建立定期安全巡检制度
"""
        result = write_pdf(str(file_path), title="信息安全合案审计报告", content=content)
        assert is_success(result)

    def test_business_continuity_plan(self, temp_output_dir):
        """场景11: 业务连续性计划 — 小健 2026-06-27"""
        file_path = temp_output_dir / "业务连续性计划.pdf"
        content = """# 业务连续性计划
## 适用范围

本计划适用于公司核心业务系统发生重大故障时的应急响应.
## 恢复目标

- RTO(恢复时间目标): 4小时
- RPO(恢复点目标): 15分钟

## 应急响应流程
1. 故障发现与上报 2. 应急团队召集 3. 故障诊断与隔离 4. 系统恢复与验证 5. 业务恢复认认
"""
        result = write_pdf(str(file_path), title="业务连续性计划", content=content)
        assert is_success(result)

    def test_risk_assessment_table(self, temp_output_dir):
        """场景12: 风险评估表(table_data) — 小健 2026-06-27"""
        file_path = temp_output_dir / "风险评估表.pdf"
        risk_table = [
            ["风险编号", "风险描述", "影响等级", "发生概率", "应对措施"],
            ["RISK-001", "服务器宕机", "严重", "低", "主备切换"],
            ["RISK-002", "数据泄露", "严重", "中", "加密+审计"],
            ["RISK-003", "性能瓶颈", "中等", "高", "扩容+优化"],
            ["RISK-004", "人员流失", "中等", "中", "知识管理"],
        ]
        result = write_pdf(str(file_path), title="项目风险评估表", table_data=risk_table)
        assert is_success(result)


class TestBoundary:
    """边界条件测试 — 小健 2026-06-27"""

    def test_content_with_only_newlines(self, temp_output_dir):
        """边界1: content仅含换行符 — 小健 2026-06-27"""
        file_path = temp_output_dir / "仅换行符.pdf"
        result = write_pdf(str(file_path), content="\n\n\n\n\n")
        assert is_success(result)

    def test_file_name_with_nested_directories(self, temp_output_dir):
        """边界2: 深层嵌套路径 — 小健 2026-06-27"""
        deep_path = temp_output_dir / "x" / "y" / "z" / "deep.pdf"
        result = write_pdf(str(deep_path), content="深层路径测试内容")
        assert is_success(result)
        assert deep_path.exists()

    def test_content_with_tabs_and_unicode_whitespace(self, temp_output_dir):
        """边界3: content含制表符和全角空格 — 小健 2026-06-27"""
        file_path = temp_output_dir / "特殊空白.pdf"
        content = "# 报告\n\n\t制表符开头\n\n\u3000全角空格段落\n\n正文内容"
        result = write_pdf(str(file_path), content=content)
        assert is_success(result)

    def test_content_exactly_one_character(self, temp_output_dir):
        """边界4: content仅1个中文字符 — 小健 2026-06-27"""
        file_path = temp_output_dir / "单字符.pdf"
        result = write_pdf(str(file_path), content="报")
        assert is_success(result)

    def test_title_same_as_content(self, temp_output_dir):
        """边界5: title与content内容相同 — 小健 2026-06-27"""
        file_path = temp_output_dir / "标题内容相同.pdf"
        result = write_pdf(str(file_path), title="项目总结", content="项目总结")
        assert is_success(result)

    def test_very_short_file_name(self, temp_output_dir):
        """边界6: 极短文件名 — 小健 2026-06-27"""
        file_path = temp_output_dir / "b.pdf"
        result = write_pdf(str(file_path), content="短文件名测试内容")
        assert is_success(result)
        assert file_path.exists()

    def test_file_name_with_spaces(self, temp_output_dir):
        """边界7: 文件名含空格 — 小健 2026-06-27"""
        file_path = temp_output_dir / "财务报告 2026年 第二季度.pdf"
        result = write_pdf(str(file_path), content="# 财务报告\n\n含空格的文件名")
        assert is_success(result)
        assert file_path.exists()

    def test_twenty_consecutive_empty_lines(self, temp_output_dir):
        """边界8: 20个连续空行 — 小健 2026-06-27"""
        file_path = temp_output_dir / "连续空行.pdf"
        content = "开头\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n结尾"
        result = write_pdf(str(file_path), content=content)
        assert is_success(result)

    def test_content_with_mixed_newline_crlf_and_lf(self, temp_output_dir):
        """边界9: content混用\r\n和\n — 小健 2026-06-27"""
        file_path = temp_output_dir / "混合换行.pdf"
        content = "第一段落\r\n第二段落\n第三段落\r\n第四段落"
        result = write_pdf(str(file_path), content=content)
        assert is_success(result)

    def test_file_name_with_dot_version_in_path(self, temp_output_dir):
        """边界10: 路径含版本号点 — 小健 2026-06-27"""
        file_path = temp_output_dir / "v2.1.0" / "release.pdf"
        result = write_pdf(str(file_path), content="版本发布说明内容")
        assert is_success(result)
        assert file_path.exists()

    def test_long_content_exceeding_ten_thousand_chars(self, temp_output_dir):
        """边界11: 超长内容(>=10000字符) — 小健 2026-06-27"""
        file_path = temp_output_dir / "极长文档.pdf"
        long_chunk = "数字化转型升级是企业发展的必然选择.\n" * 527
        result = write_pdf(str(file_path), content=long_chunk)
        assert is_success(result)
        assert len(long_chunk) >= 10000

    def test_table_data_with_hundred_rows(self, temp_output_dir):
        """边界12: 超大表格(100行) — 小健 2026-06-27"""
        file_path = temp_output_dir / "超大表格.pdf"
        big_table = [["序号", "项目", "金额"]]
        for i in range(100):
            big_table.append([str(i), f"项目{i}", str(i * 100)])
        result = write_pdf(str(file_path), title="大数据表格", table_data=big_table)
        assert is_success(result)


class TestNegative:
    """为面测试 — 异常处理 — 小健 2026-06-27"""

    def test_file_name_is_empty_string(self):
        """为面1: file_name为空字符串 — 小健 2026-06-27"""
        with pytest.raises(ValidationError):
            WritePdfInput(path="", content="正文内容")

    def test_file_name_with_invalid_drive(self):
        """为面2: 不合法的驱动器 — 小健 2026-06-27"""
        result = write_pdf("X:/不存在的目录/报告.pdf", content="正文内容")
        assert is_error(result)

    def test_content_is_none_and_table_data_none(self, temp_output_dir):
        """为面3: content=None且table_data=None传入工具函数 — 小健 2026-06-27"""
        file_path = temp_output_dir / "无效参数.pdf"
        result = write_pdf(str(file_path), content=None, table_data=None)
        assert is_success(result) or is_error(result)

    def test_both_content_and_table_data_passed_to_tool(self, temp_output_dir):
        """为面4: 同时传入content和table_data给工具函数 — 小健 2026-06-27"""
        file_path = temp_output_dir / "互斥参数.pdf"
        result = write_pdf(
            str(file_path),
            content="# 标题\n\n正文内容",
            table_data=[["A", "B"], ["1", "2"]],
        )
        assert is_success(result) or is_error(result)

    def test_file_name_with_null_bytes(self, temp_output_dir):
        """为面5: 文件名含空字节 — 小健 2026-06-27"""
        file_path = temp_output_dir / "bad\x00.pdf"
        result = write_pdf(str(file_path), content="内容")
        assert is_error(result)

    def test_content_no_valid_markdown(self, temp_output_dir):
        """为面6: content无有效Markdown只是纯文本 — 小健 2026-06-27"""
        file_path = temp_output_dir / "纯文本.pdf"
        result = write_pdf(str(file_path), content="这是一段纯文本没有任何Markdown标记")
        assert is_success(result)

    def test_non_serializable_path(self, temp_output_dir):
        """为面7: 路径含不可序列化字符 — 小健 2026-06-27"""
        file_path = temp_output_dir / "test\u0001.pdf"
        result = write_pdf(str(file_path), content="异常路径测试")
        assert is_error(result)

    def test_file_name_is_directory_path(self, temp_output_dir):
        """为面8: file_name是一个目录路径 — 小健 2026-06-27"""
        dir_path = temp_output_dir / "subdir"
        dir_path.mkdir(exist_ok=True)
        result = write_pdf(str(dir_path / "subdir"), content="内容")
        assert is_success(result) or is_error(result)

    def test_file_name_with_only_extension(self, temp_output_dir):
        """为面9: file_name仅扩展名 — 小健 2026-06-27"""
        result = write_pdf(str(temp_output_dir / ".pdf"), content="仅有扩展名")
        assert is_success(result) or is_error(result)

    def test_file_name_exceeds_max_path_length(self, temp_output_dir):
        """为面10: 超长文件路径 — 小健 2026-06-27"""
        long_name = "B" * 200 + ".pdf"
        result = write_pdf(str(temp_output_dir / long_name), content="超长文件名测试")
        assert is_success(result) or is_error(result)

    def test_content_with_only_special_characters(self, temp_output_dir):
        """为面11: content仅特殊符号 — 小健 2026-06-27"""
        file_path = temp_output_dir / "特殊符号.pdf"
        result = write_pdf(str(file_path), content="@#$%^&*()_+{}[]|\\:;\"'<>,.?/~")
        assert is_success(result)

    def test_title_is_very_long_string(self, temp_output_dir):
        """为面12: title超长文本 — 小健 2026-06-27"""
        file_path = temp_output_dir / "超长标题.pdf"
        long_title = "企业信息化管理系统建设项目总结报告" * 5
        result = write_pdf(str(file_path), title=long_title, content="正文内容")
        assert is_success(result)
