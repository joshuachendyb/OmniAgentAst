# 新增 File 工具设计和实施说明

**创建时间**: 2026-04-19 16:37:18
**版本**: v1.1
**更新人**: 小沈
**更新说明**: 修复小健审查发现的问题
**更新内容**:
- copy_file: 修正 operation_id 异常处理（第239行）
- get_file_info: 修正多次 is_dir() 调用（第551、575、588行）
- batch_rename: 修正重命名逻辑（第1265-1292行）
- compress_files: 修正 make_archive 参数（第1085-1097行）
**依据**: file_tools.py (v0.9.8.9) 和 file_schema.py 设计模式

---

## 一、设计依据和现有模式分析

### 1.1 现有工具模式总结

通过分析现有代码 (file_tools.py 1545行, file_schema.py 185行)，总结出以下设计模式：

| 模式要素 | 现有实现 | 说明 |
|---------|---------|------|
| **参数 Schema** | Pydantic BaseModel | 在 file_schema.py 中定义 |
| **工具注册** | @register_tool 装饰器 | 自动生成 JSON Schema |
| **路径验证** | _validate_path() | 白名单检查 + 前缀匹配防绕过 |
| **执行方式** | asyncio.to_thread() | 异步执行同步 IO 操作 |
| **返回格式** | _to_unified_format() | {status, summary, data, retry_count} |
| **安全机制** | safety.record_operation() | 操作记录，支持回滚 |
| **input_examples** | 在装饰器中定义 | 提供调用示例 |

### 1.2 统一返回格式

```python
{
    "status": "success",  # 或 "error"
    "summary": "人类可读摘要",
    "data": {
        "success": True/False,
        ...  # 工具特定返回字段
    },
    "retry_count": 0
}
```

---

## 二、copy_file - 文件复制功能（完整设计）

### 2.1.1 Schema 定义（插入到 file_schema.py）

```python
class CopyFileInput(BaseModel):
    """copy_file 工具的输入参数"""
    source_path: str = Field(
        description="源文件或目录的完整路径（必须是绝对路径，如 C:/Users/用户名/Documents/file.txt）"
    )
    destination_path: str = Field(
        description="目标路径（必须是绝对路径，如 D:/备份/file.txt）"
    )
    overwrite: bool = Field(
        default=False,
        description="如果目标文件已存在，是否覆盖，默认为False"
    )
```

### 2.1.2 工具实现（插入到 file_tools.py）

在 file_schema.py 导入部分添加：
```python
from app.services.tools.file.file_schema import (
    # ... 现有导入 ...
    CopyFileInput,
)
```

在 file_tools.py 中添加（放在 copy_file 方法位置）：

```python
    @register_tool(
        name="copy_file",
        description="""复制文件或目录到目标位置。

使用场景：
- 当用户想要复制文件到另一个位置时使用此工具
- 当用户想要备份文件时使用
- 当需要在不同位置创建文件副本时使用

参数说明：
- source_path: 源文件或目录的完整路径（必须是绝对路径）
- destination_path: 目标路径（必须是绝对路径）
- overwrite: 如果目标文件已存在，是否覆盖，默认为False

【重要】必须使用 source_path 和 destination_path 作为参数名，不要使用 src、dst、source、destination 等名称。
错误示例: {"src": "...", "dst": "..."}
正确示例: {"source_path": "C:/Users/用户名/Documents/file.txt", "destination_path": "D:/备份/file.txt"}

【注意】如果目标文件已存在且 overwrite=False，操作会失败。
【注意】此操作会保留文件的创建时间和修改时间。如需保留权限请使用 copy2。""",
        input_model=CopyFileInput,
        examples=[
            {
                "source_path": "C:/Users/用户名/Documents/file.txt",
                "destination_path": "D:/备份/file.txt",
                "overwrite": False
            },
            {
                "source_path": "C:/Users/用户名/Documents/folder",
                "destination_path": "D:/备份/folder",
                "overwrite": True
            },
            {
                "source_path": "D:/项目代码/src/main.py",
                "destination_path": "D:/项目代码_backup/src/main.py",
                "overwrite": True
            }
        ]
    )
    async def copy_file(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """复制文件或目录到目标位置"""
        # ===================== 1. 验证源路径 =====================
        is_valid_src, error_msg_src = self._validate_path(source_path)
        if not is_valid_src:
            return _to_unified_format({
                "success": False,
                "error": f"源路径{error_msg_src}",
                "operation_id": None
            }, "copy_file")
        
        # ===================== 2. 验证目标路径 =====================
        is_valid_dst, error_msg_dst = self._validate_path(destination_path)
        if not is_valid_dst:
            return _to_unified_format({
                "success": False,
                "error": f"目标路径{error_msg_dst}",
                "operation_id": None
            }, "copy_file")
        
        # ===================== 3. 检查会话ID =====================
        if not self.session_id:
            return _to_unified_format({
                "success": False,
                "error": "No active session",
                "operation_id": None
            }, "copy_file")
        
        src = Path(source_path)
        dst = Path(destination_path)
        
        try:
            # ===================== 4. 检查源文件是否存在 =====================
            if not src.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"Source not found: {source_path}",
                    "operation_id": None
                }, "copy_file")
            
            # ===================== 5. 记录操作（安全机制）====================
            operation_id = self.safety.record_operation(
                session_id=self.session_id,
                operation_type=OperationType.CREATE,  # 复制是创建操作
                source_path=src,
                destination_path=dst,
                sequence_number=self._get_next_sequence()
            )
            
            # ===================== 6. 定义复制操作 =====================
            def _copy_sync():
                # 6.1 检查目标是否已存在
                if dst.exists():
                    if not overwrite:
                        raise FileExistsError(
                            f"目标路径已存在: {dst}，请设置 overwrite=True 覆盖或使用其他目标路径。"
                        )
                    # 6.2 删除已存在的目标
                    if dst.is_dir():
                        shutil.rmtree(dst)
                    else:
                        dst.unlink()
                
                # 6.3 创建目标父目录
                dst.parent.mkdir(parents=True, exist_ok=True)
                
                # 6.4 执行复制
                if src.is_dir():
                    # 目录复制使用 copytree
                    shutil.copytree(src, dst)
                else:
                    # 文件复制使用 copy2（保留元数据）
                    shutil.copy2(src, dst)
                
                return True
            
            # ===================== 7. 执行复制（异步）====================
            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_copy_sync
            )
            
            # ===================== 8. 返回结果 =====================
            if success:
                # 计算复制的文件/目录数量
                if dst.is_dir():
                    file_count = sum(1 for _ in dst.rglob('*') if _.is_file())
                    dir_count = sum(1 for _ in dst.rglob('*') if _.is_dir())
                    total_size = sum(
                        f.stat().st_size for f in dst.rglob('*') 
                        if f.is_file() and f.exists()
                    )
                else:
                    file_count = 1
                    dir_count = 0
                    total_size = dst.stat().st_size if dst.exists() else 0
                
                return _to_unified_format({
                    "success": True,
                    "operation_id": operation_id,
                    "source": str(src),
                    "destination": str(dst),
                    "copied_type": "directory" if src.is_dir() else "file",
                    "file_count": file_count,
                    "dir_count": dir_count,
                    "total_bytes": total_size,
                    "message": f"成功复制: {src.name} -> {dst}"
                }, "copy_file")
            else:
                return _to_unified_format({
                    "success": False,
                    "error": "Failed to copy file",
                    "operation_id": operation_id
                }, "copy_file")
        
        except FileExistsError as e:
            logger.warning(f"Copy target exists: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "operation_id": operation_id
            }, "copy_file")
        
        except Exception as e:
            logger.error(f"Failed to copy {source_path} -> {destination_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "operation_id": None
            }, "copy_file")
```

