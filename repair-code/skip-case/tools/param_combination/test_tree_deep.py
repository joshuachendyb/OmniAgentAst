# -*- coding: utf-8 -*-
# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/tools/param_combination/test_tree_deep.py
# 归档原因: 包含 Windows 平台限制类 skip case(symlink/权限/MAX_PATH),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于未来在其他平台恢复运行。
# ================================================================
"""
tree工具深度测试 — 挖掘bug

测试目标：发现tree工具的各种bug和边界问题
测试用例：35个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.tree import tree

pytestmark = pytest.mark.asyncio(loop_scope="function")


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"



class TestTreeBasicParams:
    """参数组合测试 - 6个基础组合"""
    
    async def test_empty_dir_path(self, tmp_path):
        """Bug1: 空路径应该报错"""
        result = await tree(path="")
        assert is_error(result)
        assert "不能为空" in result.get("llm_data", {}).get("status", {}).get("detail", "")
    
    async def test_whitespace_dir_path(self, tmp_path):
        """Bug2: 纯空格路径应该报错"""
        result = await tree(path="   ")
        assert is_error(result)
    
    async def test_only_dir_path(self, tmp_path):
        """组合1: 仅必填参数"""
        test_dir = tmp_path / "test_tree"
        test_dir.mkdir()
        result = await tree(path=str(test_dir))
        assert is_success(result)
        assert "tree" in result.get("data", {})
    
    async def test_with_include_hidden(self, tmp_path):
        """组合2: dir_path + include_hidden"""
        test_dir = tmp_path / "test_hidden"
        test_dir.mkdir()
        (test_dir / ".hidden").mkdir()
        
        result1 = await tree(path=str(test_dir), include_hidden=False)
        assert is_success(result1)
        children1 = result1["data"]["tree"]["children"]
        
        result2 = await tree(path=str(test_dir), include_hidden=True)
        assert is_success(result2)
        children2 = result2["data"]["tree"]["children"]
        
        assert len(children2) > len(children1)
    
    async def test_with_sort_by_name(self, tmp_path):
        """组合3: dir_path + sort_by=name"""
        test_dir = tmp_path / "test_sort"
        test_dir.mkdir()
        (test_dir / "z_dir").mkdir()
        (test_dir / "a_dir").mkdir()
        
        result = await tree(path=str(test_dir), sort_by="name")
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert children[0]["name"] == "a_dir"
        assert children[1]["name"] == "z_dir"
    
    async def test_with_sort_by_mtime(self, tmp_path):
        """组合4: dir_path + sort_by=mtime"""
        test_dir = tmp_path / "test_mtime"
        test_dir.mkdir()
        import time
        (test_dir / "old_dir").mkdir()
        time.sleep(0.1)
        (test_dir / "new_dir").mkdir()
        
        result = await tree(path=str(test_dir), sort_by="mtime")
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert children[0]["name"] == "new_dir"


@pytest.mark.asyncio
class TestTreeInvalidParams:
    """无效参数测试 - 5个"""
    
    async def test_invalid_sort_by(self, tmp_path):
        """Bug3: 无效的sort_by应该报错"""
        test_dir = tmp_path / "test_invalid"
        test_dir.mkdir()
        result = await tree(path=str(test_dir), sort_by="invalid")
        assert is_error(result)
        assert "sort_by" in result.get("llm_data", {}).get("status", {}).get("detail", "")
    
    async def test_nonexistent_dir(self, tmp_path):
        """Bug4: 不存在的目录应该报错"""
        result = await tree(path=str(tmp_path / "nonexistent"))
        assert is_error(result)
        assert "不存在" in result.get("llm_data", {}).get("status", {}).get("detail", "")
    
    async def test_file_not_dir(self, tmp_path):
        """Bug5: 文件路径（非目录）应该报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = await tree(path=str(test_file))
        assert is_error(result)
        assert "不是目录" in result.get("llm_data", {}).get("status", {}).get("detail", "")
    
    async def test_permission_denied(self, tmp_path):
        """Bug6: 无权限目录应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows权限测试跳过")
        test_dir = tmp_path / "no_perm"
        test_dir.mkdir()
        try:
            os.chmod(str(test_dir), 0o000)
            result = await tree(path=str(test_dir))
            # 应该能读取自己创建的目录
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(test_dir), 0o755)
    
    async def test_sort_by_size_ignored(self, tmp_path):
        """Bug7: sort_by=size应该被忽略（tree只支持name/mtime）"""
        test_dir = tmp_path / "test_size"
        test_dir.mkdir()
        result = await tree(path=str(test_dir), sort_by="size")
        assert is_error(result)


@pytest.mark.asyncio
class TestTreeDepthLimit:
    """深度限制测试 - 5个"""
    
    async def test_max_depth_10(self, tmp_path):
        """Bug8: 最大深度10层应该生效"""
        test_dir = tmp_path / "depth_test"
        test_dir.mkdir()
        current = test_dir
        for i in range(15):
            current = current / f"level{i}"
            current.mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        
        def count_depth(node, depth=0):
            if not node.get("children"):
                return depth
            return max(count_depth(child, depth+1) for child in node["children"])
        
        tree_data = result["data"]["tree"]
        max_depth = count_depth(tree_data)
        assert max_depth <= 10
    
    async def test_single_level(self, tmp_path):
        """测试单层目录"""
        test_dir = tmp_path / "single"
        test_dir.mkdir()
        (test_dir / "sub1").mkdir()
        (test_dir / "sub2").mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        assert len(result["data"]["tree"]["children"]) == 2
    
    async def test_empty_directory(self, tmp_path):
        """Bug9: 空目录应该返回空children"""
        test_dir = tmp_path / "empty"
        test_dir.mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        assert result["data"]["tree"]["children"] == []
    
    async def test_deeply_nested(self, tmp_path):
        """测试深层嵌套"""
        test_dir = tmp_path / "deep"
        test_dir.mkdir()
        current = test_dir
        for i in range(8):
            current = current / f"nested{i}"
            current.mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        assert len(result["data"]["tree"]["children"]) == 1
    
    async def test_circular_symlink(self, tmp_path):
        """Bug10: 循环符号链接应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows符号链接需要管理员权限")
        test_dir = tmp_path / "circular"
        test_dir.mkdir()
        sub_dir = test_dir / "sub"
        sub_dir.mkdir()
        try:
            (sub_dir / "link").symlink_to(test_dir)
            result = await tree(path=str(test_dir))
            assert is_success(result) or is_error(result)
        except OSError:
            pytest.skip("符号链接创建失败")


