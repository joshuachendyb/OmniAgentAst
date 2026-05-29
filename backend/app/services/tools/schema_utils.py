# -*- coding: utf-8 -*-
"""
Schema处理工具 — Pydantic JSON Schema 修复和生成

拆分自 registry.py — 小沈 2026-05-29
"""

from typing import Dict, Any, Optional, Type
from pydantic import BaseModel
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


_TYPE_ORDER = ["string", "integer", "number", "boolean", "object", "array", "null"]


def _fix_schema_types(schema: Dict[str, Any]) -> Dict[str, Any]:
    """修复Pydantic生成的JSON Schema中缺失的type字段 - 小健 2026-05-06, 小沈 2026-05-08, 2026-05-13
    
    Pydantic V2对Union/Optional/Dict等复杂类型生成anyOf/oneOf，
    导致OpenAI Schema兼容的properties中缺少type字段。
    此函数遍历properties，为缺少type的字段推断并补上。
    
    【2026-05-13 小沈】不再将Union类型拼成逗号字符串（如"string,array"）。
    原因是opencode/DeepSeek等API严格校验schema，不认逗号格式。
    改为保留anyOf结构，这是标准JSON Schema，所有OpenAI兼容API都支持。
    影响：Parameter Reminder文本中Union类型显示为"any"而非"string,array"，
    不影响实际API调用（传的是input_schema原样，不是reminder文本）。
    """
    if not schema or 'properties' not in schema:
        return schema
    
    properties = schema['properties']
    for prop_name, prop_info in properties.items():
        if 'type' in prop_info:
            continue
        
        if 'anyOf' in prop_info:
            non_null_types = []
            for item in prop_info['anyOf']:
                if isinstance(item, dict) and 'type' in item:
                    t = item['type']
                    if t != 'null':
                        non_null_types.append(t)
            
            if non_null_types:
                unique_types = list(dict.fromkeys(non_null_types))
                if len(unique_types) == 1:
                    prop_info['type'] = unique_types[0]
                # 多个类型：保留anyOf结构，不合并为逗号字符串（opencode/deepseek等API不兼容逗号格式）
        
        if 'oneOf' in prop_info and 'type' not in prop_info:
            non_null_types = []
            for item in prop_info['oneOf']:
                if isinstance(item, dict) and 'type' in item:
                    t = item['type']
                    if t != 'null':
                        non_null_types.append(t)
            
            if non_null_types:
                unique_types = list(dict.fromkeys(non_null_types))
                if len(unique_types) == 1:
                    prop_info['type'] = unique_types[0]
        
        if 'type' not in prop_info and 'anyOf' not in prop_info and 'oneOf' not in prop_info:
            if '$ref' in prop_info:
                prop_info['type'] = 'object'
            elif 'allOf' in prop_info:
                prop_info['type'] = 'object'
            else:
                prop_info['type'] = 'string'
    
    return schema


def _generate_input_schema(input_model: Optional[Type[BaseModel]], input_schema: Optional[Dict]) -> Dict:
    """从 input_model 生成 input_schema（优先于传入的 schema — 小健 2026-05-25）"""
    if input_model is None:
        return input_schema or {}
    try:
        schema = input_model.model_json_schema()
        schema = _fix_schema_types(schema)
        logger.info(f"[ToolRegistry.register] 从 Pydantic 模型生成 input_schema")
        return schema
    except Exception as e:
        logger.error(f"[ToolRegistry.register] 从 Pydantic 模型生成 Schema 失败: {e}")
        return input_schema or {}
