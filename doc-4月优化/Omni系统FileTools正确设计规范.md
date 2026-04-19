# Omni系统FileTools正确设计规范

**文档版本**: v1.0  
**创建时间**: 2026-04-19  
**文档类型**: 设计规范  
**适用范围**: `backend/app/services/tools/file/` 目录下所有文件  

---

## 1. 设计原则

### 1.1 参数设计原则
1. **用户参数暴露原则**: 所有需要LLM提供的参数必须在Schema中定义
2. **内部参数隐藏原则**: 工具内部控制参数不应暴露给LLM
3. **默认值一致原则**: Schema和函数签名的默认值必须完全一致
4. **类型安全原则**: 使用Pydantic Schema进行严格的类型验证

### 1.2 安全设计原则
1. **路径验证原则**: 所有用户提供的路径必须经过`_validate_path`验证
2. **权限最小原则**: 默认使用最安全的选项
3. **错误可见原则**: 错误信息应明确，不静默失败
4. **数据保护原则**: 避免数据丢失或损坏

### 1.3 性能设计原则
1. **内存友好原则**: 避免加载大量数据到内存
2. **流式处理原则**: 大文件/大目录使用流式处理
3. **提前退出原则**: 达到限制条件时及时退出
4. **资源释放原则**: 及时释放文件句柄等资源

---

## 2. 参数分类规范

### 2.1 必须暴露给LLM的参数（在Schema中定义）

| 参数类型 | 示例 | 说明 |
|----------|------|------|
| 用户输入参数 | `file_path`, `pattern`, `content` | LLM必须提供的核心参数 |
| 配置参数 | `recursive`, `max_depth`, `encoding` | 影响工具行为的可选参数 |
| 分页参数 | `page_token`, `offset` | 用于分页续取的参数 |
| 过滤参数 | `file_pattern` | 结果过滤条件 |

### 2.2 不应暴露给LLM的参数（不在Schema中）

| 参数类型 | 示例 | 说明 |
|----------|------|------|
| 内部控制参数 | `use_regex` | 由工具内部逻辑控制 |
| 会话状态参数 | `self.session_id` | 由工具实例管理 |
| 计算中间参数 | 函数内部临时变量 | 不暴露给外部 |
| 安全验证参数 | `_validate_path`结果 | 内部安全机制 |

### 2.3 参数命名规范
1. **蛇形命名**: 使用`snake_case`，如`file_path`, `max_depth`
2. **明确含义**: 名称应清晰表达参数用途
3. **一致性**: 相同概念的参数使用相同名称
4. **避免缩写**: 使用完整单词，如`directory`而非`dir`

---

## 3. 各工具正确设计规范

### 3.1 read_file
```python
# Schema定义
class ReadFileInput(BaseModel):
    file_path: str = Field(description="文件的完整路径（必须是绝对路径）")
    offset: int = Field(default=1, ge=1, description="起始行号，从1开始计数")
    limit: int = Field(default=500, ge=1, le=10000, description="最大读取行数")
    encoding: str = Field(default="utf-8", description="文件编码")

# 函数签名
async def read_file(
    self,
    file_path: str,
    offset: int = 1,
    limit: int = READ_FILE_DEFAULT_LIMIT,  # 必须与Schema一致：500
    encoding: str = "utf-8"
) -> Dict[str, Any]:
```

**设计要点**:
- `limit`默认值必须一致（Schema:500, 函数:500）
- 使用`errors='replace'`而非`'ignore'`（P11修复）

### 3.2 write_file
```python
# Schema定义
class WriteFileInput(BaseModel):
    file_path: str = Field(description="文件的完整路径")
    content: str = Field(description="要写入文件的内容")
    encoding: str = Field(default="utf-8", description="文件编码")

# 函数签名
async def write_file(
    self,
    file_path: str,
    content: str,
    encoding: str = "utf-8"
) -> Dict[str, Any]:
```

**设计要点**:
- 实现原子写入（P12修复）
- 所有参数一致

### 3.3 list_directory
```python
# Schema定义
class ListDirectoryInput(BaseModel):
    dir_path: str = Field(description="目录的完整路径")
    recursive: bool = Field(default=False, description="是否递归列出子目录")
    max_depth: int = Field(default=10, ge=1, le=50, description="最大递归深度")
    offset: int = Field(default=0, ge=0, description="起始偏移量")  # P8新增

# 函数签名
async def list_directory(
    self,
    dir_path: str,
    recursive: bool = False,
    max_depth: int = 10,  # 必须与Schema一致：10
    offset: int = 0  # P8新增
) -> Dict[str, Any]:
```

**设计要点**:
- `max_depth`默认值必须一致（Schema:10, 函数:10）
- 添加`offset`参数支持分页（P8修复）
- 实现流式遍历避免OOM

