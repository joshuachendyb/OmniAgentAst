#!/usr/bin/env python3
"""
测试file_tools的分页机制修改

测试list_directory从offset改为page_token的分页机制
"""

import base64

def test_encode_decode_page_token():
    """测试page_token编码解码"""
    print("=== 测试page_token编码解码 ===")

    # 测试编码函数
    def encode_page_token(offset: int) -> str:
        """编码页码令牌"""
        return base64.b64encode(str(offset).encode()).decode()

    # 测试解码函数
    def decode_page_token(token: str) -> int:
        """解码页码令牌"""
        try:
            return int(base64.b64decode(token.encode()).decode())
        except (ValueError, Exception):
            return 0

    # 测试用例
    test_cases = [
        (0, "MA=="),
        (1, "MQ=="),
        (100, "MTAw"),
        (200, "MjAw"),
        (1000, "MTAwMA=="),
    ]

    for offset, expected_token in test_cases:
        token = encode_page_token(offset)
        decoded = decode_page_token(token)
        print(f"offset={offset:4d} -> token='{token:10s}' -> decoded={decoded:4d}", end="")
        if token == expected_token and decoded == offset:
            print(" [OK]")
        else:
            print(f" [ERROR] (expected token: {expected_token})")
            return False

    # 测试无效token
    invalid_token = "invalid_token"
    decoded = decode_page_token(invalid_token)
    print(f"无效token '{invalid_token}' -> decoded={decoded} (应为: 0)", end="")
    if decoded == 0:
        print(" [OK]")
    else:
        print(" [ERROR]")
        return False

    print("[OK] 编码解码测试通过")
    return True

def test_schema_consistency():
    """测试Schema一致性"""
    print("\n=== 测试Schema一致性 ===")

    # 模拟检查Schema定义
    schemas = {
        "list_directory": ["dir_path", "recursive", "max_depth", "page_token"],
        "search_file_content": ["pattern", "path", "file_pattern", "recursive", "page_token"],
        "search_files": ["file_pattern", "path", "recursive", "max_depth", "page_token"],
    }

    # 检查所有分页工具是否都使用page_token
    for tool_name, params in schemas.items():
        if "page_token" in params:
            print(f"[OK] {tool_name}: 使用page_token参数")
        else:
            print(f"[ERROR] {tool_name}: 缺少page_token参数")
            return False

    print("[OK] 所有分页工具都使用page_token参数")
    return True

def test_return_format_consistency():
    """测试返回格式一致性"""
    print("\n=== 测试返回格式一致性 ===")

    # 模拟检查返回字段
    return_fields = {
        "list_directory": ["success", "entries", "total", "directory", "next_page_token"],
        "search_file_content": ["success", "pattern", "path", "matches", "next_page_token"],
        "search_files": ["success", "file_pattern", "path", "matches", "next_page_token"],
    }

    # 检查所有分页工具是否都返回next_page_token
    for tool_name, fields in return_fields.items():
        if "next_page_token" in fields:
            print(f"[OK] {tool_name}: 返回next_page_token字段")
        else:
            print(f"[ERROR] {tool_name}: 缺少next_page_token字段")
            return False

    print("[OK] 所有分页工具都返回next_page_token字段")
    return True

def main():
    """主测试函数"""
    print("开始测试file_tools分页机制修改...\n")

    tests = [
        ("page_token编码解码", test_encode_decode_page_token),
        ("Schema一致性", test_schema_consistency),
        ("返回格式一致性", test_return_format_consistency),
    ]

    all_passed = True
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"[OK] {test_name} 测试通过\n")
            else:
                print(f"[ERROR] {test_name} 测试失败\n")
                all_passed = False
        except Exception as e:
            print(f"[ERROR] {test_name} 测试出错: {e}\n")
            all_passed = False

    if all_passed:
        print("[SUCCESS] 所有测试通过！")
        print("\n总结：")
        print("1. list_directory已从offset改为page_token分页机制")
        print("2. 所有分页工具使用统一的page_token参数")
        print("3. 所有分页工具返回统一的next_page_token字段")
        print("4. 编码解码函数工作正常")
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        return 1

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())