# -*- coding: utf-8 -*-
"""精确对比: 已注册工具的Schema参数 vs 实际函数签名参数 - 小健 2026-05-06"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tools.registry import tool_registry

issues = []

for name, meta in sorted(tool_registry._tools.items()):
    impl = tool_registry._implementations.get(name)
    if impl is None:
        issues.append(f'[{name}] 无实现函数')
        continue

    actual_func = impl
    if callable(impl) and '<lambda>' in getattr(impl, '__name__', ''):
        try:
            actual_func = impl()
        except:
            issues.append(f'[{name}] lambda无法解析')
            continue

    try:
        sig = inspect.signature(actual_func)
    except (ValueError, TypeError):
        issues.append(f'[{name}] 无法获取签名')
        continue

    func_params = {}
    for pname, param in sig.parameters.items():
        if pname in ('self', 'cls', 'kwargs', 'args'):
            continue
        func_params[pname] = {
            'required': param.default == inspect.Parameter.empty,
            'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any'
        }

    func_param_names = set(func_params.keys())
    schema_fields = meta.input_schema.get('properties', {}).keys() if meta.input_schema else []
    required_fields = set(meta.input_schema.get('required', [])) if meta.input_schema else set()
    schema_field_names = set(schema_fields)

    missing_in_schema = func_param_names - schema_field_names
    missing_in_func = schema_field_names - func_param_names

    if missing_in_schema:
        issues.append(f'[{name}] 函数有参数但Schema缺少: {missing_in_schema}')
    if missing_in_func:
        issues.append(f'[{name}] Schema有字段但函数缺少: {missing_in_func}')

    common = func_param_names & schema_field_names
    for pname in sorted(common):
        func_req = func_params[pname]['required']
        schema_req = pname in required_fields
        if func_req != schema_req:
            issues.append(f'[{name}] 参数"{pname}" required不一致: 函数={func_req}, Schema={schema_req}')

if issues:
    print(f'发现 {len(issues)} 个不一致项:')
    for i in issues:
        print(f'  ❌ {i}')
else:
    print('✅ 所有工具的函数参数与Schema完全一致!')
