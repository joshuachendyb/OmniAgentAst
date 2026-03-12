#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件写入接口增强功能测试脚本
测试时间: 2026-02-26 07:50:00
测试人: 小沈
"""

import sys
import os
import yaml
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.api.v1.config import (
    _backup_config_file,
    _validate_config_integrity,
    _fix_config_common_issues,
    _get_config_path
)

def test_backup_function():
    """测试备份功能"""
    print("=== 测试备份功能 ===")
    try:
        config_path = _get_config_path()
        print(f"配置文件路径: {config_path}")
        
        if not config_path.exists():
            print("⚠️ 配置文件不存在，跳过备份测试")
            return False
            
        backup_path = _backup_config_file(config_path)
        print(f"✅ 备份成功: {backup_path}")
        print(f"   备份文件存在: {backup_path.exists()}")
        print(f"   备份文件大小: {backup_path.stat().st_size} 字节")
        return True
    except Exception as e:
        print(f"❌ 备份测试失败: {e}")
        return False

def test_validation_function():
    """测试验证功能"""
    print("\n=== 测试验证功能 ===")
    try:
        config_path = _get_config_path()
        
        if not config_path.exists():
            print("⚠️ 配置文件不存在，跳过验证测试")
            return False
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
        
        print(f"配置文件内容: {list(config_data.keys())}")
        
        is_valid, errors, warnings = _validate_config_integrity(config_data)
        
        print(f"✅ 验证完成:")
        print(f"   是否通过: {is_valid}")
        print(f"   错误数量: {len(errors)}")
        print(f"   警告数量: {len(warnings)}")
        
        if errors:
            print("   错误列表:")
            for error in errors:
                print(f"     - {error}")
        
        if warnings:
            print("   警告列表:")
            for warning in warnings:
                print(f"     - {warning}")
        
        return is_valid
    except Exception as e:
        print(f"❌ 验证测试失败: {e}")
        return False

def test_fix_function():
    """测试修复功能"""
    print("\n=== 测试修复功能 ===")
    try:
        config_path = _get_config_path()
        
        if not config_path.exists():
            print("⚠️ 配置文件不存在，跳过修复测试")
            return False
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
        
        print("修复前配置检查:")
        ai_config = config_data.get('ai', {})
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and 'model' in provider_data:
                print(f"   ⚠️  provider '{provider_name}' 下有废弃的 model 字段")
        
        fixed_config = _fix_config_common_issues(config_data)
        
        print("修复后配置检查:")
        ai_config = fixed_config.get('ai', {})
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and 'model' in provider_data:
                print(f"   ❌  provider '{provider_name}' 下仍有废弃的 model 字段")
                return False
            else:
                print(f"   ✅  provider '{provider_name}' 下无废弃的 model 字段")
        
        print("✅ 修复功能测试通过")
        return True
    except Exception as e:
        print(f"❌ 修复测试失败: {e}")
        return False

def test_config_structure():
    """测试配置文件结构"""
    print("\n=== 测试配置文件结构 ===")
    try:
        config_path = _get_config_path()
        
        if not config_path.exists():
            print("⚠️ 配置文件不存在，跳过结构测试")
            return False
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
        
        print("配置文件结构分析:")
        
        # 检查ai部分
        if 'ai' not in config_data:
            print("   ❌ 缺少 'ai' 部分")
            return False
        else:
            print("   ✅ 存在 'ai' 部分")
        
        ai_config = config_data['ai']
        
        # 检查顶层provider和model
        if 'provider' not in ai_config:
            print("   ⚠️ 缺少顶层 ai.provider")
        else:
            print(f"   ✅ 存在顶层 ai.provider: {ai_config['provider']}")
        
        if 'model' not in ai_config:
            print("   ⚠️ 缺少顶层 ai.model")
        else:
            print(f"   ✅ 存在顶层 ai.model: {ai_config['model']}")
        
        # 检查provider配置
        provider_names = []
        for key in ai_config.keys():
            if key not in ['provider', 'model']:
                provider_names.append(key)
        
        if provider_names:
            print(f"   ✅ 发现 {len(provider_names)} 个provider: {', '.join(provider_names)}")
        else:
            print("   ⚠️ 未找到任何provider配置")
        
        # 检查其他部分
        other_sections = [key for key in config_data.keys() if key != 'ai']
        if other_sections:
            print(f"   ✅ 存在其他配置部分: {', '.join(other_sections)}")
        
        return True
    except Exception as e:
        print(f"❌ 结构测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("配置文件写入接口增强功能测试")
    print("=" * 50)
    
    # 检查配置文件是否存在
    config_path = _get_config_path()
    print(f"配置文件: {config_path}")
    print(f"配置文件存在: {config_path.exists()}")
    
    if not config_path.exists():
        print("⚠️ 配置文件不存在，无法运行完整测试")
        return
    
    # 运行测试
    test_results = []
    
    test_results.append(("备份功能", test_backup_function()))
    test_results.append(("验证功能", test_validation_function()))
    test_results.append(("修复功能", test_fix_function()))
    test_results.append(("结构检查", test_config_structure()))
    
    # 输出测试总结
    print("\n" + "=" * 50)
    print("测试总结:")
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {len(test_results)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    
    if failed == 0:
        print("\n🎉 所有测试通过！配置文件写入接口增强功能正常。")
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，需要检查。")

if __name__ == "__main__":
    main()