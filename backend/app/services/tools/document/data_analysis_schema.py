# -*- coding: utf-8 -*-
"""
Data Analysis 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.2节 Tool 77-79 定义
【2026-05-19 小沈】参数精简：
- GenerateChartInput: 9→6(砍rotation+color+figure_size)
- AnalyzeDataInput: 8→6(砍sort_ascending+encoding)
- FilterDataInput: 8→6(砍sort_ascending+encoding)

职责：
定义 data_analysis 分类的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union, Literal


class GenerateChartInput(BaseModel):
    """generate_chart 工具的输入参数 - 小沈 2026-05-19 参数精简9→6(砍rotation+color+figure_size)"""
    data: Dict[str, Any] = Field(
        ...,
        description="图表数据（JSON 格式）。如 {\"labels\": [\"A\", \"B\", \"C\"], \"values\": [10, 20, 30]}"
    )
    chart_type: Optional[Literal["bar", "line", "pie", "scatter"]] = Field(
        default="bar",
        description="图表类型。可选值：bar(柱状图)/line(折线图)/pie(饼图)/scatter(散点图)。默认为bar"
    )
    title: Optional[str] = Field(
        default=None,
        description="图表标题，显示在图的正上方。建议使用能概括数据内容的简短标题，不填则不显示标题"
    )
    x_label: Optional[str] = Field(
        default=None,
        description="X轴标签（可选）。不传则不显示X轴标签，pie图表忽略此参数"
    )
    y_label: Optional[str] = Field(
        default=None,
        description="Y轴标签（可选）。不传则不显示Y轴标签，pie图表忽略此参数"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="输出图片路径（可选）。不传则自动生成临时路径如<temp>/chart_<时间戳>.png"
    )


class AnalyzeDataInput(BaseModel):
    """analyze_data 工具的输入参数 - 小沈 2026-05-19 参数精简8→6(砍sort_ascending+encoding)"""
    data: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description="要分析的数据。可以是数组或CSV文件路径"
    )
    operations: Optional[List[str]] = Field(
        default=None,
        description="分析操作（可选）。默认执行全部（mean/sum/count/min/max/std）"
    )
    group_by: Optional[str] = Field(
        default=None,
        description="分组统计的列名。按该列的值对数据进行分组，对每组分别统计。不填则对所有数据整体统计"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="排序的列名。按此列的值对结果升序排列。需搭配 top_n 使用以只获取前N条。不填则不排序"
    )
    top_n: Optional[int] = Field(
        default=None,
        description="只返回排序后的前N条结果。需搭配 sort_by 指定排序列。不填则返回全部结果"
    )
    max_rows: Optional[int] = Field(
        default=None,
        description="最大读取行数（data为文件路径时有效）。None=全部读取"
    )


class FilterDataInput(BaseModel):
    """filter_data 工具的输入参数 - 小沈 2026-05-19 参数精简8→6(砍sort_ascending+encoding)"""
    data: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description="要筛选的数据。可以是数组或CSV/Excel文件路径"
    )
    conditions: List[Dict[str, Any]] = Field(
        ...,
        description="筛选条件列表。每个条件: {\"column\": \"列名\", \"operator\": \"操作符\", \"value\": 值}。操作符: eq/ne/gt/gte/lt/lte/in/contains/not_contains"
    )
    max_rows: Optional[int] = Field(
        default=None,
        description="最大读取行数（data为文件路径时有效）。None=全部读取"
    )
    select_columns: Optional[List[str]] = Field(
        default=None,
        description="选择返回的列（可选）。如 [\"name\", \"age\"]"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="排序的列名。按此列的值对结果升序排列。需搭配 top_n 使用以只获取前N条。不填则不排序"
    )
    top_n: Optional[int] = Field(
        default=None,
        description="只返回排序后的前N条结果。需搭配 sort_by 指定排序列。不填则返回全部结果"
    )
