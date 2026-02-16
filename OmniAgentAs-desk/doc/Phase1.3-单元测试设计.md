# Phase 1.3 单元测试设计

## 1. 测试总体策略

### 1.1 测试原则
1. **先测试后提交**：所有功能必须通过单元测试才能提交验收
2. **覆盖率要求**：核心业务逻辑覆盖率不低于80%
3. **自动化测试**：所有测试用例必须可自动执行
4. **测试即文档**：测试用例应清晰展示功能使用方式

### 1.2 测试范围与覆盖率要求

| 模块 | 测试重点 | 覆盖率要求 | 测试类型 |
|------|---------|-----------|---------|
| 文件操作安全 | 备份、回滚、历史记录 | 90% | 单元测试+集成测试 |
| MCP文件工具 | 6个工具的正确性和异常处理 | 85% | 单元测试 |
| ReAct Agent | 工具解析、执行、循环逻辑 | 80% | 单元测试+Mock测试 |
| 可视化服务 | 数据生成和报告格式 | 75% | 单元测试 |
| API端点 | 请求处理和响应格式 | 80% | 集成测试 |

---

## 2. 文件操作安全模块测试

### 2.1 操作记录测试

**测试文件**: `tests/test_safety.py`

```python
class TestOperationRecording:
    """测试操作记录功能"""
    
    def test_record_operation(self):
        """测试记录单次操作"""
        safety = FileOperationSafety()
        operation_id = safety.record_operation(
            session_id="test-session",
            operation_type=OperationType.CREATE,
            destination_path="/tmp/test.txt"
        )
        assert operation_id is not None
        assert operation_id.startswith("op-")
    
    def test_get_session_operations(self):
        """测试获取会话操作列表"""
        safety = FileOperationSafety()
        # 记录多个操作
        for i in range(3):
            safety.record_operation(
                session_id="test-session",
                operation_type=OperationType.CREATE,
                destination_path=f"/tmp/test{i}.txt",
                sequence_number=i
            )
        
        operations = safety.get_session_operations("test-session")
        assert len(operations) == 3
        assert operations[0].sequence_number == 0
        assert operations[2].sequence_number == 2
    
    def test_space_impact_calculation(self):
        """测试空间影响计算"""
        safety = FileOperationSafety()
        
        # 删除操作应释放空间（正值）
        op_delete = safety.record_operation(
            session_id="test",
            operation_type=OperationType.DELETE,
            source_path="/tmp/file.txt"
        )
        # 模拟执行后检查space_impact_bytes
        
        # 创建操作应占用空间（负值）
        op_create = safety.record_operation(
            session_id="test",
            operation_type=OperationType.CREATE,
            destination_path="/tmp/new_file.txt"
        )
        # 模拟执行后检查space_impact_bytes
```

### 2.2 备份与回滚测试

```python
class TestBackupAndRollback:
    """测试备份和回滚功能"""
    
    def test_delete_file_backup(self, tmp_path):
        """测试删除文件自动备份"""
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        safety = FileOperationSafety()
        operation_id = safety.record_operation(
            session_id="test",
            operation_type=OperationType.DELETE,
            source_path=test_file
        )
        
        # 执行删除
        def do_delete():
            test_file.unlink()
            return True
        
        success = safety.execute_with_safety(operation_id, do_delete)
        assert success is True
        
        # 验证文件已备份到回收站
        operation = safety.get_operation(operation_id)
        assert operation.backup_path is not None
        assert Path(operation.backup_path).exists()
    
    def test_rollback_single_operation(self, tmp_path):
        """测试回滚单个操作"""
        # 创建并删除文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        safety = FileOperationSafety()
        operation_id = safety.record_operation(...)
        safety.execute_with_safety(operation_id, lambda: test_file.unlink())
        
        # 回滚操作
        success = safety.rollback_operation(operation_id)
        assert success is True
        
        # 验证文件已恢复
        assert test_file.exists()
        assert test_file.read_text() == "test content"
    
    def test_rollback_session(self, tmp_path):
        """测试回滚整个会话"""
        safety = FileOperationSafety()
        session_id = "test-session"
        
        # 执行多个操作
        for i in range(3):
            op_id = safety.record_operation(
                session_id=session_id,
                operation_type=OperationType.CREATE,
                destination_path=tmp_path / f"file{i}.txt"
            )
            safety.execute_with_safety(op_id, lambda i=i: 
                (tmp_path / f"file{i}.txt").write_text("content"))
        
        # 验证文件已创建
        assert (tmp_path / "file0.txt").exists()
        
        # 回滚整个会话
        result = safety.rollback_session(session_id)
        assert result["success"] == 3
        assert result["total"] == 3
        
        # 验证文件已删除
        assert not (tmp_path / "file0.txt").exists()
```