@pytest.mark.asyncio
class TestTreeHiddenFiles:
    """隐藏文件测试 - 4个"""
    
    async def test_exclude_hidden_by_default(self, tmp_path):
        """Bug11: 默认应该排除隐藏目录"""
        test_dir = tmp_path / "hidden_test"
        test_dir.mkdir()
        (test_dir / "normal").mkdir()
        (test_dir / ".hidden").mkdir()
        
        result = await tree(path=str(test_dir), include_hidden=False)
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert len(children) == 1
        assert children[0]["name"] == "normal"
    
    async def test_include_hidden(self, tmp_path):
        """测试包含隐藏目录"""
        test_dir = tmp_path / "hidden_test2"
        test_dir.mkdir()
        (test_dir / "normal").mkdir()
        (test_dir / ".hidden").mkdir()
        
        result = await tree(path=str(test_dir), include_hidden=True)
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert len(children) == 2
    
    async def test_nested_hidden(self, tmp_path):
        """Bug12: 嵌套隐藏目录应该被排除"""
        test_dir = tmp_path / "nested_hidden"
        test_dir.mkdir()
        sub = test_dir / "sub"
        sub.mkdir()
        (sub / ".deep_hidden").mkdir()
        
        result = await tree(path=str(test_dir), include_hidden=False)
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert len(children[0]["children"]) == 0
    
    async def test_hidden_with_special_chars(self, tmp_path):
        """测试特殊字符的隐藏目录"""
        test_dir = tmp_path / "special_hidden"
        test_dir.mkdir()
        (test_dir / ".隐藏目录").mkdir()
        
        result = await tree(path=str(test_dir), include_hidden=True)
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert len(children) == 1


@pytest.mark.asyncio
class TestTreeSorting:
    """排序测试 - 4个"""
    
    async def test_sort_by_name_case_insensitive(self, tmp_path):
        """Bug13: 名称排序应该不区分大小写"""
        test_dir = tmp_path / "case_test"
        test_dir.mkdir()
        (test_dir / "Zebra").mkdir()
        (test_dir / "apple").mkdir()
        (test_dir / "Banana").mkdir()
        
        result = await tree(path=str(test_dir), sort_by="name")
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert children[0]["name"] == "apple"
        assert children[1]["name"] == "Banana"
        assert children[2]["name"] == "Zebra"
    
    async def test_sort_by_mtime_order(self, tmp_path):
        """Bug14: mtime排序应该是最新的在前"""
        test_dir = tmp_path / "mtime_test"
        test_dir.mkdir()
        import time
        (test_dir / "oldest").mkdir()
        time.sleep(0.1)
        (test_dir / "middle").mkdir()
        time.sleep(0.1)
        (test_dir / "newest").mkdir()
        
        result = await tree(path=str(test_dir), sort_by="mtime")
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert children[0]["name"] == "newest"
        assert children[1]["name"] == "middle"
        assert children[2]["name"] == "oldest"
    
    async def test_sort_with_hidden(self, tmp_path):
        """测试排序和隐藏同时生效"""
        test_dir = tmp_path / "sort_hidden"
        test_dir.mkdir()
        (test_dir / "z_normal").mkdir()
        (test_dir / "a_normal").mkdir()
        (test_dir / ".z_hidden").mkdir()
        
        result = await tree(path=str(test_dir), sort_by="name", include_hidden=False)
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert len(children) == 2
        assert children[0]["name"] == "a_normal"
    
    async def test_sort_chinese_names(self, tmp_path):
        """Bug15: 中文名称排序应该正确"""
        test_dir = tmp_path / "chinese_sort"
        test_dir.mkdir()
        (test_dir / "目录Z").mkdir()
        (test_dir / "目录A").mkdir()
        (test_dir / "目录中").mkdir()
        
        result = await tree(path=str(test_dir), sort_by="name")
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert len(children) == 3


