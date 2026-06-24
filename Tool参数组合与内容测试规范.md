# Tool参数组合与内容测试规范

**版本记录**
| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-24 | 初始创建 | 小健 |
| v1.1 | 2026-06-24 20:47:28 | 添加完整章节编号 | 小欧 |

---

## 一、核心原则与要求
***没有发现问题的测试都是狗屁测试**--必须发现问题才是有效测试*

### 1.1 必须遵守的铁规

**1.1.1 Schema驱动原则**
- ✅ 必须按照tool的schema参数要求进行分析和设计测试用例
- ✅ 测试用例必须覆盖schema中所有参数的所有组合
- ✅ 互斥参数必须验证互斥关系和优先级

**1.1.2 内容丰富性原则**
- ✅ 内容字段（如content、data等）的信息必须丰富，不能少于100行
- ✅ 测试数据必须来自真实业务场景，禁止使用"test"、"aaa"等无意义数据
- ✅ 必须覆盖所有功能点（标题、列表、表格、特殊字符等）

**1.1.3 验证完整性原则**
- ✅ 测试必须验证实际结果，不能只检查文件创建
- ✅ 必须验证：文件创建、内容数量、样式正确、内容正确、表格正确
- ✅ 每个测试case必须读取生成的文件并验证实际内容

**1.1.4 测试覆盖原则**
- ✅ 参数组合测试：穷举所有参数组合
- ✅ 功能测试：每个功能点至少1个测试case
- ✅ 边界测试：特殊字符、长内容、空值等
- ✅ 负面测试：错误路径、权限问题等

**1.1.5 真实性原则**
- ✅ 测试数据优先从 `xxx_register.py` 的 `EXAMPLES` 提取
- ✅ 真实场景测试必须使用真实业务数据（技术报告、会议纪要等）
- ✅ 边界测试必须覆盖极端情况

**1.1.6 问题发现原则**
- ✅ 测试的目的不是为了通过测试，而是必须发现tool功能代码问题
- ✅ 测试必须暴露代码bug、逻辑错误、边界处理缺陷
- ✅ 测试失败时要深入分析根本原因，不是简单修复测试

**1.1.7 Schema验证原则**
- ✅ 必须发现参数的设置说明问题（description不够清晰、examples不够丰富）
- ✅ 测试要验证LLM能否根据Schema正确调用工具
- ✅ 发现Schema描述缺失、误导、不完整的问题

---

### 1.2 禁止的行为

❌ **禁止1**：只检查文件创建，不验证内容
```python
assert is_success(result)
assert file_path.exists()  # ❌ 不够
```

❌ **禁止2**：使用无意义测试数据
```python
content = "test"  # ❌ 无意义
content = "aaa"   # ❌ 无意义
```

❌ **禁止3**：内容字段少于100行
```python
content = "简单内容"  # ❌ 太少，必须不少于100行
```

❌ **禁止4**：遗漏功能点
```python
# 只测试标题，没测试列表和表格  # ❌ 功能点遗漏
```

❌ **禁止5**：不按Schema设计测试
```python
# Schema有4个参数，测试只覆盖2个参数组合  # ❌ 组合不全
```

❌ **禁止6**：为了通过测试而测试
```python
# 测试失败后，不分析原因直接修改测试让它通过  # ❌ 掩盖代码问题
# 测试通过就认为没问题，不深入验证  # ❌ 没有发现问题
```

❌ **禁止7**：忽视Schema问题
```python
# Schema描述不清楚，测试发现了但没报告  # ❌ 放过Schema问题
# Examples不够丰富，测试没验证LLM能否正确调用  # ❌ Schema验证缺失
```

---

## 二、测试架构目录

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

## 三、测试操作流程

### 3.1 编写测试前

**步骤**：
1. 分析工具参数（必填、可选、互斥关系）
2. 识别所有功能点（标题、列表、表格等）
3. 收集测试数据：
   - 从 `xxx_register.py` 的 `EXAMPLES` 提取
   - 准备真实业务场景数据
   - 准备边界测试数据

### 3.2 编写测试

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

### 3.3 运行测试

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

### 3.4 验证测试

**检查项**：
- [ ] 所有测试通过
- [ ] 测试覆盖所有功能点
- [ ] 测试数据来自真实场景
- [ ] 每个case验证了实际结果（不只是文件创建）

### 3.5 完整流程示例

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

## 四、write_docx测试举例说明

### 4.1 参数组合测试

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

### 4.2 互斥参数测试

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

### 4.3 单一功能测试

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

### 4.4 混合内容测试

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

### 4.5 表格功能测试

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

### 4.6 真实场景测试

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

### 4.7 边界测试

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

### 4.8 负面测试

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

## 五、测试数量参考

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

**创建时间**: 2026-06-24  
**版本**: v1.1  
**作者**: 小健、小欧  
**用途**: Tool参数组合与内容测试规范