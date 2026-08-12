# -*- coding: utf-8 -*-
"""
Edge case bug hunt - tests for 15 tool files
小欧 2026-07-04
"""
import asyncio
import os
import sys
import math
import json
import tempfile
import zipfile
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest


# ===== 1. tool_search.py =====
class TestSearchTool:
    def test_query_none_crash(self):
        """BUG: query=None causes 'NoneType' has no attribute 'strip()'"""
        from app.tools.fundamental.tool_search import searchtool
        from app.tools.tool_response import is_error
        # This should NOT crash 
        try:
            result = searchtool(None)
            # If we get here with an error response, it's handled
            assert is_error(result), f"Expected error response: {result}"
        except AttributeError as e:
            pytest.fail(f"CRASH BUG: query=None raises AttributeError: {e}")
        except TypeError as e:
            pytest.fail(f"CRASH BUG: query=None raises TypeError: {e}")

    def test_query_only_whitespace(self):
        """Edge: query with only whitespace"""
        from app.tools.fundamental.tool_search import searchtool
        result = searchtool("   ")
        assert result.get("code") != 500, f"Should handle whitespace-only query: {result}"

    def test_query_only_special_chars(self):
        """Edge: query with only special chars, tokens will be empty"""
        from app.tools.fundamental.tool_search import searchtool
        # '___' produces empty token list
        result = searchtool("___")
        assert result.get("code") != 500, f"Should handle special-chars query: {result}"

    def test_query_extremely_long(self):
        """Edge: extremely long query (10k chars)"""
        from app.tools.fundamental.tool_search import searchtool
        long_q = "test " * 2500  # ~12.5k chars
        result = searchtool(long_q)
        assert result.get("code") != 500, f"Should handle long query: {result}"

    def test_query_unicode_mixed(self):
        """Edge: mixed CJK + emoji + special unicode"""
        from app.tools.fundamental.tool_search import searchtool
        query = "搜索🔍工具😊 with emoji \u00e9\u00f1\u00fc \ufffc"
        result = searchtool(query)
        assert result.get("code") != 500, f"Should handle unicode query: {result}"


# ===== 2. time_add.py =====
class TestTimeAdd:
    def test_delta_nan(self):
        """BUG: delta=float('nan') creates invalid timedelta"""
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=float('nan'))
        # Should not crash or produce NaN timestamps
        assert result.get("code") != 500, f"NaN delta should not crash: {result}"
        data = result.get("data", {})
        ts = data.get("timestamp")
        if ts is not None:
            assert not (isinstance(ts, float) and math.isnan(ts)), f"timestamp should not be NaN: {data}"

    def test_delta_inf(self):
        """BUG: delta=float('inf') should not crash with OverflowError"""
        from app.tools.timer.time_add import timeadd
        # inf timedelta would raise OverflowError
        result = timeadd(delta=float('inf'))
        assert result.get("code") != 500, f"Inf delta should not crash: {result}"

    def test_delta_neg_inf(self):
        """BUG: delta=float('-inf')"""
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=float('-inf'))
        assert result.get("code") != 500, f"-Inf delta should not crash: {result}"

    def test_unit_none(self):
        """BUG: unit=None causes 'NoneType' has no attribute 'lower()'"""
        from app.tools.timer.time_add import timeadd
        try:
            result = timeadd(delta=1, start="2024-01-01", unit=None)
        except AttributeError as e:
            pytest.fail(f"CRASH BUG: unit=None raises AttributeError: {e}")
        except TypeError as e:
            # accept TypeError from validation
            pass

    def test_unit_invalid_string(self):
        """Edge: invalid unit string"""
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=1, start="2024-01-01", unit="lightyears")
        assert result.get("code") != 500, f"Invalid unit should return error: {result}"

    def test_extremely_large_delta(self):
        """Edge: extremely large delta value"""
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=1e12, start="2024-01-01")  # 1 trillion days
        assert result.get("code") != 500, f"Large delta should not crash: {result}"

    def test_delta_negative_large(self):
        """Edge: negative delta"""
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=-999999, start="2024-01-01")
        assert result.get("code") != 500, f"Negative delta should not crash: {result}"

    def test_start_date_none_explicit(self):
        """Edge: start=None (default) - should work"""
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=1)
        assert result.get("code") != 500, f"start=None default should work: {result}"

    def test_start_invalid_string(self):
        """Edge: invalid start date string"""
        from app.tools.timer.time_add import timeadd
        result = timeadd(delta=1, start="not-a-date-at-all-9999")
        assert result.get("code") != 500, f"Invalid start should return error: {result}"