---

## 3. MCP文件工具测试

### 3.1 工具功能测试

**测试文件**: `tests/test_file_tools.py`

```python
class TestFileTools:
    """测试文件操作工具"""
    
    @pytest.fixture
    async def file_tools(self):
        """创建工具实例"""
        return FileTools(session_id="test-session")
    
    async def test_read_file_success(self, file_tools, tmp_path):
        """测试成功读取文件"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World", encoding="utf-8")
        
        result = await file_tools.read_file(str(test_file))
        
        assert result["success"] is True
        assert "Hello World" in result["content"]
        assert result["total_lines"] == 1
    
    async def test_read_file_not_found(self, file_tools):
        """测试读取不存在的文件"""
        result = await file_tools.read_file("/nonexistent/file.txt")
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    async def test_write_file(self, file_tools, tmp_path):
        """测试写入文件"""
        test_file = tmp_path / "output.txt"
        
        result = await file_tools.write_file(
            str(test_file),
            content="Test content"
        )
        
        assert result["success"] is True
        assert test_file.exists()
        assert test_file.read_text() == "Test content"
    
    async def test_list_directory(self, file_tools, tmp_path):
        """测试列出目录"""
        # 创建测试文件
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()
        (tmp_path / "subdir").mkdir()
        
        result = await file_tools.list_directory(str(tmp_path))
        
        assert result["success"] is True
        assert len(result["entries"]) == 3
        assert any(e["name"] == "file1.txt" for e in result["entries"])
    
    async def test_delete_file_with_backup(self, file_tools, tmp_path):
        """测试删除文件（带备份）"""
        test_file = tmp_path / "to_delete.txt"
        test_file.write_text("delete me")
        
        result = await file_tools.delete_file(str(test_file))
        
        assert result["success"] is True
        assert not test_file.exists()
        assert result["backup_path"] is not None
    
    async def test_move_file(self, file_tools, tmp_path):
        """测试移动文件"""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("move me")
        
        result = await file_tools.move_file(str(src), str(dst))
        
        assert result["success"] is True
        assert not src.exists()
        assert dst.exists()
    
    async def test_search_files(self, file_tools, tmp_path):
        """测试搜索文件"""
        (tmp_path / "file1.txt").write_text("hello world")
        (tmp_path / "file2.txt").write_text("hello python")
        
        result = await file_tools.search_files(
            str(tmp_path),
            pattern="hello",
            file_pattern="*.txt"
        )
        
        assert result["success"] is True
        assert len(result["matches"]) == 2
```

---

## 4. ReAct Agent测试

### 4.1 工具解析器测试

**测试文件**: `tests/test_agent.py`

