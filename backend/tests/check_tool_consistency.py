# -*- coding: utf-8 -*-
"""
工具一致性检查脚本 v2 - 小健 2026-05-06

检查内容：
1. 每个 _tools.py 中定义的公开函数，是否有对应的注册条目
2. 每个 register 中注册的函数，是否有对应的函数实现
3. 注册时使用的 input_model (Pydantic Schema) 参数是否与函数定义的参数一致
4. Schema中的字段是否与函数签名参数对应

运行方式：python -m tests.check_tool_consistency
"""

import sys
import os
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 先导入registry获取全局注册表
from app.services.tools.registry import tool_registry, ToolCategory

# 模块定义: (目录, tools模块, schema模块, register模块)
TOOL_MODULES = [
    ("code_execution", "code_execution_tools", "code_execution_schema", "code_execution_register"),
    ("data_format", "data_format_tools", "data_format_schema", "data_format_register"),
    ("database", "database_tools", "database_schema", "database_register"),
    ("desktop", "desktop_tools", "desktop_schema", "desktop_register"),
    ("document", "document_tools", "document_schema", "document_register"),
    ("environment", "env_tools", "env_schema", "env_register"),
    ("network", "network_tools", "network_schema", "network_register"),
    ("shell", "shell_tools", "shell_schema", "shell_register"),
    ("support_tool", "support_tool_tools", "support_tool_schema", "support_tool_register"),
    ("system", "system_tools", "system_schema", "system_register"),
    ("time", "time_tools", "time_schema", "time_register"),
    ("file", "file_tools", "file_schema", "file_register"),
]

EXTRA_MODULES = [
    ("desktop", "gui_tools", "gui_schema", "gui_register"),
    ("desktop", "gui_helpers", "gui_helpers_schema", "gui_helpers_register"),
    ("document", "data_analysis_tools", "data_analysis_schema", "data_analysis_register"),
    ("environment", "env_check_tools", "env_check_schema", "env_check_register"),
    ("system", "reg_tools", "reg_schema", "reg_register"),
]

# Category 到 目录 的映射
CATEGORY_DIR_MAP = {
    ToolCategory.CODE_EXECUTION: "code_execution",
    ToolCategory.DATA_FORMAT: "data_format",
    ToolCategory.DATABASE: "database",
    ToolCategory.DESKTOP: "desktop",
    ToolCategory.DOCUMENT: "document",
    ToolCategory.ENVIRONMENT: "environment",
    ToolCategory.NETWORK: "network",
    ToolCategory.SHELL: "shell",
    ToolCategory.SUPPORT_TOOL: "support_tool",
    ToolCategory.SYSTEM: "system",
    ToolCategory.TIME: "time",
    ToolCategory.FILE: "file",
}


def get_public_functions(module) -> Dict[str, inspect.Signature]:
    """获取模块中所有公开函数及其签名（排除import来的、辅助函数）"""
    funcs = {}
    module_file = getattr(module, '__file__', '')
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if name.startswith('_'):
            continue
        # 排除从其他模块导入的函数
        try:
            obj_file = getattr(obj, '__code__', None)
            if obj_file and getattr(obj_file, 'co_filename', '') != module_file:
                continue
        except:
            pass
        try:
            sig = inspect.signature(obj)
            funcs[name] = sig
        except (ValueError, TypeError):
            funcs[name] = None
    return funcs


def get_pydantic_model_fields(model_class) -> Dict[str, Dict[str, Any]]:
    """获取Pydantic模型的字段信息"""
    fields = {}
    for field_name, field_info in model_class.model_fields.items():
        fields[field_name] = {
            'type': str(field_info.annotation),
            'default': field_info.default,
            'is_required': field_info.is_required(),
            'description': field_info.description or '',
        }
    return fields


def get_func_params(sig: inspect.Signature) -> Dict[str, Dict[str, Any]]:
    """从函数签名中提取参数信息"""
    params = {}
    for name, param in sig.parameters.items():
        params[name] = {
            'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
            'default': param.default if param.default != inspect.Parameter.empty else 'REQUIRED',
            'is_required': param.default == inspect.Parameter.empty,
        }
    return params


def compare_params_with_schema(func_name: str, func_params: Dict, schema_fields: Dict) -> List[str]:
    """比较函数参数与Schema字段的一致性"""
    issues = []
    skip_params = {'self', 'cls', 'params', 'kwargs', 'args'}
    func_params = {k: v for k, v in func_params.items() if k not in skip_params}

    func_param_names = set(func_params.keys())
    schema_field_names = set(schema_fields.keys())

    missing_in_schema = func_param_names - schema_field_names
    if missing_in_schema:
        issues.append(f"    [缺Schema字段] 函数有参数 {missing_in_schema} 但Schema中未定义")

    missing_in_func = schema_field_names - func_param_names
    if missing_in_func:
        issues.append(f"    [缺函数参数] Schema有字段 {missing_in_func} 但函数签名中未定义")

    common = func_param_names & schema_field_names
    for param_name in common:
        func_required = func_params[param_name]['is_required']
        schema_required = schema_fields[param_name]['is_required']
        if func_required != schema_required:
            issues.append(f"    [required不一致] '{param_name}': 函数required={func_required}, Schema required={schema_required}")

    return issues