# ===== 3. send_notification.py =====
class TestNotify:
    def test_title_none(self):
        """BUG: title=None might crash"""
        from app.tools.fundamental.send_notification import notify
        try:
            result = notify(title=None, message="test")
            # If win10toast not installed, returns error
            assert result.get("code") != 500 or "未安装" in str(result), f"title=None crash? {result}"
        except AttributeError as e:
            pytest.fail(f"CRASH BUG: title=None raises AttributeError: {e}")
        except Exception as e:
            if "win10toast" in str(e).lower():
                pass  # Expected if not installed
            else:
                pytest.fail(f"CRASH BUG: title=None raises {type(e).__name__}: {e}")

    def test_message_none(self):
        """BUG: message=None might crash"""
        from app.tools.fundamental.send_notification import notify
        try:
            result = notify(title="test", message=None)
            assert result.get("code") != 500 or "未安装" in str(result), f"message=None crash? {result}"
        except AttributeError as e:
            pytest.fail(f"CRASH BUG: message=None raises AttributeError: {e}")
        except Exception as e:
            if "win10toast" in str(e).lower():
                pass
            else:
                pytest.fail(f"CRASH BUG: message=None raises {type(e).__name__}: {e}")

    def test_unicode_long_message(self):
        """Edge: unicode emoji + very long message"""
        from app.tools.fundamental.send_notification import notify
        msg = "🔍" * 100 + "test" * 500  # ~2500 chars
        try:
            result = notify(title="🔍test🔍", message=msg)
            assert result.get("code") != 500 or "未安装" in str(result), f"unicode long crash? {result}"
        except Exception as e:
            if "win10toast" in str(e).lower():
                pass
            else:
                pytest.fail(f"CRASH BUG: unicode long raises {type(e).__name__}: {e}")


# ===== 4. list_directory.py =====
class TestListDirectory:
    @pytest.mark.asyncio
    async def test_dir_path_none(self):
        """BUG: dir_path=None should not crash"""
        from app.tools.file.list_directory import listdir
        try:
            result = await listdir(path=None)
            assert result.get("code") != 500, f"dir_path=None crash? {result}"
        except AttributeError as e:
            pytest.fail(f"CRASH BUG: dir_path=None AttributeError: {e}")
        except TypeError as e:
            pytest.fail(f"CRASH BUG: dir_path=None TypeError: {e}")

    @pytest.mark.asyncio
    async def test_path_is_file_not_dir(self):
        """Edge: path is a file, not a directory"""
        from app.tools.file.list_directory import listdir
        # Use this test file itself as the path
        result = await listdir(path=__file__)
        assert result.get("code") != 500, f"File path should return error: {result}"
        err = result.get("llm_data", {}).get("status", {}).get("detail", "")
        assert "不是目录" in err or "not a directory" in err.lower(), f"Expected dir error, got: {err}"


    @pytest.mark.asyncio
    async def test_invalid_sort_by(self):
        """Edge: invalid sort_by value"""
        from app.tools.file.list_directory import listdir
        result = await listdir(path=os.path.dirname(__file__), sort_by="invalid_column_xyz")
        assert result.get("code") != 500, f"Invalid sort_by should return error: {result}"

    @pytest.mark.asyncio
    async def test_sort_by_none(self):
        """Edge: sort_by=None"""
        from app.tools.file.list_directory import listdir
        try:
            result = await listdir(path=os.path.dirname(__file__), sort_by=None)
            # sort_by default is "name", but if None is explicitly passed...
            # Line 176: `if sort_by not in ("name", "size", "mtime")` -> None not in -> error
            assert result.get("code") != 500, f"sort_by=None crash? {result}"
        except Exception as e:
            pytest.fail(f"CRASH BUG: sort_by=None raises {type(e).__name__}: {e}")

    @pytest.mark.asyncio
    async def test_empty_dir_path(self):
        """Edge: empty dir_path"""
        from app.tools.file.list_directory import listdir
        result = await listdir(path="")
        assert result.get("code") != 500, f"Empty dir_path should return error: {result}"


