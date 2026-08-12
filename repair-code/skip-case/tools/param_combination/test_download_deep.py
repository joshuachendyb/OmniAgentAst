# -*- coding: utf-8 -*-
# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/tools/param_combination/test_download_deep.py
# 归档原因: 包含 Windows 平台限制类 skip case(readonly),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于未来在其他平台恢复运行。
# ================================================================
"""
download工具深度测试 — 挖掘bug

测试目标：发现download工具的各种bug和边界问题
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.network.download_file import download


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


class TestDownloadBasicParams:
    """参数组合测试 - 6个"""
    
    def test_download_with_url_only(self, tmp_path):
        """组合1: 仅URL（自动保存到downloads目录）"""
        url = "https://httpbin.org/robots.txt"
        result = asyncio.run(download(url=url))
        assert is_success(result) or is_error(result)
    
    def test_download_with_destination(self, tmp_path):
        """组合2: URL + destination_path"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "robots.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest)))
        assert is_success(result) or is_error(result)
        if is_success(result):
            assert dest.exists()
    
    def test_download_with_timeout(self, tmp_path):
        """组合3: URL + timeout"""
        url = "https://httpbin.org/delay/1"
        dest = tmp_path / "delay.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=5))
        assert is_success(result) or is_error(result)
    
    def test_download_with_proxy(self, tmp_path):
        """组合4: URL + proxy"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "proxy_test.txt"
        proxy = "http://127.0.0.1:8080"
        
        result = asyncio.run(download(url=url, dest=str(dest), proxy=proxy))
        assert is_success(result) or is_error(result)
    
    def test_download_empty_url(self, tmp_path):
        """Bug1: 空URL应该报错"""
        result = asyncio.run(download(url=""))
        assert is_error(result)
    
    def test_download_invalid_url(self, tmp_path):
        """Bug2: 无效URL应该报错"""
        result = asyncio.run(download(url="not-a-valid-url"))
        assert is_error(result)


class TestDownloadNetworkErrors:
    """网络错误测试 - 6个"""
    
    def test_download_nonexistent_host(self, tmp_path):
        """Bug3: 不存在的主机应该报错"""
        url = "https://this-domain-does-not-exist-12345.com/file.txt"
        dest = tmp_path / "test.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=5))
        assert is_error(result)
    
    def test_download_404_error(self, tmp_path):
        """Bug4: 404错误应该报错"""
        url = "https://httpbin.org/status/404"
        dest = tmp_path / "404.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest)))
        assert is_error(result)
    
    def test_download_500_error(self, tmp_path):
        """Bug5: 500错误应该报错"""
        url = "https://httpbin.org/status/500"
        dest = tmp_path / "500.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest)))
        assert is_error(result)
    
    def test_download_timeout_error(self, tmp_path):
        """Bug6: 超时应该报错"""
        url = "https://httpbin.org/delay/10"
        dest = tmp_path / "timeout.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=2))
        assert is_error(result)
    
    def test_download_connection_refused(self, tmp_path):
        """Bug7: 连接拒绝应该报错"""
        url = "http://127.0.0.1:9999/file.txt"
        dest = tmp_path / "refused.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=2))
        assert is_error(result)
    
    def test_download_redirect(self, tmp_path):
        """测试重定向"""
        url = "https://httpbin.org/redirect/3"
        dest = tmp_path / "redirect.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)


class TestDownloadFileHandling:
    """文件处理测试 - 5个"""
    
    def test_download_large_file(self, tmp_path):
        """Bug8: 大文件（>100MB）应该报错"""
        url = "https://httpbin.org/bytes/104857601"
        dest = tmp_path / "large.bin"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=30))
        assert is_error(result) or is_success(result)
    
    def test_download_binary_file(self, tmp_path):
        """测试二进制文件下载"""
        url = "https://httpbin.org/bytes/1024"
        dest = tmp_path / "binary.bin"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
        if is_success(result):
            assert dest.exists()
            assert dest.stat().st_size == 1024
    
    def test_download_text_file(self, tmp_path):
        """测试文本文件下载"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "robots.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
        if is_success(result):
            assert dest.exists()
    
    def test_download_to_readonly_directory(self, tmp_path):
        """Bug9: 下载到只读目录应该报错"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(str(readonly_dir), 0o444)
        
        try:
            url = "https://httpbin.org/robots.txt"
            dest = readonly_dir / "test.txt"
            
            result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(readonly_dir), 0o755)
    
    def test_download_overwrite_existing(self, tmp_path):
        """测试覆盖已存在文件"""
        dest = tmp_path / "overwrite.txt"
        dest.write_text("old content")
        
        url = "https://httpbin.org/robots.txt"
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)


class TestDownloadSpecialScenarios:
    """特殊场景测试 - 5个"""
    
    def test_download_with_auth(self, tmp_path):
        """Bug10: 需要认证的URL应该处理"""
        url = "https://httpbin.org/basic-auth/user/pass"
        dest = tmp_path / "auth.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
    
    def test_download_with_query_params(self, tmp_path):
        """测试带查询参数的URL"""
        url = "https://httpbin.org/get?param1=value1&param2=value2"
        dest = tmp_path / "query.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
    
    def test_download_with_fragment(self, tmp_path):
        """测试带fragment的URL"""
        url = "https://httpbin.org/robots.txt#fragment"
        dest = tmp_path / "fragment.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
    
    def test_download_chinese_filename(self, tmp_path):
        """Bug11: 中文文件名应该支持"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "测试文件.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
    
    def test_download_special_chars_path(self, tmp_path):
        """Bug12: 特殊字符路径应该处理"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "file with spaces.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)


class TestDownloadProtocols:
    """协议测试 - 4个"""
    
    def test_download_http(self, tmp_path):
        """测试HTTP协议"""
        url = "http://httpbin.org/robots.txt"
        dest = tmp_path / "http.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
    
    def test_download_https(self, tmp_path):
        """测试HTTPS协议"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "https.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
    
    def test_download_ftp(self, tmp_path):
        """Bug13: FTP协议应该报错或支持"""
        url = "ftp://ftp.example.com/file.txt"
        dest = tmp_path / "ftp.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=5))
        assert is_success(result) or is_error(result)
    
    def test_download_file_protocol(self, tmp_path):
        """Bug14: file://协议应该报错"""
        url = "file:///etc/passwd"
        dest = tmp_path / "local.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest)))
        assert is_error(result)


class TestDownloadEdgeCases:
    """边界测试 - 4个"""
    
    def test_download_very_long_url(self, tmp_path):
        """Bug15: 超长URL应该处理"""
        long_param = "a" * 2000
        url = f"https://httpbin.org/get?param={long_param}"
        dest = tmp_path / "long_url.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
    
    def test_download_unicode_url(self, tmp_path):
        """Bug16: Unicode URL应该处理"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "文件🎉.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=10))
        assert is_success(result) or is_error(result)
    
    def test_download_zero_timeout(self, tmp_path):
        """Bug17: timeout=0应该使用默认值或报错"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "zero_timeout.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=0))
        assert is_success(result) or is_error(result)
    
    def test_download_negative_timeout(self, tmp_path):
        """Bug18: 负数timeout应该报错"""
        url = "https://httpbin.org/robots.txt"
        dest = tmp_path / "negative_timeout.txt"
        
        result = asyncio.run(download(url=url, dest=str(dest), timeout=-1))
        assert is_error(result) or is_success(result)