### 2.1.3 _generate_summary 补充

在 file_tools.py 的 `_generate_summary` 函数中添加：

```python
    elif tool_name == "copy_file":
        if result.get("success") is False:
            return f"复制失败：{result.get('error', '未知错误')}"
        source = result.get("source", "")
        destination = result.get("destination", "")
        file_count = result.get("file_count", 0)
        return f"成功复制 {file_count} 个项目：{source} -> {destination}"
```

---

## 三、create_directory - 目录创建功能（完整设计）

### 2.2.1 Schema 定义（插入到 file_schema.py）

```python
class CreateDirectoryInput(BaseModel):
    """create_directory 工具的输入参数"""
    dir_path: str = Field(
        description="要创建的目录完整路径（必须是绝对路径，如 C:/Users/用户名/Documents/new_folder）"
    )
    parents: bool = Field(
        default=True,
        description="是否创建父目录，默认为True（即自动创建所需的父目录，如 C:/A/B 而 C:/A 不存在，会自动创建 C:/A）"
    )
    exist_ok: bool = Field(
        default=False,
        description="如果目录已存在是否报错，默认为False（目录已存在时报错，设为True则跳过）"
    )
```

### 2.2.2 工具实现（插入到 file_tools.py）

在 file_schema.py 导��部��添加：
```python
from app.services.tools.file.file_schema import (
    # ... 现有导入 ...
    CreateDirectoryInput,
)
```

在 file_tools.py 中添加（放在 create_directory 方法位置）：

```python
    @register_tool(
        name="create_directory",
        description="""创建新目录。

使用场景：
- 当用户想要创建新的文件夹时使用此工具
- 当用户想要创建项目目录结构时使用
- 当用户说"新建文件夹"、"创建目录"时使用

参数说明：
- dir_path: 要创建的目录完整路径（必须是绝对路径，如 C:/Users/用户名/Documents/new_folder）
- parents: 是否创建父目录，默认为True（自动创建所需的父目录，如 C:/A/B 而 C:/A 不存在，会自动创建 C:/A）
- exist_ok: 如果目录已存在是否报错，默认为False（目录已存在时报错，设为True则跳过）

【重要】必须使用 dir_path 作为参数名，不要使用 folder_path、path 或其他名称。
错误示例: {"folder_path": "..."} 或 {"path": "..."}
正确示例: {"dir_path": "C:/Users/用户名/Documents/new_folder"}

【注意】如果 parents=True，会自动创建所有需要的父目录。
如果 exist_ok=False 且目录已存在，操作会失败。""",
        input_model=CreateDirectoryInput,
        examples=[
            {
                "dir_path": "C:/Users/用户名/Documents/new_folder",
                "parents": True,
                "exist_ok": False
            },
            {
                "dir_path": "D:/项目代码/src/components/widgets",
                "parents": True,
                "exist_ok": True
            },
            {
                "dir_path": "D:/项目代码_backup/logs/2026",
                "parents": True,
                "exist_ok": False
            }
        ]
    )
    async def create_directory(
        self,
        dir_path: str,
        parents: bool = True,
        exist_ok: bool = False
    ) -> Dict[str, Any]:
        """创建新目录"""
        # ===================== 1. 验证路径合法性 =====================
        is_valid, error_msg = self._validate_path(dir_path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "operation_id": None
            }, "create_directory")
        
        # ===================== 2. 检查会话ID =====================
        if not self.session_id:
            return _to_unified_format({
                "success": False,
                "error": "No active session",
                "operation_id": None
            }, "create_directory")
        
        path = Path(dir_path)
        
        try:
            # ===================== 3. 检查目录是否已存在 =====================
            if path.exists():
                # 3.1 如果存在但不是目录
                if path.is_file():
                    return _to_unified_format({
                        "success": False,
                        "error": f"路径已存在且是文件: {dir_path}",
                        "operation_id": None
                    }, "create_directory")
                
                # 3.2 如果存在且是目录
                if not exist_ok:
                    return _to_unified_format({
                        "success": False,
                        "error": f"目录已存在: {dir_path}，请设置 exist_ok=True 跳过或使用其他路径",
                        "operation_id": None
                    }, "create_directory")
                
                # 3.3 exist_ok=True 且目录已存在
                return _to_unified_format({
                    "success": True,
                    "operation_id": None,
                    "dir_path": str(path),
                    "message": "目录已存在"
                }, "create_directory")
            
            # ===================== 4. 记录操作（安全机制）====================
            operation_id = self.safety.record_operation(
                session_id=self.session_id,
                operation_type=OperationType.CREATE,
                destination_path=path,
                sequence_number=self._get_next_sequence()
            )
            
            # ===================== 5. 定义创建操作 =====================
            def _mkdir_sync():
                # 5.1 创建目录（根据 parents 参数）
                path.mkdir(parents=parents, exist_ok=exist_ok)
                return True
            
            # ===================== 6. 执行创建（异步）====================
            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_mkdir_sync
            )
            
            # ===================== 7. 返回结果 =====================
            if success:
                # 获取创建的目录信息
                return _to_unified_format({
                    "success": True,
                    "operation_id": operation_id,
                    "dir_path": str(path),
                    "parents_created": parents,
                    "message": f"成功创建目录: {path}"
                }, "create_directory")
            else:
                return _to_unified_format({
                    "success": False,
                    "error": "Failed to create directory",
                    "operation_id": operation_id
                }, "create_directory")
        
        except Exception as e:
            logger.error(f"Failed to create directory {dir_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "operation_id": None
            }, "create_directory")
```

### 2.2.3 _generate_summary 补充

在 file_tools.py 的 `_generate_summary` 函数中添加：

```python
    elif tool_name == "create_directory":
        if result.get("success") is False:
            return f"创建目录失败：{result.get('error', '未知错误')}"
        dir_path = result.get("dir_path", "")
        return f"成功创建目录: {dir_path}"
```

---

## 四、get_file_info - 文件信息获取（完整设计）

### 2.3.1 Schema 定义（插入到 file_schema.py）

```python
class GetFileInfoInput(BaseModel):
    """get_file_info 工具的输入参数"""
    file_path: str = Field(
        description="文件或目录的完整路径（必须是绝对路径，如 C:/Users/用户名/Documents/file.txt）"
    )
    include_stats: bool = Field(
        default=True,
        description="是否包含详细统计信息，默认为True（包括大小、时间等）"
    )
```