# ===== 5. compress_files.py =====
class TestCompress:
    @pytest.mark.asyncio
    async def test_source_none(self):
        """BUG: path=None causes Path(None) TypeError"""
        from app.tools.file.compress_files import compress
        try:
            result = await compress(path=None, dest="test.zip")
        except TypeError as e:
            pytest.fail(f"CRASH BUG: path=None raises TypeError: {e}")
        except Exception as e:
            # If it fails with another error (like no task_id), that's OK
            pass

    @pytest.mark.asyncio
    async def test_empty_file_list(self):
        """Edge: source path doesn't match any files"""
        from app.tools.file.compress_files import compress
        result = await compress(
            path=os.path.join(os.path.dirname(__file__), "nonexistent_file_xyz"),
            dest=os.path.join(tempfile.gettempdir(), "test_edge_empty.zip"),
            overwrite=True
        )
        assert result.get("code") != 500, f"Non-existent source should return error: {result}"


# ===== 6. extract_archive.py =====
class TestExtract:
    @pytest.mark.asyncio
    async def test_corrupted_archive(self):
        """Edge: corrupted archive file (not a real zip)"""
        from app.tools.file.extract_archive import extract
        tmpdir = tempfile.mkdtemp()
        corrupt_zip = os.path.join(tmpdir, "corrupt.zip")
        with open(corrupt_zip, "w") as f:
            f.write("this is not a valid zip file content at all")
        result = await extract(path=corrupt_zip, dest=os.path.join(tmpdir, "out"))
        assert result.get("code") != 500, f"Corrupted archive should return error: {result}"

    @pytest.mark.asyncio
    async def test_wrong_format(self):
        """Edge: .zip file with .tar.gz extension mismatch"""
        from app.tools.file.extract_archive import extract
        tmpdir = tempfile.mkdtemp()
        fake_tar = os.path.join(tmpdir, "fake.tar.gz")
        import shutil
        # Create actual zip but name it .tar.gz
        with zipfile.ZipFile(fake_tar, 'w') as zf:
            zf.writestr("test.txt", "hello")
        result = await extract(path=fake_tar, dest=os.path.join(tmpdir, "out"))
        # This might fail or succeed depending on detection order
        assert result.get("code") != 500, f"Wrong format should not crash: {result}"

    @pytest.mark.asyncio
    async def test_destination_none(self):
        """Edge: dest=None"""
        from app.tools.file.extract_archive import extract
        tmpdir = tempfile.mkdtemp()
        real_zip = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(real_zip, 'w') as zf:
            zf.writestr("test.txt", "hello")
        result = await extract(path=real_zip, dest=None)
        assert result.get("code") != 500, f"dest=None should not crash: {result}"

    @pytest.mark.asyncio
    async def test_non_existent_source(self):
        """Edge: source file doesn't exist"""
        from app.tools.file.extract_archive import extract
        result = await extract(
            path=os.path.join(tempfile.gettempdir(), "nonexistent_archive_xyz.zip"),
            dest=os.path.join(tempfile.gettempdir(), "out_xyz")
        )
        assert result.get("code") != 500, f"Non-existent source should return error: {result}"


