#!/usr/bin/env python3
"""
验证SessionUpdate类修复
验证version字段是否为必需参数
"""

import sys
from pathlib import Path

# 添加backend到路径
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.api.v1.sessions import SessionUpdate
from pydantic import ValidationError

print("=" * 60)
print("验证SessionUpdate类修复")
print("=" * 60)

# 测试1：不提供version（应该失败）
print("\n测试1：不提供version参数")
print("-" * 60)
try:
    update = SessionUpdate(title="测试标题")
    print("❌ 失败：version应该是必需参数")
    print(f"   update.version = {update.version}")
except ValidationError as e:
    print("✅ 通过：version是必需参数")
    print(f"   错误信息: {e}")

# 测试2：提供version（应该成功）
print("\n测试2：提供version参数")
print("-" * 60)
try:
    update = SessionUpdate(title="测试标题", version=1)
    print("✅ 通过：正确构造成功")
    print(f"   title = {update.title}")
    print(f"   version = {update.version}")
except ValidationError as e:
    print("❌ 失败：应该能正确构造")
    print(f"   错误信息: {e}")

# 测试3：version小于1（应该失败）
print("\n测试3：version=0（小于1）")
print("-" * 60)
try:
    update = SessionUpdate(title="测试标题", version=0)
    print("❌ 失败：version应该>=1")
except ValidationError as e:
    print("✅ 通过：version必须>=1")
    print(f"   错误信息: {e}")

# 测试4：不提供title（应该成功，因为title是Optional）
print("\n测试4：不提供title参数")
print("-" * 60)
try:
    update = SessionUpdate(version=1)
    print("✅ 通过：title是可选参数")
    print(f"   title = {update.title}")
    print(f"   version = {update.version}")
except ValidationError as e:
    print("❌ 失败：title应该是可选的")
    print(f"   错误信息: {e}")

print("\n" + "=" * 60)
print("验证完成！")
print("=" * 60)