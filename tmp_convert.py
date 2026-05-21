# -*- coding: utf-8 -*-
"""Batch convert to_unified_format_func calls in file_helpers.py - 小沈 2026-05-21"""
import re

with open('backend/app/services/tools/toolhelper/file_helpers.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
new_lines = []
i = 0
call_count = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()

    if 'return to_unified_format_func(' in stripped:
        call_count += 1
        # Collect the full call (may span multiple lines)
        call_lines = [line]
        open_braces = stripped.count('(') - stripped.count(')')
        j = i + 1
        while j < len(lines) and open_braces > 0:
            call_lines.append(lines[j])
            open_braces += lines[j].count('(') - lines[j].count(')')
            j += 1

        # Skip to after the call
        i = j

        full_call = '\n'.join(call_lines)

        # Check if this is a final_result passthrough (no inner dict start)
        has_success_true = '"success": True' in full_call or "'success': True" in full_call
        has_success_false = '"success": False' in full_call or "'success': False" in full_call
        has_inner_dict = '{' in full_call.replace('return to_unified_format_func(', '', 1).split(',')[0] if ',' in full_call else False

        if not has_success_true and not has_success_false and 'final_result' in full_call:
            indent = re.match(r'^(\s+)', line)
            ind = indent.group(1) if indent else ''
            # Extract the variable name (e.g., final_result)
            var_match = re.search(r'to_unified_format_func\((\w+)', full_call)
            var_name = var_match.group(1) if var_match else 'result'
            new_lines.append(f'{ind}return {var_name}')
            continue

        # Try to extract error message and data
        error_match = re.search(r'"error":\s*"([^"]*)"', full_call)
        data_match = re.search(r'"data":\s*(\{[^}]*\}|None)', full_call)

        indent = re.match(r'^(\s+)', line)
        ind = indent.group(1) if indent else ''

        if has_success_false:
            err = error_match.group(1) if error_match else "执行失败"
            new_lines.append(f'{ind}return {{"code": "ERROR", "data": None, "message": "{err}"}}')
        elif has_success_true:
            new_lines.append(f'{ind}return {{"code": "SUCCESS", "data": {{}}, "message": "操作完成"}}')
        else:
            new_lines.append(f'{ind}# TODO-STEP1: {full_call.strip()[:80]}')
    else:
        new_lines.append(line)
        i += 1

# Also remove to_unified_format_func from function signatures
result = '\n'.join(new_lines)
# Remove the parameter from function signatures
result = result.replace('to_unified_format_func=None,\n    ', '')
result = result.replace('to_unified_format_func: 统一格式转换函数\n    ', '')

with open('backend/app/services/tools/toolhelper/file_helpers.py', 'w', encoding='utf-8') as f:
    f.write(result)

print(f"Done. Converted {call_count} calls, removed parameter signatures.")