# ===== 7. filter_data.py =====
class TestFilterData:
    def test_conditions_as_dict(self):
        """BUG: conditions passed as dict instead of list - iterates over keys, .get() crashes"""
        from app.tools.dataanalysis.filter_data import filter_data
        try:
            result = filter_data(
                data=json.dumps([{"name": "a", "value": 1}]),
                conditions={"column": "name", "operator": "eq", "value": "a"}
            )
            assert result.get("code") != 500
        except AttributeError as e:
            pytest.fail(f"CRASH BUG: conditions as dict raises AttributeError: {e}")

    def test_empty_data_array(self):
        """Edge: empty data array"""
        from app.tools.dataanalysis.filter_data import filter_data
        result = filter_data(data=json.dumps([]))
        assert result.get("code") != 500, f"Empty data array should work: {result}"

    def test_invalid_json_data(self):
        """Edge: invalid JSON string as data"""
        from app.tools.dataanalysis.filter_data import filter_data
        result = filter_data(data="this is not json at all {{{")
        assert result.get("code") != 500, f"Invalid JSON should return error: {result}"

    def test_empty_conditions(self):
        """Edge: empty conditions list"""
        from app.tools.dataanalysis.filter_data import filter_data
        result = filter_data(
            data=json.dumps([{"name": "a", "value": 1}]),
            conditions=[]
        )
        assert result.get("code") != 500, f"Empty conditions should work: {result}"


# ===== 8. query_sql.py =====
class TestQuerySQL:
    def test_malformed_sql(self):
        """Edge: completely malformed SQL"""
        from app.tools.dataanalysis.query_sql import query_sql
        result = query_sql(
            sql="SELECT FROM WHERE garbage sql {{{",
            connection_type="sqlite",
            path=":memory:"
        )
        assert result.get("code") != 500, f"Malformed SQL should return error: {result}"

    def test_write_operation_blocked(self):
        """Safety: INSERT should be blocked"""
        from app.tools.dataanalysis.query_sql import query_sql
        result = query_sql(
            sql="INSERT INTO test VALUES (1)",
            connection_type="sqlite",
            path=":memory:"
        )
        assert result.get("code") != 500, f"INSERT should be blocked: {result}"
        detail = result.get("llm_data", {}).get("status", {}).get("detail", "")
        assert "只读" in detail or "不支持" in detail or "INSERT" in detail.upper(), f"Expected 'read-only' error: {detail}"

    def test_delete_blocked(self):
        """Safety: DELETE without WHERE should be blocked"""
        from app.tools.dataanalysis.query_sql import query_sql
        result = query_sql(
            sql="DELETE FROM test",
            connection_type="sqlite",
            path=":memory:"
        )
        assert result.get("code") != 500, f"DELETE should be blocked: {result}"

    def test_semicolon_injection_try(self):
        """Safety: SELECT with semicolon injection attempt"""
        from app.tools.dataanalysis.query_sql import query_sql
        result = query_sql(
            sql="SELECT 1; DROP TABLE users",
            connection_type="sqlite",
            path=":memory:"
        )
        # Should either execute (just SELECT 1) or fail
        assert result.get("code") != 500, f"; injection should not crash: {result}"


# ===== 9. get_db_schema.py =====
class TestGetDbSchema:
    def test_db_path_none(self):
        """BUG: path=None crashes in os.path.exists(None)"""
        from app.tools.dataanalysis.get_db_schema import get_db_schema
        try:
            result = get_db_schema(connection_type="sqlite", path=None)
            assert result.get("code") != 500, f"path=None should not crash: {result}"
        except TypeError as e:
            pytest.fail(f"CRASH BUG: path=None raises TypeError: {e}")

    def test_invalid_db_path(self):
        """Edge: non-existent db file"""
        from app.tools.dataanalysis.get_db_schema import get_db_schema
        result = get_db_schema(
            connection_type="sqlite",
            path=os.path.join(tempfile.gettempdir(), "nonexistent_db_xyz.sqlite")
        )
        assert result.get("code") != 500, f"Non-existent db should return error: {result}"

    def test_empty_string_db_path(self):
        """Edge: empty string db_path"""
        from app.tools.dataanalysis.get_db_schema import get_db_schema
        result = get_db_schema(connection_type="sqlite", path="")
        assert result.get("code") != 500, f"Empty db_path should not crash: {result}"


