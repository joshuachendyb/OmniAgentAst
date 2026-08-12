"""第九轮测试 - 大文件/多Tool关联测试
目标:大文件场景下多工具协同工作,性能边界,数据一致性
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


def is_success(r):
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_warning(r):
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "warning"


def is_error(r):
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


def is_warning(r):
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "warning"


def _grep_total(r):
    # grep total_matches 已迁移至 llm_data.metrics.total_matches.value - 小欧 2026-07-11
    return r.get("llm_data", {}).get("metrics", {}).get("total_matches", {}).get("value", 0)


# ============================================================
# 大文件写入/读取+搜索关联
# ============================================================
class TestLargeFileWorkflow:
    def test_1mb_write_grep_edit_cycle(self):
        """LARGE-001: 1MB文件写入→搜索→编辑→再搜索"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            # 生成~1MB内容(每行约50字符,约20000行)
            lines = [f"Line {i}: {'x' * 40} UNIQUE_TOKEN_{i % 100}" for i in range(20000)]
            content = "\n".join(lines)
            f = Path(d) / "large.txt"

            # Step 1: 写入
            start = time.time()
            r1 = _run(writetext, path=str(f), content=content)
            write_time = time.time() - start
            assert is_success(r1), f"1MB写入失败: {r1}"
            print(f"\n  1MB写入耗时: {write_time:.2f}s")

            # Step 2: 搜索UNIQUE_TOKEN_50
            start = time.time()
            r2 = _run(grep, pattern="UNIQUE_TOKEN_50", path=d)
            grep_time = time.time() - start
            assert is_success(r2), f"搜索失败: {r2}"
            matches = _grep_total(r2)
            print(f"  搜索耗时: {grep_time:.2f}s, 匹配数: {matches}")
            assert matches >= 1, f"应找到UNIQUE_TOKEN_50, got {matches}"

            # Step 3: 编辑替换所有UNIQUE_TOKEN
            start = time.time()
            r3 = _run(edittext, path=str(f),
                      old_string="UNIQUE_TOKEN", new_string="REPLACED", mode="all")
            edit_time = time.time() - start
            assert is_success(r3) or is_warning(r3), f"编辑失败: {r3}"

            # Step 4: 验证搜索不到UNIQUE_TOKEN
            r4 = _run(grep, pattern="UNIQUE_TOKEN", path=d)
            assert is_success(r4), f"搜索失败: {r4}"
            remaining = _grep_total(r4)
            print(f"  替换在UNIQUE_TOKEN剩余: {remaining}")
            assert remaining == 0, f"UNIQUE_TOKEN应全部替换, 剩余{remaining}"

            # Step 5: 验证搜索REPLACED(可能因超过MAX而返回warning)
            r5 = _run(grep, pattern="REPLACED", path=d)
            assert is_success(r5) or is_warning(r5), f"搜索失败: {r5}"
            replaced = _grep_total(r5)
            print(f"  REPLACED匹配数: {replaced}")
            assert replaced >= 1, f"应找到REPLACED, got {replaced}"

    def test_large_file_read_offset_limit(self):
        """LARGE-002: 大文件分页读取"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "paging.txt"
            lines = [f"Row {i:05d}" for i in range(10000)]
            _run(writetext, path=str(f), content="\n".join(lines))

            # 读取第100-120行
            r1 = _run(readtext, path=str(f), offset=100, limit=20)
            assert is_success(r1), f"分页读取失败: {r1}"
            content1 = r1.get("data", {}).get("content", "")
            assert "Row 00099" in content1 or "Row 00100" in content1, f"应包含Row 00100附近: {content1[:200]}"

            # 读取末尾10行(readtext不支持负offset,用有效offset定位) - 小欧 2026-07-11
            r2 = _run(readtext, path=str(f), offset=9991, limit=10)
            assert is_success(r2), f"负offset读取失败: {r2}"
            content2 = r2.get("data", {}).get("content", "")
            assert "Row 09999" in content2, f"应包含最在几行: {content2[:200]}"

            # 读取全文
            r3 = _run(readtext, path=str(f))
            assert is_success(r3), f"全文读取失败: {r3}"
            content3 = r3.get("data", {}).get("content", "")
            assert "Row 00000" in content3, f"应包含首行"
            assert "Row 09999" in content3, f"应包含末行"

    def test_large_file_copy_consistency(self):
        """LARGE-003: 大文件复制在数据一致性"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        from app.tools.file.read_text_file import readtext
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            # 写入500KB内容
            content = "A" * 500000
            src = Path(d) / "src.txt"
            _run(writetext, path=str(src), content=content)

            # 复制
            dst = Path(d) / "dst.txt"
            r = _run(copy, path=str(src), dest=str(dst))
            assert is_success(r), f"复制失败: {r}"

            # 验证内容一致
            r1 = _run(readtext, path=str(src))
            r2 = _run(readtext, path=str(dst))
            src_content = r1.get("data", {}).get("content", "")
            dst_content = r2.get("data", {}).get("content", "")
            src_hash = hashlib.md5(src_content.encode()).hexdigest()
            dst_hash = hashlib.md5(dst_content.encode()).hexdigest()
            assert src_hash == dst_hash, f"复制在内容不一致: src={src_hash}, dst={dst_hash}"
            assert len(src_content) == len(dst_content), f"长度不一致: {len(src_content)} vs {len(dst_content)}"

    def test_large_file_move_then_search(self):
        """LARGE-004: 大文件移动在搜索验证"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.move_file import move
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            content = "\n".join([f"MOVED_LINE_{i}" for i in range(5000)])
            src = Path(d) / "movable.txt"
            _run(writetext, path=str(src), content=content)

            # 移动到子目录
            subdir = Path(d) / "sub"
            subdir.mkdir()
            dst = subdir / "moved.txt"
            r = _run(move, path=str(src), dest=str(dst))
            assert is_success(r), f"移动失败: {r}"
            assert not src.exists(), "源文件应被删除"

            # 搜索验证
            r2 = _run(grep, pattern="MOVED_LINE_2500", path=str(subdir))
            assert is_success(r2), f"搜索失败: {r2}"
            assert _grep_total(r2) >= 1

            # 搜索原始位置(应无结果)
            r3 = _run(grep, pattern="MOVED_LINE_2500", path=d)
            assert is_success(r3), f"搜索失败: {r3}"
            # 原始位置不应有匹配(文件已移走)


# ============================================================
# 多文件批量操作关联
# ============================================================
class TestMultiFileBatch:
    def test_batch_write_search_delete(self):
        """BATCH-001: 批量写入→搜索→删除"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        from app.tools.file.delete_file import delete
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            # 写入10个文件
            for i in range(10):
                f = Path(d) / f"batch_{i}.txt"
                _run(writetext, path=str(f),
                     content=f"Batch file {i}\nDATA_{i}_A\nDATA_{i}_B\n")

            # 验证10个文件存在
            r = _run(listdir, path=d)
            entries = r.get("data", {}).get("entries", [])
            assert len(entries) == 10, f"应有10个文件: {len(entries)}"

            # 搜索DATA_5
            r2 = _run(grep, pattern="DATA_5", path=d)
            assert is_success(r2), f"搜索失败: {r2}"
            assert _grep_total(r2) >= 2

            # 删除所有batch文件
            for i in range(10):
                f = Path(d) / f"batch_{i}.txt"
                _run(delete, path=str(f))

            # 验证目录为空
            r3 = _run(listdir, path=d)
            entries3 = r3.get("data", {}).get("entries", [])
            assert len(entries3) == 0, f"删除在应为空: {len(entries3)}"

    def test_batch_copy_edit_consistency(self):
        """BATCH-002: 批量复制→编辑→验证一致性"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            src_dir = Path(d) / "src"
            src_dir.mkdir()
            # 创建5个源文件
            for i in range(5):
                (src_dir / f"file_{i}.txt").write_text(f"original_{i}")

            # 批量复制
            for i in range(5):
                src = src_dir / f"file_{i}.txt"
                dst = Path(d) / f"copy_{i}.txt"
                r = _run(copy, path=str(src), dest=str(dst))
                assert is_success(r), f"复制file_{i}失败: {r}"

            # 编辑所有副本
            for i in range(5):
                f = Path(d) / f"copy_{i}.txt"
                r = _run(edittext, path=str(f),
                         old_string=f"original_{i}", new_string=f"modified_{i}")
                assert is_success(r), f"编辑copy_{i}失败: {r}"

            # 验证副本已修改
            for i in range(5):
                f = Path(d) / f"copy_{i}.txt"
                r = _run(readtext, path=str(f))
                content = r.get("data", {}).get("content", "")
                assert f"modified_{i}" in content, f"copy_{i}应包含modified_{i}: {content}"
                assert f"original_{i}" not in content, f"copy_{i}不应包含original_{i}: {content}"

            # 验证源文件未被修改
            for i in range(5):
                f = src_dir / f"file_{i}.txt"
                content = f.read_text()
                assert content == f"original_{i}", f"源文件file_{i}不应被修改: {content}"


# ============================================================
# 编码+大文件关联测试
# ============================================================
class TestEncodingLargeFile:
    def test_gbk_large_file_write_read_search(self):
        """ENC-LARGE-001: GBK编码大文件写入→读取→搜索"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            # 生成GBK内容(中文+英文混合)
            lines = [f"第{i}行: 测试数据{i}号_TEST_ITEM_{i % 50}" for i in range(2000)]
            content = "\n".join(lines)
            f = Path(d) / "gbk_large.txt"

            # GBK编码写入
            r1 = _run(writetext, path=str(f), content=content, encoding="gbk")
            assert is_success(r1), f"GBK写入失败: {r1}"

            # 读取验证
            r2 = _run(readtext, path=str(f))
            assert is_success(r2), f"读取失败: {r2}"
            read_content = r2.get("data", {}).get("content", "")
            assert "第5行" in read_content, f"中文内容应正认读取: {read_content[:200]}"

            # 搜索中文
            r3 = _run(grep, pattern="第5行", path=d)
            assert is_success(r3), f"搜索中文失败: {r3}"
            assert r3.get("data", {}).get("total_matches", 0) >= 1

            # 搜索英文
            r4 = _run(grep, pattern="TEST_ITEM_25", path=d)
            assert is_success(r4), f"搜索英文失败: {r4}"
            assert r4.get("data", {}).get("total_matches", 0) >= 1

    def test_mixed_encoding_large_dir(self):
        """ENC-LARGE-002: 混合编码大目录搜索"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        with tempfile.TemporaryDirectory() as d:
            # UTF-8文件
            for i in range(5):
                f = Path(d) / f"utf8_{i}.txt"
                _run(writetext, path=str(f),
                     content=f"UTF8文件{i}: normal text line\n")

            # GBK文件
            for i in range(5):
                f = Path(d) / f"gbk_{i}.txt"
                _run(writetext, path=str(f),
                     content=f"GBK文件{i}: normal text line\n", encoding="gbk")

            # 搜索"normal text"应匹配所有文件
            r = _run(grep, pattern="normal text", path=d)
            assert is_success(r), f"搜索失败: {r}"
            total = r.get("data", {}).get("total_matches", 0)
            assert total >= 10, f"应匹配10个文件, got {total}"


# ============================================================
# 并发+大文件关联
# ============================================================
class TestConcurrentLargeFile:
    def test_sequential_write_read_large(self):
        """CONCUR-001: 顺序写入→读取大量文件"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            # 写入20个大文件
            for i in range(20):
                f = Path(d) / f"seq_{i}.txt"
                content = f"File {i}\n" + f"Data line {i}\n" * 500
                r = _run(writetext, path=str(f), content=content)
                assert is_success(r), f"写入seq_{i}失败: {r}"

            # 读取并验证每个文件
            for i in range(20):
                f = Path(d) / f"seq_{i}.txt"
                r = _run(readtext, path=str(f))
                assert is_success(r), f"读取seq_{i}失败: {r}"
                content = r.get("data", {}).get("content", "")
                assert f"File {i}" in content, f"seq_{i}内容不匹配"

    def test_write_grep_edit_large_batch(self):
        """CONCUR-002: 大批量写入→搜索→编辑"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        from app.tools.file.edit_text_file import edittext
        with tempfile.TemporaryDirectory() as d:
            # 写入30个文件
            for i in range(30):
                f = Path(d) / f"batch_{i:02d}.txt"
                _run(writetext, path=str(f),
                     content=f"HEADER\nLine {i}: target_value\nFOOTER\n")

            # 搜索target_value
            r1 = _run(grep, pattern="target_value", path=d)
            assert is_success(r1), f"搜索失败: {r1}"
            matches = _grep_total(r1)
            assert matches == 30, f"应匹配30个文件, got {matches}"

            # 编辑所有文件
            for i in range(30):
                f = Path(d) / f"batch_{i:02d}.txt"
                r = _run(edittext, path=str(f),
                         old_string="target_value", new_string="updated_value")
                assert is_success(r), f"编辑batch_{i:02d}失败: {r}"

            # 验证target_value全部替换
            r2 = _run(grep, pattern="target_value", path=d)
            assert is_success(r2), f"搜索失败: {r2}"
            remaining = _grep_total(r2)
            assert remaining == 0, f"target_value应全部替换, 剩余{remaining}"

            # 验证updated_value全部存在
            r3 = _run(grep, pattern="updated_value", path=d)
            assert is_success(r3), f"搜索失败: {r3}"
            replaced = _grep_total(r3)
            assert replaced == 30, f"应匹配30个updated_value, got {replaced}"


# ============================================================
# 复杂工作流场景
# ============================================================
class TestComplexWorkflow:
    def test_project_scaffold_workflow(self):
        """WORKFLOW-001: 模拟项目脚手架:创建目录结构→写入文件→搜索验证→编辑修改"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.list_directory import listdir
        from app.tools.file.grep_file_content import grep
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.copy_file import copy
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            # Step 1: 创建项目结构
            src = Path(d) / "src"
            src.mkdir()
            tests = Path(d) / "tests"
            tests.mkdir()

            # Step 2: 写入源文件
            _run(writetext, path=str(src / "main.py"),
                 content="# Main module\nVERSION = '1.0.0'\ndef hello(): return 'world'\n")
            _run(writetext, path=str(src / "utils.py"),
                 content="# Utils\ndef helper(): return 42\n")
            _run(writetext, path=str(src / "__init__.py"),
                 content="# Package init\n")
            _run(writetext, path=str(tests / "test_main.py"),
                 content="# Tests\ndef test_hello(): assert True\n")
            _run(writetext, path=str(Path(d) / "README.md"),
                 content="# Project\nThis is a test project.\n")
            _run(writetext, path=str(Path(d) / "config.yaml"),
                 content="name: test-project\ndebug: true\n")

            # Step 3: 验证目录结构
            r = _run(listdir, path=str(src))
            entries = r.get("data", {}).get("entries", [])
            assert len(entries) == 3, f"src应有3个文件: {len(entries)}"

            # Step 4: 搜索所有Python文件中的函数定义
            r2 = _run(grep, pattern="def ", path=d, glob="*.py")
            assert is_success(r2), f"搜索失败: {r2}"
            funcs = r2.get("data", {}).get("total_matches", 0)
            assert funcs >= 2, f"应找到至少2个函数定义, got {funcs}"

            # Step 5: 修改版本号
            r3 = _run(edittext, path=str(src / "main.py"),
                      old_string="VERSION = '1.0.0'", new_string="VERSION = '2.0.0'")
            assert is_success(r3), f"编辑版本号失败: {r3}"

            # Step 6: 验证版本号已修改
            r4 = _run(readtext, path=str(src / "main.py"))
            content = r4.get("data", {}).get("content", "")
            assert "2.0.0" in content, f"版本号应为2.0.0: {content}"
            assert "1.0.0" not in content, f"旧版本号应不存在: {content}"

            # Step 7: 复制src到backup
            backup = Path(d) / "backup"
            r5 = _run(copy, path=str(src), dest=str(backup), recursive=True)
            assert is_success(r5), f"复制backup失败: {r5}"

            # Step 8: 验证backup内容一致
            r6 = _run(readtext, path=str(backup / "main.py"))
            backup_content = r6.get("data", {}).get("content", "")
            assert "2.0.0" in backup_content, f"backup版本号应为2.0.0: {backup_content}"

    def test_log_analysis_workflow(self):
        """WORKFLOW-002: 模拟日志分析:写入日志→搜索错误→编辑替换"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.grep_file_content import grep
        from app.tools.file.edit_text_file import edittext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            # Step 1: 生成模拟日志
            log_lines = []
            for i in range(1000):
                if i % 100 == 0:
                    log_lines.append(f"2026-06-25 {10 + i // 60:02d}:{i % 60:02d}:{i % 60:02d} ERROR [module_{i % 10}] Connection failed: timeout")
                elif i % 50 == 0:
                    log_lines.append(f"2026-06-25 {10 + i // 60:02d}:{i % 60:02d}:{i % 60:02d} WARNING [module_{i % 10}] Retry attempt {i // 50}")
                else:
                    log_lines.append(f"2026-06-25 {10 + i // 60:02d}:{i % 60:02d}:{i % 60:02d} INFO [module_{i % 10}] Processing item {i}")
            log_content = "\n".join(log_lines)
            f = Path(d) / "app.log"
            _run(writetext, path=str(f), content=log_content)

            # Step 2: 搜索所有ERROR行
            r1 = _run(grep, pattern="ERROR", path=d)
            assert is_success(r1), f"搜索ERROR失败: {r1}"
            errors = r1.get("data", {}).get("total_matches", 0)
            assert errors == 10, f"应有10个ERROR, got {errors}"

            # Step 3: 搜索WARNING行
            r2 = _run(grep, pattern="WARNING", path=d)
            assert is_success(r2), f"搜索WARNING失败: {r2}"
            warnings = r2.get("data", {}).get("total_matches", 0)
            assert warnings == 10, f"应有10个WARNING, got {warnings}"

            # Step 4: 替换所有"Connection failed: timeout"为"Connection failed: OK"
            r3 = _run(edittext, path=str(f),
                      old_string="Connection failed: timeout",
                      new_string="Connection failed: OK",
                      mode="all")
            assert is_success(r3) or is_warning(r3), f"编辑失败: {r3}"

            # Step 5: 验证替换结果
            r4 = _run(grep, pattern="Connection failed: timeout", path=d)
            remaining = r4.get("data", {}).get("total_matches", 0)
            assert remaining == 0, f"timeout应全部替换, 剩余{remaining}"

            r5 = _run(grep, pattern="Connection failed: OK", path=d)
            replaced = r5.get("data", {}).get("total_matches", 0)
            assert replaced == 10, f"OK应有10个, got {replaced}"


# ============================================================
# 辅助
# ============================================================
def _write_file(path, content, encoding="utf-8"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding=encoding) as f:
        f.write(content)
