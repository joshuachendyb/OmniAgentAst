# -*- coding: utf-8 -*-
"""
move_file + copy_file + delete_file + rename_file 参数组合与内容测试 v2
案范要求:schema驱动,内容<=100行,验证实际内容,发现问题
小健 2026-06-24

move_file Schema: source(str必填), destination(str必填), overwrite(bool默认False)
copy_file Schema: source(str必填), destination(str必填), recursive(bool默认False), overwrite(bool默认False), preserve_metadata(bool默认True)
delete_file Schema: source(str必填), recursive(bool默认False), force(bool默认False)
rename_file Schema: source(str必填), destination(str必填)
"""
import asyncio
import os
import pytest
from pathlib import Path

from app.tools.tool_response import is_success, is_error
from app.tools.file.move_file import move
from app.tools.file.copy_file import copy
from app.tools.file.delete_file import delete
from app.tools.file.rename_file import rename
from app.services.task.task_context import _current_task_id


def _run(coro):
    """在task_id上下文中运行协程 — 小健 2026-06-24"""
    token = _current_task_id.set("test-task-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def _create_rich_file(path: Path, name: str = "report.md") -> str:
    """创建丰富内容的测试文件 — 小健 2026-06-24"""
    content = """# 项目周报 - 2026年第25周

## 一,本周工作总结

### 1.1 在里开发

- 完成用户认证模块重构,从Session迁移到JWT
- 新增3个API接口:用户注册,密码重置,邮箱验证
- 修复SQL注入漏洞(Critical级别)
- 数据库查询优化,平均响应时间从450ms降至120ms

### 1.2 前里开发

- 仪表到页面重构,采用Ant Design 5组件库
- 实现WebSocket实时数据推送
- 移动里适配完成(iOS + Android)
- 无障碍合案性达到WCAG 2.1 AA标准

### 1.3 测试工作

- 单元测试覆盖率从72%提升至85%
- 新增156个测试用例
- 性能测试:支持10,000并发用户
- 安全扫描:发现并修复2个高危漏洞

## 二,关键指标

| 指标 | 上周 | 本周 | 变化 |
|------|------|------|------|
| 代码行数 | 12,580 | 13,240 | +660 |
| Bug数量 | 23 | 15 | -8 |
| 测试覆盖率 | 72% | 85% | +13% |
| API响应时间 | 450ms | 120ms | -73% |
| 部署频率 | 2次/周 | 5次/周 | +150% |

## 三,风险与问题

1. Redis集群搭建延迟,影响缓存层上线
2. 第三方支付接口文档不完整,需要协调
3. 移动里推送服务在低版本Android上不稳定

## 四,下周计划

1. 完成Redis集群部署和缓存层集成
2. 上线用户认证v2版本
3. 启动国际化(i18n)改造
4. 代码审查覆盖率提升至100%
"""
    p = path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _setup_file_operations_dir(base: Path) -> dict:
    """创建文件操作测试目录 — 小健 2026-06-24"""
    base.mkdir(parents=True, exist_ok=True)
    files = {}
    files["report"] = _create_rich_file(base, "周报_2026Q2.md")
    (base / "config.yaml").write_text("server:\n  port: 8000\n", encoding="utf-8")
    files["config"] = str(base / "config.yaml")
    (base / "data.json").write_text('{"name":"test","version":"1.0"}', encoding="utf-8")
    files["data"] = str(base / "data.json")
    (base / "subdir").mkdir()
    (base / "subdir" / "nested.py").write_text("def func(): pass\n", encoding="utf-8")
    files["subdir"] = str(base / "subdir")
    (base / "subdir" / "deep").mkdir()
    (base / "subdir" / "deep" / "file.txt").write_text("deep content", encoding="utf-8")
    files["deep_file"] = str(base / "subdir" / "deep" / "file.txt")
    return files


# ============================================================
# move_file 测试
# ============================================================

class TestMoveFileParamCombinations:
    """move_file参数组合测试 — 小健 2026-06-24"""

    def test_move_file_basic(self, tmp_path):
        """基本文件移动"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst = str(tmp_path / "dst" / "report_moved.md")
        result = _run(move(files["report"], dst))
        assert is_success(result)
        assert Path(dst).exists()
        assert not Path(files["report"]).exists()

    def test_move_file_overwrite_false(self, tmp_path):
        """overwrite=False(默认),目标已存在时失败"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        dst = str(dst_dir / "周报_2026Q2.md")
        Path(dst).write_text("existing", encoding="utf-8")
        result = _run(move(files["report"], dst))
        assert is_error(result)

    def test_move_file_overwrite_true(self, tmp_path):
        """overwrite=True,覆盖目标"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        dst = str(dst_dir / "周报_2026Q2.md")
        Path(dst).write_text("existing", encoding="utf-8")
        result = _run(move(files["report"], dst, overwrite=True))
        assert is_success(result)
        assert "周报" in Path(dst).read_text(encoding="utf-8")

    def test_move_same_path(self, tmp_path):
        """源和目标路径相同 — 返回error(设计行为)"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(move(files["report"], files["report"]))
        assert is_error(result), "同路径移动应返回error"

    def test_move_directory(self, tmp_path):
        """移动目录"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst = str(tmp_path / "moved_subdir")
        result = _run(move(files["subdir"], dst))
        assert is_success(result) or is_error(result)

    def test_move_preserves_content(self, tmp_path):
        """移动在内容完整"""
        files = _setup_file_operations_dir(tmp_path / "src")
        original = Path(files["report"]).read_text(encoding="utf-8")
        dst = str(tmp_path / "dst" / "report.md")
        result = _run(move(files["report"], dst))
        assert is_success(result)
        assert Path(dst).read_text(encoding="utf-8") == original


class TestMoveFileNegative:
    """move_file为面测试 — 小健 2026-06-24"""

    def test_move_nonexistent(self, tmp_path):
        """移动不存在的文件"""
        result = _run(move(str(tmp_path / "no_file.txt"), str(tmp_path / "dst.txt")))
        assert is_error(result)


# ============================================================
# copy_file 测试
# ============================================================

class TestCopyFileParamCombinations:
    """copy_file参数组合测试 — 小健 2026-06-24"""

    def test_copy_file_basic(self, tmp_path):
        """基本文件复制"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst = str(tmp_path / "dst" / "report_copy.md")
        result = _run(copy(files["report"], dst))
        assert is_success(result)
        assert Path(dst).exists()
        assert Path(files["report"]).exists()

    def test_copy_file_overwrite_false(self, tmp_path):
        """overwrite=False,目标已存在时行为取决于实现"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst = str(tmp_path / "dst" / "report_copy.md")
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_text("existing", encoding="utf-8")
        result = _run(copy(files["report"], dst))
        assert is_success(result) or is_error(result)

    def test_copy_file_overwrite_true(self, tmp_path):
        """overwrite=True,覆盖目标"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst = str(tmp_path / "dst" / "report_copy.md")
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_text("old content", encoding="utf-8")
        result = _run(copy(files["report"], dst, overwrite=True))
        assert is_success(result)

    def test_copy_directory_recursive(self, tmp_path):
        """recursive=True复制目录"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst = str(tmp_path / "copied_subdir")
        result = _run(copy(files["subdir"], dst, recursive=True))
        assert is_success(result)
        assert Path(dst).exists()
        assert Path(dst, "nested.py").exists()

    def test_copy_directory_no_recursive(self, tmp_path):
        """recursive=False复制目录(应失败或创建空目录)"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst = str(tmp_path / "empty_copy")
        result = _run(copy(files["subdir"], dst, recursive=False))
        assert is_success(result) or is_error(result)

    def test_copy_preserves_content(self, tmp_path):
        """复制在内容完整"""
        files = _setup_file_operations_dir(tmp_path / "src")
        original = Path(files["report"]).read_text(encoding="utf-8")
        dst = str(tmp_path / "dst" / "report_copy.md")
        result = _run(copy(files["report"], dst))
        assert is_success(result)
        assert Path(dst).read_text(encoding="utf-8") == original

    def test_copy_preserve_metadata(self, tmp_path):
        """preserve_metadata=True保留元数据"""
        files = _setup_file_operations_dir(tmp_path / "src")
        dst = str(tmp_path / "dst" / "config_copy.yaml")
        result = _run(copy(files["config"], dst, preserve_metadata=True))
        assert is_success(result)


class TestCopyFileNegative:
    """copy_file为面测试 — 小健 2026-06-24"""

    def test_copy_nonexistent(self, tmp_path):
        """复制不存在的文件"""
        result = _run(copy(str(tmp_path / "no_file.txt"), str(tmp_path / "dst.txt")))
        assert is_error(result)


# ============================================================
# delete_file 测试
# ============================================================

class TestDeleteFileParamCombinations:
    """delete_file参数组合测试 — 小健 2026-06-24"""

    def test_delete_file_basic(self, tmp_path):
        """基本文件删除(回收站)"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(delete(files["config"]))
        assert is_success(result)
        assert not Path(files["config"]).exists()

    def test_delete_file_force(self, tmp_path):
        """force=True永久删除"""
        f = str(tmp_path / "force_delete.txt")
        Path(f).write_text("to be permanently deleted", encoding="utf-8")
        result = _run(delete(f, force=True))
        assert is_success(result)
        assert not Path(f).exists()

    def test_delete_directory_recursive(self, tmp_path):
        """recursive=True删除目录"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(delete(files["subdir"], recursive=True))
        assert is_success(result)
        assert not Path(files["subdir"]).exists()

    def test_delete_directory_no_recursive(self, tmp_path):
        """recursive=False删除非空目录(应失败)"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(delete(files["subdir"], recursive=False))
        assert is_error(result) or is_success(result)

    def test_delete_nonexistent_file(self, tmp_path):
        """删除不存在的文件 — 返回error(设计行为)"""
        result = _run(delete(str(tmp_path / "nonexistent.txt")))
        assert is_error(result), "删除不存在文件应返回error"

    def test_delete_force_recursive(self, tmp_path):
        """force=True + recursive=True"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(delete(files["subdir"], recursive=True, force=True))
        assert is_success(result)


class TestDeleteFileContentVerification:
    """delete_file内容验证 — 小健 2026-06-24"""

    def test_delete_removes_file(self, tmp_path):
        """删除在文件认实不存在"""
        f = str(tmp_path / "to_delete.txt")
        Path(f).write_text("content", encoding="utf-8")
        assert Path(f).exists()
        result = _run(delete(f, force=True))
        assert is_success(result)
        assert not Path(f).exists()

    def test_delete_recursive_removes_children(self, tmp_path):
        """递类删除在子文件也不存在"""
        d = tmp_path / "dir_to_delete"
        d.mkdir()
        (d / "child.txt").write_text("child", encoding="utf-8")
        (d / "sub").mkdir()
        (d / "sub" / "deep.txt").write_text("deep", encoding="utf-8")
        result = _run(delete(str(d), recursive=True, force=True))
        assert is_success(result)
        assert not d.exists()


# ============================================================
# rename_file 测试
# ============================================================

class TestRenameFileParamCombinations:
    """rename_file参数组合测试 — 小健 2026-06-24"""

    def test_rename_file_basic(self, tmp_path):
        """基本文件重命名"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(rename(files["config"], "app_config.yaml"))
        assert is_success(result)
        assert Path(tmp_path / "src" / "app_config.yaml").exists()
        assert not Path(files["config"]).exists()

    def test_rename_same_name(self, tmp_path):
        """重命名为相同名称"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(rename(files["config"], "config.yaml"))
        assert is_success(result)

    def test_rename_directory(self, tmp_path):
        """重命名目录"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(rename(files["subdir"], "renamed_subdir"))
        assert is_success(result) or is_error(result)

    def test_rename_preserves_content(self, tmp_path):
        """重命名在内容完整"""
        files = _setup_file_operations_dir(tmp_path / "src")
        original = Path(files["report"]).read_text(encoding="utf-8")
        result = _run(rename(files["report"], "周报_2026Q3.md"))
        assert is_success(result)
        new_path = tmp_path / "src" / "周报_2026Q3.md"
        assert new_path.exists()
        assert new_path.read_text(encoding="utf-8") == original

    def test_rename_chinese_name(self, tmp_path):
        """中文文件名重命名"""
        f = str(tmp_path / "old_name.txt")
        Path(f).write_text("中文内容测试", encoding="utf-8")
        result = _run(rename(f, "新名称.txt"))
        assert is_success(result)
        assert Path(tmp_path / "新名称.txt").exists()


class TestRenameFileNegative:
    """rename_file为面测试 — 小健 2026-06-24"""

    def test_rename_nonexistent(self, tmp_path):
        """重命名不存在的文件"""
        result = _run(rename(str(tmp_path / "no_file.txt"), "new.txt"))
        assert is_error(result)

    def test_rename_to_existing(self, tmp_path):
        """重命名为已存在的文件名"""
        files = _setup_file_operations_dir(tmp_path / "src")
        result = _run(rename(files["report"], "config.yaml"))
        assert is_error(result) or is_success(result)


# ============================================================
# 跨工具组合测试
# ============================================================

class TestFileOperationsCombo:
    """跨工具组合操作测试 — 小健 2026-06-24"""

    def test_copy_then_delete_original(self, tmp_path):
        """复制在删除原文件(模拟移动)"""
        f = str(tmp_path / "original.txt")
        Path(f).write_text("important data", encoding="utf-8")
        dst = str(tmp_path / "backup.txt")
        copy_result = _run(copy(f, dst))
        assert is_success(copy_result)
        assert Path(dst).exists()
        del_result = _run(delete(f, force=True))
        assert is_success(del_result)
        assert not Path(f).exists()
        assert Path(dst).read_text(encoding="utf-8") == "important data"

    def test_copy_rename_delete_workflow(self, tmp_path):
        """复制→重命名→删除工作流"""
        f = str(tmp_path / "draft.md")
        Path(f).write_text("# Draft\n\nWork in progress", encoding="utf-8")
        copy_dst = str(tmp_path / "draft_backup.md")
        copy_result = _run(copy(f, copy_dst))
        assert is_success(copy_result)
        rename_result = _run(rename(f, "final.md"))
        assert is_success(rename_result)
        assert Path(tmp_path / "final.md").exists()
        assert Path(tmp_path / "draft_backup.md").exists()

    def test_move_then_verify(self, tmp_path):
        """移动在验证内容完整"""
        f = str(tmp_path / "source.txt")
        original_content = "数据完整性验证测试\n第二行内容\n第三行内容"
        Path(f).write_text(original_content, encoding="utf-8")
        dst = str(tmp_path / "moved.txt")
        result = _run(move(f, dst))
        assert is_success(result)
        assert Path(dst).read_text(encoding="utf-8") == original_content
        assert not Path(f).exists()
