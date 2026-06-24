# Tool参数组合与内容测试规范

## 核心原则

**测试必须验证实际结果，不能只检查文件创建！**

---

## 一、参数组合测试规范

### 1.1 参数组合矩阵

**原则**：穷举所有参数组合情况

**方法**：
- 必填参数 + 可选参数的所有组合
- 每个组合一个测试case
- 使用pytest.mark.parametrize减少重复代码

**示例**：

```python
# 参数：file_name(必填), title(可选), content(可选), table_data(可选)

class TestParamCombinations:
    """参数组合测试"""
    
    def test_file_name_only(self, tmp_path):
        """组合1: 仅必填参数"""
        result = write_docx(str(tmp_path / "test.docx"))
        assert is_success(result)
    
    def test_with_title(self, tmp_path):
        """组合2: 必填 + title"""
        result = write_docx(str(tmp_path / "test.docx"), title="标题")
        assert is_success(result)
    
    def test_with_content(self, tmp_path):
        """组合3: 必填 + content"""
        result = write_docx(str(tmp_path / "test.docx"), content="内容")
        assert is_success(result)
    
    def test_with_all_params(self, tmp_path):
        """组合4: 所有参数"""
        result = write_docx(
            str(tmp_path / "test.docx"),
            title="标题",
            content="内容",
            table_data=[["A", "B"]]
        )
        assert is_success(result)
```

### 1.2 互斥参数测试

**原则**：明确互斥关系，验证优先级

**示例**：

```python
def test_content_table_data_mutex(self, tmp_path):
    """互斥关系：content优先，table_data被忽略"""
    result = write_docx(
        str(tmp_path / "test.docx"),
        content="# 有content",
        table_data=[["A", "B"]]  # 应该被忽略
    )
    
    assert is_success(result)
    
    doc = Document(str(tmp_path / "test.docx"))
    assert len(doc.tables) == 0, "table_data应该被忽略"
    assert len(doc.paragraphs) > 0, "content应该生效"
```

---

## 二、参数内容丰富性测试规范

### 2.1 内容丰富性原则

**核心要求**：
1. **每个功能点必须有测试** - 标题、段落、列表、表格等
2. **内容必须真实** - 不用"test"、"aaa"等无意义数据
3. **必须验证实际效果** - 读取文件验证内容、样式、数量

### 2.2 内容测试分类

#### A. 单一功能测试

**原则**：一个case只测试一个功能

```python
class TestMarkdownHeadings:
    """标题功能测试"""
    
    @pytest.mark.parametrize("level,prefix", [
        (1, "# "), (2, "## "), (3, "### "), (4, "#### "), (5, "##### ")
    ])
    def test_heading_level(self, tmp_path, level, prefix):
        """测试单个标题级别"""
        file_path = tmp_path / f"heading_{level}.docx"
        content = f"{prefix}标题内容"
        
        result = write_docx(str(file_path), content=content)
        assert is_success(result)
        
        # ✅ 必须验证实际效果
        doc = Document(str(file_path))
        assert doc.paragraphs[0].style.name == f'Heading {level}'
        assert doc.paragraphs[0].text == "标题内容"
```

#### B. 混合内容测试

**原则**：测试真实场景，多种内容混合

```python
def test_mixed_content(self, tmp_path):
    """混合内容：标题+段落+列表+表格"""
    content = """# 报告标题

介绍段落。

## 数据表格

| 项目 | 数值 |
|------|------|
| A | 100 |

## 分析要点

- 要点1
- 要点2

## 步骤

1. 第一步
2. 第二步"""
    
    result = write_docx(str(tmp_path / "test.docx"), content=content)
    assert is_success(result)
    
    # ✅ 验证所有内容都正确生成
    doc = Document(str(tmp_path / "test.docx"))
    
    # 验证标题
    headings = [p for p in doc.paragraphs if 'Heading' in p.style.name]
    assert len(headings) >= 4, "应该有4个标题"
    
    # 验证列表
    bullets = [p for p in doc.paragraphs if p.style.name == 'List Bullet']
    assert len(bullets) == 2, "应该有2个无序列表项"
    
    numbers = [p for p in doc.paragraphs if p.style.name == 'List Number']
    assert len(numbers) == 2, "应该有2个有序列表项"
    
    # 验证表格
    assert len(doc.tables) == 1, "应该有1个表格"
    assert len(doc.tables[0].rows) == 2, "表格应该有2行"
```

#### C. 真实场景测试

**原则**：使用真实业务场景数据

```python
class TestRealScenarios:
    """真实场景测试"""
    
    def test_tech_report(self, tmp_path):
        """场景1: 技术报告"""
        content = """# 代码审查报告

## 审查概览

本次审查覆盖3个模块，发现12个问题。

## 问题清单

### 严重问题

1. SQL注入风险 - user_service.py:45
2. 硬编码密钥 - config.py:12

### 一般问题

- 缺少错误处理
- 日志级别不当
- 未使用类型注解

## 统计数据

| 指标 | 数值 |
|------|------|
| 总文件数 | 156 |
| 问题文件 | 23 |
| 覆盖率 | 67% |"""
        
        result = write_docx(str(tmp_path / "tech_report.docx"), content=content)
        assert is_success(result)
        
        # 验证报告结构完整
        doc = Document(str(tmp_path / "tech_report.docx"))
        assert len([p for p in doc.paragraphs if 'Heading' in p.style.name]) >= 5
        assert len(doc.tables) == 1
    
    def test_meeting_minutes(self, tmp_path):
        """场景2: 会议纪要"""
        content = """# 项目周会纪要

## 会议信息

- 时间：2026-06-24 14:00
- 地点：会议室A
- 参会人：张三、李四、王五

## 议题讨论

### 进度汇报

1. 前端开发完成80%
2. 后端API已上线
3. 测试覆盖率达75%

## 行动项

- 张三：完成前端剩余功能
- 李四：性能测试报告"""
        
        result = write_docx(str(tmp_path / "meeting.docx"), content=content)
        assert is_success(result)
```