### 2.3.2 工具实现（插入到 file_tools.py）

在 file_schema.py 导入部分添加：
```python
from app.services.tools.file.file_schema import (
    # ... 现有导入 ...
    GetFileInfoInput,
)
```

在 file_tools.py 中添加（放在 get_file_info 方法位置）：

```python
    @register_tool(
        name="get_file_info",
        description="""获取文件或目录的详细信息。

使用场景：
- 当用户想要查看文件大小时使用此工具
- 当用户想要查看文件的创建时间、修改时间时使用
- 当用户想要查看文件类型、权限等元数据时使用
- 当用户说"查看文件信息"、"查看文件属性"、"查看文件大小"时使用

参数说明：
- file_path: 文件或目录的完整路径（必须是绝对路径）
- include_stats: 是否包含详细统计信息，默认为True（包括大小、时间、权限等）

返回信息：
- 文件：名称、路径、类型、大小、创建时间、修改时间、访问时间、权限
- 目录：名称、路径、类型、子目录数、子文件数、总大小

【重要】必须使用 file_path 作为参数名，不要使用 filepath、path 或其他名称。
错误示例: {"filepath": "..."} 或 {"path": "..."}
正确示例: {"file_path": "C:/Users/用户名/Documents/file.txt", "include_stats": True}""",
        input_model=GetFileInfoInput,
        examples=[
            {
                "file_path": "C:/Users/用户名/Documents/file.txt",
                "include_stats": True
            },
            {
                "file_path": "D:/项目代码",
                "include_stats": True
            },
            {
                "file_path": "D:/项目代码/src/main.py",
                "include_stats": True
            }
        ]
    )
    async def get_file_info(
        self,
        file_path: str,
        include_stats: bool = True
    ) -> Dict[str, Any]:
        """获取文件或目录的详细信息"""
        # ===================== 1. 验证路径合法性 =====================
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "file_info": None
            }, "get_file_info")
        
        path = Path(file_path)
        
        try:
            # ===================== 2. 检查文件是否存在 =====================
            if not path.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"Path not found: {file_path}",
                    "file_info": None
                }, "get_file_info")
            
            # ===================== 2.5 缓存 is_dir 结果 =====================
            is_directory = path.is_dir()
            
            # ===================== 3. 获取文件信息 =====================
            def _info_sync():
                # 3.1 基本信息
                info = {
                    "name": path.name,
                    "path": str(path.absolute()),
                    "type": "directory" if is_directory else "file",
                    "is_symlink": path.is_symlink(),
                }
                
                # 3.2 详细统计信息
                if include_stats:
                    stat = path.stat()
                    info.update({
                        "size": stat.st_size,
                        "size_formatted": _format_file_size(stat.st_size),
                        "created_timestamp": stat.st_ctime,
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_timestamp": stat.st_mtime,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "accessed_timestamp": stat.st_atime,
                        "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
                        "mode": oct(stat.st_mode),
                        "mode_raw": stat.st_mode,
                        "is_readable": os.access(path, os.R_OK),
                        "is_writable": os.access(path, os.W_OK),
                        "is_executable": os.access(path, os.X_OK),
                    })
                    
                    # 3.3 目录额外统计
                    if is_directory:
                        file_count = 0
                        dir_count = 0
                        total_size = 0
                        
                        try:
                            for item in path.rglob('*'):
                                try:
                                    if item.is_file():
                                        file_count += 1
                                        total_size += item.stat().st_size
                                    elif item.is_dir():
                                        dir_count += 1
                                except (PermissionError, OSError):
                                    # 跳过无权限访问的文件
                                    continue
                        except (PermissionError, OSError):
                            # 跳过无权限访问的目录
                            pass
                        
                        info.update({
                            "file_count": file_count,
                            "dir_count": dir_count,
                            "total_size": total_size,
                            "total_size_formatted": _format_file_size(total_size),
                            "item_count": file_count + dir_count
                        })
                
                return info
            
            # ===================== 4. 执行获取（异步）====================
            file_info = await asyncio.to_thread(_info_sync)
            
            # ===================== 5. 返回结果 =====================
            return _to_unified_format({
                "success": True,
                "file_info": file_info
            }, "get_file_info")
        
        except Exception as e:
            logger.error(f"Failed to get info for {file_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "file_info": None
            }, "get_file_info")


def _format_file_size(size: int) -> str:
    """格式化文件大小为人类可读格式"""
    if size < 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    
    return f"{size:.2f} EB"
```

### 2.3.3 _generate_summary 补充

在 file_tools.py 的 `_generate_summary` 函数中添加：

```python
    elif tool_name == "get_file_info":
        if result.get("success") is False:
            return f"获取文件信息失败：{result.get('error', '未知错误')}"
        file_info = result.get("file_info", {})
        file_type = file_info.get("type", "unknown")
        if file_type == "directory":
            file_count = file_info.get("file_count", 0)
            dir_count = file_info.get("dir_count", 0)
            return f"成功获取目录信息：{file_count} 文件，{dir_count} 子目录"
        else:
            size = file_info.get("size_formatted", "0 B")
            return f"成功获取文件信息：大小 {size}"
```

---

## 五、Schema 导入更新

### 5.1 file_schema.py 更新

在 `__all__` 列表中添加：

```python
__all__ = [
    "ReadFileInput",
    "WriteFileInput",
    "ListDirectoryInput",
    "DeleteFileInput",
    "MoveFileInput",
    "SearchFileContentInput",
    "SearchFilesByNameInput",
    "GenerateReportInput",
    # 新增
    "CopyFileInput",
    "CreateDirectoryInput",
    "GetFileInfoInput",
]
```

### 5.2 file_tools.py 导入更新

在 file_tools.py 的导入部分修改：

```python
from app.services.tools.file.file_schema import (
    ReadFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFileContentInput,
    SearchFilesByNameInput,
    GenerateReportInput,
    # 新增
    CopyFileInput,
    CreateDirectoryInput,
    GetFileInfoInput,
)
```

---

## 六、实施检查清单

### 6.1 copy_file 实施

- [ ] 在 file_schema.py 末尾添加 CopyFileInput 类
- [ ] 在 file_schema.py __all__ 列表添加 "CopyFileInput"
- [ ] 在 file_tools.py 导入添加 CopyFileInput
- [ ] 在 file_tools.py 添加 copy_file 方法（找到 move_file 方法位置，在其后添加）
- [ ] 在 _generate_summary 添加 copy_file 分支
- [ ] 测试单文件复制
- [ ] 测试目录复制（递归）
- [ ] 测试 overwrite=False（已存在报错）
- [ ] 测试 overwrite=True（覆盖）
- [ ] 测试权限错误
- [ ] 测试跨盘符复制

### 6.2 create_directory 实施

