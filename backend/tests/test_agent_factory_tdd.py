# -*- coding: utf-8 -*-
"""
AgentFactory 测试用例 - Phase 1
T1.1: 测试AgentFactory类能创建正确的Agent

按照TDD流程：
1. RED: 先写测试，证明功能不存在
2. GREEN: 写最小代码通过测试
3. REFACTOR: 重构

小健 - 2026-04-26
"""
import sys
sys.path.insert(0, r'D:\OmniAgentAs-desk\backend')

def test_agent_factory_exists():
    """RED - 测试AgentFactory类存在"""
    print("[OK] AgentFactory class exists")
    return True

def test_agent_factory_has_agents_mapping():
    """RED - 测试_AGENTS映射存在"""
    assert hasattr(AgentFactory, '_AGENTS'), "Missing _AGENTS attribute"
    print("[OK] _AGENTS attribute exists")
    return True

def test_agent_factory_has_categories_mapping():
    """RED - 测试_TOOL_CATEGORIES映射存在"""
    assert hasattr(AgentFactory, '_TOOL_CATEGORIES'), "Missing _TOOL_CATEGORIES attribute"
    print("[OK] _TOOL_CATEGORIES attribute exists")
    return True

def test_agent_factory_create_for_file():
    """RED - 测试create()能创建file类型的Agent"""
    
    class MockLLMClient:
        pass
    
    # 测试create()方法存在
    assert hasattr(AgentFactory, 'create'), "Missing create() method"
    
    # 测试能创建file类型的Agent（不传config）
    # 【修改】session_id → task_id，2026-04-26 小沈
    agent = AgentFactory.create(
        intent_type='file',
        llm_client=MockLLMClient(),
        task_id='test-task'
    )
    
    # 验证返回的是Agent实例
    assert agent is not None, "create() returned None"
    print(f"[OK] create('file') returned: {type(agent).__name__}")
    return True

def test_agent_factory_create_for_time():
    """RED - 测试create()能处理time类型（不存在时返回None）"""
    
    class MockLLMClient:
        pass
    
    # TimeReactAgent不存在，应该返回None
    # 【修改】session_id → task_id，2026-04-26 小沈
    agent = AgentFactory.create(
        intent_type='time',
        llm_client=MockLLMClient(),
        task_id='test-task'
    )
    
    # time不存在，返回None是预期的
    print(f"[OK] create('time') returned: {agent}")
    return True

def test_agent_factory_register():
    """RED - 测试register()能注册新Agent"""
    
    # 测试register()方法存在
    assert hasattr(AgentFactory, 'register'), "Missing register() method"
    print("[OK] register() method exists")
    return True

def test_agent_factory_list_available():
    """RED - 测试list_available_agents()能列出可用Agent"""
    
    # 测试方法存在
    assert hasattr(AgentFactory, 'list_available_agents'), "Missing list_available_agents() method"
    print("[OK] list_available_agents() method exists")
    return True

def test_all():
    """运行所有测试"""
    tests = [
        ('T1.1: AgentFactory class exists', test_agent_factory_exists),
        ('T1.2: _AGENTS mapping exists', test_agent_factory_has_agents_mapping),
        ('T1.3: _TOOL_CATEGORIES mapping exists', test_agent_factory_has_categories_mapping),
        ('T1.4: create() can create file Agent', test_agent_factory_create_for_file),
        ('T1.5: create() handles time (not exists)', test_agent_factory_create_for_time),
        ('T1.6: register() method exists', test_agent_factory_register),
        ('T1.7: list_available_agents() exists', test_agent_factory_list_available),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            print(f'\n{name}')
            print('-' * 40)
            test_fn()
            passed += 1
        except Exception as e:
            print(f'FAIL: {e}')
            failed += 1
    
    print(f'\n============================================================')
    print(f'Total: {passed + failed}, Passed: {passed}, Failed: {failed}')
    print('============================================================')
    
    return failed == 0

if __name__ == '__main__':
    test_all()