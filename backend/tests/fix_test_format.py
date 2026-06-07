"""Fix test files for new build_success/build_error format.
The old format used: {success: True/False, data: ..., error: ...}
The new format uses: {code: "SUCCESS"/"ERR_...", data: ..., message: ...}

This script updates assertions accordingly.
小健 2026-05-25
"""
import re
import os

TEST_DIR = r"G:\OmniAgentAs-desk\backend\tests"
FILES = [
    "test_f1_read_file.py",
    "test_f2_write_text_file.py",
    "test_f4_edit_file.py",
    "test_f5_list_directory.py",
    "test_f6_search_files.py",
    "test_f7_grep_file_content.py",
    "test_f8_rename_file.py",
    "test_f9_archive_tool.py",
    "test_f10_file_operation.py",
    "test_f11_data_file_format.py",
    "test_file_tools_fixes.py",
]

REPLACEMENTS = []


def add_replacement(old, new, desc=""):
    REPLACEMENTS.append((old, new, desc))


# Pattern 1: success True assertion with error message
# data = _ok(result)\n    assert data["success"] is True, f"失败: {data.get('error')}"
# -> keep data = _ok(result), but change success True to check code
add_replacement(
    '''    assert data["success"] is True, f"失败: {data.get('error')}"''',
    '''    assert result["code"] == "SUCCESS", f"失败: {result.get('message', '')}"''',
    "success True with error message"
)

# Pattern 2: success True assertion without error message
add_replacement(
    '''    assert data["success"] is True''',
    '''    assert result["code"] == "SUCCESS"''',
    "success True without error message"
)

# Pattern 3: success False assertion (simple)
add_replacement(
    '''    assert data["success"] is False''',
    '''    assert result["code"] != "SUCCESS"''',
    "success False"
)

# Pattern 4: data.get("error") in assertion messages
add_replacement(
    '''data.get("error", "")''',
    '''result.get("message", "")''',
    "error -> message"
)

# Pattern 5: data.get("error") in failure messages
add_replacement(
    """data.get('error')""",
    """result.get('message', '')""",
    "error -> message"
)

# Pattern 6: F3 read_media also has same pattern
# Note: f3 uses raw function import, not FileTools class


def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    changes = []
    for old, new, desc in REPLACEMENTS:
        if old in new_content:
            count = new_content.count(old)
            new_content = new_content.replace(old, new)
            changes.append(f"  {desc}: {count}x")
        # also check with different indentation (tab variations)
        old_space = old.replace("    ", "\t")
        if old_space in new_content:
            count = new_content.count(old_space)
            new_content = new_content.replace(old_space, new.replace("    ", "\t"))
            changes.append(f"  {desc} (tab): {count}x")

    if changes:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"\nFixed: {os.path.basename(filepath)}")
        for c in changes:
            print(c)
        return True
    return False


if __name__ == "__main__":
    count = 0
    for fname in FILES:
        fpath = os.path.join(TEST_DIR, fname)
        if os.path.exists(fpath):
            if fix_file(fpath):
                count += 1
        else:
            print(f"Not found: {fpath}")
    print(f"\n=== Total: {count} files fixed ===")