- [ ] 在 file_schema.py 末尾添加 CreateDirectoryInput 类
- [ ] 在 file_schema.py __all__ 列表添加 "CreateDirectoryInput"
- [ ] 在 file_tools.py 导入添加 CreateDirectoryInput
- [ ] 在 file_tools.py 添加 create_directory 方法
- [ ] 在 _generate_summary 添加 create_directory 分支
- [ ] 测试基本创建
- [ ] 测试 parents=True 自动创建父目录
- [ ] 测试 parents=False（父目录不存在报错）
- [ ] 测试 exist_ok=True（已存在跳过）
- [ ] 测试 exist_ok=False（已存在报错）
- [ ] 测试目标已是文件报错

### 6.3 get_file_info 实施

- [ ] 在 file_schema.py 末尾添加 GetFileInfoInput 类
- [ ] 在 file_schema.py __all__ 列表添加 "GetFileInfoInput"
- [ ] 在 file_tools.py 导入添加 GetFileInfoInput
- [ ] 在 file_tools.py 添加 get_file_info 方法
- [ ] 在 file_tools.py 末尾添加 _format_file_size 辅助函数
- [ ] 在 _generate_summary 添加 get_file_info 分支
- [ ] 测试文件信息获取
- [ ] 测试 include_stats=False
- [ ] 测试目录统计（包括子目录）
- [ ] 测试符号链接处理
- [ ] 测试大文件大小格式化

---

## 七、版本更新

实施完成后需要更新 version.txt：

```
v0.9.9.0: 2026-04-19 16:37:18 小沈 - 新增文件工具
- copy_file: 文件复制功能（支持文件和目录，覆盖选项）
- create_directory: 目录创建功能（自动创建父目录，存在跳过）
- get_file_info: 文件信息获取（大小、时间、权限、目录统计）
```

---

## 八、错误码参考

| 错误场景 | 返回错误信息 |
|---------|-----------|
| 源文件不存在 | "Source not found: {path}" |
| 目标已存在 | "目标路径已存在: {path}，请设置 overwrite=True 覆盖或使用其他目标路径。" |
| 目录已存在 | "目录已存在: {path}，请设置 exist_ok=True 跳过或使用其他路径" |
| 路径是文件 | "路径已存在且是文件: {path}" |
| 无权限 | "Permission denied: {path}" |
| 路径不在白名单 | "路径 '{path}' 不在允许的操作范围内" |

---

## 九、compare_files - 文件比较功能（完整设计）

### 9.1 Schema 定义（插入到 file_schema.py）

```python
class CompareFilesInput(BaseModel):
    """compare_files 工具的输入参数"""
    source_path: str = Field(
        description="源文件路径（必须是绝对路径）"
    )
    destination_path: str = Field(
        description="目标文件路径（必须是绝对路径）"
    )
    ignore_case: bool = Field(
        default=False,
        description="比较时是否忽略大小写，默认为False"
    )
    ignore_blank_lines: bool = Field(
        default=False,
        description="比较时是否忽略空白行，默认为False"
    )
```

### 9.2 工具实现（插入到 file_tools.py）

```python
@register_tool(
    name="compare_files",
    description="""比较两个文件的差异。

使用场景：
- 当用户想要比较两个文件的内容差异时使用此工具
- 当用户想要检查两个版本的文件是否相同时使用
- 当用户说"比较文件"、"查看文件差异"时使用

参数说明：
- source_path: 源文件路径（必须是绝对路径）
- destination_path: 目标文件路径（必须是绝对路径）
- ignore_case: 比较时是否忽略大小写，默认为False
- ignore_blank_lines: 比较时是否忽略空白行，默认为False

返回信息：
- identical: 文件是否相同
- diff_lines: 不同行数
- added_lines: 新增行数
- removed_lines: 删除行数
- changed_lines: 修改行数
- diff_content: 具体差异内容（统一diff格式）

【重要】必须使用 source_path 和 destination_path 作为参数名。
错误示例: {"file1": "...", "file2": "..."}
正确示例: {"source_path": "C:/A.txt", "destination_path": "D:/B.txt"}""",
    input_model=CompareFilesInput,
    examples=[
        {
            "source_path": "C:/Users/用户名/Documents/v1.txt",
            "destination_path": "C:/Users/用户名/Documents/v2.txt",
            "ignore_case": False,
            "ignore_blank_lines": False
        },
        {
            "source_path": "D:/项目代码/src/main.py",
            "destination_path": "D:/项目代码_backup/src/main.py",
            "ignore_case": True,
            "ignore_blank_lines": True
        }
    ]
)
async def compare_files(
    self,
    source_path: str,
    destination_path: str,
    ignore_case: bool = False,
    ignore_blank_lines: bool = False
) -> Dict[str, Any]:
    """比较两个文件的差异"""
    # ===================== 1. 验证源路径 =====================
    is_valid_src, error_msg_src = self._validate_path(source_path)
    if not is_valid_src:
        return _to_unified_format({
            "success": False,
            "error": f"源路径{error_msg_src}",
            "diff_result": None
        }, "compare_files")
    
    # ===================== 2. 验证目标路径 =====================
    is_valid_dst, error_msg_dst = self._validate_path(destination_path)
    if not is_valid_dst:
        return _to_unified_format({
            "success": False,
            "error": f"目标路径{error_msg_dst}",
            "diff_result": None
        }, "compare_files")
    
    src = Path(source_path)
    dst = Path(destination_path)
    
    try:
        # ===================== 3. 检查文件是否存在 =====================
        if not src.exists():
            return _to_unified_format({
                "success": False,
                "error": f"Source not found: {source_path}",
                "diff_result": None
            }, "compare_files")
        
        if not dst.exists():
            return _to_unified_format({
                "success": False,
                "error": f"Destination not found: {destination_path}",
                "diff_result": None
            }, "compare_files")
        
        if not src.is_file() or not dst.is_file():
            return _to_unified_format({
                "success": False,
                "error": "Only files can be compared, directories are not supported",
                "diff_result": None
            }, "compare_files")
        
        # ===================== 4. 执行文件比较 =====================
        def _compare_sync():
            import difflib
            
            # 4.1 读取文件内容
            with open(src, 'r', encoding='utf-8', errors='replace') as f1:
                lines1 = f1.readlines()
            
            with open(dst, 'r', encoding='utf-8', errors='replace') as f2:
                lines2 = f2.readlines()
            
            # 4.2 预处理
            if ignore_case:
                lines1 = [l.lower() for l in lines1]
                lines2 = [l.lower() for l in lines2]
            
            if ignore_blank_lines:
                lines1 = [l for l in lines1 if l.strip()]
                lines2 = [l for l in lines2 if l.strip()]
            
            # 4.3 使用 unified_diff 获取差异
            diff = list(difflib.unified_diff(
                lines1, lines2,
                fromfile=str(src),
                tofile=str(dst),
                lineterm=''
            ))
            
            # 4.4 统计差异
            added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
            removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
            
            # 4.5 判断是否相同
            identical = (added == 0 and removed == 0)
            
            return {
                "identical": identical,
                "source": str(src),
                "destination": str(dst),
                "added_lines": added,
                "removed_lines": removed,
                "changed_lines": min(added, removed),
                "total_changes": added + removed,
                "diff_content": '\n'.join(diff[:100]) if diff else "",  # 限制显示前100行
                "has_more": len(diff) > 100
            }
        
        # ===================== 5. 执行比较（异步）====================
        diff_result = await asyncio.to_thread(_compare_sync)
        
        # ===================== 6. 返回结果 =====================
        return _to_unified_format({
            "success": True,
            "diff_result": diff_result
        }, "compare_files")
    
    except Exception as e:
        logger.error(f"Failed to compare files: {e}")
        return _to_unified_format({
            "success": False,
            "error": str(e),
            "diff_result": None
        }, "compare_files")
```