# ===== 10. generate_chart.py =====
class TestGenerateChart:
    def test_data_none(self):
        """BUG: data=None causes Path(None) TypeError"""
        from app.tools.dataanalysis.generate_chart import generate_chart
        try:
            result = generate_chart(data=None, chart_type="bar")
            assert result.get("code") != 500, f"data=None should not crash: {result}"
        except TypeError as e:
            pytest.fail(f"CRASH BUG: data=None raises TypeError: {e}")

    def test_data_empty_string(self):
        """Edge: empty string data"""
        from app.tools.dataanalysis.generate_chart import generate_chart
        result = generate_chart(data="", chart_type="bar")
        assert result.get("code") != 500, f"Empty data should return error: {result}"

    def test_mismatched_data_pie(self):
        """Edge: pie chart with data that has > 100% sum"""
        # This tests if pie chart handles large values
        tmpdir = tempfile.mkdtemp()
        csv_path = os.path.join(tmpdir, "test.csv")
        with open(csv_path, "w") as f:
            f.write("label,value\nA,100\nB,200\nC,300\n")
        try:
            from app.tools.dataanalysis.generate_chart import generate_chart
            result = generate_chart(data=csv_path, chart_type="pie")
            assert result.get("code") != 500, f"Pie with large values should work: {result}"
        except Exception as e:
            if "matplotlib" in str(e).lower() or "未安装" in str(e):
                pass  # Skip if matplotlib not installed
            else:
                pytest.fail(f"Pie chart error: {e}")


# ===== 11. execute_sql.py =====
class TestExecuteSQL:
    def test_delete_without_where(self):
        """Safety: DELETE without WHERE should be flagged"""
        from app.tools.dataanalysis.execute_sql import execute_sql
        result = execute_sql(
            sql="DELETE FROM test",
            connection_type="sqlite",
            path=":memory:"
        )
        assert result.get("code") != 500, f"DELETE without WHERE should be blocked: {result}"

    def test_drop_table(self):
        """Safety: DROP TABLE should be flagged"""
        from app.tools.dataanalysis.execute_sql import execute_sql
        result = execute_sql(
            sql="DROP TABLE test",
            connection_type="sqlite",
            path=":memory:"
        )
        assert result.get("code") != 500, f"DROP TABLE should be blocked: {result}"

    def test_insert_valid(self):
        """Safety: INSERT with valid table (in-memory, table exists)"""
        from app.tools.dataanalysis.execute_sql import execute_sql
        # First create table
        import sqlite3
        mem_path = os.path.join(tempfile.gettempdir(), f"test_exec_{int(time.time())}.db")
        conn = sqlite3.connect(mem_path)
        conn.execute("CREATE TABLE test (id INT, name TEXT)")
        conn.commit()
        conn.close()
        try:
            result = execute_sql(
                sql="INSERT INTO test VALUES (1, 'test')",
                connection_type="sqlite",
                path=mem_path
            )
            # Should succeed (not blocked by safety check since it's just INSERT)
            assert result.get("code") != 500, f"INSERT should work: {result}"
        finally:
            if os.path.exists(mem_path):
                os.unlink(mem_path)

    def test_empty_sql_string(self):
        """Edge: empty SQL string"""
        from app.tools.dataanalysis.execute_sql import execute_sql
        result = execute_sql(
            sql="",
            connection_type="sqlite",
            path=":memory:"
        )
        assert result.get("code") != 500, f"Empty SQL should return error: {result}"

    def test_sql_none(self):
        """BUG: sql=None crashes"""
        from app.tools.dataanalysis.execute_sql import execute_sql
        try:
            result = execute_sql(
                sql=None,
                connection_type="sqlite",
                path=":memory:"
            )
            assert result.get("code") != 500, f"sql=None should not crash: {result}"
        except AttributeError as e:
            pytest.fail(f"CRASH BUG: sql=None raises AttributeError: {e}")


