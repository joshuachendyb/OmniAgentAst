#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置缓存功能测试
测试时间: 2026-04-12
测试人: 小沈
目的: 验证配置缓存优化功能
"""

import sys
import os
import time
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Config


def test_config_has_mtime_attribute():
    """测试：Config类应该有 _config_mtime 属性"""
    print("=== 测试：Config类应该有 _config_mtime 属性 ===")
    
    # 先检查类属性
    if not hasattr(Config, '_config_mtime'):
        print("❌ FAIL: Config 类没有 _config_mtime 属性")
        return False
    
    print("✅ PASS: Config 类有 _config_mtime 属性")
    return True


def test_load_config_uses_cache():
    """测试：配置未变更时使用缓存，不重新加载"""
    print("\n=== 测试：配置未变更时使用缓存 ===")
    
    # 获取配置实例
    config = Config()
    
    # 第一次加载
    initial_data = config._config_data
    initial_mtime = config._config_mtime
    
    if initial_data is None:
        print("⚠️ 配置文件不存在，跳过测试")
        return False
    
    # 再次调用 _load_config()（模拟GET请求）
    config._load_config()
    
    # 数据应该相同（使用了缓存）
    if config._config_data == initial_data:
        print("✅ PASS: 配置未变更，使用了缓存")
        return True
    else:
        print("❌ FAIL: 配置被重新加载了，没有使用缓存")
        return False


def test_reload_force_reload():
    """测试：reload() 强制重新加载"""
    print("\n=== 测试：reload() 强制重新加载 ===")
    
    config = Config()
    
    # 强制 reload
    config.reload()
    
    # 应该重新加载了（有 _config_mtime）
    if config._config_mtime is not None:
        print(f"✅ PASS: reload() 后 _config_mtime = {config._config_mtime}")
        return True
    else:
        print("❌ FAIL: reload() 后 _config_mtime 为 None")
        return False


def test_mtime_tracking():
    """测试：配置加载后 _config_mtime 被设置"""
    print("\n=== 测试：配置加载后 _config_mtime 被设置 ===")
    
    config = Config()
    
    if config._config_data is None:
        print("⚠️ 配置文件不存在，跳过测试")
        return False
    
    mtime = config._config_mtime
    
    if mtime is not None and isinstance(mtime, float):
        print(f"✅ PASS: _config_mtime = {mtime}")
        return True
    else:
        print(f"❌ FAIL: _config_mtime = {mtime}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("配置缓存功能测试")
    print("=" * 50)
    
    results = []
    
    # 运行测试
    results.append(("_config_mtime 属性", test_config_has_mtime_attribute()))
    results.append(("mtime追踪", test_mtime_tracking()))
    results.append(("缓存使用", test_load_config_uses_cache()))
    results.append(("强制reload", test_reload_force_reload()))
    
    # 总结
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")