---

## 十、compress_files - 文件压缩功能（完整设计）

### 10.1 Schema 定义（插入到 file_schema.py）

```python
class CompressFilesInput(BaseModel):
    """compress_files 工具的输入参数"""
    source_path: str = Field(
        description="要压缩的文件或目录路径（必须是绝对路径）"
    )
    output_path: str = Field(
        description="压缩文件输出路径（必须是绝对路径，不包含扩展名）"
    )
    format: str = Field(
        default="zip",
        description="压缩格式: zip/tar/gztar/bztar/xztar，默认为zip"
    )
```

### 10.2 工具实现（插入到 file_tools.py）

```python
@register_tool(
    name="compress_files",
    description="""压缩文件或目录为压缩包。

使用场景：
- 当用户想要打包文件或目录时使用此工具
- 当用户想要创建压缩归档时使用
- 当用户说"压缩文件"、"打包文件"时使用

参数说明：
- source_path: 要压缩的文件或目录路径（必须是绝对路径）
- output_path: 压缩文件输出路径（必须是绝对路径，不包含扩展名，如 C:/backup/myarchive）
- format: 压缩格式，默认为zip，可选：zip/tar/gztar/bztar/xztar

返回信息：
- archive_path: 压缩文件路径
- archive_size: 压缩后大小
- source_count: 源文件数量

【注意】output_path 不要包含扩展名，程序会自动添加 .zip 等扩展名。""",
    input_model=CompressFilesInput,
    examples=[
        {
            "source_path": "C:/Users/用户名/Documents/folder",
            "output_path": "C:/Users/用户名/Backup/folder",
            "format": "zip"
        },
        {
            "source_path": "D:/项目代码",
            "output_path": "D:/项目代码_backup/project",
            "format": "gztar"
        }
    ]
)
async def compress_files(
    self,
    source_path: str,
    output_path: str,
    format: str = "zip"
) -> Dict[str, Any]:
    """压缩文件或目录为压缩包"""
    # ===================== 1. 验证源路径 =====================
    is_valid_src, error_msg_src = self._validate_path(source_path)
    if not is_valid_src:
        return _to_unified_format({
            "success": False,
            "error": f"源路径{error_msg_src}",
            "archive_info": None
        }, "compress_files")
    
    # ===================== 2. 验证输出路径 =====================
    is_valid_dst, error_msg_dst = self._validate_path(output_path)
    if not is_valid_dst:
        return _to_unified_format({
            "success": False,
            "error": f"输出路径{error_msg_dst}",
            "archive_info": None
        }, "compress_files")
    
    # ===================== 3. 验证压缩格式 =====================
    valid_formats = ['zip', 'tar', 'gztar', 'bztar', 'xztar']
    if format not in valid_formats:
        return _to_unified_format({
            "success": False,
            "error": f"Invalid format: {format}. Valid formats: {', '.join(valid_formats)}",
            "archive_info": None
        }, "compress_files")
    
    if not self.session_id:
        return _to_unified_format({
            "success": False,
            "error": "No active session",
            "operation_id": None
        }, "compress_files")
    
    src = Path(source_path)
    
    # 输出路径添加扩展名
    format_ext = f".{format}" if not output_path.endswith(f".{format}") else ""
    output_file = Path(output_path + format_ext)
    
    try:
        # ===================== 4. 检查源文件是否存在 =====================
        if not src.exists():
            return _to_unified_format({
                "success": False,
                "error": f"Source not found: {source_path}",
                "archive_info": None
            }, "compress_files")
        
        # ===================== 5. 记录操作 =====================
        operation_id = self.safety.record_operation(
            session_id=self.session_id,
            operation_type=OperationType.CREATE,
            destination_path=output_file,
            sequence_number=self._get_next_sequence()
        )
        
        # ===================== 6. 执行压缩 =====================
        def _compress_sync():
            # 删除已存在的压缩文件
            if output_file.exists():
                output_file.unlink()
            
            # 计算正确的base_name（不带扩展名）
            base_name = str(Path(output_path).with_suffix(''))
            
            # 执行压缩
            # root_dir = src: 直接压缩 src 内容
            # base_dir = src.name: 压缩包内只显示 src 的名字作为顶层
            shutil.make_archive(
                base_name,       # 如 "C:/backup/folder"
                format,           # 压缩格式
                root_dir=src,     # 直接用 src 作为根目录
                base_dir=src.name # 只取目录名，压缩包内只有这一层
            )
            return True
        
        success = await asyncio.to_thread(
            self.safety.execute_with_safety,
            operation_id=operation_id,
            operation_func=_compress_sync
        )
        
        if success:
            archive_size = output_file.stat().st_size
            source_count = sum(1 for _ in src.rglob('*') if _.is_file()) if src.is_dir() else 1
            
            return _to_unified_format({
                "success": True,
                "operation_id": operation_id,
                "archive_path": str(output_file),
                "archive_size": archive_size,
                "archive_size_formatted": _format_file_size(archive_size),
                "source_count": source_count,
                "format": format,
                "message": f"成功压缩: {src.name} -> {output_file.name}"
            }, "compress_files")
        else:
            return _to_unified_format({
                "success": False,
                "error": "Failed to compress",
                "operation_id": operation_id
            }, "compress_files")
    
    except Exception as e:
        logger.error(f"Failed to compress: {e}")
        return _to_unified_format({
            "success": False,
            "error": str(e),
            "archive_info": None
        }, "compress_files")
```

---

## 十一、batch_rename - 批量重命名功能（完整设计）

### 11.1 Schema 定义（插入到 file_schema.py）

```python
class BatchRenameInput(BaseModel):
    """batch_rename 工具的输入参数"""
    dir_path: str = Field(
        description="要重命名的目录路径（必须是绝对路径）"
    )
    pattern: str = Field(
        description="文件名匹配模式（支持通配符 * 和 ?）"
    )
    replacement: str = Field(
        description="替换为的字符串"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归处理子目录，默认为False"
    )
    dry_run: bool = Field(
        default=True,
        description="预览模式，不实际修改文件，默认为True"
    )
```

### 11.2 工具实现（插入到 file_tools.py）

