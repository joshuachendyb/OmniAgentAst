# -*- coding: utf-8 -*-
"""
集成测试 - AgentFactory系统（Phase 0-5完整测试）

测试整个Agent系统的完整集成：
- Phase 0: mixin.py + registry.py基础设施
- Phase 1: BaseAgent基础Agent
- Phase 2: FileReactAgent文件操作Agent
- Phase 3: TimeReactAgent时间操作Agent
- Phase 4: AgentFactory工厂
- Phase 5: 集成测试

修复 - 2026-04-26 小沈
【修复 2026-04-30 小沈】session_id→task_id, _load_tools→load_tools_by_category
"""
import sys
sys.path.insert(0, r'D:\OmniAgentAs-desk\backend')

import pytest


class TestPhase0Infrastructure:
    """Phase 0: 基础设施测试"""
    
    def test_mixin_get_exact_implementation(self):
        """测试mixin.py使用正确的get_exact_implementation方法"""
        from app.services.tools.mixin import ToolLoaderMixin
        from app.services.tools.registry import tool_registry, ToolCategory
        
        # 验证Mixin类存在
        assert ToolLoaderMixin is not None
        
        # 【修复 2026-04-30 小沈】_load_tools 已改名为 load_tools_by_category（消除MRO遮蔽）
        assert hasattr(ToolLoaderMixin, 'load_tools_by_category')
        
        print("[OK] Phase0: ToolLoaderMixin ready")
    
    def test_registry_get_tools_function(self):
        """测试registry.py的get_tools_from_registry_by_category函数"""
        from app.services.tools.registry import get_tools_from_registry_by_category, ToolCategory
        
        # 验证函数存在
        assert get_tools_from_registry_by_category is not None
        
        # 验证函数可调用
        result = get_tools_from_registry_by_category(ToolCategory.TIME)
        assert isinstance(result, dict)
        
        print(f"[OK] Phase0: get_tools_from_registry_by_category returns {len(result)} tools")


class TestPhase1BaseAgent:
    """Phase 1: BaseAgent测试"""
    
    def test_base_agent_signature(self):
        """测试BaseAgent新签名包含llm_client, task_id"""
        from app.services.agent.base_react import BaseAgent
        import inspect
        
        # 获取__init__签名
        sig = inspect.signature(BaseAgent.__init__)
        params = list(sig.parameters.keys())
        
        # 验证参数
        assert 'llm_client' in params, "Missing llm_client parameter"
        assert 'task_id' in params, "Missing task_id parameter"
        assert 'tool_category' in params, "Missing tool_category parameter"
        assert 'max_steps' in params, "Missing max_steps parameter"
        
        print(f"[OK] Phase1: BaseAgent signature: {params}")
    
    def test_base_agent_instantiation(self):
        """测试BaseAgent可以实例化（使用mock）"""
        from app.services.agent.base_react import BaseAgent
        from app.services.tools.registry import ToolCategory
        
        # 创建mock子类
        class MockAgent(BaseAgent):
            async def _get_llm_response(self):
                return ""
            async def _execute_tool(self, action, params):
                return {"status": "success"}
            def _get_system_prompt(self):
                return "test"
            def _get_task_prompt(self, task, context=None):
                return task
        
        # 实例化
        agent = MockAgent(
            llm_client=None,
            task_id="test-session",
            tool_category=ToolCategory.TIME,
            max_steps=10
        )
        
        # 验证属性
        assert agent.llm_client is None
        assert agent.task_id == "test-session"
        assert agent.tool_category == ToolCategory.TIME
        assert agent.max_steps == 10
        
        print("[OK] Phase1: BaseAgent instantiation OK")


class TestPhase2FileReactAgent:
    """Phase 2: FileReactAgent测试"""
    
    def test_file_react_agent_signature(self):
        """测试FileReactAgent支持tool_category参数"""
        from app.services.agent.file_react import FileReactAgent
        import inspect
        
        sig = inspect.signature(FileReactAgent.__init__)
        params = list(sig.parameters.keys())
        
        assert 'llm_client' in params
        assert 'task_id' in params
        assert 'tool_category' in params
        assert 'max_steps' in params
        
        print(f"[OK] Phase2: FileReactAgent signature: {params}")
    
    def test_file_react_agent_instantiation(self):
        """测试FileReactAgent可以实例化"""
        from app.services.agent.file_react import FileReactAgent
        from app.services.tools.registry import ToolCategory
        
        agent = FileReactAgent(
            llm_client=None,
            task_id="test-file-session",
            tool_category=ToolCategory.FILE,
            max_steps=10
        )
        
        assert agent.task_id == "test-file-session"
        assert agent.tool_category == ToolCategory.FILE
        assert agent.max_steps == 10
        
        print("[OK] Phase2: FileReactAgent instantiation OK")