### 3.4 delete_file
```python
# Schema定义
class DeleteFileInput(BaseModel):
    file_path: str = Field(description="要删除的文件或目录的完整路径")
    recursive: bool = Field(default=False, description="是否递归删除目录")

# 函数签名
async def delete_file(
    self,
    file_path: str,
    recursive: bool = False
) -> Dict[str, Any]:
```

**设计要点**:
- 所有参数一致
- 已实现回收站机制

### 3.5 move_file
```python
# Schema定义
class MoveFileInput(BaseModel):
    source_path: str = Field(description="源文件或目录的完整路径")
    destination_path: str = Field(description="目标路径")

# 函数签名
async def move_file(
    self,
    source_path: str,
    destination_path: str
) -> Dict[str, Any]:
```

**设计要点**:
- 添加目标存在检查（P9修复）
- 所有参数一致

### 3.6 search_file_content
```python
# Schema定义
class SearchFileContentInput(BaseModel):
    pattern: str = Field(description="搜索内容的关键字")
    path: str = Field(default="~", description="搜索的起始目录，默认为用户主目录")  # P7修复
    file_pattern: str = Field(default="*", description="文件名匹配模式")
    recursive: bool = Field(default=True, description="是否递归搜索子目录")
    page_token: Optional[str] = Field(default=None, description="分页令牌")

# 函数签名
async def search_file_content(
    self,
    pattern: str,
    path: str = "~",  # P7修复
    file_pattern: str = "*",
    recursive: bool = True,
    # 内部参数，不暴露给LLM
    use_regex: bool = False,
    page_token: Optional[str] = None
) -> Dict[str, Any]:
```

**设计要点**:
- `use_regex`是内部参数，不在Schema中 ✅
- `path`默认值改为`"~"`（P7修复）
- 修复`recursive`参数逻辑（P6修复）
- 使用`fnmatch`替代手工正则（P10修复）
- 使用`errors='replace'`（P11修复）

### 3.7 search_files
```python
# Schema定义
class SearchFilesByNameInput(BaseModel):
    file_pattern: str = Field(description="文件名匹配模式")
    path: str = Field(default="~", description="搜索的起始目录，默认为用户主目录")  # P7修复
    recursive: bool = Field(default=True, description="是否递归搜索子目录")
    max_depth: int = Field(default=100000, ge=1, description="最大递归深度")
    page_token: Optional[str] = Field(default=None, description="分页令牌")

# 函数签名
async def search_files(
    self,
    file_pattern: str,
    path: str = "~",  # P7修复
    recursive: bool = True,
    max_depth: int = 100000,
    page_token: Optional[str] = None
) -> Dict[str, Any]:
```

**设计要点**:
- `path`默认值改为`"~"`（P7修复）
- 修复`recursive`参数逻辑（P15修复）
- 使用`fnmatch`替代手工正则（P10修复）
- 清理攻击性注释（P17修复）

### 3.8 generate_report
```python
# Schema定义
class GenerateReportInput(BaseModel):
    output_dir: Optional[str] = Field(default=None, description="报告输出目录")

# 函数签名
async def generate_report(
    self,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
```

**设计要点**:
- 添加路径验证（P5修复）
- 所有参数一致

---

## 4. 关键修复设计规范

### 4.1 P1/P2: 默认值不一致
```python
# 错误设计
# Schema: default=2000
# 函数: limit=READ_FILE_DEFAULT_LIMIT (500)

# 正确设计
# Schema: default=500
# 函数: limit=READ_FILE_DEFAULT_LIMIT (500)
# 或
# Schema: default=10
# 函数: max_depth=10
```

**规范**: Schema和函数的默认值必须完全一致

### 4.2 P5/P9: 安全验证
```python
# 错误设计
output_path = Path(output_dir) if output_dir else None
# 或
shutil.move(str(src), str(dst))

# 正确设计
# P5: generate_report
if output_dir:
    is_valid, error_msg = self._validate_path(output_dir)
    if not is_valid:
        return error_response

# P9: move_file
if dst.exists():
    raise FileExistsError(f"目标路径已存在: {dst}")
```

**规范**: 所有用户提供的路径必须验证，危险操作前必须检查

### 4.3 P6/P15: 递归控制
```python
# 错误设计
for root, dirs, files in os.walk(search_path):
    # 缺少递归控制

# 正确设计
for root, dirs, files in os.walk(search_path):
    if not recursive:
        dirs.clear()  # 不递归
    elif recursive and max_depth:
        rel_root = Path(root).relative_to(search_path)
        depth = len(rel_root.parts) if str(rel_root) != "." else 0
        if depth >= max_depth:
            dirs.clear()  # 达到深度限制
```

**规范**: 必须正确处理`recursive`和`max_depth`参数

### 4.4 P10: 通配符匹配
```python
# 错误设计
fp = file_pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
fp = f"^{fp}$"
if not re.match(fp, filename):
    continue

# 正确设计
import fnmatch
if not fnmatch.fnmatch(filename, file_pattern):
    continue
```

**规范**: 使用标准库`fnmatch`进行通配符匹配

