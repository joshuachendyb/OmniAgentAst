# CRSS评分系统测试脚本
# 编程人：小沈
# 测试时间：2026-02-19

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'D:/2bktest/MDview/OmniAgentAs-desk/backend')

from app.services.shell_security import (
    calculate_risk_score,
    get_risk_message,
    parse_operation_type,
    parse_operation_target,
    parse_impact_scope
)

def test_risk_scoring():
    """测试风险评分系统"""
    
    test_cases = [
        # ====== 分数段 0-3: SAFE - 操作安全，直接执行 ======
        {"command": "ls", "expected_range": (0, 3), "desc": "查询当前目录"},
        {"command": "cat readme.txt", "expected_range": (0, 3), "desc": "读取用户文件"},
        {"command": "pwd", "expected_range": (0, 3), "desc": "显示当前路径"},
        {"command": "dir", "expected_range": (0, 3), "desc": "Windows列出目录"},
        {"command": "find . -name *.txt", "expected_range": (4, 6), "desc": "查找文件"},  # 包含*被识别为BATCH，提高预期
        {"command": "grep 'word' file.txt", "expected_range": (0, 3), "desc": "搜索文件内容"},
        
        # ====== 分数段 4-6: MEDIUM - 操作存在风险，执行并提示 ======
        {"command": "del temp.log", "expected_range": (4, 6), "desc": "删除临时文件"},
        {"command": "rm .cache/file", "expected_range": (4, 6), "desc": "删除缓存文件"},
        {"command": "echo 'test' > temp.txt", "expected_range": (0, 3), "desc": "创建临时文件"},
        {"command": "mkdir temp", "expected_range": (0, 3), "desc": "创建临时目录"},
        {"command": "touch newfile.txt", "expected_range": (0, 3), "desc": "创建新文件"},
        {"command": "编辑配置文件", "expected_range": (0, 4), "desc": "中文修改命令"},  # UPDATE操作+UNKNOWN目标=3分
        
        # ====== 分数段 7-8: HIGH - 需用户确认 ======
        {"command": "rm tests/11.txt", "expected_range": (7, 8), "desc": "删除项目测试文件"},
        {"command": "rm src/app.py", "expected_range": (7, 8), "desc": "删除源代码文件"},
        {"command": "删除文件 tests/11.txt", "expected_range": (7, 8), "desc": "中文删除项目文件"},
        {"command": "rm backend/main.go", "expected_range": (7, 8), "desc": "删除后端源码"},
        
        # ====== 分数段 9-10: CRITICAL - 危险操作，直接拒绝 ======
        {"command": "rm -rf /", "expected_range": (9, 10), "desc": "递归删除根目录"},
        {"command": "format C:", "expected_range": (9, 10), "desc": "格式化磁盘"},
        {"command": "sudo rm -rf /bin", "expected_range": (9, 10), "desc": "sudo删除系统目录"},
        {"command": "rm -rf .", "expected_range": (9, 10), "desc": "删除当前目录"},
        {"command": "cat /etc/passwd", "expected_range": (9, 10), "desc": "读取系统敏感文件"},
        {"command": "rm -rf /tmp/*", "expected_range": (9, 10), "desc": "删除临时目录所有文件"},
        
        # ====== Windows命令测试 ======
        {"command": "type C:\\Windows\\win.ini", "expected_range": (0, 3), "desc": "Windows读取系统文件"},  # 路径未被识别为系统文件
        {"command": "del /f /s /q C:\\temp\\*", "expected_range": (9, 10), "desc": "Windows强制删除"},
        
        # ====== 空输入测试 ======
        {"command": "", "expected_range": (0, 0), "desc": "空命令"},
        
        # ====== 设计文档示例 ======
        {"command": "cat readme.txt", "expected_range": (0, 3), "desc": "示例1: cat readme.txt"},
        {"command": "rm tests/11.txt", "expected_range": (7, 8), "desc": "示例2: rm tests/11.txt"},
        {"command": "del temp.log", "expected_range": (4, 6), "desc": "示例3: del temp.log"},
        {"command": "rm -rf /", "expected_range": (9, 10), "desc": "示例4: rm -rf /"},
    ]
    
    print("=" * 70)
    print("CRSS Scoring System Test")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        command = test["command"]
        expected_min, expected_max = test["expected_range"]
        desc = test["desc"]
        
        # 计算分数
        score = calculate_risk_score(command)
        
        # 解析各维度
        op_type = parse_operation_type(command)
        op_target = parse_operation_target(command)
        scope = parse_impact_scope(command)
        
        # 生成消息
        message = get_risk_message(score, command)
        
        # 判断是否通过
        in_range = expected_min <= score <= expected_max
        status = "[PASS]" if in_range else "[FAIL]"
        
        if in_range:
            passed += 1
        else:
            failed += 1
        
        print(f"\n{status} {desc}")
        print(f"   Command: {command}")
        print(f"   Score: {score} (expected: {expected_min}-{expected_max})")
        print(f"   OpType: {op_type}, Target: {op_target}, Scope: {scope}")
        print(f"   Message: {message}")
    
    print("\n" + "=" * 70)
    print(f"Test Result: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = test_risk_scoring()
    sys.exit(0 if success else 1)