class TestPhase3TimeReactAgent:
    """Phase 3: TimeReactAgent测试"""
    
    def test_time_react_agent_signature(self):
        """测试TimeReactAgent支持tool_category参数"""
        from app.services.agent.time_react import TimeReactAgent
        import inspect
        
        sig = inspect.signature(TimeReactAgent.__init__)
        params = list(sig.parameters.keys())
        
        assert 'llm_client' in params
        assert 'task_id' in params
        assert 'tool_category' in params
        assert 'max_steps' in params
        
        print(f"[OK] Phase3: TimeReactAgent signature: {params}")
    
    def test_time_react_agent_loads_9_tools(self):
        """测试TimeReactAgent加载9个时间工具"""
        from app.services.agent.time_react import TimeReactAgent
        from app.services.tools.registry import ToolCategory
        
        agent = TimeReactAgent(
            llm_client=None,
            task_id="test-time-session",
            tool_category=ToolCategory.TIME,
            max_steps=50
        )
        
        # 验证加载了9个工具
        assert len(agent._tools_dict) == 9, f"Expected 9 tools, got {len(agent._tools_dict)}"
        
        # 验证关键工具存在
        expected_tools = ['time_now', 'time_format', 'time_diff', 
                         'timer_set', 'timer_clear',
                         'time_utc_to_local', 'time_local_to_utc',
                         'time_is_weekend', 'time_is_holiday']
        
        for tool in expected_tools:
            assert tool in agent._tools_dict, f"Missing tool: {tool}"
        
        print(f"[OK] Phase3: TimeReactAgent loaded {len(agent._tools_dict)} tools")


class TestPhase4AgentFactory:
    """Phase 4: AgentFactory测试"""
    
    def test_agent_factory_create_file(self):
        """测试工厂创建FileReactAgent"""
        from app.services.agent.agent_factory import AgentFactory
        from app.services.tools.registry import ToolCategory
        
        agent = AgentFactory.create(
            intent_type='file',
            llm_client=None,
            task_id='factory-test-file',
            tool_category=ToolCategory.FILE
        )
        
        assert agent is not None
        assert agent.task_id == 'factory-test-file'
        assert agent.tool_category == ToolCategory.FILE
        
        print(f"[OK] Phase4: Created {type(agent).__name__}")
    
    def test_agent_factory_create_time(self):
        """测试工厂创建TimeReactAgent"""
        from app.services.agent.agent_factory import AgentFactory
        from app.services.tools.registry import ToolCategory
        
        agent = AgentFactory.create(
            intent_type='time',
            llm_client=None,
            task_id='factory-test-time',
            tool_category=ToolCategory.TIME
        )
        
        assert agent is not None
        assert agent.task_id == 'factory-test-time'
        assert agent.tool_category == ToolCategory.TIME
        assert len(agent._tools_dict) == 9  # 9个时间工具
        
        print(f"[OK] Phase4: Created {type(agent).__name__} with {len(agent._tools_dict)} tools")
    
    def test_agent_factory_list_available(self):
        """测试列出所有可用的Agent"""
        from app.services.agent.agent_factory import AgentFactory
        
        available = AgentFactory.list_available_agents()
        
        assert isinstance(available, dict)
        assert 'file' in available
        assert 'time' in available
        assert available['file'] == 'FileReactAgent'
        assert available['time'] == 'TimeReactAgent'
        
        print(f"[OK] Phase4: Available agents: {available}")


class TestPhase5Integration:
    """Phase 5: 端到端集成测试"""
    
    def test_full_pipeline_file(self):
        """测试完整的file Agent流程"""
        from app.services.agent.agent_factory import AgentFactory
        
        # 1. 通过工厂创建
        agent = AgentFactory.create(
            intent_type='file',
            llm_client=None,
            task_id='integration-test-file'
        )
        
        # 2. 验证属性
        assert agent.task_id == 'integration-test-file'
        assert agent.tool_category is not None
        
        # 3. 验证工具加载
        assert hasattr(agent, '_tools_dict')
        
        print(f"[OK] Phase5: Full file pipeline test passed")
    
    def test_full_pipeline_time(self):
        """测试完整的time Agent流程"""
        from app.services.agent.agent_factory import AgentFactory
        
        # 1. 通过工厂创建
        agent = AgentFactory.create(
            intent_type='time',
            llm_client=None,
            task_id='integration-test-time'
        )
        
        # 2. 验证属性
        assert agent.task_id == 'integration-test-time'
        assert agent.tool_category is not None
        
        # 3. 验证工具加载（9个）
        assert len(agent._tools_dict) == 9
        
        # 4. 验证工具可调用
        tool = agent._tools_dict.get('time_now')
        assert tool is not None
        result = tool()
        assert result.get('code') == 'SUCCESS'
        
        print(f"[OK] Phase5: Full time pipeline test passed - time_now returned: {result.get('code')}")
    
    def test_cross_agent_compatibility(self):
        """测试不同Agent之间的兼容性"""
        from app.services.agent.agent_factory import AgentFactory
        from app.services.tools.registry import ToolCategory
        
        # 创建file agent
        file_agent = AgentFactory.create(
            intent_type='file',
            llm_client=None,
            task_id='compat-file'
        )
        
        # 创建time agent
        time_agent = AgentFactory.create(
            intent_type='time',
            llm_client=None,
            task_id='compat-time'
        )
        
        # 验证两者类型不同
        assert type(file_agent).__name__ == 'FileReactAgent'
        assert type(time_agent).__name__ == 'TimeReactAgent'
        
        # 验证工具不共享
        assert file_agent._tools_dict != time_agent._tools_dict
        
        print(f"[OK] Phase5: Cross-agent compatibility test passed")


# pytest执行入口
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