### 4.5 P11: 错误处理
```python
# 错误设计
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:

# 正确设计
with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
```

**规范**: 使用`errors='replace'`让用户知道文件编码问题

### 4.6 P12: 原子写入
```python
# 错误设计
with open(path, 'w', encoding=encoding) as f:
    f.write(content)

# 正确设计
import tempfile
import os

with tempfile.NamedTemporaryFile(
    mode='w', 
    encoding=encoding,
    dir=path.parent,
    delete=False,
    prefix=f".{path.name}.tmp.",
    suffix=""
) as f:
    f.write(content)
    temp_path = f.name

try:
    os.replace(temp_path, str(path))
except Exception:
    try:
        os.unlink(temp_path)
    except:
        pass
    raise
```

**规范**: 使用临时文件+原子重命名避免数据损坏

### 4.7 P13: 路径验证
```python
# 错误设计
if str(real_path).startswith(str(allowed_real)):
    return True, None

# 正确设计（Python 3.9+）
if real_path.is_relative_to(allowed_real):
    return True, None

# 或（兼容旧版本）
try:
    common = os.path.commonpath([str(real_path), str(allowed_real)])
    if os.path.samefile(common, str(allowed_real)):
        return True, None
except (ValueError, OSError):
    pass
```

**规范**: 使用路径关系检查而非前缀匹配

### 4.8 P8: 流式分页
```python
# 错误设计（内存OOM）
all_entries = load_all_entries()  # 加载所有到内存
display_entries = all_entries[:MAX_DISPLAY_ENTRIES]

# 正确设计（流式）
def _list_sync():
    entries = []
    count = 0
    skip_count = 0
    
    for item in path.iterdir():
        if skip_count < offset:
            skip_count += 1
            continue
        
        entries.append(process_item(item))
        count += 1
        
        if count >= MAX_DISPLAY_ENTRIES:
            break
    
    return entries, count, skip_count
```

**规范**: 大目录使用流式遍历，避免内存溢出

---

## 5. 代码质量规范

### 5.1 注释规范
```python
# 错误示例（攻击性语言）
# 小沈是一个大混蛋，几次纠正都死不悔改

# 正确示例（专业描述）
# 修改原因：取消深度限制，确保返回完整搜索结果
# 之前的限制会导致数据丢失，影响工具功能完整性
```

### 5.2 异常处理规范
```python
# 错误示例
except:
    continue

# 正确示例
except (PermissionError, OSError):
    continue
```

### 5.3 函数设计规范
1. **单一职责**: 每个函数只做一件事
2. **参数验证**: 在函数开头验证所有参数
3. **错误处理**: 明确处理各种错误情况
4. **资源管理**: 使用`with`语句管理资源

### 5.4 测试规范
1. **单元测试**: 每个修复都要有对应的单元测试
2. **边界测试**: 测试各种边界情况
3. **性能测试**: 测试大文件/大目录场景
4. **安全测试**: 测试路径绕过等安全漏洞

---

## 6. 实施检查清单

### 6.1 修复前检查
- [ ] 理解问题根本原因
- [ ] 评估影响范围
- [ ] 设计修复方案
- [ ] 编写测试用例

### 6.2 修复中检查
- [ ] 修改Schema（如需要）
- [ ] 修改函数实现
- [ ] 保持向后兼容
- [ ] 更新文档

### 6.3 修复后检查
- [ ] 通过所有单元测试
- [ ] 通过集成测试
- [ ] 验证参数一致性
- [ ] 更新API文档

### 6.4 参数一致性检查表
| 检查项 | read_file | write_file | list_directory | delete_file | move_file | search_file_content | search_files | generate_report |
|--------|-----------|------------|----------------|-------------|-----------|---------------------|--------------|-----------------|
| Schema参数数量 = 函数参数数量 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️(差use_regex) | ✅ | ✅ |
| 参数名称一致 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 参数类型一致 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 默认值一致 | ❌(P1) | ✅ | ❌(P2) | ✅ | ✅ | ✅ | ✅ | ✅ |
| 内部参数不暴露 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 7. 总结

### 7.1 设计正确性确认
1. **参数分类正确**: 用户参数和内部参数分离明确
2. **架构设计合理**: 使用Pydantic Schema进行参数验证
3. **分页机制统一**: 使用`page_token`实现统一分页
4. **错误处理基本合理**: 大部分错误都有处理

### 7.2 需要修复的问题
1. **安全漏洞**: P5,P9,P13
2. **功能错误**: P3,P4,P6,P10,P11,P15
3. **设计不一致**: P1,P2,P7
4. **代码质量**: P12,P14,P16,P17

### 7.3 实施建议
1. **按优先级修复**: 先安全漏洞，再功能错误，最后代码质量
2. **充分测试**: 每个修复都要有对应的测试
3. **保持兼容**: 尽量保持API向后兼容
4. **更新文档**: 修复后更新所有相关文档

**最终目标**: 通过修复这些问题，使FileTools成为安全、可靠、易用的文件操作工具集。