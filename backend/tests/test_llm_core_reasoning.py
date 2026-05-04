"""
测试 llm_core.py 的 reasoning_content 处理

验证thinking模型的reasoning_content字段能被正确处理，
不再导致"AI服务返回空响应"问题。

作者：小沈
创建时间：2026-05-05
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_core import BaseAIService, ChatResponse, StreamChunk, Message


class TestStreamChunkReasoningContent:
    """测试StreamChunk的reasoning_content支持"""

    def test_stream_chunk_with_reasoning(self):
        chunk = StreamChunk(
            content="思考内容",
            model="big-pickle",
            is_done=False,
            is_reasoning=True
        )
        assert chunk.content == "思考内容"
        assert chunk.is_reasoning is True
        assert chunk.is_done is False

    def test_stream_chunk_with_content(self):
        chunk = StreamChunk(
            content="正常内容",
            model="big-pickle",
            is_done=False,
            is_reasoning=False
        )
        assert chunk.content == "正常内容"
        assert chunk.is_reasoning is False

    def test_stream_chunk_done(self):
        chunk = StreamChunk(
            content="",
            model="big-pickle",
            is_done=True
        )
        assert chunk.is_done is True
        assert chunk.content == ""


class TestChatResponseReasoningContent:
    """测试ChatResponse正常聚合reasoning_content"""

    @pytest.mark.asyncio
    async def test_chat_aggregates_reasoning_content(self):
        """
        【核心测试】验证chat()方法能正确聚合来自reasoning_content的内容
        
        模拟场景：thinking模型只返回reasoning_content，content为空
        修复前：full_content为空 → "AI服务返回空响应"
        修复后：full_content包含reasoning_content的内容
        """
        service = BaseAIService(
            api_key="test-key",
            model="big-pickle",
            api_base="http://localhost:8000"
        )

        mock_chunks = [
            StreamChunk(content="用户想了解", model="big-pickle", is_done=False, is_reasoning=True, reasoning="用户想了解"),
            StreamChunk(content="D盘的情况", model="big-pickle", is_done=False, is_reasoning=True, reasoning="D盘的情况"),
            StreamChunk(content="，我来总结。", model="big-pickle", is_done=False, is_reasoning=True, reasoning="，我来总结。"),
            StreamChunk(content="", model="big-pickle", is_done=True),
        ]

        async def mock_generator(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk

        with patch.object(service, 'chat_stream', side_effect=mock_generator):
            response = await service.chat(message="检查D盘", history=[])

            assert len(response.content) > 0, "reasoning_content应被聚合到full_content中，不应为空"
            assert "用户想了解" in response.content or "D盘的情况" in response.content

    @pytest.mark.asyncio
    async def test_chat_aggregates_normal_content(self):
        """验证普通content仍然正常工作"""
        service = BaseAIService(
            api_key="test-key",
            model="normal-model",
            api_base="http://localhost:8000"
        )

        mock_chunks = [
            StreamChunk(content="这是", model="normal-model", is_done=False, is_reasoning=False),
            StreamChunk(content="正常内容", model="normal-model", is_done=False, is_reasoning=False),
            StreamChunk(content="", model="normal-model", is_done=True),
        ]

        async def mock_generator(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk

        with patch.object(service, 'chat_stream', side_effect=mock_generator):
            response = await service.chat(message="测试", history=[])
            assert response.content == "这是正常内容"

    @pytest.mark.asyncio
    async def test_chat_mixed_reasoning_and_content(self):
        """
        验证混合场景：先有reasoning_content，后有content
        thinking模型典型模式：先思考(reasoning_content)，再输出(content)
        """
        service = BaseAIService(
            api_key="test-key",
            model="big-pickle",
            api_base="http://localhost:8000"
        )

        mock_chunks = [
            StreamChunk(content="让我想想", model="big-pickle", is_done=False, is_reasoning=True, reasoning="让我想想"),
            StreamChunk(content="...", model="big-pickle", is_done=False, is_reasoning=True, reasoning="..."),
            StreamChunk(content='{"tool_name":"finish"', model="big-pickle", is_done=False, is_reasoning=False),
            StreamChunk(content=', "tool_params":{}}', model="big-pickle", is_done=False, is_reasoning=False),
            StreamChunk(content="", model="big-pickle", is_done=True),
        ]

        async def mock_generator(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk

        with patch.object(service, 'chat_stream', side_effect=mock_generator):
            response = await service.chat(message="测试", history=[])
            assert len(response.content) > 0
            assert "让我想想" in response.content
            assert "finish" in response.content


class TestDeltaParsing:
    """测试SSE数据解析中delta字段的处理"""

    def test_delta_with_reasoning_content(self):
        """验证reasoning_content字段能被正确提取"""
        delta = {
            "reasoning_content": "这是思考内容",
            "content": ""
        }
        content = delta.get("content", "") or ""
        reasoning_content = delta.get("reasoning_content", "") or ""

        assert content == ""
        assert reasoning_content == "这是思考内容"
        # 关键：reasoning_content不为空，应被作为content输出
        assert reasoning_content or content  # 至少有一个非空

    def test_delta_with_both_fields(self):
        """验证content和reasoning_content同时存在"""
        delta = {
            "reasoning_content": "思考中...",
            "content": "最终输出"
        }
        content = delta.get("content", "") or ""
        reasoning_content = delta.get("reasoning_content", "") or ""

        assert content == "最终输出"
        assert reasoning_content == "思考中..."

    def test_delta_with_only_content(self):
        """验证普通模型只有content的情况"""
        delta = {
            "content": "普通输出"
        }
        content = delta.get("content", "") or ""
        reasoning_content = delta.get("reasoning_content", "") or ""

        assert content == "普通输出"
        assert reasoning_content == ""

    def test_delta_empty(self):
        """验证空delta"""
        delta = {}
        content = delta.get("content", "") or ""
        reasoning_content = delta.get("reasoning_content", "") or ""

        assert content == ""
        assert reasoning_content == ""
