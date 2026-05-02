# -*- coding: utf-8 -*-
"""
DB Helper 工具参数 Schema 定义

【创建时间】2026-05-02 小沈

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional


class CheckDbExistsInput(BaseModel):
    """check_db_exists 工具的输入参数"""
    db_path: str = Field(..., description="数据库文件路径。如 D:/data/app.db")


class GetTableSchemaInput(BaseModel):
    """get_table_schema 工具的输入参数"""
    db_path: str = Field(..., description="数据库文件路径")
    table_name: str = Field(..., description="表名称")


class ValidateUrlInput(BaseModel):
    """validate_url 工具的输入参数"""
    url: str = Field(..., description="要验证的URL。如 https://example.com")
