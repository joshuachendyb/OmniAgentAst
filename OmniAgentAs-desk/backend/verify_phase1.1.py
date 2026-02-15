#!/usr/bin/env python3
"""
阶段1.1 手动验证脚本
不依赖pytest，直接验证核心功能
"""

import sys
import json
from datetime import datetime

# 验证结果存储
results = []

def test(name, condition, details=""):
    """简单的测试断言"""
    status = "✅ 通过" if condition else "❌ 失败"
    results.append({
        "name": name,
        "status": condition,
        "details": details
    })
    print(f"{status} - {name}")
    if details and not condition:
        print(f"   详情: {details}")
    return condition

def main():
    print("=" * 60)
    print("OmniAgentAst 阶段1.1 功能验证")
    print("=" * 60)
    print()
    
    # 测试1: 导入测试
    print("[测试1] 模块导入...")
    try:
        from app.main import app
        test("FastAPI应用导入", True)
    except Exception as e:
        test("FastAPI应用导入", False, str(e))
    
    # 测试2: FastAPI实例检查
    print("\n[测试2] FastAPI配置...")
    try:
        from app.main import app
        test("FastAPI实例存在", app is not None)
        test("应用标题正确", app.title == "OmniAgentAst API")
        test("应用版本正确", app.version == "0.1.0")
    except Exception as e:
        test("FastAPI配置", False, str(e))
    
    # 测试3: 路由检查
    print("\n[测试3] API路由...")
    try:
        from app.main import app
        routes = [route.path for route in app.routes]
        test("根路由存在", "/" in routes or "" in routes)
        test("健康检查路由存在", "/api/v1/health" in routes)
        test("回显路由存在", "/api/v1/echo" in routes)
    except Exception as e:
        test("路由检查", False, str(e))
    
    # 测试4: CORS中间件
    print("\n[测试4] CORS配置...")
    try:
        from app.main import app
        middleware_types = [type(m).__name__ for m in app.user_middleware]
        test("CORS中间件存在", "CORSMiddleware" in str(app.user_middleware))
    except Exception as e:
        test("CORS配置", False, str(e))
    
    # 测试5: 健康检查逻辑
    print("\n[测试5] 健康检查逻辑...")
    try:
        from app.api.v1.health import router
        test("健康检查路由模块导入", True)
    except Exception as e:
        test("健康检查逻辑", False, str(e))
    
    # 测试6: 项目结构
    print("\n[测试6] 项目结构...")
    import os
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    required_files = [
        "app/main.py",
        "app/api/v1/health.py",
        "requirements.txt",
        "tests/test_health.py",
        "tests/test_integration.py"
    ]
    
    for file in required_files:
        full_path = os.path.join(base_path, file)
        exists = os.path.exists(full_path)
        test(f"文件存在: {file}", exists)
    
    # 汇总
    print("\n" + "=" * 60)
    print("📊 验证结果汇总")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for r in results if r["status"])
    failed = total - passed
    
    print(f"总测试数: {total}")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    print("\n" + "=" * 60)
    if failed == 0:
        print("🎉 阶段1.1 验证通过！所有检查项均正常。")
        print("=" * 60)
        return 0
    else:
        print(f"⚠️  阶段1.1 验证未完全通过，有 {failed} 项检查失败。")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
