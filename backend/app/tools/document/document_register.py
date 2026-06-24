# -*- coding: utf-8 -*-
"""
Document Register - 文档操作工具注册点（仅DOCUMENT分类）

【2026-06-18 小欧】DATAANALYSIS 6个工具已迁出到 dataanalysis/ 独立目录
【2026-06-18 小健】添加TOOL_DEPENDENCIES常量管理工具依赖

【工具列表】(共8个) → DOCUMENT分类:
1. read_pdf - 读取PDF文档 (依赖: pdfplumber)
2. read_docx - 读取Word文档 (依赖: python-docx)
3. read_pptx - 读取PPT文档 (依赖: python-pptx)
4. read_xlsx - 读取Excel文档 (依赖: pandas, openpyxl)
5. write_docx - 写入Word文档 (依赖: python-docx)
6. write_xlsx - 写入Excel文档 (依赖: pandas, openpyxl)
7. write_pdf - 写入PDF文档 (依赖: reportlab, pdfplumber)
8. write_pptx - 写入PPT文档 (依赖: python-pptx)

创建时间: 2026-05-02
更新时间: 2026-06-18 小健
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 文档工具依赖配置 — 小健 2026-06-18
# 注意：pip包名与import名不一致时必须用字典格式指定import_name
TOOL_DEPENDENCIES = {
    "read_pdf": ["pdfplumber"],
    "read_docx": [
        {"import_name": "docx", "pip_package": "python-docx"},
    ],
    "read_pptx": [{"import_name": "pptx", "pip_package": "python-pptx"}],
    "read_xlsx": [
        "pandas",
        "openpyxl",
        "xlrd",
    ],
    "write_docx": [{"import_name": "docx", "pip_package": "python-docx"}],
    "write_xlsx": ["pandas", "openpyxl"],
    "write_pdf": ["reportlab", "pdfplumber"],
    "write_pptx": [{"import_name": "pptx", "pip_package": "python-pptx"}],
}


from app.tools.document.document_schema import (
    ReadPdfInput,
    ReadDocxInput,
    ReadPptxInput,
    ReadXlsxInput,
    WriteDocxInput,
    WriteXlsxInput,
    WritePdfInput,
    WritePptxInput,
)

from app.tools.document.read_pdf import read_pdf
from app.tools.document.read_docx import read_docx
from app.tools.document.read_pptx import read_pptx
from app.tools.document.read_xlsx import read_xlsx
from app.tools.document.write_docx import write_docx
from app.tools.document.write_xlsx import write_xlsx
from app.tools.document.write_pdf import write_pdf
from app.tools.document.write_pptx import write_pptx

DESCRIPTIONS = {
    "read_pdf": """读取PDF(.pdf)文件内容。自动提取文本、表格和图片。适用场景:需要读取PDF文档内容时使用。""",
    "read_docx": """读取Word(.docx/.doc)文档内容。自动提取文本和表格。适用场景:需要读取Word文档内容时使用。""",
    "read_pptx": """读取PPT(.pptx)演示文稿内容。自动提取每页文本和备注。适用场景:需要读取PPT内容时使用。""",
    "read_xlsx": """读取Excel(.xls/.xlsx/.csv)文件。自动检测编码和分隔符,自动识别表头。适用场景:需要读取表格数据时使用。""",
    "write_docx": """写入Word(.docx)文档。适用场景:需要生成Word报告、导出文档时使用。""",
    "write_xlsx": """写入Excel(.xlsx)文件。适用场景:需要导出数据到Excel表格时使用。""",
    "write_pdf": """写入PDF(.pdf)文件。适用场景:需要生成PDF报告、归档文档时使用。""",
    "write_pptx": """写入PPT(.pptx)演示文稿。适用场景:需要生成PPT演示文稿时使用。""",

}

EXAMPLES = {
    "read_pdf": [
        {"file_name": "D:/documents/report.pdf"},
    ],
    "read_docx": [
        {"file_name": "D:/documents/report.docx"},
        {"file_name": "D:/documents/report.doc"},
    ],
    "read_pptx": [
        {"file_name": "D:/documents/presentation.pptx"},
    ],
    "read_xlsx": [
        {"file_name": "D:/data/sales.xlsx"},
        {"file_name": "D:/data/sales.xls"},
        {"file_name": "D:/data/sales.csv"},
    ],
    "write_docx": [
        {"file_name": "D:/output/report.docx", "title": "测试报告", "content": "这是测试内容"},
        {"file_name": "D:/output/report_structured.docx", "title": "结构化报告", "content": "# 第一章\n\n正文内容\n\n## 第二节\n\n- 列表项1\n- 列表项2"},
        {"file_name": "D:/output/report_with_table.docx", "title": "数据报告", "content": "# 概述\n\n本次统计结果如下。\n\n## 数据表格\n\n| 项目 | 数值 | 占比 |\n|------|------|------|\n| A | 100 | 40% |\n| B | 150 | 60% |\n\n## 结论\n\n- 数据A占比40%\n- 数据B占比60%"},
        {"file_name": "D:/output/tech_report.docx", "title": "代码审查报告", "content": "# 审查概览\n\n本次审查覆盖3个模块。\n\n## 问题清单\n\n### 严重问题\n\n1. SQL注入风险\n2. 硬编码密钥\n\n### 一般问题\n\n- 缺少错误处理\n- 日志级别不当"},
        {"file_name": "D:/output/data_table.docx", "title": "数据表", "table_data": [["姓名", "年龄", "城市"], ["张三", "25", "北京"], ["李四", "30", "上海"]]},
    ],
    "write_xlsx": [
        {"file_name": "D:/output/data.xlsx", "data": [{"姓名": "张三", "年龄": 25}, {"姓名": "李四", "年龄": 30}]},
        {"file_name": "D:/output/report.xlsx", "data": [{"产品": "A", "销量": 100}, {"产品": "B", "销量": 200}], "sheet_name": "销售数据"},
        {"file_name": "D:/output/empty.xlsx"},
    ],
    "write_pdf": [
        {"file_name": "D:/output/report.pdf", "title": "测试报告", "content": "这是报告内容"},
        {"file_name": "D:/output/structured_report.pdf", "title": "结构化报告", "content": "# 第一章\n\n正文内容\n\n## 第二节\n\n- 列表项1\n- 列表项2"},
        {"file_name": "D:/output/tech_report.pdf", "title": "代码审查报告", "content": "# 审查概览\n\n本次审查覆盖3个模块。\n\n## 问题清单\n\n### 严重问题\n\n1. SQL注入风险\n2. 硬编码密钥"},
        {"file_name": "D:/output/guide.pdf", "title": "使用指南", "content": "# 快速开始\n\n## 安装步骤\n\n1. 下载安装包\n2. 运行安装程序\n3. 配置环境变量\n\n## 注意事项\n\n- 需要管理员权限\n- 建议关闭杀毒软件"},
    ],
    "write_pptx": [
        {"file_name": "D:/output/cover.pptx", "slides": [{"title": "项目汇报"}]},
        {"file_name": "D:/output/slides.pptx", "slides": [{"title": "业绩概览", "content": "本季度销售额增长20%"}]},
        {"file_name": "D:/output/full.pptx", "slides": [{"title": "封面", "subtitle": "2026年度"}, {"title": "数据", "tables": [[["项目", "数值"], ["A", "100"]]]}]},
        {"file_name": "D:/output/bullets.pptx", "slides": [{"title": "要点", "content": [{"type": "bullets", "items": ["完成目标", "提升效率"]}]}]},
    ],
}

TOOL_IMPLEMENTATIONS = {
    "read_pdf": read_pdf,
    "read_docx": read_docx,
    "read_pptx": read_pptx,
    "read_xlsx": read_xlsx,
    "write_docx": write_docx,
    "write_xlsx": write_xlsx,
    "write_pdf": write_pdf,
    "write_pptx": write_pptx,
}

TOOL_INPUT_MODELS = {
    "read_pdf": ReadPdfInput,
    "read_docx": ReadDocxInput,
    "read_pptx": ReadPptxInput,
    "read_xlsx": ReadXlsxInput,
    "write_docx": WriteDocxInput,
    "write_xlsx": WriteXlsxInput,
    "write_pdf": WritePdfInput,
    "write_pptx": WritePptxInput,
}


def _register_document_tools():
    """注册8个文档操作工具到DOCUMENT分类 — 小欧 2026-06-19"""
    
    for name, func in TOOL_IMPLEMENTATIONS.items():
        desc = DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DOCUMENT,
            implementation=func,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            dependencies=TOOL_DEPENDENCIES.get(name, []),
        )
        logger.debug(
            f"[document_register] \u5df2\u6ce8\u518c\u5de5\u5177: {name}, "
            f"Pydantic\u6a21\u578b: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}\u4e2a"
        )


__all__ = [
    "_register_document_tools",
    "read_pdf",
    "read_docx",
    "read_pptx",
    "read_xlsx",
    "write_docx",
    "write_xlsx",
    "write_pdf",
    "write_pptx",
]
