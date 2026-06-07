# -*- coding: utf-8 -*-
"""
Prompt与Schema一致性检查 - 小沈 2026-05-19

检查每个prompt文件中列出的工具名和参数名是否与对应schema一致。
"""
import sys
import os
import re
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.tools.registry import tool_registry, ToolCategory
from app.services.tools import ensure_tools_registered


def get_schema_field_names(input_schema):
    """从JSON Schema dict中提取字段名"""
    if input_schema is None:
        return {}
    if isinstance(input_schema, dict):
        props = input_schema.get('properties', {})
        return set(props.keys())
    elif hasattr(input_schema, 'model_fields'):
        return set(input_schema.model_fields.keys())
    return {}


def extract_prompt_tools(prompt_text):
    """从prompt文本中提取工具名和参数名"""
    tools = {}
    # 匹配模式1: 数字. tool_name - Description
    pattern1 = re.compile(r'^\s*\d+\.\s+(\w+)\s*-?\s*', re.MULTILINE)
    for m in pattern1.finditer(prompt_text):
        tool_name = m.group(1)
        if tool_name not in ('Example', 'Task', 'Use', 'When', 'For', 'If', 'Note', 'Important', 'Remember'):
            tools[tool_name] = {'params': set(), 'raw_line': m.group(0).strip()}
    
    # 匹配模式2: - param_name: Description (参数行，属于最近一个工具)
    # 先找所有工具的位置，然后按位置归属参数
    tool_positions = []
    for m in pattern1.finditer(prompt_text):
        tool_name = m.group(1)
        if tool_name not in ('Example', 'Task', 'Use', 'When', 'For', 'If', 'Note', 'Important', 'Remember'):
            tool_positions.append((m.start(), tool_name))
    
    tool_positions.sort()
    
    # 匹配参数: - param_name: 或 - param_name (REQUIRED)
    param_pattern = re.compile(r'^\s+-\s+(\w+)\s*[:\(]', re.MULTILINE)
    for m in param_pattern.finditer(prompt_text):
        param_name = m.group(1)
        # 找到该参数属于哪个工具（最近的前一个工具）
        for i in range(len(tool_positions) - 1, -1, -1):
            if tool_positions[i][0] < m.start():
                tool_name = tool_positions[i][1]
                if tool_name in tools:
                    tools[tool_name]['params'].add(param_name)
                break
    
    # 匹配示例中的 tool_name: "xxx"
    example_pattern = re.compile(r'"tool_name"\s*:\s*"(\w+)"')
    example_tools = set(example_pattern.findall(prompt_text))
    
    return tools, example_tools


PROMPT_FILES = {
    'file': 'backend/app/services/prompts/file/file_prompts.py',
    'shell': 'backend/app/services/prompts/shell/shell_prompts.py',
    'network': 'backend/app/services/prompts/network/network_prompts.py',
    'desktop': 'backend/app/services/prompts/desktop/desktop_prompts.py',
    'document': 'backend/app/services/prompts/document/document_prompts.py',
    'system': 'backend/app/services/prompts/system/system_prompts.py',
    'meta': 'backend/app/services/prompts/meta/time_prompts.py',
}

# shell/code_execution_prompts.py 是独立agent的prompt，也检查
PROMPT_FILES['shell_code'] = 'backend/app/services/prompts/shell/code_execution_prompts.py'
# document/database_prompts.py 也是独立agent的prompt
PROMPT_FILES['document_db'] = 'backend/app/services/prompts/document/database_prompts.py'


def check_prompts():
    ensure_tools_registered()
    
    # 构建工具schema字段映射
    all_tools = {}
    for t in tool_registry._tools.values():
        if t.expose_to_llm:
            all_tools[t.name] = {
                'category': t.category.value,
                'schema_fields': get_schema_field_names(t.input_schema),
                'schema_title': t.input_schema.get('title', 'Unknown') if isinstance(t.input_schema, dict) else getattr(t.input_schema, '__name__', 'Unknown'),
            }
    
    issues = []
    
    base_dir = os.path.dirname(__file__)
    
    for prompt_cat, prompt_file in PROMPT_FILES.items():
        full_path = os.path.join(base_dir, prompt_file)
        if not os.path.exists(full_path):
            print(f"⚠️ 文件不存在: {prompt_file}")
            continue
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取get_system_prompt中的prompt文本
        # 找到return语句中的长字符串
        prompt_text = content
        
        prompt_tools, example_tools = extract_prompt_tools(prompt_text)
        
        print(f"\n{'─'*60}")
        print(f"Prompt文件: {prompt_file}")
        print(f"  列出工具: {sorted(prompt_tools.keys())}")
        print(f"  示例中工具: {sorted(example_tools)}")
        
        # 检查prompt中列出的每个工具
        for tool_name, tool_info in prompt_tools.items():
            if tool_name not in all_tools:
                print(f"  ❌ {tool_name}: 不在已注册工具中")
                issues.append((prompt_cat, tool_name, f"不在已注册工具中"))
                continue
            
            schema_fields = all_tools[tool_name]['schema_fields']
            prompt_params = tool_info['params']
            
            if not prompt_params and not schema_fields:
                print(f"  ✅ {tool_name}: 无参数，一致")
                continue
            
            if not prompt_params:
                print(f"  ⚠️ {tool_name}: prompt中未提取到参数(schema有: {sorted(schema_fields)})")
                continue
            
            # 比较参数名
            extra_in_prompt = prompt_params - schema_fields
            missing_in_prompt = schema_fields - prompt_params
            
            if not extra_in_prompt and not missing_in_prompt:
                print(f"  ✅ {tool_name}: 参数一致({len(prompt_params)}个)")
            else:
                detail = []
                if extra_in_prompt:
                    detail.append(f"prompt多余参数: {extra_in_prompt}")
                if missing_in_prompt:
                    detail.append(f"prompt缺少参数: {missing_in_prompt}")
                print(f"  ❌ {tool_name}: {'; '.join(detail)}")
                issues.append((prompt_cat, tool_name, '; '.join(detail)))
        
        # 检查prompt中未列出但属于该分类的工具
        # (仅做提醒，不作为error)
    
    # 汇总
    print(f"\n{'='*80}")
    print(f"Prompt与Schema一致性检查汇总")
    print(f"{'='*80}")
    if not issues:
        print("✅ 所有prompt中工具名和参数名与schema一致！")
    else:
        print(f"❌ 发现 {len(issues)} 个不一致项：\n")
        for cat, name, issue in issues:
            print(f"  [{cat}] {name}: {issue}")
    
    return issues


if __name__ == '__main__':
    check_prompts()
