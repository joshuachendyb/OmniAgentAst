import ast
import os
from pathlib import Path

files = [
    r"G:\OmniAgentAs-desk\backend\app\services\tools\file\file_tools.py",
    r"G:\OmniAgentAs-desk\backend\app\services\agent\react_output_parser.py",
    r"G:\OmniAgentAs-desk\backend\app\services\tools\toolhelper\file_helpers.py",
    r"G:\OmniAgentAs-desk\backend\app\services\tools\system\system_tools.py",
    r"G:\OmniAgentAs-desk\backend\app\api\v1\routes.py",
    r"G:\OmniAgentAs-desk\backend\app\services\tools\meta\time_tools.py",
    r"G:\OmniAgentAs-desk\backend\app\api\v1\sessions.py",
    r"G:\OmniAgentAs-desk\backend\app\services\tools\document\document_tools.py",
    r"G:\OmniAgentAs-desk\backend\app\services\tools\network\network_tools.py",
    r"G:\OmniAgentAs-desk\backend\app\utils\visualization\file_visualization.py",
]

for fpath in files:
    filename = Path(fpath).name
    print(f"\n{'='*70}")
    print(f"FILE: {filename}")
    print(f"{'='*70}")

    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        functions = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lc = node.end_lineno - node.lineno + 1
                functions.append((node.name, lc, node.lineno))
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        lc = item.end_lineno - item.lineno + 1
                        functions.append((f"{node.name}.{item.name}", lc, item.lineno))

        total = len(functions)
        p1 = [f for f in functions if 100 <= f[1] <= 199]
        p2 = [f for f in functions if 50 <= f[1] <= 99]
        p3 = [f for f in functions if 30 <= f[1] <= 49]

        print(f"Total functions/async: {total}")
        print(f"P1 (100-199 lines): {len(p1)}")
        print(f"P2 (50-99 lines):  {len(p2)}")
        print(f"P3 (30-49 lines):  {len(p3)}")

        if p2:
            print(f"\n--- P2 Functions (50-99 lines) ---")
            for name, lines, lineno in sorted(p2, key=lambda x: -x[1]):
                print(f"  [{lines:3d} lines] L{lineno:4d}  {name}")
        else:
            print(f"\n  (no P2 functions found)")

        if p1:
            print(f"\n--- Also P1 Functions (100-199 lines) ---")
            for name, lines, lineno in sorted(p1, key=lambda x: -x[1]):
                print(f"  [{lines:3d} lines] L{lineno:4d}  {name}")

    except Exception as e:
        print(f"  ERROR: {e}")
