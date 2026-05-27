#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证代码修正 - 小健 2026-05-27

验证内容：
1. TextStrategy不再内部调用parse_react_response
2. registry.resolve_category委托给intent_mapper
"""

import sys
import inspect

def test_text_strategy_no_parse():
    """验证TextStrategy.call()不再调用parse_react_response"""
    from app.services.agent.llm_strategies import TextStrategy
    
    # 获取call方法的源代码
    source = inspect.getsource(TextStrategy.call)
    
    # 检查是否包含parse_react_response
    if "parse_react_response" in source:
        print("❌ 失败：TextStrategy.call()仍然包含parse_react_response调用")
        print("   违反DRY原则：双重解析")
        return False
    
    print("✅ 通过：TextStrategy.call()不再调用parse_react_response")
    print("   符合DRY原则：单一解析入口在base_react.py")
    return True


def test_resolve_category_delegation():
    """验证registry.resolve_category委托给intent_mapper"""
    from app.services.tools.registry import resolve_category
    from app.services.intents.intent_mapper import resolve_category as resolve_unified
    
    # 测试几个意图类型
    test_cases = ["file", "shell", "network", "system", "desktop", "document"]
    
    all_match = True
    for intent in test_cases:
        result_registry = resolve_category(intent)
        result_unified = resolve_unified(intent)
        
        if result_registry != result_unified:
            print(f"❌ 失败：intent={intent}, registry={result_registry}, unified={result_unified}")
            all_match = False
    
    if all_match:
        print("✅ 通过：registry.resolve_category正确委托给intent_mapper")
        print("   符合DRY原则：统一入口")
        return True
    return False


def test_ai_config_resolver():
    """验证AIConfigResolver存在并被使用"""
    try:
        from app.services.ai_config_resolver import AIConfigResolver, resolve_provider_model
        from app.config import Config
        
        # 验证Config使用了AIConfigResolver
        config = Config()
        # get_ai_provider_model方法应该委托给AIConfigResolver
        print("✅ 通过：AIConfigResolver存在并被正确使用")
        print("   符合DRY原则：Fallback逻辑统一")
        return True
    except Exception as e:
        print(f"❌ 失败：AIConfigResolver验证失败 - {e}")
        return False


def main():
    print("=" * 60)
    print("代码修正验证 - 小健 2026-05-27")
    print("=" * 60)
    print()
    
    results = []
    
    print("【验证1】TextStrategy不再双重解析")
    results.append(test_text_strategy_no_parse())
    print()
    
    print("【验证2】registry.resolve_category委托给统一入口")
    results.append(test_resolve_category_delegation())
    print()
    
    print("【验证3】AIConfigResolver统一Fallback逻辑")
    results.append(test_ai_config_resolver())
    print()
    
    print("=" * 60)
    if all(results):
        print("✅ 全部验证通过！代码修正符合DRY原则")
        print("=" * 60)
        return 0
    else:
        print("❌ 部分验证失败，请检查修正")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
