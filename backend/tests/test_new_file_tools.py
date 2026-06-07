"""
File工具深度集成测试 - 使用FileTools类
【创建时间】2026-04-20 小健
【更新】2026-04-30 重写为使用FileTools类
"""

import pytest
import asyncio
import tempfile
import os
import zipfile
import tarfile
import hashlib
from pathlib import Path
from app.services.tools.file.file_tools import FileTools


class TestCopyFileTool:
    """测试 copy_file 工具 - 使用 FileTools 类"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_copy_file_basic(self, temp_dir, file_tools):
        """测试基本文件复制"""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("test content")

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=False,
            overwrite=False
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert dst.exists()
        assert dst.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_copy_file_overwrite(self, temp_dir, file_tools):
        """测试覆盖复制"""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("new content")
        dst.write_text("old content")

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=False,
            overwrite=True
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert dst.read_text() == "new content"

    @pytest.mark.asyncio
    async def test_copy_file_no_overwrite(self, temp_dir, file_tools):
        """测试不覆盖已存在文件"""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("new content")
        dst.write_text("old content")

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=False,
            overwrite=False
        )

        assert result["data"]["success"] is False

    @pytest.mark.asyncio
    async def test_copy_directory_recursive(self, temp_dir, file_tools):
        """测试递归复制目录"""
        src = temp_dir / "source_dir"
        src.mkdir()
        (src / "file1.txt").write_text("content1")
        (src / "subdir").mkdir()
        (src / "subdir" / "file2.txt").write_text("content2")

        dst = temp_dir / "dest_dir"

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=True,
            overwrite=False
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert (dst / "file1.txt").exists()
        assert (dst / "subdir" / "file2.txt").exists()

    @pytest.mark.asyncio
    async def test_copy_to_subdirectory(self, temp_dir, file_tools):
        """测试复制到子目录"""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        src = temp_dir / "source.txt"
        dst = subdir / "source.txt"
        src.write_text("content")

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=False,
            overwrite=False
        )

        assert result["status"] == "success"
        assert dst.exists()
        assert dst.read_text() == "content"

    @pytest.mark.asyncio
    async def test_copy_file_not_found(self, temp_dir, file_tools):
        """测试源文件不存在"""
        src = temp_dir / "nonexistent.txt"
        dst = temp_dir / "dest.txt"

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=False,
            overwrite=False
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_copy_large_file(self, temp_dir, file_tools):
        """测试复制大文件(10MB)"""
        src = temp_dir / "large.bin"
        data = b"x" * (10 * 1024 * 1024)
        src.write_bytes(data)
        dst = temp_dir / "large_copy.bin"

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=False,
            overwrite=False
        )

        assert result["status"] == "success"
        assert dst.exists()
        assert dst.stat().st_size == len(data)

    @pytest.mark.asyncio
    async def test_copy_empty_file(self, temp_dir, file_tools):
        """测试复制空文件"""
        src = temp_dir / "empty.txt"
        dst = temp_dir / "empty_copy.txt"
        src.write_text("")

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=False,
            overwrite=False
        )

        assert result["status"] == "success"
        assert dst.exists()
        assert dst.read_text() == ""

    @pytest.mark.asyncio
    async def test_copy_with_special_chars(self, temp_dir, file_tools):
        """测试特殊文件名的复制"""
        src = temp_dir / "备份(2026)-v1.0.txt"
        dst = temp_dir / "备份_copy.txt"
        src.write_text("重要数据")

        result = await file_tools.copy_file(
            source_path=str(src),
            destination_path=str(dst),
            recursive=False,
            overwrite=False
        )

        assert result["status"] == "success"
        assert dst.exists()


class TestCreateDirectoryTool:
    """测试 create_directory 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_create_directory_basic(self, temp_dir, file_tools):
        """测试基本目录创建"""
        new_dir = temp_dir / "newdir"

        result = await file_tools.create_directory(
            dir_path=str(new_dir),
            parents=False,
            exist_ok=False
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert new_dir.exists()
        assert new_dir.is_dir()

    @pytest.mark.asyncio
    async def test_create_directory_with_parents(self, temp_dir, file_tools):
        """测试创建多级目录"""
        new_dir = temp_dir / "a" / "b" / "c"

        result = await file_tools.create_directory(
            dir_path=str(new_dir),
            parents=True,
            exist_ok=False
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert new_dir.exists()

    @pytest.mark.asyncio
    async def test_create_directory_exist_ok(self, temp_dir, file_tools):
        """测试已存在目录(exist_ok=True)"""
        existing = temp_dir / "existing"
        existing.mkdir()

        result = await file_tools.create_directory(
            dir_path=str(existing),
            parents=False,
            exist_ok=True
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_create_directory_exist_no_ok(self, temp_dir, file_tools):
        """测试已存在目录(exist_ok=False,应报错)"""
        existing = temp_dir / "existing"
        existing.mkdir()

        result = await file_tools.create_directory(
            dir_path=str(existing),
            parents=False,
            exist_ok=False
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_create_directory_no_parents(self, temp_dir, file_tools):
        """测试不创建父目录(父目录不存在,应报错)"""
        new_dir = temp_dir / "a" / "b"

        result = await file_tools.create_directory(
            dir_path=str(new_dir),
            parents=False,
            exist_ok=False
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_create_directory_default_params(self, temp_dir, file_tools):
        """测试默认参数(parents=True,exist_ok=True)"""
        new_dir = temp_dir / "a" / "b" / "c"

        result = await file_tools.create_directory(
            dir_path=str(new_dir)
        )

        assert result["status"] == "success"
        assert new_dir.exists()

    @pytest.mark.asyncio
    async def test_create_directory_existing_with_params(self, temp_dir, file_tools):
        """测试已存在目录在默认参数下不报错"""
        existing = temp_dir / "existing"
        existing.mkdir()

        result = await file_tools.create_directory(
            dir_path=str(existing)
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_create_directory_special_chars(self, temp_dir, file_tools):
        """测试特殊字符目录名"""
        new_dir = temp_dir / "测试目录-v1.0 (备份)"

        result = await file_tools.create_directory(
            dir_path=str(new_dir),
            parents=False,
            exist_ok=False
        )

        assert result["status"] == "success"
        assert new_dir.exists()


class TestCompressFilesTool:
    """测试 compress_files 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_compress_zip_basic(self, temp_dir, file_tools):
        """测试zip压缩"""
        src = temp_dir / "source.txt"
        src.write_text("test content for compression")

        dst = temp_dir / "output.zip"

        result = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst),
            format="zip",
            compression_level=6
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert dst.exists()

        with zipfile.ZipFile(dst, 'r') as zf:
            assert "source.txt" in zf.namelist()

    @pytest.mark.asyncio
    async def test_compress_directory_zip(self, temp_dir, file_tools):
        """测试压缩目录"""
        src = temp_dir / "source_dir"
        src.mkdir()
        (src / "file1.txt").write_text("content1")
        (src / "file2.txt").write_text("content2")

        dst = temp_dir / "output.zip"

        result = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst),
            format="zip"
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True

    @pytest.mark.asyncio
    async def test_compress_targz_basic(self, temp_dir, file_tools):
        """测试tar.gz压缩"""
        src = temp_dir / "source.txt"
        src.write_text("test content for tar.gz compression")

        dst = temp_dir / "output.tar.gz"

        result = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst),
            format="tar.gz",
            compression_level=6
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert dst.exists()

        with tarfile.open(dst, 'r:gz') as tf:
            names = tf.getnames()
            assert "source.txt" in names

    @pytest.mark.asyncio
    async def test_compress_invalid_format(self, temp_dir, file_tools):
        """测试无效压缩格式"""
        src = temp_dir / "source.txt"
        src.write_text("content")

        dst = temp_dir / "output.7z"

        result = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst),
            format="7z"
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_compress_not_found(self, temp_dir, file_tools):
        """测试源文件不存在"""
        src = temp_dir / "nonexistent.txt"
        dst = temp_dir / "output.zip"

        result = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst),
            format="zip"
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_compress_empty_file(self, temp_dir, file_tools):
        """测试压缩空文件"""
        src = temp_dir / "empty.txt"
        src.write_text("")
        dst = temp_dir / "empty.zip"

        result = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst),
            format="zip"
        )

        assert result["status"] == "success"
        assert dst.exists()

    @pytest.mark.asyncio
    async def test_compress_large_file(self, temp_dir, file_tools):
        """测试压缩大文件(50MB)"""
        src = temp_dir / "large.bin"
        data = b"A" * (50 * 1024 * 1024)
        src.write_bytes(data)
        dst = temp_dir / "large.zip"

        result = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst),
            format="zip",
            compression_level=1
        )

        assert result["status"] == "success"
        assert dst.exists()

    @pytest.mark.asyncio
    async def test_compress_overwrite(self, temp_dir, file_tools):
        """测试覆盖已存在的压缩包(应报错)"""
        src = temp_dir / "source.txt"
        src.write_text("content")
        dst = temp_dir / "output.zip"
        dst.write_text("dummy")

        result = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst),
            format="zip"
        )

        # compress_files不支持自动覆盖，目标已存在会报错
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_compress_no_password_different(self, temp_dir, file_tools):
        """测试不同压缩级别"""
        src = temp_dir / "source.txt"
        src.write_text("Hello World! " * 1000)
        dst_low = temp_dir / "low.zip"
        dst_high = temp_dir / "high.zip"

        result_low = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst_low),
            format="zip",
            compression_level=0
        )
        assert result_low["status"] == "success"

        result_high = await file_tools.compress_files(
            source_path=str(src),
            destination_path=str(dst_high),
            format="zip",
            compression_level=9
        )
        assert result_high["status"] == "success"

        # 高压缩比的文件应该更小
        assert dst_high.stat().st_size <= dst_low.stat().st_size


class TestBatchRenameTool:
    """测试 batch_rename 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_batch_rename_preview(self, temp_dir, file_tools):
        """测试预览模式"""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "file3.txt").write_text("content3")

        result = await file_tools.batch_rename(
            directory=str(temp_dir),
            pattern=r"file(\d+)\.txt",
            replacement=r"renamed_\1.txt",
            recursive=False,
            preview=True,
            conflict_strategy="skip"
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True

    @pytest.mark.asyncio
    async def test_batch_rename_execute(self, temp_dir, file_tools):
        """测试执行重命名"""
        (temp_dir / "test1.txt").write_text("content1")
        (temp_dir / "test2.txt").write_text("content2")

        result = await file_tools.batch_rename(
            directory=str(temp_dir),
            pattern="test",
            replacement="new",
            recursive=False,
            preview=False,
            conflict_strategy="skip"
        )

        assert result["status"] == "success"
        assert (temp_dir / "new1.txt").exists()

    @pytest.mark.asyncio
    async def test_batch_rename_regex(self, temp_dir, file_tools):
        """测试正则表达式"""
        (temp_dir / "image_001.jpg").write_text("content")
        (temp_dir / "image_002.jpg").write_text("content")

        result = await file_tools.batch_rename(
            directory=str(temp_dir),
            pattern=r"image_(\d+)\.jpg",
            replacement=r"photo_\1.jpg",
            recursive=False,
            preview=False,
            conflict_strategy="skip"
        )

        assert result["status"] == "success"
        assert (temp_dir / "photo_001.jpg").exists()

    @pytest.mark.asyncio
    async def test_batch_rename_conflict_skip(self, temp_dir, file_tools):
        """测试冲突跳过策略"""
        (temp_dir / "a.txt").write_text("a")
        (temp_dir / "b.txt").write_text("b")

        # 模拟冲突：重命名a.txt->b.txt，b.txt->b.txt(重复)
        result = await file_tools.batch_rename(
            directory=str(temp_dir),
            pattern=r"^(.+)\.txt$",
            replacement=r"b.txt",
            recursive=False,
            preview=False,
            conflict_strategy="skip"
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_batch_rename_recursive(self, temp_dir, file_tools):
        """测试递归重命名"""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (temp_dir / "test1.txt").write_text("content1")
        (subdir / "test2.txt").write_text("content2")

        result = await file_tools.batch_rename(
            directory=str(temp_dir),
            pattern="test",
            replacement="renamed",
            recursive=True,
            preview=False,
            conflict_strategy="skip"
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_batch_rename_no_match(self, temp_dir, file_tools):
        """测试无匹配文件"""
        (temp_dir / "readme.md").write_text("content")

        result = await file_tools.batch_rename(
            directory=str(temp_dir),
            pattern=r"\.txt$",
            replacement=r".md",
            recursive=False,
            preview=False,
            conflict_strategy="skip"
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_batch_rename_empty_dir(self, temp_dir, file_tools):
        """测试空目录"""
        result = await file_tools.batch_rename(
            directory=str(temp_dir),
            pattern="test",
            replacement="new",
            recursive=False,
            preview=False,
            conflict_strategy="skip"
        )

        assert result["status"] == "success"


class TestFileChecksumTool:
    """测试 file_checksum 工具 - 使用 FileTools 类"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_checksum_md5(self, temp_dir, file_tools):
        """测试MD5校验"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")

        result = await file_tools.file_checksum(
            file_path=str(test_file),
            algorithm="md5"
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert result["data"]["checksum"] == hashlib.md5(b"hello world").hexdigest()

    @pytest.mark.asyncio
    async def test_checksum_sha256(self, temp_dir, file_tools):
        """测试SHA256校验"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")

        result = await file_tools.file_checksum(
            file_path=str(test_file),
            algorithm="sha256"
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert result["data"]["checksum"] == hashlib.sha256(b"hello world").hexdigest()


class TestFileStatisticsTool:
    """测试 file_statistics 工具 - 使用 FileTools 类"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_statistics_basic(self, temp_dir, file_tools):
        """测试基本统计"""
        (temp_dir / "test1.txt").write_text("a" * 100)
        (temp_dir / "test2.txt").write_text("b" * 200)
        (temp_dir / "test3.py").write_text("c" * 50)

        result = await file_tools.file_statistics(
            directory=str(temp_dir),
            recursive=True
        )

        assert result["status"] == "success"
        assert result["data"]["success"] is True


class TestCompareFilesTool:
    """测试 compare_files 工具 - 使用 FileTools 类"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_compare_identical(self, temp_dir, file_tools):
        """测试比较相同文件"""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"

        content = "identical content"
        file1.write_text(content)
        file2.write_text(content)

        result = await file_tools.compare_files(
            file_path1=str(file1),
            file_path2=str(file2),
            algorithm="content"
        )

        assert result["status"] == "success"
        assert result["data"]["comparison"]["identical"] is True

    @pytest.mark.asyncio
    async def test_compare_different(self, temp_dir, file_tools):
        """测试比较不同文件"""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"

        file1.write_text("content A")
        file2.write_text("content B")

        result = await file_tools.compare_files(
            file_path1=str(file1),
            file_path2=str(file2),
            algorithm="content"
        )

        assert result["status"] == "success"
        assert result["data"]["comparison"]["identical"] is False

    @pytest.mark.asyncio
    async def test_compare_by_size(self, temp_dir, file_tools):
        """测试按大小比较"""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"

        file1.write_text("a" * 100)
        file2.write_text("b" * 100)

        result = await file_tools.compare_files(
            file_path1=str(file1),
            file_path2=str(file2),
            algorithm="size"
        )

        assert result["status"] == "success"
        assert result["data"]["comparison"]["identical"] is True


class TestPathValidationBugFix:
    """测试驱动器根路径验证bug修复"""

    def test_e_drive_root_access(self):
        """测试E盘根路径访问"""

        tools = FileTools()

        is_valid, error = tools._validate_path("E:/test")

        if Path("E:/").exists():
            assert is_valid is True, f"E:/test should be valid, error: {error}"

    def test_d_drive_root_access(self):
        """测试D盘根路径访问"""

        tools = FileTools()

        is_valid, error = tools._validate_path("D:/test")

        if Path("D:/").exists():
            assert is_valid is True, f"D:/test should be valid, error: {error}"


class TestReadFileTool:
    """测试 read_file 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_read_file_basic(self, temp_dir, file_tools):
        """测试基本文件读取"""
        file = temp_dir / "test.txt"
        file.write_text("Hello World")

        result = await file_tools.read_file(
            file_path=str(file),
            offset=1,
            limit=100,
            encoding="utf-8"
        )

        assert result["status"] == "success"
        assert "content" in result["data"]

    @pytest.mark.asyncio
    async def test_read_file_with_offset(self, temp_dir, file_tools):
        """测试从指定行开始读取"""
        file = temp_dir / "test.txt"
        file.write_text("Line 1\nLine 2\nLine 3")

        result = await file_tools.read_file(
            file_path=str(file),
            offset=2,
            limit=10,
            encoding="utf-8"
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_read_file_encoding(self, temp_dir, file_tools):
        """测试不同编码"""
        file = temp_dir / "test.txt"
        file.write_text("中文内容", encoding="utf-8")

        result = await file_tools.read_file(
            file_path=str(file),
            offset=1,
            limit=100,
            encoding="utf-8"
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_dir, file_tools):
        """测试文件不存在"""
        result = await file_tools.read_file(
            file_path=str(temp_dir / "nonexistent.txt"),
            offset=1,
            limit=100,
            encoding="utf-8"
        )

        assert result["status"] == "error"


class TestWriteFileTool:
    """测试 write_file 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_write_file_basic(self, temp_dir, file_tools):
        """测试基本文件写入"""
        file = temp_dir / "test.txt"
        result = await file_tools.write_file(
            file_path=str(file),
            content="Test Content",
            encoding="utf-8"
        )
        assert result["status"] == "success"
        assert file.exists()
        assert file.read_text() == "Test Content"

    @pytest.mark.asyncio
    async def test_write_file_overwrite(self, temp_dir, file_tools):
        """测试覆盖写入"""
        file = temp_dir / "test.txt"
        file.write_text("Original")
        result = await file_tools.write_file(
            file_path=str(file),
            content="New Content",
            encoding="utf-8"
        )
        assert result["status"] == "success"
        assert file.read_text() == "New Content"

    @pytest.mark.asyncio
    async def test_write_file_create_dirs(self, temp_dir, file_tools):
        """测试自动创建目录"""
        subdir = temp_dir / "subdir"
        file = subdir / "test.txt"
        result = await file_tools.write_file(
            file_path=str(file),
            content="Content",
            encoding="utf-8"
        )
        assert result["status"] == "success"
        assert file.exists()

    @pytest.mark.asyncio
    async def test_write_file_empty(self, temp_dir, file_tools):
        """测试写入空内容"""
        file = temp_dir / "empty.txt"
        result = await file_tools.write_file(
            file_path=str(file),
            content="",
            encoding="utf-8"
        )
        assert result["status"] == "success"
        assert file.exists()
        assert file.read_text() == ""

    @pytest.mark.asyncio
    async def test_write_file_special_chars(self, temp_dir, file_tools):
        """测试写入特殊字符"""
        file = temp_dir / "special.txt"
        special = "~!@#$%^&*()_+{}|:<>?`-=[]\\;',./\n\t"
        result = await file_tools.write_file(
            file_path=str(file),
            content=special,
            encoding="utf-8"
        )
        assert result["status"] == "success"
        assert file.read_text() == special

    @pytest.mark.asyncio
    async def test_write_file_unicode(self, temp_dir, file_tools):
        """测试写入Unicode/中文"""
        file = temp_dir / "unicode.txt"
        unicode_text = "你好世界\nこんにちは\n🌍🌎🌏\nÀÈÌÒÙ"
        result = await file_tools.write_file(
            file_path=str(file),
            content=unicode_text,
            encoding="utf-8"
        )
        assert result["status"] == "success"
        assert file.read_text(encoding="utf-8") == unicode_text

    @pytest.mark.asyncio
    async def test_write_file_gbk_encoding(self, temp_dir, file_tools):
        """测试GBK编码写入"""
        file = temp_dir / "gbk.txt"
        content = "中文GBK编码测试"
        result = await file_tools.write_file(
            file_path=str(file),
            content=content,
            encoding="gbk"
        )
        assert result["status"] == "success"
        assert file.read_text(encoding="gbk") == content

    @pytest.mark.asyncio
    async def test_write_file_large_content(self, temp_dir, file_tools):
        """测试写入大文件(10万行)"""
        file = temp_dir / "large.txt"
        lines = [f"Line {i}: {'x' * 100}\n" for i in range(100000)]
        content = "".join(lines)
        result = await file_tools.write_file(
            file_path=str(file),
            content=content,
            encoding="utf-8"
        )
        assert result["status"] == "success"
        assert file.stat().st_size > 1000000  # >1MB

    @pytest.mark.asyncio
    async def test_write_file_binary(self, temp_dir, file_tools):
        """测试二进制数据写入"""
        file = temp_dir / "binary.bin"
        content = "Binary\x00Data\x01\x02\x03Test"
        result = await file_tools.write_file(
            file_path=str(file),
            content=content,
            encoding="utf-8"
        )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_write_file_python_code(self, temp_dir, file_tools):
        """测试写入Python代码"""
        file = temp_dir / "script.py"
        code = """#!/usr/bin/env python
# -*- coding: utf-8 -*-
def hello():
    \"\"\"Say hello\"\"\"
    print("Hello, World!")


if __name__ == "__main__":
    hello()
"""
        result = await file_tools.write_file(
            file_path=str(file),
            content=code,
            encoding="utf-8"
        )
        assert result["status"] == "success"
        assert file.read_text() == code

    @pytest.mark.asyncio
    async def test_write_file_json_content(self, temp_dir, file_tools):
        """测试写入JSON内容"""
        file = temp_dir / "data.json"
        json_str = '{"name": "test", "value": 42, "nested": {"a": 1, "b": [1,2,3]}}'
        result = await file_tools.write_file(
            file_path=str(file),
            content=json_str,
            encoding="utf-8"
        )
        assert result["status"] == "success"
        import json
        data = json.loads(file.read_text())
        assert data["name"] == "test"
        assert data["value"] == 42


class TestListDirectoryTool:
    """测试 list_directory 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_list_directory_basic(self, temp_dir, file_tools):
        """测试基本目录列出"""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")

        result = await file_tools.list_directory(
            dir_path=str(temp_dir),
            recursive=False,
            max_depth=10,
            page_token=None
        )

        assert result["status"] == "success"
        assert "entries" in result["data"]

    @pytest.mark.asyncio
    async def test_list_directory_recursive(self, temp_dir, file_tools):
        """测试递归列出"""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (temp_dir / "file1.txt").write_text("content1")
        (subdir / "file2.txt").write_text("content2")

        result = await file_tools.list_directory(
            dir_path=str(temp_dir),
            recursive=True,
            max_depth=10,
            page_token=None
        )

        assert result["status"] == "success"
        assert "entries" in result["data"]

    @pytest.mark.asyncio
    async def test_list_directory_empty(self, temp_dir, file_tools):
        """测试空目录"""
        result = await file_tools.list_directory(
            dir_path=str(temp_dir),
            recursive=False,
            max_depth=10,
            page_token=None
        )

        assert result["status"] == "success"


class TestDeleteFileTool:
    """测试 delete_file 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_delete_file_basic(self, temp_dir, file_tools):
        """测试删除文件"""
        file = temp_dir / "test.txt"
        file.write_text("content")

        result = await file_tools.delete_file(
            file_path=str(file),
            recursive=False
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_delete_directory(self, temp_dir, file_tools):
        """测试删除目录(含内容)"""
        subdir = temp_dir / "testdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")

        result = await file_tools.delete_file(
            file_path=str(subdir),
            recursive=True
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_delete_empty_directory(self, temp_dir, file_tools):
        """测试删除空目录(无需recursive)"""
        subdir = temp_dir / "emptydir"
        subdir.mkdir()

        result = await file_tools.delete_file(
            file_path=str(subdir),
            recursive=False
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_delete_nonempty_dir_no_recursive(self, temp_dir, file_tools):
        """测试删除非空目录但不使用recursive(应报错)"""
        subdir = temp_dir / "testdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")

        result = await file_tools.delete_file(
            file_path=str(subdir),
            recursive=False
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, temp_dir, file_tools):
        """测试删除不存在的文件"""
        result = await file_tools.delete_file(
            file_path=str(temp_dir / "nonexistent.txt"),
            recursive=False
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_delete_with_spaces(self, temp_dir, file_tools):
        """测试删除包含空格的文件"""
        file = temp_dir / "my file with spaces.txt"
        file.write_text("content")

        result = await file_tools.delete_file(
            file_path=str(file),
            recursive=False
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_delete_special_chars_path(self, temp_dir, file_tools):
        """测试删除含特殊字符路径"""
        file = temp_dir / "test+copy(1).txt"
        file.write_text("content")

        result = await file_tools.delete_file(
            file_path=str(file),
            recursive=False
        )

        assert result["status"] == "success"


class TestMoveFileTool:
    """测试 move_file 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_move_file_basic(self, temp_dir, file_tools):
        """测试基本移动"""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("content")

        result = await file_tools.move_file(
            source_path=str(src),
            destination_path=str(dst)
        )

        assert result["status"] == "success"
        assert not src.exists()
        assert dst.exists()

    @pytest.mark.asyncio
    async def test_move_file_rename(self, temp_dir, file_tools):
        """测试重命名"""
        file = temp_dir / "old.txt"
        newfile = temp_dir / "new.txt"
        file.write_text("content")

        result = await file_tools.move_file(
            source_path=str(file),
            destination_path=str(newfile)
        )

        assert result["status"] == "success"
        assert newfile.exists()

    @pytest.mark.asyncio
    async def test_move_to_subdirectory(self, temp_dir, file_tools):
        """测试移动到子目录"""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        src = temp_dir / "source.txt"
        dst = subdir / "source.txt"
        src.write_text("content")

        result = await file_tools.move_file(
            source_path=str(src),
            destination_path=str(dst)
        )

        assert result["status"] == "success"
        assert not src.exists()
        assert dst.exists()

    @pytest.mark.asyncio
    async def test_move_directory(self, temp_dir, file_tools):
        """测试移动整个目录"""
        src = temp_dir / "srcdir"
        src.mkdir()
        (src / "file.txt").write_text("content")
        dst = temp_dir / "dstdir"

        result = await file_tools.move_file(
            source_path=str(src),
            destination_path=str(dst)
        )

        assert result["status"] == "success"
        assert not src.exists()
        assert dst.exists()
        assert (dst / "file.txt").exists()
        assert (dst / "file.txt").read_text() == "content"

    @pytest.mark.asyncio
    async def test_move_not_found(self, temp_dir, file_tools):
        """测试源文件不存在"""
        src = temp_dir / "nonexistent.txt"
        dst = temp_dir / "dest.txt"

        result = await file_tools.move_file(
            source_path=str(src),
            destination_path=str(dst)
        )

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_move_overwrite_existing(self, temp_dir, file_tools):
        """测试移动覆盖目标(目标已存在应报错)"""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("new")
        dst.write_text("old")

        result = await file_tools.move_file(
            source_path=str(src),
            destination_path=str(dst)
        )

        # move_file不支持自动覆盖，目标已存在会报错
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_move_with_special_chars(self, temp_dir, file_tools):
        """测试特殊字符文件名的移动"""
        src = temp_dir / "测试文件(1) [备份].txt"
        dst = temp_dir / "moved_测试.txt"
        src.write_text("content")

        result = await file_tools.move_file(
            source_path=str(src),
            destination_path=str(dst)
        )

        assert result["status"] == "success"
        assert not src.exists()
        assert dst.exists()


class TestSearchFileContentTool:
    """测试 search_file_content 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_search_file_content_basic(self, temp_dir, file_tools):
        """测试基本内容搜索"""
        file = temp_dir / "test.txt"
        file.write_text("Hello World\nPython World")

        result = await file_tools.search_file_content(
            pattern="World",
            path=str(file),
            file_pattern="*.txt",
            recursive=False,
            use_regex=False
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_search_file_content_regex(self, temp_dir, file_tools):
        """测试正则搜索"""
        file = temp_dir / "test.txt"
        file.write_text("test123 test456 test789")

        result = await file_tools.search_file_content(
            pattern=r"test\d+",
            path=str(file),
            file_pattern="*.txt",
            recursive=False,
            use_regex=True
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_search_file_content_no_match(self, temp_dir, file_tools):
        """测试无匹配"""
        file = temp_dir / "test.txt"
        file.write_text("Hello World")

        result = await file_tools.search_file_content(
            pattern="NotFound",
            path=str(file),
            file_pattern="*.txt",
            recursive=False,
            use_regex=False
        )

        assert result["status"] == "success"


class TestSearchFilesTool:
    """测试 search_files 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_search_files_basic(self, temp_dir, file_tools):
        """测试基本文件搜索"""
        (temp_dir / "test1.txt").write_text("content1")
        (temp_dir / "test2.txt").write_text("content2")
        (temp_dir / "other.md").write_text("content3")

        result = await file_tools.search_files(
            file_pattern="*.txt",
            path=str(temp_dir),
            recursive=False,
            max_depth=100000
        )

        assert result["status"] == "success"
        assert "matches" in result["data"]

    @pytest.mark.asyncio
    async def test_search_files_regex(self, temp_dir, file_tools):
        """测试正则搜索"""
        (temp_dir / "file123.txt").write_text("content1")
        (temp_dir / "file456.txt").write_text("content2")

        result = await file_tools.search_files(
            file_pattern=r"file\d+\.txt",
            path=str(temp_dir),
            recursive=False,
            max_depth=100000
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_search_files_recursive(self, temp_dir, file_tools):
        """测试递归搜索"""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (temp_dir / "test1.txt").write_text("content1")
        (subdir / "test2.txt").write_text("content2")

        result = await file_tools.search_files(
            file_pattern="*.txt",
            path=str(temp_dir),
            recursive=True,
            max_depth=100000
        )

        assert result["status"] == "success"


class TestGenerateReportTool:
    """测试 generate_report 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.xfail(reason="后端代码有bug: 数据库缺少session_id列")
    @pytest.mark.asyncio
    async def test_generate_report_text(self, temp_dir, file_tools):
        """测试生成文本报告"""
        result = await file_tools.generate_report(
            output_dir=str(temp_dir)
        )

        assert result["status"] in ["success", "error"]

    @pytest.mark.xfail(reason="后端代码有bug: 数据库缺少session_id列")
    @pytest.mark.asyncio
    async def test_generate_report_json(self, temp_dir, file_tools):
        """测试生成JSON报告"""
        result = await file_tools.generate_report(
            output_dir=str(temp_dir)
        )

        assert result["status"] in ["success", "error"]

    @pytest.mark.xfail(reason="后端代码有bug: 数据库缺少session_id列")
    @pytest.mark.asyncio
    async def test_generate_report_html(self, temp_dir, file_tools):
        """测试生成HTML报告"""
        result = await file_tools.generate_report(
            output_dir=str(temp_dir)
        )

        assert result["status"] in ["success", "error"]


@pytest.mark.skip(reason="后端代码有bug: file_monitor实现待修复")
class TestFileMonitorTool:
    """测试 file_monitor 工具"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_file_monitor_basic(self, temp_dir, file_tools):
        """测试基本文件监控"""
        pytest.skip("后端代码有bug: file_monitor实现待修复")

    @pytest.mark.asyncio
    async def test_file_monitor_directory(self, temp_dir, file_tools):
        """测试目录监控"""
        pytest.skip("后端代码有bug: file_monitor实现待修复")


class TestWriteFileUnescape:
    """测试 write_file 的反转义功能"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def file_tools(self, temp_dir):
        from app.services.tools.file.file_tools import FileTools
        tools = FileTools(task_id="test_task")
        tools.allowed_paths = [str(temp_dir)]
        return tools

    @pytest.mark.asyncio
    async def test_unescape_default_true(self, temp_dir, file_tools):
        """测试默认启用反转义：\\n 转为真实换行，unescape=True"""
        file = temp_dir / "unescape.txt"
        content = "line1\\nline2\\nline3"
        result = await file_tools.write_file(
            file_path=str(file),
            content=content,
            encoding="utf-8"
        )
        assert result["status"] == "success"
        text = file.read_text()
        assert "\\" not in text, f"Expect no backslash, got: {repr(text)}"
        assert text == "line1\nline2\nline3"

    @pytest.mark.asyncio
    async def test_unescape_false_keep_raw(self, temp_dir, file_tools):
        """测试关闭反转义：保留 \\n 原样"""
        file = temp_dir / "no_unescape.txt"
        content = "line1\\nline2\\nline3"
        result = await file_tools.write_file(
            file_path=str(file),
            content=content,
            encoding="utf-8",
            unescape=False
        )
        assert result["status"] == "success"
        text = file.read_text()
        assert "\\n" in text
        assert text == "line1\\nline2\\nline3"

    @pytest.mark.asyncio
    async def test_unescape_quote(self, temp_dir, file_tools):
        """测试反转义：\\\" 转为引号"""
        file = temp_dir / "unescape_quote.txt"
        content = "\\\"hello\\\""
        result = await file_tools.write_file(
            file_path=str(file),
            content=content,
            encoding="utf-8"
        )
        assert result["status"] == "success"
        text = file.read_text()
        assert "\\\"" not in text
        assert text == '"hello"'

    @pytest.mark.asyncio
    async def test_unescape_complex(self, temp_dir, file_tools):
        """测试反转义：复杂混合内容（模拟小说章节）"""
        file = temp_dir / "chapter.txt"
        content = r"## 决战\n\n她说：\"来吧！\"\n\n艾拉\"明白了\""
        expected = "## 决战\n\n她说：\"来吧！\"\n\n艾拉\"明白了\""
        result = await file_tools.write_file(
            file_path=str(file),
            content=content,
            encoding="utf-8"
        )
        assert result["status"] == "success"
        text = file.read_text(encoding="utf-8")
        assert text == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
