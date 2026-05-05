#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量修改Python文件的导入引用
把 app.services.tools.env. 改为 app.services.tools.environment.
把 app.services.tools.env_check. 改为 app.services.tools.environment.
"""
import os
import re

TARGET_DIR = r"D:\OmniAgentAs-desk\backend\app\services\tools\environment"
OLD_PATTERNS = [
    (r"from app\.services\.tools\.env\.", "from app.services.tools.environment."),
    (r"from app\.services\.tools\.env_check\.", "from app.services.tools.environment."),
    (r"import app\.services\.tools\.env\.", "import app.services.tools.environment."),
    (r"import app\.services\.tools\.env_check\.", "import app.services.tools.environment."),
]

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    for pattern, replacement in OLD_PATTERNS:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"已修改: {os.path.basename(filepath)}")
        return True
    return False

def main():
    fixed = 0
    for filename in os.listdir(TARGET_DIR):
        if filename.endswith('.py'):
            filepath = os.path.join(TARGET_DIR, filename)
            if fix_file(filepath):
                fixed += 1
    print(f"\n共修改 {fixed} 个文件")

if __name__ == "__main__":
    main()
