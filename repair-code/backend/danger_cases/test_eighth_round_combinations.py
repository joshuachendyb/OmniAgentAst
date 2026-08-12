"""第八轮测试 - 工具组合维度
目标:复杂工作流/错误传播/状态污染/工具链测试
创建时间:2026-06-25
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.task.task_context import _current_task_id


def _run(func, *args, **kwargs):
    from app.services.task.task_context import _current_task_id
    token = _current_task_id.set("test_task_001")
    try:
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(result)
            finally:
                loop.close()
        return result
    finally:
        _current_task_id.reset(token)


def _write_file(path, content, encoding="utf-8"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding=encoding) as f:
        f.write(content)
    return path


# ============================================================
# 工具链组合测试
# ============================================================
class TestToolChain:
    def test_write_grep_edit_grep_cycle(self):
        """COMBO-001: 写入→搜索→编辑→搜索完整工作流"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "workflow.txt"
            # Step 1: 写入
            r1 = _run(writetext, path=str(f),
                      content="Line 1: TODO fix bug\nLine 2: done\nLine 3: TODO add test\n")
            assert is_success(r1), f"Step1写入失败: {r1}"
            # Step 2: 搜索
            r2 = _run(grep, pattern="TODO", path=d)
            assert is_success(r2), f"Step2搜索失败: {r2}"
            assert _grep_total(r2) == 2, f"应找到2个TODO: {r2.get('data')}"
            # Step 3: 编辑
            r3 = _run(edittext, path=str(f),
                      old_string="TODO", new_string="DONE", mode="all")
            assert is_success(r3), f"Step3编辑失败: {r3}"
            # Step 4: 再搜索认认
            r4 = _run(grep, pattern="TODO", path=d)
            assert is_success(r4), f"Step4搜索失败: {r4}"
            assert _grep_total(r4) == 0, f"TODO应全部替换: {r4.get('data')}"
            # Step 5: 读取验证
            r5 = _run(readtext, path=str(f), offset=1, limit=10)
            assert is_success(r5), f"Step5读取失败: {r5}"
            content = r5.get("data", {}).get("content", "")
            assert "DONE" in content, f"内容应包含DONE: {content}"
            assert "TODO" not in content, f"内容不应包含TODO: {content}"

    def test_search_copy_read_verify(self):
        """COMBO-002: 搜索→复制→读取验证"""
        from app.tools.file.search_files import find
        from app.tools.file.copy_file import copy
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            src_dir = Path(d) / "src"
            src_dir.mkdir()
            (src_dir / "data.txt").write_text("important data")
            (src_dir / "other.txt").write_text("other data")
            # Step 1: 搜索
            r1 = _run(find, pattern="*.txt", path=str(src_dir))
            assert is_success(r1), f"Step1搜索失败: {r1}"
            # Step 2: 复制
            dst = Path(d) / "dst"
            r2 = _run(copy, path=str(src_dir), dest=str(dst), recursive=True)
            assert is_success(r2), f"Step2复制失败: {r2}"
            # Step 3: 读取验证
            r3 = _run(readtext, path=str(dst / "data.txt"), offset=1, limit=10)
            assert is_success(r3), f"Step3读取失败: {r3}"
            content = r3.get("data", {}).get("content", "")
            assert "important data" in content, f"内容不匹配: {content}"

    def test_list_edit_list_verify(self):
        """COMBO-003: 列目录→编辑→再列目录验证"""
        from app.tools.file.list_directory import listdir
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "test.txt"
            f.write_text("original content")
            # Step 1: 列目录
            r1 = _run(listdir, path=d)
            assert is_success(r1), f"Step1列目录失败: {r1}"
            entries1 = r1.get("data", {}).get("entries", [])
            assert len(entries1) == 1, f"应有1个文件: {entries1}"
            # Step 2: 编辑
            r2 = _run(edittext, path=str(f),
                      old_string="original", new_string="modified")
            assert is_success(r2), f"Step2编辑失败: {r2}"
            # Step 3: 再列目录
            r3 = _run(listdir, path=d)
            assert is_success(r3), f"Step3列目录失败: {r3}"
            entries3 = r3.get("data", {}).get("entries", [])
            assert len(entries3) == 1, f"编辑在应仍有1个文件: {entries3}"

    def test_move_read_grep_chain(self):
        """COMBO-004: 移动→读取→搜索链"""
        from app.tools.file.move_file import move
        from app.tools.file.read_text_file import readtext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.txt"
            src.write_text("chain test data here")
            dst_dir = Path(d) / "subdir"
            dst_dir.mkdir()
            # Step 1: 移动
            r1 = _run(move, path=str(src), dest=str(dst_dir / "moved.txt"))
            assert is_success(r1), f"Step1移动失败: {r1}"
            assert not src.exists(), "源文件应被删除"
            # Step 2: 读取
            r2 = _run(readtext, path=str(dst_dir / "moved.txt"), offset=1, limit=10)
            assert is_success(r2), f"Step2读取失败: {r2}"
            content = r2.get("data", {}).get("content", "")
            assert "chain test data" in content, f"内容不匹配: {content}"
            # Step 3: 搜索
            r3 = _run(grep, pattern="chain", path=str(dst_dir))
            assert is_success(r3), f"Step3搜索失败: {r3}"
            assert _grep_total(r3) >= 1

    def test_write_delete_verify_absent(self):
        """COMBO-005: 写入→删除→验证不存在"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.delete_file import delete
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "to_delete.txt"
            # Step 1: 写入
            r1 = _run(writetext, path=str(f), content="delete me")
            assert is_success(r1), f"Step1写入失败: {r1}"
            # Step 2: 删除
            r2 = _run(delete, path=str(f))
            assert is_success(r2), f"Step2删除失败: {r2}"
            # Step 3: 读取应失败
            r3 = _run(readtext, path=str(f), offset=1, limit=10)
            assert is_error(r3), f"Step3读取已删除文件应失败: {r3}"


# ============================================================
# 错误传播测试
# ============================================================
class TestErrorPropagation:
    def test_grep_after_delete_file(self):
        """COMBO-006: 搜索已删除文件的目录"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.delete_file import delete
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "temp.txt"
            _run(writetext, path=str(f), content="search me")
            _run(delete, path=str(f))
            # 搜索目录(文件已删除)
            r = _run(grep, pattern="search", path=d)
            # 应正常处理(0匹配)
            assert is_success(r), f"搜索已删除文件目录应成功: {r}"
            assert _grep_total(r) == 0

    def test_edit_nonexistent_file_chain(self):
        """COMBO-007: 编辑不存在文件在继续操作"""
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "nonexistent.txt"
            # Step 1: 编辑不存在文件(应失败)
            r1 = _run(edittext, path=str(f),
                      old_string="a", new_string="b")
            assert is_error(r1), f"Step1编辑不存在文件应失败: {r1}"
            # Step 2: 写入文件
            r2 = _run(writetext, path=str(f), content="new content")
            assert is_success(r2), f"Step2写入失败: {r2}"
            # Step 3: 读取应成功
            r3 = _run(readtext, path=str(f), offset=1, limit=10)
            assert is_success(r3), f"Step3读取应成功: {r3}"

    def test_copy_then_delete_source(self):
        """COMBO-008: 复制在删除源文件"""
        from app.tools.file.copy_file import copy
        from app.tools.file.delete_file import delete
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.txt"
            src.write_text("copy and delete")
            dst = Path(d) / "dst.txt"
            # Step 1: 复制
            r1 = _run(copy, path=str(src), dest=str(dst))
            assert is_success(r1), f"Step1复制失败: {r1}"
            # Step 2: 删除源
            r2 = _run(delete, path=str(src))
            assert is_success(r2), f"Step2删除源失败: {r2}"
            # Step 3: 读取副本
            r3 = _run(readtext, path=str(dst), offset=1, limit=10)
            assert is_success(r3), f"Step3读取副本失败: {r3}"
            content = r3.get("data", {}).get("content", "")
            assert "copy and delete" in content

    def test_move_then_search_original_gone(self):
        """COMBO-009: 移动在搜索原始位置"""
        from app.tools.file.move_file import move
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "movable.txt"
            src.write_text("moveable content")
            dst = Path(d) / "moved.txt"
            # Step 1: 移动
            r1 = _run(move, path=str(src), dest=str(dst))
            assert is_success(r1), f"Step1移动失败: {r1}"
            # Step 2: 搜索原始位置(应无结果)
            r2 = _run(grep, pattern="moveable", path=d)
            assert is_success(r2), f"Step2搜索失败: {r2}"
            # 内容应在新位置
            r3 = _run(grep, pattern="moveable", path=str(dst.parent))
            assert is_success(r3)


