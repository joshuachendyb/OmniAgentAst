# 会话管理API测试
# 测试范围：标题版本控制、批量操作、并发控制
# 编写人：小沈（后端开发）
# 创建时间：2026-02-25
# 协作人：小健（代码审查）

import pytest
import pytest_asyncio
import json
import uuid
from httpx import AsyncClient
from datetime import datetime


class TestSessionTitleVersionControl:
    """测试标题版本控制功能（11.2.1节）"""
    
    @pytest.mark.asyncio
    async def test_title_history_created(self, client: AsyncClient):
        """测试：创建会话时，title_history表正确创建"""
        # 这个测试在初始化数据库时已经验证
        # 这里通过创建会话来验证表存在
        response = await client.post(
            "/api/v1/sessions",
            json={"title": "测试标题历史"}
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        # 验证会话创建成功
        assert session_id is not None
        
        # TODO: 后续添加直接查询数据库的验证
        # 需要数据库连接工具类
    
    @pytest.mark.asyncio
    async def test_update_session_records_history(self, client: AsyncClient):
        """测试：更新会话标题时，记录标题历史"""
        # 1. 创建会话
        create_response = await client.post(
            "/api/v1/sessions",
            json={"title": "原始标题"}
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # 2. 更新标题
        update_response = await client.put(
            f"/api/v1/sessions/{session_id}",
            json={
                "title": "修改后的标题",
                "version": 1,
                "updated_by": "test_user"
            }
        )
        assert update_response.status_code == 200
        update_data = update_response.json()
        assert update_data["success"] is True
        assert update_data["title"] == "修改后的标题"
        assert "version" in update_data
        assert update_data["version"] >= 1
        
        # TODO: 验证title_history表中有记录
        # 需要数据库查询验证


class TestBatchTitleOperations:
    """测试批量操作优化功能（11.3.2节）"""
    
    @pytest.mark.asyncio
    async def test_batch_get_titles(self, client: AsyncClient):
        """测试：批量获取会话标题（12.1.3节）"""
        # 1. 创建3个会话
        session_ids = []
        for i in range(3):
            response = await client.post(
                "/api/v1/sessions",
                json={"title": f"测试会话{i+1}"}
            )
            assert response.status_code == 200
            session_ids.append(response.json()["session_id"])
        
        # 2. 批量获取标题
        batch_response = await client.get(
            "/api/v1/sessions/titles/batch",
            params={"session_ids": ",".join(session_ids)}
        )
        
        assert batch_response.status_code == 200
        batch_data = batch_response.json()
        
        # 验证响应结构
        assert "sessions" in batch_data
        assert len(batch_data["sessions"]) == 3
        
        # 验证每个会话的数据
        returned_ids = [s["session_id"] for s in batch_data["sessions"]]
        for sid in session_ids:
            assert sid in returned_ids
        
        # 验证新字段
        for session in batch_data["sessions"]:
            assert "title" in session
            assert "title_locked" in session
            assert "title_updated_at" in session
    
    @pytest.mark.asyncio
    async def test_batch_get_titles_empty_ids(self, client: AsyncClient):
        """测试：批量获取标题时，ID列表为空"""
        response = await client.get(
            "/api/v1/sessions/titles/batch",
            params={"session_ids": ""}
        )
        assert response.status_code == 400  # 应该返回400错误
    
    @pytest.mark.asyncio
    async def test_batch_get_titles_too_many(self, client: AsyncClient):
        """测试：批量获取标题时，ID数量超过限制"""
        # 生成101个虚拟ID
        fake_ids = [str(uuid.uuid4()) for _ in range(101)]
        
        response = await client.get(
            "/api/v1/sessions/titles/batch",
            params={"session_ids": ",".join(fake_ids)}
        )
        assert response.status_code == 400  # 应该返回400错误


class TestConcurrencyControl:
    """测试并发控制功能（11.4.2节）"""
    
    @pytest.mark.asyncio
    async def test_optimistic_locking(self, client: AsyncClient):
        """测试：乐观锁版本控制（12.1.2节）"""
        # 1. 创建会话
        create_response = await client.post(
            "/api/v1/sessions",
            json={"title": "初始标题"}
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # 2. 第一次更新（不传递version，兼容模式）
        update1_response = await client.put(
            f"/api/v1/sessions/{session_id}",
            json={"title": "第一次更新", "version": 1}
        )
        assert update1_response.status_code == 200
        update1_data = update1_response.json()
        
        # 3. 第二次更新（传递version）
        version = update1_data.get("version", 1)
        update2_response = await client.put(
            f"/api/v1/sessions/{session_id}",
            json={
                "title": "第二次更新",
                "version": version,
                "updated_by": "test_user"
            }
        )
        assert update2_response.status_code == 200
        update2_data = update2_response.json()
        
        # 验证版本号递增
        assert update2_data["version"] > version
        
        # 4. 尝试使用旧版本号更新（应该失败）
        update3_response = await client.put(
            f"/api/v1/sessions/{session_id}",
            json={
                "title": "使用旧版本号更新",
                "version": version  # 使用旧版本号
            }
        )
        assert update3_response.status_code == 409  # 应该返回409冲突错误
    
    @pytest.mark.asyncio
    async def test_title_lock_functionality(self, client: AsyncClient):
        """测试：标题锁定功能（11.2.2节）"""
        # 1. 创建会话
        create_response = await client.post(
            "/api/v1/sessions",
            json={"title": "新会话"}
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # 2. 手动更新标题（应该锁定）
        update_response = await client.put(
            f"/api/v1/sessions/{session_id}",
            json={"title": "用户手动标题", "version": 1}
        )
        assert update_response.status_code == 200
        
        # 3. 发送消息（不应该更新锁定的标题）
        message_response = await client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={
                "role": "user",
                "content": "这是一条测试消息，不应该改变标题"
            }
        )
        assert message_response.status_code == 200
        message_data = message_response.json()
        
        # 验证标题没有被消息内容覆盖
        assert message_data.get("title_updated", False) is False
        
        # 4. 获取会话消息，验证新字段
        get_response = await client.get(f"/api/v1/sessions/{session_id}/messages")
        assert get_response.status_code == 200
        get_data = get_response.json()
        
        # 验证新字段存在（12.1.1节要求）
        assert "title_locked" in get_data
        assert "title_source" in get_data
        assert "title_updated_at" in get_data
        
        # 验证标题状态
        assert get_data["title"] == "用户手动标题"
        assert get_data["title_locked"] is True
        assert get_data["title_source"] == "user"


class TestBackwardCompatibility:
    """测试向后兼容性（P0风险缓解）"""
    
    @pytest.mark.asyncio
    async def test_create_session_backward_compatible(self, client: AsyncClient):
        """测试：创建会话时，即使新字段不存在也能正常工作"""
        # 这个测试需要模拟旧数据库结构
        # 在实际测试中，可以通过直接操作数据库移除新字段来验证
        
        # 正常创建会话
        response = await client.post(
            "/api/v1/sessions",
            json={"title": "测试兼容性"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] is not None
        assert data["title"] == "测试兼容性"
    
    @pytest.mark.asyncio
    async def test_get_session_messages_backward_compatible(self, client: AsyncClient):
        """测试：获取会话消息时，新字段缺失时使用默认值"""
        # 1. 创建会话
        create_response = await client.post(
            "/api/v1/sessions",
            json={"title": "测试会话"}
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # 2. 获取消息（即使新字段不存在也应有默认值）
        get_response = await client.get(f"/api/v1/sessions/{session_id}/messages")
        assert get_response.status_code == 200
        data = get_response.json()
        
        # 验证新字段有默认值
        assert "title_locked" in data
        assert "title_source" in data
        assert "title_updated_at" in data
        
        # 验证默认值合理
        assert isinstance(data["title_locked"], bool)
        assert data["title_source"] in ["user", "auto"]


class TestIntegratedScenarios:
    """综合场景测试"""
    
    @pytest.mark.asyncio
    async def test_user_session_workflow(self, client: AsyncClient):
        """测试：用户使用会话的完整流程"""
        # 1. 创建新会话
        create_response = await client.post("/api/v1/sessions")
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # 2. 发送第一条消息（标题应该自动更新）
        message1_response = await client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"role": "user", "content": "你好，这是一条消息"}
        )
        assert message1_response.status_code == 200
        assert message1_response.json()["title_updated"] is True
        
        # 3. 手动修改标题（标题应该锁定）
        update_response = await client.put(
            f"/api/v1/sessions/{session_id}",
            json={"title": "用户自定义标题", "version": 1}
        )
        assert update_response.status_code == 200
        
        # 4. 再次发送消息（标题不应该被覆盖）
        message2_response = await client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"role": "assistant", "content": "助手回复"}
        )
        assert message2_response.status_code == 200
        assert message2_response.json()["title_updated"] is False
        
        # 5. 获取会话信息，验证状态
        get_response = await client.get(f"/api/v1/sessions/{session_id}/messages")
        assert get_response.status_code == 200
        data = get_response.json()
        
        # 验证标题仍然是用户自定义的
        assert data["title"] == "用户自定义标题"
        assert data["title_locked"] is True
        assert data["title_source"] == "user"


# Pytest fixtures
@pytest_asyncio.fixture
async def client():
    """创建测试客户端"""
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# 运行测试：
# pytest tests/test_sessions_enhanced.py -v
