# -*- coding: utf-8 -*-
"""
Data Analysis 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.2节 Tool 77-79 定义

职责：
定义 data_analysis 分类的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union


class ReadCsvDataframeInput(BaseModel):
    """read_csv_dataframe 工具的输入参数（Tool 77）"""
    file_path: str = Field(
        ...,
        description="CSV 文件路径。如 D:/data/users.csv"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="文件编码（可选）。Agent根据文件来源自动判断，中文文件→gbk/GB2312，英文→utf-8，支持utf-8-sig（带BOM）"
    )
    delimiter: Optional[str] = Field(
        default=",",
        description="分隔符（可选）。Agent根据文件内容自动检测，CSV→逗号，TSV→制表符，中文CSV常用分号"
    )
    has_header: Optional[bool] = Field(
        default=True,
        description="是否有表头（可选）。Agent分析第一行是否为表头，自动判断"
    )
    max_rows: Optional[int] = Field(
        default=1000,
        description="最大读取行数（可选）。Agent根据文件大小自动调整，大文件→500，小文件→2000"
    )


class GenerateChartInput(BaseModel):
    """generate_chart 工具的输入参数（Tool 78）"""
    data: Dict[str, Any] = Field(
        ...,
        description="图表数据（JSON 格式）。如 {\"labels\": [\"A\", \"B\", \"C\"], \"values\": [10, 20, 30]}"
    )
    chart_type: Optional[str] = Field(
        default="bar",
        description="图表类型（可选）。Agent根据数据特征自动判断，趋势数据→line，比例数据→pie，可选 bar/line/pie/scatter"
    )
    title: Optional[str] = Field(
        default=None,
        description="图表标题（可选）。Agent根据数据内容生成描述性标题"
    )
    x_label: Optional[str] = Field(
        default=None,
        description="X轴标签（可选）。Agent从数据列名推断"
    )
    y_label: Optional[str] = Field(
        default=None,
        description="Y轴标签（可选）。Agent从数据列名推断"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="输出图片路径（可选）。Agent根据上下文自动生成，含时间戳"
    )


class AnalyzeDataInput(BaseModel):
    """analyze_data 工具的输入参数（Tool 79）"""
    data: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description="要分析的数据。可以是数组（如 [{\"name\": \"A\", \"value\": 10}]）或 CSV 文件路径（如 \"D:/data/users.csv\"）"
    )
    operations: Optional[List[str]] = Field(
        default=None,
        description="分析操作（可选）。Agent根据query语义推断所需操作，默认执行全部（mean/sum/count/min/max/std）"
    )
    group_by: Optional[str] = Field(
        default=None,
        description="分组字段（可选）。Agent根据query推断分组字段"
    )