def check_module(dir_name: str, tools_mod_name: str, schema_mod_name: str, register_mod_name: str) -> List[str]:
    """检查单个模块的一致性"""
    issues = []
    base_pkg = f"app.services.tools.{dir_name}"

    # 1. 导入tools模块
    try:
        tools_module = importlib.import_module(f"{base_pkg}.{tools_mod_name}")
    except Exception as e:
        issues.append(f"[导入失败] {base_pkg}.{tools_mod_name}: {e}")
        return issues

    # 2. 导入schema模块
    try:
        schema_module = importlib.import_module(f"{base_pkg}.{schema_mod_name}")
    except Exception as e:
        issues.append(f"[导入失败] {base_pkg}.{schema_mod_name}: {e}")
        schema_module = None

    # 3. 导入register模块（触发注册）
    try:
        register_module = importlib.import_module(f"{base_pkg}.{register_mod_name}")
    except Exception as e:
        issues.append(f"[导入失败] {base_pkg}.{register_mod_name}: {e}")
        return issues

    # 4. 获取tools模块中的公开函数
    func_map = get_public_functions(tools_module)
    func_names = set(func_map.keys())

    # 5. 从全局注册表获取该目录下已注册的工具名
    # 按category查找
    category = None
    for cat, d in CATEGORY_DIR_MAP.items():
        if d == dir_name:
            category = cat
            break

    if category:
        registered_names = set(tool_registry._categories.get(category, []))
    else:
        registered_names = set()

    # 6. 从register模块提取 tool_methods 字典（注册名→实现函数的映射）
    # 这样我们就能知道注册名和函数名的对应关系
    reg_to_func = {}
    if hasattr(register_module, 'tool_methods'):
        for k, v in register_module.tool_methods.items():
            reg_to_func[k] = getattr(v, '__name__', str(v))
    # 尝试从 _register_xxx_tools 的局部变量提取
    # 也可以从 TOOL_INPUT_MODELS 获取注册名列表
    if hasattr(register_module, 'TOOL_INPUT_MODELS'):
        for k in register_module.TOOL_INPUT_MODELS.keys():
            if k not in reg_to_func:
                reg_to_func[k] = "?"

    # 7. 获取所有注册名（包括reg_to_func和registered_names的并集）
    all_reg_names = set(reg_to_func.keys()) | registered_names

    # 8. 函数已定义但可能未被注册（通过注册名映射检查）
    # 需要建立 反向映射: 函数名→注册名
    func_to_reg = {}
    for reg_name, impl_name in reg_to_func.items():
        func_to_reg[impl_name] = reg_name

    # 检查: 函数有定义但无对应注册名
    unregistered_funcs = []
    for fn in func_names:
        if fn in func_to_reg:
            continue
        if fn in all_reg_names:
            continue
        # 函数名可能是注册名（1:1映射）
        unregistered_funcs.append(fn)

    if unregistered_funcs:
        issues.append(f"[函数未注册] {unregistered_funcs} 在 {tools_mod_name}.py 中定义但未在 {register_mod_name}.py 中找到对应注册")

    # 9. 注册了但没有函数实现
    registered_func_impls = set(reg_to_func.values())
    no_impl = []
    for reg_name in all_reg_names:
        impl_name = reg_to_func.get(reg_name, reg_name)
        if impl_name in func_names or impl_name == "?":
            continue
        # 可能是通过类方法(FileTools)实现的
        if impl_name not in func_names and impl_name not in registered_func_impls:
            no_impl.append(reg_name)

    if no_impl:
        issues.append(f"[注册可能无实现] {no_impl} 在register中注册但在tools模块中可能无对应实现(可能是类方法)")

    # 10. Schema参数一致性检查
    if schema_module and hasattr(register_module, 'TOOL_INPUT_MODELS'):
        for reg_name, input_model in register_module.TOOL_INPUT_MODELS.items():
            if not hasattr(input_model, 'model_fields'):
                continue

            schema_fields = get_pydantic_model_fields(input_model)

            # 找到对应的函数签名
            impl_name = reg_to_func.get(reg_name, reg_name)
            sig = func_map.get(impl_name) or func_map.get(reg_name)
            if sig is None:
                # 可能是类方法, 尝试查找
                continue

            func_params = get_func_params(sig)
            param_issues = compare_params_with_schema(reg_name, func_params, schema_fields)
            if param_issues:
                issues.append(f"[参数不一致] 注册名'{reg_name}'(函数'{impl_name}') vs Schema'{input_model.__name__}':")
                issues.extend(param_issues)

    return issues


def main():
    print("=" * 80)
    print("工具一致性检查 v2 - 小健 2026-05-06")
    print("检查项: 函数注册完整性 + Schema参数一致性")
    print("=" * 80)

    all_issues = []

    modules = TOOL_MODULES + EXTRA_MODULES
    for dir_name, tools_mod, schema_mod, register_mod in modules:
        print(f"\n--- 检查模块: {dir_name}/{tools_mod} ---")
        issues = check_module(dir_name, tools_mod, schema_mod, register_mod)
        if issues:
            for issue in issues:
                print(f"  ❌ {issue}")
            all_issues.extend([(dir_name, issue) for issue in issues])
        else:
            print(f"  ✅ 一致性检查通过")

    print("\n" + "=" * 80)
    print(f"检查完成！共发现 {len(all_issues)} 个不一致项")
    print("=" * 80)

    if all_issues:
        print("\n不一致项汇总：")
        for dir_name, issue in all_issues:
            print(f"  [{dir_name}] {issue}")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
