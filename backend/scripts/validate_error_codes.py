"""
ERR code规范检查脚本 - 验证所有工具返回的ERR code是否符合三段式规范
规范: ERR_MODULE_OPERATION_DETAIL
示例: ERR_FILE_NOT_FOUND, ERR_SHELL_TIMEOUT, ERR_DOC_UNSUPPORTED_FORMAT
小健 2026-05-21
"""
import re
import sys
from pathlib import Path

# 已知合规的模块前缀
MODULES = ["FILE", "DOC", "DOCUMENT", "SHELL", "NET", "NETWORK", "META", "DESKTOP", "SYS", "SYSTEM", "DB", "DATABASE"]


def check_error_code(code: str) -> tuple[bool, str]:
    """验证ERR code是否符合三段式规范
    
    返回: (是否合规, 错误描述)
    """
    if not code or not code.startswith("ERR_"):
        return False, "ERR code必须以ERR_开头"
    
    parts = code[4:].split("_")
    if len(parts) != 3:
        return False, f"ERR code应为三段式(实际{len(parts)}段): ERR_MODULE_OPERATION_DETAIL"
    
    module, operation, detail = parts
    
    # 检查模块名
    if len(module) < 2:
        return False, f"模块名过短: {module} (至少2字符)"
    if module not in MODULES:
        return False, f"未知模块前缀: {module} (合规: {', '.join(MODULES)})"
    
    # 检查操作名
    if len(operation) < 2:
        return False, f"操作名过短: {operation} (至少2字符)"
    
    # 检查详情
    if len(detail) < 2:
        return False, f"详情过短: {detail} (至少2字符)"
    
    return True, ""


def scan_file(file_path: Path) -> list:
    """扫描单个Python文件中的所有ERR code
    
    返回: [(行号, code, 错误描述), ...]
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return [(0, f"READ_ERROR", f"无法读取文件: {e}")]
    
    errors = []
    pattern = r'"code":\s*"(ERR_[A-Z_]+)"'
    
    for line_num, line in enumerate(content.split('\n'), 1):
        matches = re.findall(pattern, line)
        for code in set(matches):
            ok, msg = check_error_code(code)
            if not ok:
                errors.append((line_num, code, msg))
    
    return errors


def main():
    """扫描所有工具文件"""
    tools_dir = Path("app/services/tools")
    if not tools_dir.exists():
        print(f"错误: 找不到工具目录 {tools_dir}")
        sys.exit(1)
    
    all_errors = {}
    for py_file in tools_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        file_errors = scan_file(py_file)
        if file_errors:
            all_errors[py_file.relative_to(tools_dir)] = file_errors
    
    # 输出结果
    if all_errors:
        print(f"发现 {len(all_errors)} 个文件存在不规范的ERR code:\n")
        for file, errors in sorted(all_errors.items()):
            print(f"  {file}:")
            for line_num, code, msg in errors:
                print(f"    行{line_num}: {code} - {msg}")
        print(f"\n总计: {sum(len(e) for e in all_errors.values())} 处违规")
        sys.exit(1)
    else:
        print("✓ 所有ERR code符合三段式规范")
        sys.exit(0)


if __name__ == "__main__":
    main()