```python
@register_tool(
    name="batch_rename",
    description="""批量重命名匹配的文件。

使用场景：
- 当用户想要批量修改文件名时使用此工具
- 当用户想要添加前缀/后缀时使用
- 当用户说"批量重命名"、"批量修改文件名"时使用

参数说明：
- dir_path: 要重命名的目录路径（必须是绝对路径）
- pattern: 文件名匹配模式（支持通配符 * 和 ?，如 *.txt 或 test_*）
- replacement: 替换为的字符串（如 prefix_ 或 _backup）
- recursive: 是否递归处理子目录，默认为False
- dry_run: 预览模式，默认为True（不实际执行，只返回预览结果）

返回信息：
- dry_run模式下返回预览列表
- 非dry_run返回实际重命名结果

【重要】必须使用 pattern 和 replacement 作为参数名。""",
    input_model=BatchRenameInput,
    examples=[
        {
            "dir_path": "C:/Users/用户名/Documents",
            "pattern": "*.txt",
            "replacement": "doc_",
            "recursive": False,
            "dry_run": True
        },
        {
            "dir_path": "D:/项目代码",
            "pattern": "*.py",
            "replacement": "_backup",
            "recursive": True,
            "dry_run": False
        }
    ]
)
async def batch_rename(
    self,
    dir_path: str,
    pattern: str,
    replacement: str,
    recursive: bool = False,
    dry_run: bool = True
) -> Dict[str, Any]:
    """批量重命名匹配的文件"""
    # ===================== 1. 验证目录路径 =====================
    is_valid, error_msg = self._validate_path(dir_path)
    if not is_valid:
        return _to_unified_format({
            "success": False,
            "error": error_msg,
            "rename_result": None
        }, "batch_rename")
    
    # ===================== 2. 验证参数 =====================
    if not pattern or not pattern.strip():
        return _to_unified_format({
            "success": False,
            "error": "Pattern cannot be empty",
            "rename_result": None
        }, "batch_rename")
    
    if not self.session_id:
        return _to_unified_format({
            "success": False,
            "error": "No active session",
            "operation_id": None
        }, "batch_rename")
    
    path = Path(dir_path)
    
    try:
        # ===================== 3. 检查目录是否存在 =====================
        if not path.exists():
            return _to_unified_format({
                "success": False,
                "error": f"Directory not found: {dir_path}",
                "rename_result": None
            }, "batch_rename")
        
        if not path.is_dir():
            return _to_unified_format({
                "success": False,
                "error": f"Not a directory: {dir_path}",
                "rename_result": None
            }, "batch_rename")
        
        # ===================== 4. 查找匹配文件 =====================
        def _find_matching():
            import fnmatch
            import re
            
            matches = []
            for item in path.rglob('*') if recursive else path.iterdir():
                if not item.is_file():
                    continue
                if fnmatch.fnmatch(item.name, pattern):
                    new_name = item.name
                    
                    # 正确的通配符替换逻辑
                    if '*' in pattern:
                        # 将 pattern 转换为正则，提取匹配部分
                        # 例如：*.txt 匹配任意.txt文件
                        # 提取扩展名部分
                        if pattern.startswith('*.'):
                            # 匹配扩展名：*.txt -> 获取 "txt" 部分
                            ext = pattern[2:]  # ".txt"
                            if item.name.endswith(ext):
                                base_name = item.name[:-len(ext)]  # 去掉扩展名
                                new_name = replacement + ext  # replacement替换基础名
                        else:
                            # 其他 * 模式：test_* 匹配 test_任意
                            regex_pattern = pattern.replace('*', r'(.+)')
                            match = re.match(regex_pattern, item.name)
                            if match:
                                matched_part = match.group(1)
                                new_name = replacement.replace('*', matched_part)
                    elif '?' in pattern:
                        # ? 匹配单个字符
                        regex_pattern = pattern.replace('?', r'(.)')
                        match = re.match(regex_pattern, item.name)
                        if match:
                            new_name = replacement.replace('?', match.group(1))
                    else:
                        # 无通配符，直接替换
                        new_name = replacement
                    
                    new_path = item.parent / new_name
                    matches.append({
                        "original": str(item),
                        "original_name": item.name,
                        "new": str(new_path),
                        "new_name": new_name,
                        "exists": new_path.exists()
                    })
            return matches
        
        matches = await asyncio.to_thread(_find_matching)
        
        # ===================== 5. Dry run 模式 =====================
        if dry_run:
            return _to_unified_format({
                "success": True,
                "dry_run": True,
                "matches": matches,
                "total": len(matches),
                "message": f"预览模式：找到 {len(matches)} 个匹配文件（设置 dry_run=False 执行实际重命名）"
            }, "batch_rename")
        
        # ===================== 6. 执行重命名 =====================
        if not matches:
            return _to_unified_format({
                "success": True,
                "dry_run": False,
                "renamed": [],
                "total": 0,
                "message": "没有匹配的文件"
            }, "batch_rename")
        
        # 记录操作
        operation_id = self.safety.record_operation(
            session_id=self.session_id,
            operation_type=OperationType.MOVE,
            destination_path=path,
            sequence_number=self._get_next_sequence()
        )
        
        # 执行重命名
        renamed = []
        errors = []
        
        for match in matches:
            if match["exists"]:
                errors.append({
                    "file": match["original_name"],
                    "error": "目标文件已存在"
                })
                continue
            
            try:
                orig_path = Path(match["original"])
                new_path = Path(match["new"])
                orig_path.rename(new_path)
                renamed.append(match)
            except Exception as e:
                errors.append({
                    "file": match["original_name"],
                    "error": str(e)
                })
        
        return _to_unified_format({
            "success": True,
            "dry_run": False,
            "renamed": renamed,
            "errors": errors,
            "total": len(matches),
            "success_count": len(renamed),
            "error_count": len(errors),
            "message": f"成功重命名 {len(renamed)}/{len(matches)} 个文件"
        }, "batch_rename")
    
    except Exception as e:
        logger.error(f"Failed to batch rename: {e}")
        return _to_unified_format({
            "success": False,
            "error": str(e),
            "rename_result": None
        }, "batch_rename")
```

---

## 十二、文件监控功能（完整设计）

### 12.1 Schema 定义（插入到 file_schema.py）

```python
class FileMonitorInput(BaseModel):
    """file_monitor 工具的输入参数"""
    watch_path: str = Field(
        description="要监控的目录或文件路径"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归监控子目录，默认为True"
    )
    events: str = Field(
        default="created,modified,deleted",
        description="要监控的事件类型，默认为created,modified,deleted"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="监控超时时间（秒），默认为30秒"
    )
```

### 12.2 工具实现（插入到 file_tools.py）

