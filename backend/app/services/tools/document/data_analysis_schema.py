# -*- coding: utf-8 -*-
"""
Data Analysis 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.2节 Tool 77-79 定义

职责：
定义 data_analysis 分类的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
【修正 2026-05-05 小沈】
1. GenerateChartInput.figure_size 改为 Tuple[float,float] + validator
2. AnalyzeDataInput 新增 encoding/max_rows 参数
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List, Union, Tuple


# 【2026-05-19 小沈】ReadCsvDataframeInput 已删除
# read_csv_dataframe 工具已迁入 document_tools.py（read_document统一入口）
# 保留 GenerateChartInput 及以下活跃 Schema


class GenerateChartInput(BaseModel):
    """generate_chart 工具的输入参数（Tool 78）
    【修正 2026-05-05 小沈】figure_size 改为 Tuple[float,float] + validator
    """
    data: Dict[str, Any] = Field(
        ...,
        description="图表数据（JSON 格式）。如 {\"labels\": [\"A\", \"B\", \"C\"], \"values\": [10, 20, 30]}"
    )
    chart_type: Optional[str] = Field(
        default="bar",
        description="图表类型。Agent根据数据特征自动判断（趋势→line，比例→pie）。可选值：bar/line/pie/scatter。默认为bar"
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
    figure_size: Optional[Tuple[float, float]] = Field(
        default=None,
        description="图表尺寸，必须为2个正数的元组。默认为(10, 6)"
    )
    rotation: Optional[int] = Field(
        default=0,
        description="X轴标签旋转角度（可选）。如 45，设置标签旋转避免重叠"
    )
    color: Optional[str] = Field(
        default=None,
        description="图表颜色（可选）。如 #FF5733 或 blue"
    )

    @field_validator("figure_size")
    @classmethod
    def validate_figure_size(cls, v):
        """校验figure_size必须为2个正数 - 小沈 2026-05-05"""
        if v is not None:
            if len(v) != 2:
                raise ValueError("figure_size必须包含2个元素(宽, 高)")
            if v[0] <= 0 or v[1] <= 0:
                raise ValueError("figure_size的宽和高必须为正数")
        return v


class AnalyzeDataInput(BaseModel):
    """analyze_data 工具的输入参数（Tool 79）
    【修正 2026-05-05 小沈】新增 encoding/max_rows 参数
    """
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
    sort_by: Optional[str] = Field(
        default=None,
        description="排序字段（可选）。按指定列排序"
    )
    sort_ascending: Optional[bool] = Field(
        default=True,
        description="升序/降序。默认为True（升序）"
    )
    top_n: Optional[int] = Field(
        default=None,
        description="返回前N条（可选）。如 top_n=10 返回前10条"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="文件编码。当data为文件路径时使用，中文文件→gbk。默认为utf-8"
    )
    max_rows: Optional[int] = Field(
        default=None,
        description="最大读取行数（可选）。当data为文件路径时使用，None=全部读取。默认 None - 小沈 2026-05-05"
    )


# 【2026-05-19 小沈】ReadExcelDataframeInput 已删除
# read_excel_dataframe 工具已迁入 document_tools.py（read_document统一入口）


class FilterDataInput(BaseModel):
    """filter_data 工具的输入参数 - 小沈 2026-05-05"""
    data: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description="要筛选的数据。可以是数组或CSV/Excel文件路径"
    )
    conditions: List[Dict[str, Any]] = Field(
        ...,
        description="筛选条件列表。每个条件: {\"column\": \"列名\", \"operator\": \"操作符\", \"value\": 值}。操作符: eq(=), ne(!=), gt(>), gte(>=), lt(<), lte(<=), in(在列表中), contains(包含文本), not_contains(不包含文本)"
    )
    select_columns: Optional[List[str]] = Field(
        default=None,
        description="选择返回的列（可选）。如 [\"name\", \"age\"]"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="排序字段（可选）"
    )
    sort_ascending: Optional[bool] = Field(
        default=True,
        description="升序/降序。默认为True（升序）"
    )
    top_n: Optional[int] = Field(
        default=None,
        description="返回前N条（可选）"
    )