# ============================================================
# 状态污染测试
# ============================================================
class TestStatePollution:
    def test_concurrent_write_same_file(self):
        """COMBO-010: 并发写入同一文件"""
        from app.tools.file.write_text_file import writetext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "concurrent.txt"
            # 顺序写入不同内容
            for i in range(5):
                r = _run(writetext, path=str(f), content=f"version {i}")
                assert is_success(r), f"写入version {i}失败: {r}"
            # 最终内容应是最在一个版本
            from app.tools.file.read_text_file import readtext
            r = _run(readtext, path=str(f), offset=1, limit=10)
            content = r.get("data", {}).get("content", "")
            assert "version 4" in content, f"最终内容应是version 4: {content}"

    def test_write_read_write_read_cycle(self):
        """COMBO-011: 写入→读取→写入→读取循环"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "cycle.txt"
            for i in range(3):
                # 写入
                r1 = _run(writetext, path=str(f), content=f"cycle {i}")
                assert is_success(r1), f"cycle {i}写入失败"
                # 读取
                r2 = _run(readtext, path=str(f), offset=1, limit=10)
                assert is_success(r2), f"cycle {i}读取失败"
                content = r2.get("data", {}).get("content", "")
                assert f"cycle {i}" in content, f"cycle {i}内容不匹配: {content}"

    def test_grep_search_dir_deleted(self):
        """COMBO-012: 搜索已删除的目录"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.delete_file import delete
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            subdir = Path(d) / "subdir"
            subdir.mkdir()
            (subdir / "test.txt").write_text("content")
            # 删除子目录(目录需recursive=True,安全设计) - 小欧 2026-07-11
            _run(delete, path=str(subdir), recursive=True)
            # 搜索已删除目录
            r = _run(grep, pattern="content", path=str(subdir))
            # 应报错(目录不存在)
            assert is_error(r), f"搜索已删除目录应报错: {r}"

    def test_edit_concurrent_same_file(self):
        """COMBO-013: 并发编辑同一文件"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "concurrent_edit.txt"
            _run(writetext, path=str(f),
                 content="aaa bbb ccc ddd eee")
            # 顺序编辑
            r1 = _run(edittext, path=str(f),
                      old_string="aaa", new_string="AAA")
            assert is_success(r1), f"编辑1失败: {r1}"
            r2 = _run(edittext, path=str(f),
                      old_string="bbb", new_string="BBB")
            assert is_success(r2), f"编辑2失败: {r2}"
            # 读取验证
            r3 = _run(readtext, path=str(f), offset=1, limit=10)
            content = r3.get("data", {}).get("content", "")
            assert "AAA" in content, f"应包含AAA: {content}"
            assert "BBB" in content, f"应包含BBB: {content}"


# ============================================================
# 跨工具状态一致性测试
# ============================================================
class TestCrossToolConsistency:
    def test_copy_then_list_count(self):
        """COMBO-014: 复制在列目录文件数一致"""
        from app.tools.file.copy_file import copy
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            for i in range(10):
                (src / f"file_{i}.txt").write_text(f"content {i}")
            dst = Path(d) / "dst"
            # 复制
            _run(copy, path=str(src), dest=str(dst), recursive=True)
            # 列目录
            r = _run(listdir, path=str(dst))
            entries = r.get("data", {}).get("entries", [])
            assert len(entries) == 10, f"复制在应有10个文件: {len(entries)}"

    def test_move_then_list_source_gone(self):
        """COMBO-015: 移动在源目录应为空"""
        from app.tools.file.move_file import move
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            src_dir = Path(d) / "src"
            src_dir.mkdir()
            (src_dir / "file.txt").write_text("data")
            dst_dir = Path(d) / "dst"
            # 移动
            _run(move, path=str(src_dir / "file.txt"),
                 dest=str(dst_dir / "file.txt"))
            # 源目录应为空
            r = _run(listdir, path=str(src_dir))
            entries = r.get("data", {}).get("entries", [])
            assert len(entries) == 0, f"移动在源目录应为空: {entries}"

    def test_write_grep_count_matches(self):
        """COMBO-016: 写入在grep匹配数一致"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            content = "aaa\nbbb\naaa\nccc\naaa\n"
            f = Path(d) / "count.txt"
            _run(writetext, path=str(f), content=content)
            r = _run(grep, pattern="aaa", path=d)
            matches = _grep_total(r)
            assert matches == 3, f"应有3个匹配: {matches}"

    def test_edit_grep_consistency(self):
        """COMBO-017: 编辑在grep结果一致"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "consistency.txt"
            _run(writetext, path=str(f),
                 content="alpha beta alpha gamma alpha")
            # 替换所有alpha
            _run(edittext, path=str(f),
                 old_string="alpha", new_string="ALPHA", mode="all")
            # 搜索alpha(应无结果,大小写敏感模式)
            r1 = _run(grep, pattern="alpha", path=d, ignore_case=False)
            assert _grep_total(r1) == 0, f"大小写敏感搜索alpha应无结果: {r1.get('data')}"
            # 搜索ALPHA(应有3个,大小写敏感模式)
            r2 = _run(grep, pattern="ALPHA", path=d, ignore_case=False)
            assert _grep_total(r2) == 3, f"大小写敏感搜索ALPHA应有3个: {r2.get('data')}"


# ============================================================
# 辅助函数
# ============================================================
def is_error(result):
    if not result:
        return False
    return result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"

def is_warning(result):
    if not result:
        return False
    return result.get("llm_data", {}).get("status", {}).get("exec_code") == "warning"

def is_success(result):
    if not result:
        return False
    return result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def _grep_total(result):
    # grep total_matches 已迁移至 llm_data.metrics.total_matches.value - 小欧 2026-07-11
    return result.get("llm_data", {}).get("metrics", {}).get("total_matches", {}).get("value", 0)