```python
@register_tool(
    name="file_monitor",
    description="""监控文件或目录的变化事件。

使用场景：
- 当用户想要实时了解文件变更时使用此工具
- 当用户想要监听目录的文件创建、修改、删除事件时使用

参数说明：
- watch_path: 要监控的目录或文件路径
- recursive: 是否递归监控子目录，默认为True
- events: 要监控的事件类型，默认为created,modified,deleted（用逗号分隔）
- timeout: 监控超时时间（秒），默认为30秒

返回信息：
- events: 捕获到的事件列表
- event_count: 事件数量

【注意】超时后返回监控结果，此工具不支持长时间运行。""",
    input_model=FileMonitorInput,
    examples=[
        {
            "watch_path": "C:/Users/用户名/Downloads",
            "recursive": True,
            "events": "created,deleted",
            "timeout": 30
        },
        {
            "watch_path": "D:/项目代码",
            "recursive": True,
            "events": "created,modified,deleted",
            "timeout": 60
        }
    ]
)
async def file_monitor(
    self,
    watch_path: str,
    recursive: bool = True,
    events: str = "created,modified,deleted",
    timeout: int = 30
) -> Dict[str, Any]:
    """监控文件或目录的变化事件"""
    # ===================== 1. 验证路径 =====================
    is_valid, error_msg = self._validate_path(watch_path)
    if not is_valid:
        return _to_unified_format({
            "success": False,
            "error": error_msg,
            "monitor_result": None
        }, "file_monitor")
    
    path = Path(watch_path)
    
    if not path.exists():
        return _to_unified_format({
            "success": False,
            "error": f"Path not found: {watch_path}",
            "monitor_result": None
        }, "file_monitor")
    
    # ===================== 2. 解析事件类型 =====================
    event_types = []
    for e in events.split(','):
        e = e.strip().lower()
        if e == 'created':
            event_types.append('created')
        elif e == 'modified':
            event_types.append('modified')
        elif e == 'deleted':
            event_types.append('deleted')
    
    if not event_types:
        return _to_unified_format({
            "success": False,
            "error": "No valid events specified",
            "monitor_result": None
        }, "file_monitor")
    
    # ===================== 3. 执行监控 =====================
    def _monitor_sync():
        try:
            # 3.1 尝试导入 watchdog
            try:
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler
            except ImportError:
                return {"error": "watchdog library not installed", "events": []}
            
            class EventHandler(FileSystemEventHandler):
                def __init__(self):
                    super().__init__()
                    self.captured_events = []
                
                def on_created(self, event):
                    if 'created' in event_types and not event.is_directory:
                        self.captured_events.append({
                            "type": "created",
                            "path": event.src_path,
                            "time": datetime.now().isoformat()
                        })
                
                def on_modified(self, event):
                    if 'modified' in event_types and not event.is_directory:
                        self.captured_events.append({
                            "type": "modified",
                            "path": event.src_path,
                            "time": datetime.now().isoformat()
                        })
                
                def on_deleted(self, event):
                    if 'deleted' in event_types:
                        self.captured_events.append({
                            "type": "deleted",
                            "path": event.src_path,
                            "time": datetime.now().isoformat()
                        })
            
            handler = EventHandler()
            observer = Observer()
            observer.schedule(handler, str(path), recursive=recursive)
            observer.start()
            
            # 等待超时
            import time
            time.sleep(timeout)
            
            observer.stop()
            observer.join()
            
            return {"events": handler.captured_events}
        
        except Exception as e:
            return {"error": str(e), "events": []}
    
    # ===================== 4. 执行监控（异步）====================
    result = await asyncio.to_thread(_monitor_sync)
    
    if "error" in result:
        # watchdog 未安装，使用简单轮询方案
        def _simple_monitor():
            import time
            events = []
            known_files = {}
            
            # 记录初始状态
            for item in path.rglob('*') if recursive else path.iterdir():
                if item.is_file():
                    known_files[str(item)] = item.stat().st_mtime
            
            time.sleep(timeout)
            
            # 检查变更
            current_files = {}
            for item in path.rglob('*') if recursive else path.iterdir():
                if item.is_file():
                    current_files[str(item)] = item.stat().st_mtime
            
            # 新建
            for f in current_files:
                if f not in known_files:
                    events.append({
                        "type": "created",
                        "path": f,
                        "time": datetime.now().isoformat()
                    })
            
            # 删除
            for f in known_files:
                if f not in current_files:
                    events.append({
                        "type": "deleted",
                        "path": f,
                        "time": datetime.now().isoformat()
                    })
            
            # 修改
            for f in current_files:
                if f in known_files and known_files[f] != current_files[f]:
                    events.append({
                        "type": "modified",
                        "path": f,
                        "time": datetime.now().isoformat()
                    })
            
            return {"events": events}
        
        result = await asyncio.to_thread(_simple_monitor)
    
    # ===================== 5. 返回结果 =====================
    return _to_unified_format({
        "success": True,
        "monitor_result": {
            "events": result.get("events", []),
            "event_count": len(result.get("events", [])),
            "timeout": timeout
        }
    }, "file_monitor")
```

---

## 十三、文件链接支持（完整设计）

### 13.1 Schema 定义

```python
class CreateLinkInput(BaseModel):
    """create_link 工具的输入参数"""
    source_path: str = Field(
        description="源文件路径（必须是绝对路径）"
    )
    link_path: str = Field(
        description="链接路径（必须是绝对路径）"
    )
    link_type: str = Field(
        default="symbolic",
        description="链接类型: symbolic（符号链接）/ hard（硬链接），默认为symbolic"
    )
```

### 13.2 工具实现

```python
@register_tool(
    name="create_link",
    description="""创建文件链接（符号链接或硬链接）。

使用场景：
- 当用户想要创建快捷方式或链接时使用此工具
- 当用户想要节省磁盘空间时使用硬链接（同文件）
- 当用户说"创建链接"、"创建快捷方式"时使用

参数说明：
- source_path: 源文件路径
- link_path: 链接路径
- link_type: 链接类型，默认为symbolic，可选：symbolic/hard

【注意】硬链接只能用于文件，不能跨文件系统。
符号链接可以用于文件或目录，可以跨文件系统。""",
    input_model=CreateLinkInput,
    examples=[
        {
            "source_path": "C:/Users/用户名/Documents/file.txt",
            "link_path": "C:/Users/用户名/Desktop/file_link",
            "link_type": "symbolic"
        }
    ]
)
async def create_link(
    self,
    source_path: str,
    link_path: str,
    link_type: str = "symbolic"
) -> Dict[str, Any]:
    """创建文件链接"""
    # 验证源路径
    is_valid_src, error_msg_src = self._validate_path(source_path)
    if not is_valid_src:
        return _to_unified_format({"success": False, "error": f"源路径{error_msg_src}"}, "create_link")
    
    # 验证链接路径
    is_valid_dst, error_msg_dst = self._validate_path(link_path)
    if not is_valid_dst:
        return _to_unified_format({"success": False, "error": f"链接路径{error_msg_dst}"}, "create_link")
    
    src = Path(source_path)
    dst = Path(link_path)
    
    try:
        if not src.exists():
            return _to_unified_format({"success": False, "error": f"Source not found: {source_path}"}, "create_link")
        
        if not src.is_file() and link_type == "hard":
            return _to_unified_format({"success": False, "error": "Hard links only for files"}, "create_link")
        
        if dst.exists():
            return _to_unified_format({"success": False, "error": f"Link path exists: {link_path}"}, "create_link")
        
        # 创建链接
        def _link_sync():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if link_type == "hard":
                os.link(src, dst)
            else:
                os.symlink(src, dst)
            return True
        
        success = await asyncio.to_thread(_link_sync)
        
        return _to_unified_format({
            "success": True,
            "link_type": link_type,
            "source": str(src),
            "link": str(dst),
            "message": f"成功创建 {link_type} 链接"
        }, "create_link")
    
    except Exception as e:
        return _to_unified_format({"success": False, "error": str(e)}, "create_link")
```