### 2.3 边界内容测试

**原则**：覆盖极端情况

```python
class TestBoundary:
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
        content = "\n".join([f"第{i}行：测试内容" for i in range(100)])
        result = write_docx(str(tmp_path / "test.docx"), content=content)
        assert is_success(result)
        
        doc = Document(str(tmp_path / "test.docx"))
        assert len(doc.paragraphs) >= 100
```

---

## 三、内容验证规范

### 3.1 必须验证的项目

| 验证项 | 方法 | 示例 |
|--------|------|------|
| 文件创建 | `file_path.exists()` | ✅ |
| 文件大小 | `file_path.stat().st_size > 0` | ✅ |
| 内容数量 | `len(doc.paragraphs)` | ✅ |
| 样式正确 | `para.style.name == 'Heading 1'` | ✅ |
| 内容正确 | `para.text == "期望内容"` | ✅ |
| 表格正确 | `len(doc.tables)`, `table.rows[0].cells[0].text` | ✅ |

### 3.2 验证示例对比

**❌ 错误示例（只检查文件创建）**：

```python
def test_write_docx(self, tmp_path):
    result = write_docx(str(tmp_path / "test.docx"), content="测试")
    assert is_success(result)
    assert file_path.exists()  # ❌ 只验证文件存在，不验证内容
```

**✅ 正确示例（验证实际内容）**：

```python
def test_write_docx(self, tmp_path):
    result = write_docx(str(tmp_path / "test.docx"), content="# 标题\n\n段落")
    assert is_success(result)
    assert file_path.exists()
    
    # ✅ 读取文件验证内容
    doc = Document(str(tmp_path / "test.docx"))
    assert len(doc.paragraphs) == 2, "应该有2个段落"
    assert doc.paragraphs[0].style.name == 'Heading 1', "第一个应该是标题"
    assert doc.paragraphs[0].text == "标题", "标题内容应该是'标题'"
```

---

## 四、测试数据设计规范

### 4.1 数据来源

**优先级**：
1. **register.py的Examples** - 工具注册时的示例
2. **真实业务场景** - 技术报告、会议纪要等
3. **边界数据** - 特殊字符、长内容等

### 4.2 数据要求

**必须**：
- ✅ 内容真实有意义
- ✅ 覆盖所有功能点
- ✅ 包含各种边界情况

**禁止**：
- ❌ 无意义的"test"、"aaa"
- ❌ 过于简单的示例
- ❌ 遗漏功能点

### 4.3 测试数据组织

**推荐使用conftest.py集中管理**：

```python
# conftest.py

@pytest.fixture
def docx_test_data():
    """测试数据集"""
    return {
        "simple": {
            "title": "简单文档",
            "content": "简单内容",
            "desc": "基础测试"
        },
        "tech_report": {
            "title": "技术报告",
            "content": """# 审查概览
...""",
            "desc": "真实场景"
        },
        "special_chars": {
            "content": "特殊字符：<>&\"'",
            "desc": "边界测试"
        }
    }
```

---

## 五、测试组织结构

### 5.1 测试类组织

```python
# test_write_docx.py

class TestParamCombinations:
    """参数组合测试（4-8个case）"""
    pass

class TestSingleFeatures:
    """单一功能测试（每个功能1-2个case）"""
    pass

class TestMixedContent:
    """混合内容测试（2-3个case）"""
    pass

class TestRealScenarios:
    """真实场景测试（2-4个case）"""
    pass

class TestBoundary:
    """边界测试（4-6个case）"""
    pass

class TestNegative:
    """负面测试（错误处理，2-3个case）"""
    pass
```

### 5.2 测试数量参考

| 工具复杂度 | 测试数量 | 说明 |
|-----------|---------|------|
| 简单工具 | 15-20个 | 单一功能，参数少 |
| 中等工具 | 25-35个 | 多功能，参数中等 |
| 复杂工具 | 35-50个 | 多功能，参数多，互斥关系 |

---

## 六、检查清单

### 测试编写前

- [ ] 分析工具参数组合矩阵
- [ ] 识别互斥/依赖关系
- [ ] 收集真实业务场景数据
- [ ] 确定边界测试数据

### 测试编写时

- [ ] 每个case验证实际内容
- [ ] 使用真实有意义的测试数据
- [ ] 覆盖所有功能点
- [ ] 验证样式、数量、内容

### 测试完成后

- [ ] 所有测试通过
- [ ] 覆盖率达标（核心功能100%）
- [ ] 测试数据来自register.py的Examples
- [ ] 真实场景测试完整

---

## 七、常见错误

### ❌ 错误1：只检查文件创建

```python
assert is_success(result)
assert file_path.exists()  # ❌ 不够
```

### ✅ 正确：验证实际内容

```python
assert is_success(result)
assert file_path.exists()
doc = Document(str(file_path))
assert len(doc.paragraphs) > 0  # ✅ 验证内容
```

---

### ❌ 错误2：使用无意义数据

```python
content = "test"  # ❌ 无意义
```

### ✅ 正确：使用真实数据

```python
content = "# 代码审查报告\n\n## 问题清单\n\n1. SQL注入风险"  # ✅ 真实场景
```

---

### ❌ 错误3：遗漏功能点

```python
# 只测试了标题，没测试列表和表格
```

### ✅ 正确：覆盖所有功能

```python
# 标题测试、列表测试、表格测试都要有
```

---

创建时间：2026-06-24  
作者：小健  
用途：Tool参数组合与内容测试规范