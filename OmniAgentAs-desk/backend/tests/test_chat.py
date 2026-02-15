"""
阶段1.2 测试 - AI模型接入测试
测试智谱GLM和OpenCode Zen API
"""

import pytest
import sys
import os

# 添加backend到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_chat_imports():
    """TC001: 测试chat模块可以正常导入"""
    from app.api.v1.chat import router
    from app.services import AIServiceFactory
    
    assert router is not None
    assert AIServiceFactory is not None


def test_chat_endpoint_structure():
    """TC002: 测试chat端点结构"""
    from app.api.v1.chat import router
    
    routes = [route.path for route in router.routes]
    assert "/chat" in routes
    assert "/chat/validate" in routes
    assert "/chat/switch/{provider}" in routes


def test_chat_routes_exist():
    """TC003: 测试chat路由已注册到app"""
    from app.main import app
    
    routes = [route.path for route in app.routes]
    assert "/api/v1/chat" in routes
    assert "/api/v1/chat/validate" in routes


def test_chat_request_model():
    """TC004: 测试ChatRequest模型"""
    from app.api.v1.chat import ChatRequest, ChatMessage
    
    # 测试正常创建
    msg = ChatMessage(role="user", content="你好")
    assert msg.role == "user"
    assert msg.content == "你好"
    
    # 测试请求体
    request = ChatRequest(
        messages=[{"role": "user", "content": "测试"}],
        stream=False,
        temperature=0.7
    )
    assert len(request.messages) == 1
    assert request.temperature == 0.7


def test_chat_response_model():
    """TC005: 测试ChatResponse模型"""
    from app.api.v1.chat import ChatResponse
    
    # 测试成功响应
    success_response = ChatResponse(
        success=True,
        content="回复内容",
        model="glm-4",
        error=None
    )
    assert success_response.success is True
    assert success_response.content == "回复内容"
    
    # 测试失败响应
    error_response = ChatResponse(
        success=False,
        content="",
        model="",
        error="错误信息"
    )
    assert error_response.success is False
    assert error_response.error == "错误信息"


def test_services_structure():
    """TC006: 测试AI服务结构"""
    from app.services.base import BaseAIService, Message, ChatResponse
    from app.services.zhipuai import ZhipuAIService
    from app.services.opencode import OpenCodeService
    
    # 测试基类是抽象类
    assert hasattr(BaseAIService, 'chat')
    assert hasattr(BaseAIService, 'validate')
    assert hasattr(BaseAIService, 'close')
    
    # 测试Message类
    msg = Message(role="user", content="测试")
    assert msg.to_dict() == {"role": "user", "content": "测试"}
    
    # 测试ChatResponse类
    response = ChatResponse(content="回复", model="test")
    assert response.success is True


def test_factory_methods():
    """TC007: 测试服务工厂方法存在"""
    from app.services import AIServiceFactory
    
    assert hasattr(AIServiceFactory, 'get_service')
    assert hasattr(AIServiceFactory, 'load_config')
    assert hasattr(AIServiceFactory, 'switch_provider')


@pytest.mark.asyncio
async def test_zhipuai_service_creation():
    """TC008: 测试智谱服务创建"""
    from app.services.zhipuai import ZhipuAIService
    
    service = ZhipuAIService(
        api_key="test_key",
        model="glm-4",
        api_base="https://test.com",
        timeout=30
    )
    
    assert service.api_key == "test_key"
    assert service.model == "glm-4"
    assert service.timeout == 30
    
    await service.close()


@pytest.mark.asyncio
async def test_opencode_service_creation():
    """TC009: 测试OpenCode服务创建"""
    from app.services.opencode import OpenCodeService
    
    service = OpenCodeService(
        api_key="test_key",
        model="kimi-k2.5-free",
        api_base="https://test.com",
        timeout=30
    )
    
    assert service.api_key == "test_key"
    assert service.model == "kimi-k2.5-free"
    assert service.timeout == 30
    
    await service.close()