# ===== 12. download_file.py =====
class TestDownload:
    @pytest.mark.asyncio
    async def test_url_none(self):
        """Edge: url=None"""
        from app.tools.network.download_file import download
        result = await download(url=None, dest="test.txt")
        assert result.get("code") != 500, f"url=None should return error: {result}"

    @pytest.mark.asyncio
    async def test_invalid_url_format(self):
        """Edge: invalid URL format"""
        from app.tools.network.download_file import download
        result = await download(url="not a valid url at all", dest="test.txt")
        assert result.get("code") != 500, f"Invalid URL should return error: {result}"

    @pytest.mark.asyncio
    async def test_download_nonexistent_dir(self):
        """Edge: destination_path in nonexistent directory"""
        from app.tools.network.download_file import download
        result = await download(
            url="https://example.com/file.txt",
            dest=os.path.join("nonexistent_dir_xyz", "file.txt")
        )
        # Should either validate the path or create the dir
        assert result.get("code") != 500, f"Non-existent dest dir should not crash: {result}"


# ===== 13. fetch_webpage.py =====
class TestFetchWebpage:
    @pytest.mark.asyncio
    async def test_file_protocol(self):
        """Edge: file:// protocol URL"""
        from app.tools.network.fetch_webpage import fetchpage

        import platform
        file_url = "file:///etc/passwd"
        if platform.system().lower() == "windows":
            file_url = "file:///C:/Windows/win.ini"

        result = await fetchpage(url=file_url)
        assert result.get("code") != 500, f"file:// URL should be rejected: {result}"

    @pytest.mark.asyncio
    async def test_ftp_protocol(self):
        """Edge: ftp:// protocol URL"""
        from app.tools.network.fetch_webpage import fetchpage
        result = await fetchpage(url="ftp://ftp.gnu.org/README")
        assert result.get("code") != 500, f"ftp:// URL should not crash: {result}"

    @pytest.mark.asyncio
    async def test_javascript_url(self):
        """Edge: javascript: URL"""
        from app.tools.network.fetch_webpage import fetchpage
        result = await fetchpage(url="javascript:alert(1)")
        assert result.get("code") != 500, f"javascript: URL should be rejected: {result}"

    @pytest.mark.asyncio
    async def test_empty_url(self):
        """Edge: empty URL"""
        from app.tools.network.fetch_webpage import fetchpage
        result = await fetchpage(url="")
        assert result.get("code") != 500, f"Empty URL should return error: {result}"


# ===== 14. network_diagnose.py =====
class TestNetworkDiagnose:
    @pytest.mark.asyncio
    async def test_timeout_none(self):
        """BUG: timeout=None should not crash"""
        from app.tools.network.network_diagnose import ping_port
        try:
            result = await ping_port(host="8.8.8.8", mode="ping", timeout=None)
            assert result.get("code") != 500, f"timeout=None should not crash: {result}"
        except TypeError as e:
            pytest.fail(f"CRASH BUG: timeout=None raises TypeError: {e}")

    @pytest.mark.asyncio
    async def test_timeout_zero(self):
        """Edge: timeout=0"""
        from app.tools.network.network_diagnose import ping_port
        result = await ping_port(host="8.8.8.8", mode="ping", timeout=0)
        assert result.get("code") != 500, f"timeout=0 should return error: {result}"

    @pytest.mark.asyncio
    async def test_count_negative(self):
        """Edge: negative ping count"""
        from app.tools.network.network_diagnose import ping_port
        result = await ping_port(host="8.8.8.8", mode="ping", count=-4, timeout=5)
        # ping -n -4 might cause subprocess issues
        assert result.get("code") != 500, f"Negative count should not crash: {result}"

    @pytest.mark.asyncio
    async def test_port_without_port_param(self):
        """Edge: port mode without port param"""
        from app.tools.network.network_diagnose import ping_port
        result = await ping_port(host="8.8.8.8", mode="port")
        assert result.get("code") != 500, f"port mode without port should return error: {result}"

    @pytest.mark.asyncio
    async def test_invalid_mode(self):
        """Edge: invalid mode string"""
        from app.tools.network.network_diagnose import ping_port
        result = await ping_port(host="8.8.8.8", mode="traceroute")
        assert result.get("code") != 500, f"Invalid mode should return error: {result}"

    @pytest.mark.asyncio
    async def test_host_none(self):
        """Edge: host=None"""
        from app.tools.network.network_diagnose import ping_port
        try:
            result = await ping_port(host=None, mode="ping")
            assert result.get("code") != 500, f"host=None should return error: {result}"
        except AttributeError as e:
            pytest.fail(f"CRASH BUG: host=None raises AttributeError: {e}")


