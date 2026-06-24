# Tool参数组合与内容测试规范

---

## 测试架构目录

```
backend/tests/tools/param_combination/
├── __init__.py                    # 包初始化
├── conftest.py                    # pytest fixtures + 测试数据集
├── test_write_docx.py             # write_docx参数组合测试 (35个case)
├── test_write_pdf.py              # write_pdf参数组合测试 (24个case)
├── README.md                      # 测试目录说明文档
└── ...                            # 其他工具测试文件
```

**目录说明**：
- `conftest.py` - 定义共享fixtures（temp_output_dir、测试数据集）
- `test_xxx.py` - 每个工具一个测试文件
- `README.md` - 测试目录结构和使用说明

---

## 测试操作流程

### 1. 编写测试前

**步骤**：
1. 分析工具参数（必填、可选、互斥关系）
2. 识别所有功能点（标题、列表、表格等）
3. 收集测试数据：
   - 从 `xxx_register.py` 的 `EXAMPLES` 提取
   - 准备真实业务场景数据
   - 准备边界测试数据

### 2. 编写测试

**步骤**：
1. 创建测试文件 `test_xxx.py`
2. 在 `conftest.py` 添加测试数据fixture（可选）
3. 按规范编写测试类：
   - TestParamCombinations - 参数组合测试
   - TestSingleFeatures - 单一功能测试
   - TestMixedContent - 混合内容测试
   - TestRealScenarios - 真实场景测试
   - TestBoundary - 边界测试
   - TestNegative - 负面测试
4. 每个测试case必须验证实际结果

### 3. 运行测试

**命令**：

```bash
# 运行单个工具测试
pytest tests/tools/param_combination/test_write_docx.py -v

# 运行特定测试类
pytest tests/tools/param_combination/test_write_docx.py::TestWriteDocxTables -v

# 运行特定测试case
pytest tests/tools/param_combination/test_write_docx.py::TestWriteDocxTables::test_markdown_table_basic -v

# 运行所有参数组合测试
pytest tests/tools/param_combination/ -v

# 带详细错误信息
pytest tests/tools/param_combination/test_write_docx.py -v --tb=short

# 仅显示失败信息
pytest tests/tools/param_combination/test_write_docx.py -v --tb=line
```

### 4. 验证测试

**检查项**：
- [ ] 所有测试通过
- [ ] 测试覆盖所有功能点
- [ ] 测试数据来自真实场景
- [ ] 每个case验证了实际结果（不只是文件创建）

### 5. 完整流程示例

**以write_docx为例**：

```bash
# 1. 进入backend目录
cd backend

# 2. 运行测试
pytest tests/tools/param_combination/test_write_docx.py -v

# 3. 查看结果
# ============================= 35 passed in 7.16s ==============================

# 4. 如果失败，查看详细错误
pytest tests/tools/param_combination/test_write_docx.py -v --tb=short

# 5. 调试单个case
pytest tests/tools/param_combination/test_write_docx.py::TestWriteDocxTables::test_markdown_table_basic -v -s
```

---

## 核心原则

**测试必须验证实际结果，不能只检查文件创建！**

---

---

## write_docx测试举例说明

### 一、参数组合测试

**测试文件**：`test_write_docx.py`

```python
class TestWriteDocxBasicParams:
    """参数组合测试 - 4个基础组合"""
    
    def test_empty_document(self, tmp_path):
        """组合1: 仅必填参数"""
        result = write_docx(str(tmp_path / "empty.docx"))
        assert is_success(result)
    
    def test_title_only(self, tmp_path):
        """组合2: 必填 + title"""
        result = write_docx(str(tmp_path / "test.docx"), title="标题")
        assert is_success(result)
        # ✅ 验证内容
        doc = Document(str(tmp_path / "test.docx"))
        assert doc.paragraphs[0].text == "标题"
    
    def test_content_only(self, tmp_path):
        """组合3: 必填 + content"""
        result = write_docx(str(tmp_path / "test.docx"), content="内容")
        assert is_success(result)
    
    def test_all_params(self, tmp_path):
        """组合4: 所有参数"""
        result = write_docx(str(tmp_path / "test.docx"), title="标题", content="内容")
        assert is_success(result)
```

### 二、互斥参数测试

```python
class TestWriteDocxTables:
    """互斥关系测试"""
    
    def test_content_table_data_mutex(self, tmp_path):
        """content和table_data互斥，content优先"""
        result = write_docx(
            str(tmp_path / "test.docx"),
            content="# 有content",
            table_data=[["A", "B"]]  # 被忽略
        )
        assert is_success(result)
        doc = Document(str(tmp_path / "test.docx"))
        assert len(doc.tables) == 0  # table_data被忽略
        assert len(doc.paragraphs) > 0  # content生效
```

### 三、单一功能测试

```python
class TestWriteDocxMarkdownHeadings:
    """标题功能测试 - parametrize减少重复"""
    
    @pytest.mark.parametrize("level,prefix", [
        (1, "# "), (2, "## "), (3, "### "), (4, "#### "), (5, "##### ")
    ])
    def test_heading_level(self, tmp_path, level, prefix):
        """测试单个标题级别"""
        result = write_docx(str(tmp_path / "test.docx"), content=f"{prefix}标题")
        assert is_success(result)
        # ✅ 验证样式
        doc = Document(str(tmp_path / "test.docx"))
        assert doc.paragraphs[0].style.name == f'Heading {level}'
```

