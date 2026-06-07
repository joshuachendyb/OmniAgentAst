# -*- coding: utf-8 -*-
"""
工具一致性检查脚本 - 小沈 2026-05-19

逐工具检查 register/schema/examples 三方一致性：
1. description是否存在且足够长
2. input_schema中的字段名
3. examples参数名是否与schema字段名一致
"""
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.tools.registry import tool_registry, ToolCategory
from app.services.tools import ensure_tools_registered


def get_schema_field_names(input_schema):
    """从JSON Schema dict或Pydantic model中提取字段名"""
    if input_schema is None:
        return {}, None
    if isinstance(input_schema, dict):
        title = input_schema.get('title', 'Unknown')
        props = input_schema.get('properties', {})
        required = set(input_schema.get('required', []))
        fields = {}
        for fname, finfo in props.items():
            fields[fname] = {
                'required': fname in required,
                'type': finfo.get('type', 'unknown'),
                'description': finfo.get('description', '')[:60]
            }
        return fields, title
    elif hasattr(input_schema, 'model_fields'):
        title = input_schema.__name__
        fields = {}
        for fname, finfo in input_schema.model_fields.items():
            fields[fname] = {
                'required': finfo.is_required(),
                'type': str(finfo.annotation)[:40],
                'description': (finfo.description or '')[:60]
            }
        return fields, title
    return {}, None


def check_all():
    ensure_tools_registered()

    all_tools = list(tool_registry._tools.values())
    llm_tools = [t for t in all_tools if t.expose_to_llm]
    print(f"\n{'='*80}")
    print(f"已注册工具总数: {len(all_tools)}, LLM可见: {len(llm_tools)}")
    print(f"{'='*80}")

    by_category = defaultdict(list)
    for t in llm_tools:
        by_category[t.category.value].append(t)

    issues = []

    for cat_name in sorted(by_category.keys()):
        tools = by_category[cat_name]
        print(f"\n{'─'*60}")
        print(f"分类: {cat_name} ({len(tools)}个LLM可见工具)")
        print(f"{'─'*60}")

        for t in tools:
            tool_issues = []

            # 1. 检查description
            if not t.description or len(t.description.strip()) < 10:
                tool_issues.append(f"⚠️ description缺失或过短(len={len(t.description.strip()) if t.description else 0})")

            # 2. 检查input_schema字段
            schema_fields, schema_title = get_schema_field_names(t.input_schema)
            if not schema_fields:
                tool_issues.append("⚠️ input_schema无字段或为None")

            # 3. 检查examples参数名与schema一致
            if t.examples and schema_fields:
                schema_field_names = set(schema_fields.keys())
                for i, ex in enumerate(t.examples):
                    if isinstance(ex, dict):
                        ex_keys = set(ex.keys())
                        wrong_keys = ex_keys - schema_field_names
                        if wrong_keys:
                            tool_issues.append(f"⚠️ examples[{i}]含schema不存在参数: {wrong_keys} (schema字段: {sorted(schema_field_names)})")

            # 打印工具信息
            status = "✅" if not tool_issues else "❌"
            print(f"  {status} {t.name}")
            print(f"      schema={schema_title or 'None'}, examples={len(t.examples) if t.examples else 0}, desc_len={len(t.description) if t.description else 0}")

            if schema_fields:
                required = [f for f, v in schema_fields.items() if v['required']]
                optional = [f for f, v in schema_fields.items() if not v['required']]
                print(f"      required={required}")
                if optional:
                    print(f"      optional({len(optional)})={optional}")

            for issue in tool_issues:
                print(f"      {issue}")
                issues.append((t.name, cat_name, issue))

    # 汇总
    print(f"\n{'='*80}")
    print(f"一致性检查汇总")
    print(f"{'='*80}")
    if not issues:
        print("✅ 所有工具 register/schema/examples 一致性检查通过！")
    else:
        print(f"❌ 发现 {len(issues)} 个不一致项：\n")
        for name, cat, issue in issues:
            print(f"  [{cat}] {name}: {issue}")

    return issues


if __name__ == '__main__':
    check_all()