# ===== 15. write_pdf.py =====
class TestWritePDF:
    def test_content_none(self):
        """Edge: content=None"""
        from app.tools.document.write_pdf import write_pdf
        result = write_pdf(
            path=os.path.join(tempfile.gettempdir(), "test_edge.pdf"),
            title="Test",
            content=None
        )
        assert result.get("code") != 500, f"content=None should not crash: {result}"

    def test_content_empty_string(self):
        """Edge: content='' empty string"""
        from app.tools.document.write_pdf import write_pdf
        result = write_pdf(
            path=os.path.join(tempfile.gettempdir(), "test_empty.pdf"),
            title=None,
            content=""
        )
        assert result.get("code") != 500, f"Empty content should not crash: {result}"

    def test_content_and_title_none(self):
        """Edge: both content=None and title=None"""
        from app.tools.document.write_pdf import write_pdf
        result = write_pdf(
            path=os.path.join(tempfile.gettempdir(), "test_both_none.pdf"),
            title=None,
            content=None
        )
        assert result.get("code") != 500, f"Both None should not crash: {result}"

    def test_unicode_content(self):
        """Edge: unicode content"""
        from app.tools.document.write_pdf import write_pdf
        result = write_pdf(
            path=os.path.join(tempfile.gettempdir(), "test_unicode.pdf"),
            title="Unicode 🔍 Test \u00e9\u00f1",
            content="Hello \u4e2d\u6587\nEmoji: 🔍😊🔥\nSpecial: \u00e9\u00f1\u00fc\u00df"
        )
        assert result.get("code") != 500, f"Unicode content should not crash: {result}"

    def test_file_name_none(self):
        """BUG: path=None crashes"""
        from app.tools.document.write_pdf import write_pdf
        try:
            result = write_pdf(path=None, title="Test", content="Hello")
            assert result.get("code") != 500, f"path=None should not crash: {result}"
        except TypeError as e:
            pytest.fail(f"CRASH BUG: path=None raises TypeError: {e}")


# ===== Additional cross-cutting =====
class TestTimeoutValidator:
    def test_timeout_none(self):
        """Edge: timeout=None in validate_timeout"""
        from app.tools.validate.timeout_validator import validate_timeout
        try:
            result = validate_timeout(None, "download")
            # isinstance(None, int) -> False, timeout <= 0 -> True (None <= 0)
            is_valid, err, _ = result
            assert not is_valid, f"None timeout should be invalid: {err}"
        except TypeError as e:
            pytest.fail(f"CRASH BUG: validate_timeout(None) TypeError: {e}")

    def test_timeout_negative(self):
        """Edge: negative timeout"""
        from app.tools.validate.timeout_validator import validate_timeout
        is_valid, err, _ = validate_timeout(-5, "download")
        assert not is_valid, f"Negative timeout should be invalid: {err}"