```python
class TestToolParser:
    """测试工具解析器"""
    
    def test_parse_json_response(self):
        """测试解析JSON格式响应"""
        response = '''```json
        {
            "thought": "I need to read a file",
            "action": "read_file",
            "action_input": {"path": "/tmp/test.txt"}
        }
        ```'''
        
        parser = ToolParser()
        result = parser.parse_response(response)
        
        assert result["thought"] == "I need to read a file"
        assert result["action"] == "read_file"
        assert result["action_input"]["path"] == "/tmp/test.txt"
    
    def test_parse_plain_json(self):
        """测试解析纯JSON响应"""
        response = '{"thought": "test", "action": "finish", "action_input": {"result": "done"}}'
        
        parser = ToolParser()
        result = parser.parse_response(response)
        
        assert result["action"] == "finish"
    
    def test_parse_invalid_response(self):
        """测试解析无效响应"""
        response = "This is not valid JSON"
        
        parser = ToolParser()
        with pytest.raises(ValueError):
            parser.parse_response(response)
```

### 4.2 Agent执行测试

```python
class TestFileOperationAgent:
    """测试文件操作Agent"""
    
    @pytest.fixture
    def mock_llm(self):
        """模拟LLM客户端"""
        async def mock_llm_client(prompt, messages):
            return type('Response', (), {
                'content': '{"thought": "test", "action": "finish", "action_input": {"result": "success"}}'
            })()
        return mock_llm_client
    
    async def test_agent_run_success(self, mock_llm):
        """测试Agent成功执行任务"""
        agent = FileOperationAgent(
            llm_client=mock_llm,
            max_steps=10
        )
        
        result = await agent.run("Test task")
        
        assert result.success is True
        assert result.total_steps == 1
    
    async def test_agent_max_steps(self, mock_llm):
        """测试Agent最大步数限制"""
        async def never_finish(prompt, messages):
            return type('Response', (), {
                'content': '{"thought": "continue", "action": "read_file", "action_input": {"path": "/tmp/test.txt"}}'
            })()
        
        agent = FileOperationAgent(
            llm_client=never_finish,
            max_steps=3
        )
        
        result = await agent.run("Test task")
        
        assert result.success is False
        assert result.total_steps == 3
    
    async def test_agent_rollback(self, mock_llm):
        """测试Agent回滚功能"""
        agent = FileOperationAgent(llm_client=mock_llm)
        await agent.run("Test task")
        
        agent.steps = [Step(1, "test", "action", {}, {"success": True})]
        
        success = await agent.rollback()
        assert success is True
        assert agent.status == AgentStatus.ROLLED_BACK
```

---

## 5. API端点测试

### 5.1 数据API测试

**测试文件**: `tests/test_api.py`

```python
class TestFileOperationsAPI:
    """测试文件操作API"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)
    
    def test_get_tree_data(self, client):
        """测试获取树形数据"""
        response = client.get("/api/v1/operations/tree-data?session_id=test")
        
        assert response.status_code == 200
        data = response.json()
        assert "root" in data
        assert "operations_count" in data
    
    def test_get_stats_data(self, client):
        """测试获取统计数据"""
        response = client.get("/api/v1/operations/stats-data?session_id=test")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_operations" in data
        assert "success_rate" in data
    
    def test_generate_report_txt(self, client):
        """测试生成文本报告"""
        response = client.get("/api/v1/operations/report?session_id=test&format=txt")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["format"] == "txt"
    
    def test_rollback_session(self, client):
        """测试回滚会话"""
        response = client.post("/api/v1/operations/session/test-session/rollback")
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "total_operations" in data
```

---

## 6. 测试执行计划

### 6.1 执行顺序
```
1. 单元测试（独立模块）
   ├── 安全模块测试
   ├── 工具模块测试
   ├── Agent模块测试
   └── API模块测试

2. 集成测试（模块组合）
   └── 完整工作流程测试

3. 验收测试（用户视角）
   └── 端到端场景测试
```

### 6.2 测试命令
```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/test_safety.py -v
pytest tests/test_file_tools.py -v
pytest tests/test_agent.py -v
pytest tests/test_api.py -v

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

### 6.3 测试通过标准
- [ ] 所有单元测试通过
- [ ] 代码覆盖率≥80%
- [ ] 核心模块覆盖率≥90%
- [ ] 无严重级别Bug
- [ ] 集成测试通过
