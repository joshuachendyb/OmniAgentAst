"""
测试空闲超时异步迭代器

创建时间: 2026-03-14
测试内容: IdleTimeoutIterator 的实时超时检测功能
"""

import pytest
import asyncio
from app.utils.idle_timeout import IdleTimeoutIterator, IdleTimeoutError


class TestIdleTimeoutIterator:
    """测试 IdleTimeoutIterator 类"""
    
    @pytest.mark.asyncio
    async def test_normal_iteration(self):
        """测试正常迭代（不超时）"""
        async def async_gen():
            yield "chunk1"
            yield "chunk2"
            yield "chunk3"
        
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=30.0)
        results = []
        async for item in wrapper:
            results.append(item)
        
        assert results == ["chunk1", "chunk2", "chunk3"]
    
    @pytest.mark.asyncio
    async def test_empty_iterator(self):
        """测试空迭代器"""
        async def async_gen():
            return
            yield  # never reached
        
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=30.0)
        results = []
        async for item in wrapper:
            results.append(item)
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_timeout_during_iteration(self):
        """测试迭代过程中超时"""
        async def async_gen():
            yield "chunk1"
            await asyncio.sleep(0.5)  # 短暂延迟，不超过超时
            yield "chunk2"
            await asyncio.sleep(2.0)  # 长延迟，超过超时
            yield "chunk3"  # 不会到达
        
        # 设置超时为1秒
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=1.0)
        results = []
        
        with pytest.raises(IdleTimeoutError):
            async for item in wrapper:
                results.append(item)
        
        # 应该收到前两个chunk
        assert results == ["chunk1", "chunk2"]
    
    @pytest.mark.asyncio
    async def test_get_elapsed_time(self):
        """测试获取空闲时间"""
        async def async_gen():
            yield "chunk1"
            await asyncio.sleep(0.1)
            yield "chunk2"
        
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=30.0)
        
        async for item in wrapper:
            elapsed = wrapper.get_elapsed_time()
            # elapsed时间应该很小（刚收到内容）
            assert elapsed < 1.0  # 小于1秒
    
    @pytest.mark.asyncio
    async def test_get_remaining_time(self):
        """测试获取剩余时间"""
        async def async_gen():
            yield "chunk1"
        
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=30.0)
        
        async for item in wrapper:
            remaining = wrapper.get_remaining_time()
            # 剩余时间应该接近30秒
            assert remaining > 28.0  # 允许一点误差
    
    @pytest.mark.asyncio
    async def test_get_count(self):
        """测试获取元素数量"""
        async def async_gen():
            yield "chunk1"
            yield "chunk2"
            yield "chunk3"
        
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=30.0)
        count = 0
        
        async for item in wrapper:
            count += 1
            assert wrapper.get_count() == count
        
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_reset_timer(self):
        """测试手动重置计时器"""
        async def async_gen():
            yield "chunk1"
            await asyncio.sleep(0.1)
            yield "chunk2"
        
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=30.0)
        
        async for item in wrapper:
            if item == "chunk1":
                # 手动重置计时器
                wrapper.reset_timer()
                elapsed = wrapper.get_elapsed_time()
                # 重置后elapsed应该很小
                assert elapsed < 0.5
    
    @pytest.mark.asyncio
    async def test_timeout_error_message(self):
        """测试超时错误消息"""
        async def async_gen():
            yield "chunk1"
            await asyncio.sleep(2.0)  # 超时
            yield "chunk2"
        
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=0.5)
        
        with pytest.raises(IdleTimeoutError) as exc_info:
            async for item in wrapper:
                pass
        
        # 验证错误消息包含超时信息
        assert "超时" in str(exc_info.value) or "timeout" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_repr(self):
        """测试字符串表示"""
        async def async_gen():
            yield "chunk1"
        
        wrapper = IdleTimeoutIterator(async_gen(), timeout_seconds=30.0, name="test")
        repr_str = repr(wrapper)
        
        assert "IdleTimeoutIterator" in repr_str
        assert "test" in repr_str
        assert "timeout=30" in repr_str


class TestIdleTimeoutError:
    """测试 IdleTimeoutError 异常"""
    
    def test_error_message(self):
        """测试错误消息"""
        error = IdleTimeoutError("测试超时", timeout_seconds=30)
        assert "30" in str(error)
        assert "测试超时" in str(error)
    
    def test_error_timeout_attribute(self):
        """测试超时属性"""
        error = IdleTimeoutError("测试超时", timeout_seconds=30)
        assert error.timeout_seconds == 30


class TestWrapWithIdleTimeout:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_wrap_function(self):
        """测试包装函数"""
        from app.utils.idle_timeout import wrap_with_idle_timeout
        
        async def async_gen():
            yield "chunk1"
            yield "chunk2"
        
        wrapper = wrap_with_idle_timeout(async_gen(), timeout_seconds=30.0, name="test")
        assert isinstance(wrapper, IdleTimeoutIterator)
        
        results = []
        async for item in wrapper:
            results.append(item)
        
        assert results == ["chunk1", "chunk2"]