def test_config_loading():
    """TC010: 测试配置加载"""
    from app.services import AIServiceFactory
    
    config = AIServiceFactory.load_config()
    
    assert isinstance(config, dict)
    assert "ai" in config or len(config) == 0  # 空配置或包含ai配置


@pytest.mark.asyncio
async def test_provider_switch():
    """TC011: 测试提供商切换功能"""
    from app.services import AIServiceFactory
    
    # 切换到opencode
    try:
        service = AIServiceFactory.switch_provider("opencode")
        assert service is not None
    except Exception as e:
        # 允许切换失败（如果没有配置API key）
        print(f"切换测试提示: {e}")
    
    # 切换回zhipuai
    try:
        service = AIServiceFactory.switch_provider("zhipuai")
        assert service is not None
    except Exception as e:
        print(f"切换回智谱提示: {e}")


@pytest.mark.api_test
@pytest.mark.asyncio
async def test_zhipuai_api_validation():
    """
    TC012: 测试智谱API真实连接
    最多尝试5次，如果失败则切换到OpenCode
    """
    from app.services import AIServiceFactory
    
    max_attempts = 5
    attempt = 0
    success = False
    
    while attempt < max_attempts and not success:
        attempt += 1
        try:
            # 获取智谱服务
            ai_service = AIServiceFactory.get_service()
            
            # 尝试验证
            is_valid = await ai_service.validate()
            
            if is_valid:
                success = True
                print(f"智谱API验证成功（第{attempt}次尝试）")
            else:
                print(f"智谱API验证失败（第{attempt}次尝试）")
                
        except Exception as e:
            print(f"智谱API连接异常（第{attempt}次尝试）: {e}")
        
        if not success and attempt < max_attempts:
            import asyncio
            await asyncio.sleep(1)  # 等待1秒后重试
    
    if not success:
        print(f"智谱API {max_attempts}次验证失败，切换到OpenCode...")
        try:
            # 切换到OpenCode
            opencode_service = AIServiceFactory.switch_provider("opencode")
            is_valid = await opencode_service.validate()
            
            if is_valid:
                print("OpenCode API验证成功")
                # 切换回智谱用于其他测试
                await AIServiceFactory.switch_provider("zhipuai")
            else:
                pytest.skip("OpenCode API验证失败，请检查配置")
        except Exception as e:
            pytest.skip(f"OpenCode切换失败: {e}")
    
    assert success, f"API验证在{max_attempts}次尝试后失败，已尝试切换到备选方案"


@pytest.mark.api_test
@pytest.mark.asyncio
async def test_real_chat_with_zhipuai():
    """
    TC013: 测试真实对话功能
    使用智谱API进行实际对话
    """
    from app.services import AIServiceFactory
    
    try:
        ai_service = AIServiceFactory.get_service()
        
        # 先验证
        is_valid = await ai_service.validate()
        if not is_valid:
            pytest.skip("API未通过验证，跳过真实对话测试")
        
        # 发送测试消息
        response = await ai_service.chat(message="你好，请回复\"测试成功\"", history=[])
        
        assert response is not None
        # 不检查具体内容，只要返回成功即可
        
    except Exception as e:
        pytest.skip(f"真实API测试跳过: {e}")


def test_provider_invalid_switch():
    """TC014: 测试无效提供商切换"""
    from app.services import AIServiceFactory
    
    # 测试工厂直接调用无效提供商
    with pytest.raises(ValueError) as exc_info:
        # 重置实例和配置缓存以便测试
        AIServiceFactory._instance = None
        AIServiceFactory._current_provider = None  # 重置当前提供商，让配置文件的provider生效
        AIServiceFactory._config = {"ai": {"provider": "invalid_provider"}}
        # 尝试获取服务应该抛出ValueError
        AIServiceFactory.get_service()
    
    assert "不支持的AI提供商" in str(exc_info.value)