### 四、混合内容测试

```python
class TestWriteDocxMarkdownLists:
    """列表功能测试"""
    
    def test_mixed_lists(self, tmp_path):
        """混合列表：无序+有序"""
        content = """无序列表：
- 项目A
- 项目B

有序列表：
1. 步骤1
2. 步骤2"""
        result = write_docx(str(tmp_path / "test.docx"), content=content)
        assert is_success(result)
        # ✅ 验证列表数量
        doc = Document(str(tmp_path / "test.docx"))
        bullets = [p for p in doc.paragraphs if p.style.name == 'List Bullet']
        numbers = [p for p in doc.paragraphs if p.style.name == 'List Number']
        assert len(bullets) == 2
        assert len(numbers) == 2
```

### 五、表格功能测试

```python
class TestWriteDocxTables:
    """表格功能测试"""
    
    def test_markdown_table(self, tmp_path):
        """Markdown表格"""
        content = """| 项目 | 数值 |
|------|------|
| A | 100 |
| B | 200 |"""
        result = write_docx(str(tmp_path / "test.docx"), content=content)
        assert is_success(result)
        # ✅ 验证表格
        doc = Document(str(tmp_path / "test.docx"))
        assert len(doc.tables) == 1
        assert len(doc.tables[0].rows) == 3  # 表头+2行数据
    
    def test_table_data_parameter(self, tmp_path):
        """table_data参数"""
        table_data = [["姓名", "年龄"], ["张三", "25"], ["李四", "30"]]
        result = write_docx(str(tmp_path / "test.docx"), table_data=table_data)
        assert is_success(result)
        doc = Document(str(tmp_path / "test.docx"))
        assert len(doc.tables[0].rows) == 3
```

### 六、真实场景测试

```python
class TestWriteDocxRealScenarios:
    """真实业务场景"""
    
    def test_tech_report(self, tmp_path):
        """技术报告"""
        content = """# 代码审查报告

## 问题清单

### 严重问题

1. SQL注入风险
2. 硬编码密钥

### 一般问题

- 缺少错误处理
- 日志级别不当

## 统计数据

| 指标 | 数值 |
|------|------|
| 总文件数 | 156 |
| 问题文件 | 23 |"""
        result = write_docx(str(tmp_path / "tech_report.docx"), content=content)
        assert is_success(result)
        # ✅ 验证报告结构
        doc = Document(str(tmp_path / "tech_report.docx"))
        assert len([p for p in doc.paragraphs if 'Heading' in p.style.name]) >= 5
        assert len(doc.tables) == 1
```

### 七、边界测试

```python
class TestWriteDocxBoundary:
    """边界测试"""
    
    def test_special_chars(self, tmp_path):
        """特殊字符"""
        content = "特殊字符：<>&\"' 中文：测试 emoji：😀🎉"
        result = write_docx(str(tmp_path / "test.docx"), content=content)
        assert is_success(result)
        doc = Document(str(tmp_path / "test.docx"))
        assert "特殊字符" in doc.paragraphs[0].text
    
    def test_long_content(self, tmp_path):
        """长内容（100行）"""
        content = "\n".join([f"第{i}行内容" for i in range(100)])
        result = write_docx(str(tmp_path / "test.docx"), content=content)
        assert is_success(result)
        doc = Document(str(tmp_path / "test.docx"))
        assert len(doc.paragraphs) >= 100
```

### 八、负面测试

```python
class TestWriteDocxNegative:
    """错误处理"""
    
    def test_invalid_path(self):
        """无效路径"""
        result = write_docx("Z:/invalid/path.docx")
        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"
```

---

## 测试验证要点

### ✅ 必须验证

| 验证项 | 方法 | 说明 |
|--------|------|------|
| 文件创建 | `file_path.exists()` | 文件存在 |
| 内容数量 | `len(doc.paragraphs)` | 段落数正确 |
| 样式正确 | `para.style.name == 'Heading 1'` | 样式应用正确 |
| 内容正确 | `para.text == "期望内容"` | 内容完整 |
| 表格正确 | `len(doc.tables)`, `table.rows[i].cells[j].text` | 表格数据正确 |

### ❌ 常见错误

**错误1**：只检查文件创建
```python
assert is_success(result)
assert file_path.exists()  # ❌ 不够
```

**正确**：验证实际内容
```python
assert is_success(result)
doc = Document(str(file_path))
assert len(doc.paragraphs) > 0  # ✅ 验证内容
```

**错误2**：使用无意义数据
```python
content = "test"  # ❌ 无意义
```

**正确**：使用真实数据
```python
content = "# 代码审查报告\n\n## 问题清单\n\n1. SQL注入风险"  # ✅ 真实场景
```

---

## 测试数量参考

| 测试类型 | 数量 | 说明 |
|---------|------|------|
| 参数组合 | 4-8个 | 穷举所有组合 |
| 单一功能 | 10-15个 | 每个功能1-2个 |
| 混合内容 | 2-3个 | 多功能组合 |
| 真实场景 | 2-4个 | 业务场景 |
| 边界测试 | 4-6个 | 极端情况 |
| 负面测试 | 2-3个 | 错误处理 |
| **总计** | **25-40个** | |

---

创建时间：2026-06-24  
作者：小健  
用途：Tool参数组合与内容测试规范