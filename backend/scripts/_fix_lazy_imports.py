"""
将测试方法内的 from...import 提升到模块顶部，消除惰性导入。

规则：
1. 只处理 test_ 方法内的 from X import Y 语句
2. 将其移到文件顶部（在已有 import 之后）
3. 如果模块顶部已有相同导入，删除方法内的重复
4. 保留非测试方法内的导入不动（如 helper 函数）
5. 跳过有 try/except 包裹的导入（这些是有意为之）
"""
import ast
import os
import re
from pathlib import Path

TESTS_DIR = Path(r"G:\OmniAgentAs-desk\backend\tests")
SKIP_DIRS = {".git", "__pycache__", "reports", "data", "utils", "document", "e2e_real"}

def fix_file(filepath: Path) -> tuple[int, int]:
    with open(filepath, encoding="utf-8") as f:
        source = f.read()

    lines = source.split("\n")
    new_lines = list(lines)

    # Find top-level imports end line
    top_import_end = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")) and not line.startswith(" ") and not line.startswith("\t"):
            top_import_end = i + 1
        elif stripped.startswith("#") or stripped == "" or stripped.startswith('"""') or stripped.startswith("'''"):
            if top_import_end > 0 and stripped == "":
                continue
            elif top_import_end > 0:
                break
        elif top_import_end > 0:
            break

    # Collect all from-imports inside test methods
    lazy_imports = []  # (line_index, dedented_text, indent_level, multi_line_count)
    in_test_method = False
    in_try = False
    method_indent = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect test method start
        if re.match(r'^(\s*)def test_', line):
            m = re.match(r'^(\s*)def test_', line)
            method_indent = len(m.group(1))
            in_test_method = True
            in_try = False
            continue

        # Detect if we left the test method
        if in_test_method and stripped and not stripped.startswith("#"):
            current_indent = len(line) - len(stripped)
            if current_indent <= method_indent:
                in_test_method = False
                in_try = False
                continue

        # Track try blocks
        if in_test_method and stripped.startswith("try:"):
            in_try = True
        if in_test_method and in_try and stripped.startswith(("except", "finally")):
            in_try = False

        # Find from...import inside test method (not in try/except)
        if in_test_method and not in_try:
            if re.match(r'^from\s+\S+\s+import\s+', stripped):
                # Check for multi-line import (opening paren)
                if stripped.rstrip().endswith('('):
                    # Collect continuation lines until closing paren
                    multi_lines = [stripped]
                    multi_count = 1
                    j = i + 1
                    while j < len(lines):
                        cont_stripped = lines[j].strip()
                        multi_lines.append(cont_stripped)
                        multi_count += 1
                        if cont_stripped.rstrip().endswith(')'):
                            break
                        j += 1
                    full_import = '\n    '.join(multi_lines)
                    lazy_imports.append((i, full_import, current_indent, multi_count))
                    continue  # skip individual line processing

                lazy_imports.append((i, stripped, current_indent, 1))

    if not lazy_imports:
        return 0, 0

    # Extract the import statement (dedented) and check if already at top
    top_import_texts = set()
    for i, line in enumerate(lines[:top_import_end + 5]):
        if line.strip().startswith(("import ", "from ")):
            top_import_texts.add(line.strip())

    imports_to_add = []
    lines_to_remove = set()
    moved = 0
    deduped = 0

    for item in lazy_imports:
        line_idx = item[0]
        import_text = item[1]
        indent = item[2]
        multi_count = item[3] if len(item) > 3 else 1
        # Dedent the import
        dedented = import_text.lstrip()
        if dedented in top_import_texts:
            # Already at top, remove from method
            for n in range(multi_count):
                lines_to_remove.add(line_idx + n)
            deduped += 1
        else:
            # Need to add to top and remove from method
            imports_to_add.append(dedented)
            for n in range(multi_count):
                lines_to_remove.add(line_idx + n)
            top_import_texts.add(dedented)
            moved += 1

    if not lines_to_remove:
        return 0, 0

    # Build new file
    result_lines = []
    for i, line in enumerate(lines):
        if i in lines_to_remove:
            continue
        result_lines.append(line)

    # Insert new imports after top_import_end
    if imports_to_add:
        # Find insertion point (after existing imports, before first non-import)
        insert_at = 0
        for i, line in enumerate(result_lines):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and not line.startswith(" ") and not line.startswith("\t"):
                insert_at = i + 1
            elif stripped.startswith("#") or stripped == "":
                if insert_at > 0:
                    continue
            elif insert_at > 0:
                break

        # Deduplicate
        unique_new = []
        seen = set()
        for imp in imports_to_add:
            if imp not in seen:
                seen.add(imp)
                unique_new.append(imp)

        for imp in reversed(unique_new):
            imp_lines = imp.split('\n    ')
            for il in reversed(imp_lines):
                result_lines.insert(insert_at, il)

    new_source = "\n".join(result_lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_source)

    return moved, deduped

def main():
    total_moved = 0
    total_deduped = 0
    files_fixed = 0

    for root, dirs, files in os.walk(TESTS_DIR):
        for d in list(dirs):
            if d.startswith(".") or d in SKIP_DIRS:
                dirs.remove(d)
        for f in files:
            if not f.endswith(".py") or f.startswith("_"):
                continue
            filepath = Path(root) / f
            moved, deduped = fix_file(filepath)
            if moved > 0 or deduped > 0:
                total_moved += moved
                total_deduped += deduped
                files_fixed += 1
                rel = filepath.relative_to(TESTS_DIR)
                print(f"  {rel}: moved={moved}, deduped={deduped}")

    print(f"\n总计: {files_fixed}个文件, 移动{total_moved}处, 去重{total_deduped}处")

if __name__ == "__main__":
    main()