@pytest.mark.asyncio
class TestTreeStatistics:
    """统计信息测试 - 4个"""
    
    async def test_statistics_accuracy(self, tmp_path):
        """Bug16: 统计信息应该准确"""
        test_dir = tmp_path / "stats_test"
        test_dir.mkdir()
        (test_dir / "sub1").mkdir()
        (test_dir / "sub2").mkdir()
        (test_dir / "sub1" / "file1.txt").write_text("test")
        (test_dir / "sub1" / "file2.txt").write_text("test")
        (test_dir / "file3.txt").write_text("test")
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        stats = result["data"]["statistics"]
        assert stats["file_count"] == 3
        assert stats["dir_count"] == 2
    
    async def test_statistics_empty_dir(self, tmp_path):
        """测试空目录统计"""
        test_dir = tmp_path / "empty_stats"
        test_dir.mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        stats = result["data"]["statistics"]
        assert stats["file_count"] == 0
        assert stats["dir_count"] == 0
    
    async def test_statistics_total_size(self, tmp_path):
        """Bug17: total_size应该正确计算"""
        test_dir = tmp_path / "size_test"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("a" * 100)
        (test_dir / "file2.txt").write_text("b" * 200)
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        stats = result["data"]["statistics"]
        assert stats["total_size"] == 300
    
    async def test_statistics_with_hidden(self, tmp_path):
        """测试统计是否包含隐藏文件"""
        test_dir = tmp_path / "hidden_stats"
        test_dir.mkdir()
        (test_dir / "normal.txt").write_text("test")
        (test_dir / ".hidden.txt").write_text("test")
        
        result = await tree(path=str(test_dir), include_hidden=False)
        assert is_success(result)
        stats = result["data"]["statistics"]
        assert stats["file_count"] == 1


@pytest.mark.asyncio
class TestTreeRealScenarios:
    """真实场景测试 - 4个"""
    
    async def test_project_structure(self, tmp_path):
        """测试项目目录结构"""
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "src").mkdir()
        (project / "tests").mkdir()
        (project / "docs").mkdir()
        (project / "src" / "main.py").write_text("print('hello')")
        (project / "tests" / "test_main.py").write_text("assert True")
        
        result = await tree(path=str(project))
        assert is_success(result)
        children = result["data"]["tree"]["children"]
        assert len(children) == 3
    
    async def test_nested_packages(self, tmp_path):
        """测试嵌套包结构"""
        project = tmp_path / "package"
        project.mkdir()
        (project / "pkg").mkdir()
        (project / "pkg" / "subpkg").mkdir()
        (project / "pkg" / "subpkg" / "deep").mkdir()
        
        result = await tree(path=str(project))
        assert is_success(result)
        assert len(result["data"]["tree"]["children"]) == 1
    
    async def test_mixed_content(self, tmp_path):
        """测试混合内容（文件+目录）"""
        test_dir = tmp_path / "mixed"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("test")
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "nested.txt").write_text("nested")
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        assert len(result["data"]["tree"]["children"]) == 1  # 只有目录
    
    async def test_large_directory(self, tmp_path):
        """Bug18: 大量目录应该正常处理"""
        test_dir = tmp_path / "large"
        test_dir.mkdir()
        for i in range(100):
            (test_dir / f"dir{i:03d}").mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        assert len(result["data"]["tree"]["children"]) == 100


@pytest.mark.asyncio
class TestTreeEdgeCases:
    """边界测试 - 3个"""
    
    async def test_special_chars_in_path(self, tmp_path):
        """Bug19: 特殊字符路径应该处理"""
        test_dir = tmp_path / "特殊目录"
        test_dir.mkdir()
        (test_dir / "子目录").mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
    
    async def test_very_long_path(self, tmp_path):
        """Bug20: 超长路径应该处理"""
        import sys
        # Windows 默认启用MAX_PATH限制(260字符), 构造200字符名+临时目录前缀易超限, 属系统约束 — 小欧 2026-07-12
        if sys.platform == "win32":
            pytest.skip("Windows MAX_PATH限制, 超长路径mkdir在系统层失败, 非代码问题")
        long_name = "a" * 200
        test_dir = tmp_path / long_name
        test_dir.mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result) or is_error(result)
    
    async def test_unicode_path(self, tmp_path):
        """测试Unicode路径"""
        test_dir = tmp_path / "目录🎉测试"
        test_dir.mkdir()
        (test_dir / "子目录📁").mkdir()
        
        result = await tree(path=str(test_dir))
        assert is_success(result)
        assert len(result["data"]["tree"]["children"]) == 1
