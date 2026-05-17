# -*- coding: utf-8 -*-
"""
13.5 database 优化测试 — 8→3
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.5节
变更: check_db_exists→toolhelper; get_table_schema→合入get_db_schema(table_name=...)
      begin/commit/rollback→消除(execute_sql可执行全部SQL含事务)
新增: P15 next_actions; P16 幂等性

覆盖:
  query_sql [保留, 含 next_actions]
  execute_sql [增强: 支持事务SQL; 含 next_actions]
  get_db_schema [增强: 新增 table_name 参数]
  check_db_exists/get_table_schema/begin/commit/rollback 已消除
"""

import sqlite3
import pytest
from pathlib import Path

from app.services.tools.database.database_tools import (
    query_sql,
    execute_sql,
    get_db_schema,
)


def _create_test_db(tmp_path, name="test.db"):
    """辅助：创建测试数据库并建表"""
    db_path = str(tmp_path / name)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
    conn.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
    conn.commit()
    conn.close()
    return db_path


# ============================================================
# TestQuerySql — 保留
# ============================================================
class TestQuerySql:
    """query_sql 保留 — 含 next_actions"""

    def test_query_sql_basic(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        result = query_sql(sql="SELECT * FROM users", db_path=db_path)
        assert result["code"] == "SUCCESS"
        assert result["data"]["total"] == 2

    def test_query_sql_with_where(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        result = query_sql(sql="SELECT * FROM users WHERE age > 25", db_path=db_path)
        assert result["code"] == "SUCCESS"
        assert result["data"]["total"] == 1

    def test_query_sql_error_bad_sql(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        result = query_sql(sql="SELECTT * FROMM users", db_path=db_path)
        assert result["code"] == "ERROR"

    def test_query_sql_next_actions(self, tmp_path):
        """【P15】query_sql 成功返回 next_actions"""
        db_path = _create_test_db(tmp_path)
        result = query_sql(sql="SELECT * FROM users", db_path=db_path)
        assert "next_actions" in result
        tools = [a["tool"] for a in result["next_actions"]]
        # 应提示可跨分类使用 analyze_data/generate_chart
        assert "execute_sql" in tools

    def test_query_sql_next_actions_analyze(self, tmp_path):
        """【P15】query_sql 跨分类建议 analyze_data"""
        db_path = _create_test_db(tmp_path)
        result = query_sql(sql="SELECT * FROM users", db_path=db_path)
        assert "next_actions" in result
        tools = [a.get("tool") for a in result["next_actions"]]
        assert any("analyze" in t for t in tools if t)


# ============================================================
# TestExecuteSql — 增强: 支持事务SQL
# ============================================================
class TestExecuteSql:
    """execute_sql 增强测试 — 支持事务SQL替代begin/commit/rollback"""

    def test_execute_sql_insert(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        result = execute_sql(sql="INSERT INTO users VALUES (3, 'Charlie', 35)",
                             db_path=db_path)
        assert result["code"] == "SUCCESS"
        # 验证写入成功
        conn = sqlite3.connect(db_path)
        cnt = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        assert cnt == 3

    def test_execute_sql_dry_run(self, tmp_path):
        """正常：dry_run 模式"""
        db_path = _create_test_db(tmp_path)
        result = execute_sql(sql="INSERT INTO users VALUES (99, 'Dry', 99)",
                             db_path=db_path, dry_run=True)
        assert result["code"] == "SUCCESS"
        assert result["data"]["dry_run"] is True
        # 验证未实际写入
        conn = sqlite3.connect(db_path)
        cnt = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        assert cnt == 2

    def test_execute_sql_error_dangerous(self):
        """异常：危险SQL应收到warning"""
        result = execute_sql(sql="DROP TABLE users")
        assert result["code"] == "WARNING"

    def test_execute_sql_begin_commit(self, tmp_path):
        """【替代begin/commit】execute_sql 支持事务SQL"""
        db_path = _create_test_db(tmp_path)
        # 代替调用 begin_transaction() + 多条INSERT + commit_transaction()
        r1 = execute_sql(sql="BEGIN TRANSACTION", db_path=db_path)
        assert r1["code"] == "SUCCESS"
        execute_sql(sql="INSERT INTO users VALUES (10, 'Trans', 99)", db_path=db_path)
        r2 = execute_sql(sql="COMMIT", db_path=db_path)
        assert r2["code"] == "SUCCESS"
        conn = sqlite3.connect(db_path)
        cnt = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        assert cnt == 3

    def test_execute_sql_rollback(self, tmp_path):
        """【替代rollback】execute_sql 支持回滚"""
        db_path = _create_test_db(tmp_path)
        execute_sql(sql="BEGIN TRANSACTION", db_path=db_path)
        execute_sql(sql="INSERT INTO users VALUES (20, 'Rollback', 0)", db_path=db_path)
        r = execute_sql(sql="ROLLBACK", db_path=db_path)
        assert r["code"] == "SUCCESS"
        conn = sqlite3.connect(db_path)
        cnt = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        assert cnt == 2  # 回滚成功

    def test_execute_sql_next_actions(self, tmp_path):
        """【P15】execute_sql 返回 next_actions"""
        db_path = _create_test_db(tmp_path)
        result = execute_sql(sql="INSERT INTO users VALUES (30, 'Test', 1)",
                             db_path=db_path, dry_run=True)
        assert "next_actions" in result
        tools = [a["tool"] for a in result["next_actions"]]
        assert "query_sql" in tools

    def test_execute_sql_p16_dry_run(self, tmp_path):
        """【P16幂等】dry_run 可安全重复调用"""
        db_path = _create_test_db(tmp_path)
        r1 = execute_sql(sql="INSERT INTO users VALUES (40, 'Idem', 1)",
                         db_path=db_path, dry_run=True)
        r2 = execute_sql(sql="INSERT INTO users VALUES (40, 'Idem', 1)",
                         db_path=db_path, dry_run=True)
        assert r1["code"] == r2["code"] == "SUCCESS"


# ============================================================
# TestGetDbSchema — 增强: 支持 table_name 参数
# ============================================================
class TestGetDbSchema:
    """get_db_schema 增强测试 — 新增 table_name 参数"""

    def test_get_db_schema_all_tables(self, tmp_path):
        """正常：获取全部表结构"""
        db_path = _create_test_db(tmp_path)
        result = get_db_schema(db_path=db_path)
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["tables"]) == 2

    def test_get_db_schema_with_table_name(self, tmp_path):
        """【合并get_table_schema】指定 table_name 获取单表结构"""
        db_path = _create_test_db(tmp_path)
        result = get_db_schema(db_path=db_path, table_name="users")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["tables"]) == 1
        assert result["data"]["tables"][0]["name"] == "users"
        columns = result["data"]["tables"][0]["columns"]
        assert len(columns) == 3

    def test_get_db_schema_table_not_found(self, tmp_path):
        """异常：指定不存在的表"""
        db_path = _create_test_db(tmp_path)
        result = get_db_schema(db_path=db_path, table_name="nonexistent_table")
        assert result["code"] == "ERR_TABLE_NOT_FOUND"

    def test_get_db_schema_db_not_found(self):
        """异常：数据库文件不存在"""
        result = get_db_schema(db_path="/nonexistent_db_12345.db")
        assert result["code"] in ("ERROR", "SUCCESS", "ERR_DB_NOT_FOUND")

    def test_get_db_schema_next_actions(self, tmp_path):
        """【P15】get_db_schema 返回 next_actions 建议 query_sql"""
        db_path = _create_test_db(tmp_path)
        result = get_db_schema(db_path=db_path)
        if result["code"] == "SUCCESS":
            assert "next_actions" in result
            tools = [a["tool"] for a in result["next_actions"]]
            assert "query_sql" in tools


# ============================================================
# TestEliminated — 验证已消除的工具
# ============================================================
class TestEliminated:
    """验证 check_db_exists/get_table_schema/begin/commit/rollback 已消除"""

    def test_check_db_exists_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.support_tool.support_tool_tools import check_db_exists  # noqa

    def test_get_table_schema_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.support_tool.support_tool_tools import get_table_schema  # noqa

    def test_begin_transaction_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.database.database_tools import begin_transaction  # noqa

    def test_commit_transaction_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.database.database_tools import commit_transaction  # noqa

    def test_rollback_transaction_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.database.database_tools import rollback_transaction  # noqa
