# -*- coding: utf-8 -*-
"""工具参数问题审查 - 只输出可疑问题 - 小健 2026-05-06"""
import inspect, sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.tools.registry import tool_registry, ToolCategory

ISSUES = []

def check(name, meta):
    schema = meta.input_schema
    if not schema:
        ISSUES.append(f"[{name}] 无Schema")
        return
    
    props = schema.get('properties', {})
    req_set = set(schema.get('required', []))
    
    # 1. 检查每个参数的合理性
    for pname, pinfo in props.items():
        is_req = pname in req_set
        desc = pinfo.get('description', '')
        ptype = pinfo.get('type', '?')
        default = pinfo.get('default', 'N/A')
        
        # 必填但description太短
        if is_req and len(desc) < 5:
            ISSUES.append(f"[{name}] 必填参数'{pname}'描述过短: '{desc}'")
        
        # type为?说明Schema类型未定义
        if ptype == '?':
            ISSUES.append(f"[{name}] 参数'{pname}'类型未定义(type=?), desc='{desc[:40]}'")
        
        # 常见应为可选的参数被标为必填
        always_optional = ['encoding', 'verbose', 'dry_run', 'debug', 'output_format', 
                          'format', 'locale', 'append', 'recursive', 'overwrite', 'force',
                          'create_parents', 'ignore_case', 'sort_by', 'descending']
        if pname in always_optional and is_req:
            ISSUES.append(f"[{name}] '{pname}'通常是可选参数但被标为必填")
        
        # timeout不应为必填
        if 'timeout' in pname.lower() and is_req:
            ISSUES.append(f"[{name}] timeout参数'{pname}'不应为必填")
    
    # 2. 与函数签名对比
    impl = tool_registry._implementations.get(name)
    if not impl:
        return
    actual_func = impl
    if '<lambda>' in getattr(impl, '__name__', ''):
        try:
            actual_func = impl()
        except:
            return
    if not actual_func:
        return
    try:
        sig = inspect.signature(actual_func)
    except:
        return
    
    func_params = {}
    for pname, param in sig.parameters.items():
        if pname in ('self', 'cls', 'kwargs', 'args'):
            continue
        func_params[pname] = param.default == inspect.Parameter.empty
    
    schema_names = set(props.keys())
    func_names = set(func_params.keys())
    
    # 函数有但Schema无
    func_only = func_names - schema_names
    if func_only:
        ISSUES.append(f"[{name}] 函数有参数{func_only}但Schema中无")
    
    # Schema有但函数无
    schema_only = schema_names - func_names
    if schema_only:
        ISSUES.append(f"[{name}] Schema有字段{schema_only}但函数中无")
    
    # required不一致
    for pname in schema_names & func_names:
        schema_req = pname in req_set
        func_req = func_params[pname]
        if schema_req != func_req:
            ISSUES.append(f"[{name}] '{pname}' required不一致: Schema={schema_req}, 函数={func_req}")

for name, meta in sorted(tool_registry._tools.items()):
    check(name, meta)

if ISSUES:
    print(f"发现 {len(ISSUES)} 个问题:")
    for i in ISSUES:
        print(f"  ❌ {i}")
else:
    print("✅ 所有参数合理性检查通过!")
