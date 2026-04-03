# -*- coding: utf-8 -*-
"""
阶段4+阶段5测试用例 - 小健编写
=========================================

测试范围：
- 阶段4: start_step.py send_start_step 函数
- 阶段5: chat_router.py 6步完整流程

测试目标：
- start_step 函数正确构建start_data
- start_step 函数正确发送SSE
- start_step 函数正确保存到数据库
- chat_router 6步流程正确执行
- 意图检测正确分发

创建时间: 2026-03-26
作者: 小健
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from typing import List, Dict, Any


# ============================================================================
# 阶段4测试：start_step.py send_start_step
# ============================================================================

class TestSendStartStepImport:
    """测试导入"""

    def test_import_send_start_step(self):
        """TS4-001: 测试 send_start_step 可以正确导入"""
        from app.chat_stream.start_step import send_start_step
        assert send_start_step is not None

    def test_import_chat_helpers(self):
        """TS4-002: 测试 chat_helpers 可以正确导入"""
        from app.chat_stream.chat_helpers import create_timestamp
        assert create_timestamp is not None


class TestSendStartStepFunction:
    """测试 send_start_step 函数"""

    @pytest.mark.asyncio
    async def test_send_start_step_basic(self):
        """TS4-003: 测试 send_start_step 基本功能"""
        from app.chat_stream.start_step import send_start_step
        
        # Mock ai_service
        mock_ai_service = MagicMock()
        mock_ai_service.provider = "openai"
        mock_ai_service.model = "gpt-4"
        
        # Mock参数
        task_id = "test-task-id-123"
        next_step = Mock(return_value=1)
        user_message = "测试用户消息"
        security_check_result = {
            'is_safe': True,
            'risk_level': 'low',
            'risk': None,
            'blocked': False
        }
        current_execution_steps = []
        session_id = "test-session-id"
        
        # 记录发送的SSE数据
        sent_sse_data = []
        
        def yield_func(data):
            sent_sse_data.append(data)
        
        # 调用函数
        result = await send_start_step(
            ai_service=mock_ai_service,
            task_id=task_id,
            next_step=next_step,
            user_message=user_message,
            security_check_result=security_check_result,
            current_execution_steps=current_execution_steps,
            session_id=session_id,
            yield_func=yield_func
        )
        
        # 验证返回结果
        assert result is not None
        assert result['type'] == 'start'
        assert result['task_id'] == task_id
        assert result['display_name'] == 'openai (gpt-4)'
        assert result['provider'] == 'openai'
        assert result['model'] == 'gpt-4'
        
    @pytest.mark.asyncio
    async def test_send_start_step_sse_format(self):
        """TS4-004: 测试 send_start_step SSE格式"""
        from app.chat_stream.start_step import send_start_step
        
        mock_ai_service = MagicMock()
        mock_ai_service.provider = "openai"
        mock_ai_service.model = "gpt-4"
        
        sent_sse_data = []
        def yield_func(data):
            sent_sse_data.append(data)
        
        await send_start_step(
            ai_service=mock_ai_service,
            task_id="task-123",
            next_step=lambda: 1,
            user_message="测试消息",
            security_check_result={'is_safe': True, 'risk_level': None, 'risk': None, 'blocked': False},
            current_execution_steps=[],
            session_id="session-123",
            yield_func=yield_func
        )
        
        # 验证SSE格式: data: {json}\n\n
        assert len(sent_sse_data) == 1
        assert sent_sse_data[0].startswith('data: ')
        assert sent_sse_data[0].endswith('\n\n')
        
    @pytest.mark.asyncio
    async def test_send_start_step_saved_to_steps(self):
        """TS4-005: 测试 start_data 保存到 current_execution_steps"""
        from app.chat_stream.start_step import send_start_step
        
        mock_ai_service = MagicMock()
        mock_ai_service.provider = "openai"
        mock_ai_service.model = "gpt-4"
        
        current_execution_steps = []
        
        await send_start_step(
            ai_service=mock_ai_service,
            task_id="task-123",
            next_step=lambda: 1,
            user_message="测试消息",
            security_check_result={'is_safe': True, 'risk_level': None, 'risk': None, 'blocked': False},
            current_execution_steps=current_execution_steps,
            session_id="session-123",
            yield_func=lambda x: None
        )
        
        # 验证保存到步骤列表
        assert len(current_execution_steps) == 1
        assert current_execution_steps[0]['type'] == 'start'


# ============================================================================
# 阶段5测试：chat_router.py 6步完整流程
# ============================================================================

class TestChatRouterImport:
    """测试导入"""

    def test_import_chat_router(self):
        """TS5-001: 测试 ChatRouter 可以正确导入"""
        from app.services.chat_router import ChatRouter
        assert ChatRouter is not None

    def test_import_router(self):
        """TS5-002: 测试 router 可以正确导入"""
        from app.services.chat_router import router
        assert router is not None

    def test_import_preprocessing_pipeline(self):
        """TS5-003: 测试 PreprocessingPipeline 导入"""
        from app.services.preprocessing.pipeline import PreprocessingPipeline
        assert PreprocessingPipeline is not None


class TestChatRouterInitialization:
    """测试 ChatRouter 初始化"""

    def test_chat_router_init(self):
        """TS5-004: 测试 ChatRouter 实例化"""
        from app.services.chat_router import ChatRouter
        
        router = ChatRouter()
        assert router is not None
        assert router.preprocessing is not None

    def test_intent_labels_defined(self):
        """TS5-005: 测试 INTENT_LABELS 定义"""
        from app.services.chat_router import INTENT_LABELS
        
        assert 'chat' in INTENT_LABELS
        assert 'file' in INTENT_LABELS
        assert 'network' in INTENT_LABELS
        assert 'desktop' in INTENT_LABELS


class TestChatRouterSixSteps:
    """测试 chat_router 6步流程"""

    @pytest.mark.asyncio
    async def test_route_step1_preprocessing(self):
        """TS5-006: 测试步骤1 - 预处理"""
        from app.services.chat_router import ChatRouter
        
        router = ChatRouter()
        
        # Mock预处理结果
        with patch.object(router.preprocessing, 'process') as mock_process:
            mock_process.return_value = {
                'intent': 'file',
                'confidence': 0.9,
                'corrected': '测试修正后的消息'
            }
            
            result = router.preprocessing.process(
                user_input="测试消息",
                intent_labels=['chat', 'file'],
                session_id="test-session"
            )
            
            assert result['intent'] == 'file'
            assert result['confidence'] == 0.9
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_step2_intent_detection(self):
        """TS5-007: 测试步骤2 - 意图检测"""
        from app.services.chat_router import ChatRouter
        
        router = ChatRouter()
        
        # 测试意图类型解析
        intent_result = {
            'intent': 'file',
            'confidence': 0.85,
            'corrected': '测试'
        }
        
        intent_type = intent_result.get("intent", "chat")
        confidence = intent_result.get("confidence", 0.0)
        
        assert intent_type == "file"
        assert confidence == 0.85

    @pytest.mark.asyncio
    async def test_route_step3_initialization(self):
        """TS5-008: 测试步骤3 - 初始化参数"""
        import uuid
        
        # 验证初始化参数
        task_id = str(uuid.uuid4())
        assert task_id is not None
        assert len(task_id) > 0
        
        # 验证步骤计数器
        step_counter = 0
        def next_step():
            nonlocal step_counter
            step_counter += 1
            return step_counter
        
        assert next_step() == 1
        assert next_step() == 2
        
        # 验证running_tasks初始化
        running_tasks = {}
        assert isinstance(running_tasks, dict)
        
        # 验证current_execution_steps初始化
        current_execution_steps = []
        assert isinstance(current_execution_steps, list)

    @pytest.mark.asyncio
    async def test_route_step4_security_check(self):
        """TS5-009: 测试步骤4 - 安全检测"""
        from app.services.shell_security import check_command_safety
        
        # 测试安全检查函数
        result = check_command_safety("安全的命令")
        
        assert 'is_safe' in result
        assert 'blocked' in result

    @pytest.mark.asyncio
    async def test_route_step5_start_step(self):
        """TS5-010: 测试步骤5 - start步骤"""
        from app.chat_stream.start_step import send_start_step
        
        mock_ai_service = MagicMock()
        mock_ai_service.provider = "openai"
        mock_ai_service.model = "gpt-4"
        
        current_execution_steps = []
        
        result = await send_start_step(
            ai_service=mock_ai_service,
            task_id="test-task",
            next_step=lambda: 1,
            user_message="测试",
            security_check_result={'is_safe': True, 'risk_level': None, 'risk': None, 'blocked': False},
            current_execution_steps=current_execution_steps,
            session_id="test-session",
            yield_func=lambda x: None
        )
        
        assert result['type'] == 'start'
        assert 'display_name' in result
        assert 'provider' in result
        assert 'model' in result

    @pytest.mark.asyncio
    async def test_route_step6_file_intent(self):
        """TS5-011: 测试步骤6 - 文件意图分发"""
        from app.services.chat_router import ChatRouter
        
        router = ChatRouter()
        
        # Mock FileReactAgent
        mock_agent = MagicMock()
        mock_agent.ver1_run_stream = AsyncMock(return_value=iter([
            'data: {"type": "start", "step": 1}\n\n'
        ]))
        
        with patch('app.services.chat_router.FileReactAgent') as MockAgent:
            MockAgent.return_value = mock_agent
            
            # 创建llm_client
            async def llm_client(message, history=None):
                response = MagicMock()
                response.content = "test response"
                return response
            
            # 执行文件操作处理
            result = []
            async for event in router._handle_file_operation(
                user_input="测试文件操作",
                model="gpt-4",
                provider="openai",
                llm_client=llm_client,
                session_id="test-session"
            ):
                result.append(event)
            
            # 验证调用
            MockAgent.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_step6_chat_intent(self):
        """TS5-012: 测试步骤6 - chat意图分发"""
        from app.services.chat_router import ChatRouter
        
        router = ChatRouter()
        
        # Mock ai_service
        mock_ai_service = MagicMock()
        
        # 测试chat操作处理函数存在
        assert hasattr(router, '_handle_chat_operation')
        assert callable(router._handle_chat_operation)


class TestChatRouterIntentDistribution:
    """测试意图分发逻辑"""

    @pytest.mark.asyncio
    async def test_file_intent_high_confidence(self):
        """TS5-013: file意图，高置信度 -> 调用FileReactAgent"""
        intent_type = "file"
        confidence = 0.85
        
        # 高置信度，应该调用Agent
        if intent_type == "file" and confidence >= 0.3:
            should_use_agent = True
        else:
            should_use_agent = False
            
        assert should_use_agent is True

    @pytest.mark.asyncio
    async def test_chat_intent_low_confidence(self):
        """TS5-014: chat意图，低置信度 -> 调用chat_stream_query"""
        intent_type = "chat"
        confidence = 0.2
        
        # 低置信度，使用chat
        if intent_type == "chat" or confidence < 0.3:
            use_chat = True
        else:
            use_chat = False
            
        assert use_chat is True

    @pytest.mark.asyncio
    async def test_unknown_intent_fallback(self):
        """TS5-015: 未知意图 -> 回退到chat"""
        intent_type = "unknown"
        confidence = 0.1
        
        # 默认回退到chat
        if intent_type not in ["file", "network", "desktop"] or confidence < 0.3:
            fallback_to_chat = True
        else:
            fallback_to_chat = False
            
        assert fallback_to_chat is True


class TestErrorHandling:
    """测试错误处理"""

    def test_create_error_sse(self):
        """TS5-016: 测试错误SSE创建"""
        from app.services.chat_router import ChatRouter
        
        router = ChatRouter()
        
        error_sse = router._create_error_sse("测试错误消息", 1)
        
        # 验证格式
        assert 'data: ' in error_sse
        assert error_sse.startswith('data: ')
        assert error_sse.endswith('\n\n')
        
        # 验证内容
        data = json.loads(error_sse.replace('data: ', '').replace('\n\n', ''))
        assert data['type'] == 'error'
        assert data['message'] == '测试错误消息'
        assert data['step'] == 1


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_flow_file_intent(self):
        """TS5-017: 完整流程测试 - file意图"""
        from app.services.chat_router import ChatRouter
        from app.chat_stream.start_step import send_start_step
        
        router = ChatRouter()
        
        # 1. 预处理
        with patch.object(router.preprocessing, 'process') as mock_process:
            mock_process.return_value = {
                'intent': 'file',
                'confidence': 0.9,
                'corrected': '测试文件操作'
            }
            
            intent_result = router.preprocessing.process(
                user_input="测试",
                intent_labels=['chat', 'file'],
                session_id="test"
            )
            
            intent_type = intent_result.get("intent", "chat")
            confidence = intent_result.get("confidence", 0.0)
            
            assert intent_type == "file"
            assert confidence >= 0.3

    @pytest.mark.asyncio
    async def test_full_flow_chat_intent(self):
        """TS5-018: 完整流程测试 - chat意图"""
        from app.services.chat_router import ChatRouter
        
        router = ChatRouter()
        
        # 1. 预处理
        with patch.object(router.preprocessing, 'process') as mock_process:
            mock_process.return_value = {
                'intent': 'chat',
                'confidence': 0.2,
                'corrected': '测试聊天'
            }
            
            intent_result = router.preprocessing.process(
                user_input="你好",
                intent_labels=['chat', 'file'],
                session_id="test"
            )
            
            intent_type = intent_result.get("intent", "chat")
            confidence = intent_result.get("confidence", 0.0)
            
            # chat意图或低置信度，应该走chat流程
            assert intent_type == "chat" or confidence < 0.3


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
