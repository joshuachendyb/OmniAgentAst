"""
ReAct Agent导入测试 - 验证2026-05-06以来的代码更新
Author: 小沈 - 2026-05-09
"""
import pytest


class TestReActAgentImports:
    """测试各ReAct Agent可导入"""
    
    def test_file_react(self):
        from app.services.agent.file_react import FileReactAgent
        assert FileReactAgent is not None
    
    def test_time_react(self):
        from app.services.agent.time_react import TimeReactAgent
        assert TimeReactAgent is not None
    
    def test_shell_react(self):
        from app.services.agent.shell_react import ShellReactAgent
        assert ShellReactAgent is not None
    
    def test_network_react(self):
        from app.services.agent.network_react import NetworkReactAgent
        assert NetworkReactAgent is not None
    
    def test_system_react(self):
        from app.services.agent.system_react import SystemReactAgent
        assert SystemReactAgent is not None
    
    def test_database_react(self):
        from app.services.agent.database_react import DatabaseReactAgent
        assert DatabaseReactAgent is not None
    
    def test_document_react(self):
        from app.services.agent.document_react import DocumentReactAgent
        assert DocumentReactAgent is not None
    
    def test_desktop_react(self):
        from app.services.agent.desktop_react import DesktopReactAgent
        assert DesktopReactAgent is not None
    
    def test_code_execution_react(self):
        from app.services.agent.code_execution_react import CodeExecutionReactAgent
        assert CodeExecutionReactAgent is not None
    
    def test_tool_executor(self):
        from app.services.agent.tool_executor import ToolExecutor
        assert ToolExecutor is not None
    
    def test_agent_factory(self):
        from app.services.agent.agent_factory import AgentFactory
        assert AgentFactory is not None


class TestCodeStructure:
    """验证代码结构"""
    
    def test_time_react_inherits(self):
        """TimeReactAgent继承关系"""
        from app.services.agent.time_react import TimeReactAgent
        from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
        # 验证继承
        assert issubclass(TimeReactAgent, ReactAgentMixin)
    
    def test_file_react_inherits(self):
        """FileReactAgent继承关系"""
        from app.services.agent.file_react import FileReactAgent
        from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
        assert issubclass(FileReactAgent, ReactAgentMixin)
    
    def test_shell_react_inherits(self):
        """ShellReactAgent继承关系"""
        from app.services.agent.shell_react import ShellReactAgent
        from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin
        assert issubclass(ShellReactAgent, ReactAgentMixin)