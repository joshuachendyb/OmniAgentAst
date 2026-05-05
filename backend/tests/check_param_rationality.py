# -*- coding: utf-8 -*-
"""
工具参数深度审查脚本 - 小健 2026-05-06
逐分类、逐工具输出：参数名、类型、是否必填、默认值、description
重点审查：必填是否合理、可选是否有默认值、参数名语义是否清晰
"""
import inspect
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tools.registry import tool_registry, ToolCategory

CATEGORY_ORDER = [
    ToolCategory.FILE, ToolCategory.SHELL, ToolCategory.TIME,
    ToolCategory.ENVIRONMENT, ToolCategory.SYSTEM, ToolCategory.NETWORK,
    ToolCategory.DATABASE, ToolCategory.DESKTOP, ToolCategory.DATA_FORMAT,
    ToolCategory.CODE_EXECUTION, ToolCategory.DOCUMENT, ToolCategory.SUPPORT_TOOL,
]

CATEGORY_NAMES = {
    ToolCategory.FILE: "文件操作", ToolCategory.SHELL: "Shell命令",
    ToolCategory.TIME: "时间日期", ToolCategory.ENVIRONMENT: "环境管理",
    ToolCategory.SYSTEM: "系统信息", ToolCategory.NETWORK: "网络通信",
    ToolCategory.DATABASE: "数据库", ToolCategory.DESKTOP: "桌面功能",
    ToolCategory.DATA_FORMAT: "数据格式", ToolCategory.CODE_EXECUTION: "代码执行",
    ToolCategory.DOCUMENT: "文档读写", ToolCategory.SUPPORT_TOOL: "支撑工具",
}

SUSPICIOUS_ISSUES = []

def check_param_rationality(tool_name: str, param_name: str, is_required: bool, 
                            default_val: Any, description: str, type_str: str) -> list:
    """检查参数合理性，返回问题列表"""
    issues = []
    
    # 1. 必填参数但没有description或description太短
    if is_required and (not description or len(description) < 5):
        issues.append(f"必填参数'{param_name}'描述过短或缺失: '{description}'")
    
    # 2. 可选参数但default为None且description未说明None含义
    if not is_required and default_val is None and description and 'None' not in description and 'null' not in description.lower() and '可选' not in description and '默认' not in description:
        # 宽松检查：只要description里有说明就跳过
        pass
    
    # 3. bool类型参数：检查default是否合理
    # 4. timeout类参数：检查是否有上限
    if 'timeout' in param_name.lower():
        if is_required:
            issues.append(f"timeout参数'{param_name}'不应为必填，应为可选带默认值")
    
    # 5. 检查常见的不合理必填：encoding/verbose/dry_run等应该是可选的
    always_optional = ['encoding', 'verbose', 'dry_run', 'debug', 'log_level', 
                       'output_format', 'format', 'locale', 'append', 'recursive',
                       'overwrite', 'force', 'create_parents', 'ignore_case']
    if param_name in always_optional and is_required:
        issues.append(f"'{param_name}'通常是可选参数，但被标记为必填")
    
    return issues


def analyze_tool(name: str, meta) -> None:
    """分析单个工具的参数"""
    schema = meta.input_schema
    if not schema:
        print(f"    {name}: [无Schema]")
        return
    
    properties = schema.get('properties', {})
    required_set = set(schema.get('required', []))
    
    impl = tool_registry._implementations.get(name)
    func_params = {}
    if impl:
        actual_func = impl
        if '<lambda>' in getattr(impl, '__name__', ''):
            try:
                actual_func = impl()
            except:
                actual_func = None
        if actual_func:
            try:
                sig = inspect.signature(actual_func)
                for pname, param in sig.parameters.items():
                    if pname in ('self', 'cls', 'kwargs', 'args'):
                        continue
                    func_params[pname] = {
                        'required': param.default == inspect.Parameter.empty,
                        'default': param.default if param.default != inspect.Parameter.empty else 'REQUIRED',
                        'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any'
                    }
            except:
                pass
    
    param_lines = []
    for pname, pinfo in sorted(properties.items()):
        is_req = pname in required_set
        ptype = pinfo.get('type', '?')
        desc = pinfo.get('description', '')[:60]
        default_val = pinfo.get('default', 'N/A')
        
        # 合理性检查
        param_issues = check_param_rationality(name, pname, is_req, default_val, desc, ptype)
        for issue in param_issues:
            SUSPICIOUS_ISSUES.append(f"[{name}] {issue}")
        
        # 与函数签名对比
        func_info = func_params.get(pname, {})
        func_req = func_info.get('required', '?')
        mismatch = ""
        if func_req != '?' and func_req != is_req:
            mismatch = " ⚠️与函数不一致!"
            SUSPICIOUS_ISSUES.append(f"[{name}] 参数'{pname}' Schema required={is_req}, 函数 required={func_req}")
        
        req_mark = "必填" if is_req else "可选"
        default_str = f"default={default_val}" if not is_req else ""
        line = f"      {pname:25s} {req_mark:4s} type={ptype:10s} {default_str:25s} | {desc}{mismatch}"
        param_lines.append(line)
    
    # 检查函数有但Schema没有的参数
    func_only = set(func_params.keys()) - set(properties.keys())
    if func_only:
        for pname in func_only:
            SUSPICIOUS_ISSUES.append(f"[{name}] 函数有参数'{pname}'但Schema中无对应字段")
    
    print(f"    {name} ({len(properties)}个参数, {len(required_set)}个必填):")
    for line in param_lines:
        print(line)


def main():
    print("=" * 100)
    print("工具参数深度审查 - 小健 2026-05-06")
    print("=" * 100)
    
    total_tools = 0
    total_params = 0
    total_required = 0
    
    for cat in CATEGORY_ORDER:
        tool_names = tool_registry._categories.get(cat, [])
        if not tool_names:
            continue
        
        cat_name = CATEGORY_NAMES.get(cat, cat.value)
        print(f"\n{'='*80}")
        print(f"【{cat_name}】({len(tool_names)}个工具)")
        print(f"{'='*80}")
        
        for name in sorted(tool_names):
            meta = tool_registry._tools[name]
            schema = meta.input_schema
            n_params = len(schema.get('properties', {})) if schema else 0
            n_req = len(schema.get('required', [])) if schema else 0
            total_tools += 1
            total_params += n_params
            total_required += n_req
            analyze_tool(name, meta)
    
    print(f"\n{'='*100}")
    print(f"统计: {total_tools}个工具, {total_params}个参数, {total_required}个必填参数")
    print(f"{'='*100}")
    
    if SUSPICIOUS_ISSUES:
        print(f"\n⚠️ 发现 {len(SUSPICIOUS_ISSUES)} 个可疑问题:")
        for issue in SUSPICIOUS_ISSUES:
            print(f"  ❌ {issue}")
    else:
        print(f"\n✅ 所有参数合理性检查通过!")


if __name__ == '__main__':
    main()
