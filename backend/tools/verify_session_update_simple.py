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
print("Verify SessionUpdate Fix")
print("=" * 60)

# 测试1：不提供version（应该失败）
print("\nTest 1: No version parameter")
print("-" * 60)
try:
    update = SessionUpdate(title="Test Title")
    print("[FAIL] version should be required")
    print(f"   update.version = {update.version}")
except ValidationError as e:
    print("[PASS] version is required")
    print(f"   Error: {e}")

# 测试2：提供version（应该成功）
print("\nTest 2: With version parameter")
print("-" * 60)
try:
    update = SessionUpdate(title="Test Title", version=1)
    print("[PASS] Construction successful")
    print(f"   title = {update.title}")
    print(f"   version = {update.version}")
except ValidationError as e:
    print("[FAIL] Should construct successfully")
    print(f"   Error: {e}")

# 测试3：version小于1（应该失败）
print("\nTest 3: version=0 (less than 1)")
print("-" * 60)
try:
    update = SessionUpdate(title="Test Title", version=0)
    print("[FAIL] version should be >= 1")
except ValidationError as e:
    print("[PASS] version must be >= 1")
    print(f"   Error: {e}")

# 测试4：不提供title（应该成功，因为title是Optional）
print("\nTest 4: No title parameter")
print("-" * 60)
try:
    update = SessionUpdate(version=1)
    print("[PASS] title is optional")
    print(f"   title = {update.title}")
    print(f"   version = {update.version}")
except ValidationError as e:
    print("[FAIL] title should be optional")
    print(f"   Error: {e}")

print("\n" + "=" * 60)
print("Verification Complete!")
print("=" * 60)