---

## 十四、文件统计功能（完整设计）

### 14.1 Schema 定义

```python
class FileStatsInput(BaseModel):
    """file_stats 工具的输入参数"""
    dir_path: str = Field(
        description="要统计的目录路径"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归统计子目录，默认为True"
    )
    by_extension: bool = Field(
        default=True,
        description="是否按扩展名分类统计，默认为True"
    )
```

### 14.2 工具实现

```python
@register_tool(
    name="file_stats",
    description="""统计目录文件信息。

使用场景：
- 当用户想要了解目录占用空间时使用此工具
- 当用户想要按扩展名查看文件分布时使用
- 当用户说"统计目录"、"查看磁盘占用"时使用

参数说明：
- dir_path: 要统计的目录路径
- recursive: 是否递归统计子目录，默认为True
- by_extension: 是否按扩展名分类统计，默认为True""",
    input_model=FileStatsInput,
    examples=[
        {
            "dir_path": "C:/Users/用户名/Documents",
            "recursive": True,
            "by_extension": True
        }
    ]
)
async def file_stats(
    self,
    dir_path: str,
    recursive: bool = True,
    by_extension: True
) -> Dict[str, Any]:
    """统计目录文件信息"""
    is_valid, error_msg = self._validate_path(dir_path)
    if not is_valid:
        return _to_unified_format({"success": False, "error": error_msg}, "file_stats")
    
    path = Path(dir_path)
    
    if not path.exists():
        return _to_unified_format({"success": False, "error": f"Directory not found: {dir_path}"}, "file_stats")
    
    def _stats_sync():
        stats = {
            "total_files": 0,
            "total_dirs": 0,
            "total_size": 0,
            "by_extension": {},
            "largest_files": []
        }
        
        files_list = []
        
        for item in path.rglob('*') if recursive else path.iterdir():
            try:
                if item.is_file():
                    size = item.stat().st_size
                    stats["total_files"] += 1
                    stats["total_size"] += size
                    files_list.append((str(item), size))
                    
                    if by_extension:
                        ext = item.suffix.lower() or "(无扩展名)"
                        if ext not in stats["by_extension"]:
                            stats["by_extension"][ext] = {"count": 0, "size": 0}
                        stats["by_extension"][ext]["count"] += 1
                        stats["by_extension"][ext]["size"] += size
                        
                elif item.is_dir():
                    stats["total_dirs"] += 1
            except (PermissionError, OSError):
                continue
        
        # 最大的10个文件
        files_list.sort(key=lambda x: x[1], reverse=True)
        stats["largest_files"] = [
            {"path": f[0], "size": f[1], "size_formatted": _format_file_size(f[1])}
            for f in files_list[:10]
        ]
        
        # 按扩展名排序
        stats["by_extension"] = dict(
            sorted(stats["by_extension"].items(),
                  key=lambda x: x[1]["size"],
                  reverse=True)
        )
        
        return stats
    
    stats_result = await asyncio.to_thread(_stats_sync)
    
    return _to_unified_format({
        "success": True,
        "stats": stats_result
    }, "file_stats")
```

---

## 十五、文件校验功能（完整设计）

### 15.1 Schema 定义

```python
class VerifyFileInput(BaseModel):
    """verify_file 工具的输入参数"""
    file_path: str = Field(
        description="要校验的文件路径"
    )
    algorithm: str = Field(
        default="md5",
        description="哈希算法: md5/sha1/sha256/sha512，默认为md5"
    )
    expected_hash: Optional[str] = Field(
        default=None,
        description="期望的哈希值（用于验证文件完整性）"
    )
```

### 15.2 工具实现

```python
@register_tool(
    name="verify_file",
    description="""计算或验证文件哈希。

使用场景：
- 当用户想要验证文件完整性时使用此工具
- 当用户想要计算文件的hash值时使用
- 当用户说"验证文件"、"计算hash"时使用

参数说明：
- file_path: 要校验的文件路径
- algorithm: 哈希算法，默认为md5，可选：md5/sha1/sha256/sha512
- expected_hash: 期望的哈希值（可选，提供后会比较是否一致）""",
    input_model=VerifyFileInput,
    examples=[
        {
            "file_path": "C:/Users/用户名/Downloads/file.zip",
            "algorithm": "sha256",
            "expected_hash": None
        },
        {
            "file_path": "D:/项目代码/src/main.py",
            "algorithm": "md5",
            "expected_hash": "d41d8cd98f00b204e9800998ecf8427e"
        }
    ]
)
async def verify_file(
    self,
    file_path: str,
    algorithm: str = "md5",
    expected_hash: Optional[str] = None
) -> Dict[str, Any]:
    """计算或验证文件哈希"""
    is_valid, error_msg = self._validate_path(file_path)
    if not is_valid:
        return _to_unified_format({"success": False, "error": error_msg}, "verify_file")
    
    path = Path(file_path)
    
    if not path.exists():
        return _to_unified_format({"success": False, "error": f"File not found: {file_path}"}, "verify_file")
    
    if not path.is_file():
        return _to_unified_format({"success": False, "error": "Not a file"}, "verify_file")
    
    valid_algos = ['md5', 'sha1', 'sha256', 'sha512']
    if algorithm not in valid_algos:
        return _to_unified_format({"success": False, "error": f"Invalid algorithm: {algorithm}"}, "verify_file")
    
    def _verify_sync():
        import hashlib
        
        h = hashlib.new(algorithm)
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        
        return h.hexdigest()
    
    actual_hash = await asyncio.to_thread(_verify_sync)
    
    result = {
        "file_path": str(path),
        "algorithm": algorithm,
        "hash": actual_hash,
        "file_size": path.stat().st_size
    }
    
    if expected_hash:
        expected_hash = expected_hash.lower()
        actual_hash_lower = actual_hash.lower()
        result["match"] = (expected_hash == actual_hash_lower)
        result["expected_hash"] = expected_hash
    
    return _to_unified_format({
        "success": True,
        "verify_result": result
    }, "verify_file")
```

---

## 十六、实施总检查清单

### 工具实施顺序

| 序号 | 工具 | Schema | 实现 | 测试 |
|------|------|-------|------|------|
| 1 | copy_file | [ ] | [ ] | [ ] |
| 2 | create_directory | [ ] | [ ] | [ ] |
| 3 | get_file_info | [ ] | [ ] | [ ] |
| 4 | compare_files | [ ] | [ ] | [ ] |
| 5 | compress_files | [ ] | [ ] | [ ] |
| 6 | batch_rename | [ ] | [ ] | [ ] |
| 7 | file_monitor | [ ] | [ ] | [ ] |
| 8 | create_link | [ ] | [ ] | [ ] |
| 9 | file_stats | [ ] | [ ] | [ ] |
| 10 | verify_file | [ ] | [ ] | [ ] |

---

**更新时间**: 2026-04-19 16:40:45
**版本**: v1.0
**编写人**: 小沈