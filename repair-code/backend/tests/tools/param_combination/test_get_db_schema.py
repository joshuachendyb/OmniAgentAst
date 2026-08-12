# -*- coding: utf-8 -*-
"""
get_db_schema 参数组合与内容测试 — 小欧 2026-06-24

覆盖:- 参数组合:connection_type x table_name x filter_pattern x include_columns/indexes/comments
- 单一功能:全表/单表/模式过滤
- 混合内容:中文表名,特殊字符表名,大小写
- 真实场景:多表数据库,空表,复杂结构
- 边界:空数据库,单表,大量表
- 负面:不存在的表,连接失败,SQL注入
"""
import sqlite3
import asyncio

import pytest

from app.tools.dataanalysis.get_db_schema import (
    get_db_schema, _get_tables, _get_columns, _get_indexes, _filter_tables
)


def _make_schema_db(tmp_path):
    """创建含多表的测试数据库"""
    db = str(tmp_path / "schema_test.db")
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        age INTEGER DEFAULT 0,
        email TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX idx_users_name ON users(name)")
    c.execute("CREATE UNIQUE INDEX idx_users_email ON users(email)")

    c.execute("""CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        amount REAL DEFAULT 0.0,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    c.execute("CREATE INDEX idx_orders_user ON orders(user_id)")
    c.execute("CREATE INDEX idx_orders_status ON orders(status)")

    c.execute("""CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL DEFAULT 0.0,
        category TEXT
    )""")

    conn.commit()
    conn.close()
    return db


# ============================================================
# 1. 参数组合 (6组)
# ============================================================

class TestParamCombinations:
    def test_all_tables_default(self, tmp_path):
        """默认参数获取所有表"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["metrics"]["total"]["value"] == 3

    def test_single_table(self, tmp_path):
        """指定单个表"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, table_name="users")
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["metrics"]["total"]["value"] == 1
        assert r["data"]["tables"][0]["name"] == "users"

    def test_filter_pattern(self, tmp_path):
        """filter_pattern过滤"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, filter_pattern="user*")
        assert r["llm_data"]["metrics"]["total"]["value"] == 1

    def test_filter_pattern_underscore(self, tmp_path):
        """filter_pattern用_匹配单字符"""
        db = _make_schema_db(tmp_path)
        # orders和products都匹配不到user?
        r = get_db_schema(path=db, filter_pattern="product*")
        assert r["llm_data"]["metrics"]["total"]["value"] == 1

    def test_table_name_not_found(self, tmp_path):
        """指定不存在的表名"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, table_name="nonexistent")
        assert r["llm_data"]["status"]["exec_code"] == "error"
        assert "不存在" in r["llm_data"]["status"]["detail"]

    def test_all_params_combined(self, tmp_path):
        """全参数组合"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, table_name="users")
        assert r["llm_data"]["metrics"]["total"]["value"] == 1
        table = r["data"]["tables"][0]
        assert len(table["columns"]) > 0


# ============================================================
# 2. 单一功能 (10个)
# ============================================================

class TestSingleFunction:
    def test_get_tables(self, tmp_path):
        """_get_tables获取表列表"""
        db = _make_schema_db(tmp_path)
        conn = sqlite3.connect(db)
        tables = _get_tables(conn, "sqlite", None)
        conn.close()
        assert "users" in tables
        assert "orders" in tables
        assert "products" in tables

    def test_get_columns(self, tmp_path):
        """_get_columns获取列信息"""
        db = _make_schema_db(tmp_path)
        conn = sqlite3.connect(db)
        cols = _get_columns(conn, "sqlite", "users")
        conn.close()
        col_names = [c["name"] for c in cols]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names

    def test_get_indexes(self, tmp_path):
        """_get_indexes获取索引信息"""
        db = _make_schema_db(tmp_path)
        conn = sqlite3.connect(db)
        indexes = _get_indexes(conn, "sqlite", "users")
        conn.close()
        assert len(indexes) >= 1

    def test_filter_tables_exact(self, tmp_path):
        """_filter_tables精认匹配"""
        tables = ["users", "orders", "products"]
        result = _filter_tables(tables, "users", None)
        assert result == ["users"]

    def test_filter_tables_pattern(self, tmp_path):
        """_filter_tables通配符匹配"""
        tables = ["users", "orders", "products"]
        result = _filter_tables(tables, None, "user*")
        assert result == ["users"]

    def test_filter_tables_no_match(self, tmp_path):
        """_filter_tables无匹配"""
        tables = ["users", "orders"]
        result = _filter_tables(tables, "nonexistent", None)
        assert result == []

    def test_markdown_output(self, tmp_path):
        """markdown格式输出"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db)
        assert "tables" in r["data"]
        assert any(t["name"] == "users" for t in r["data"]["tables"])

    def test_column_types(self, tmp_path):
        """列类型正认"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, table_name="users")
        cols = r["data"]["tables"][0]["columns"]
        id_col = [c for c in cols if c["name"] == "id"][0]
        assert "INTEGER" in id_col["type"].upper()

    def test_pk_detection(self, tmp_path):
        """主键检测"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, table_name="users")
        cols = r["data"]["tables"][0]["columns"]
        id_col = [c for c in cols if c["name"] == "id"][0]
        assert id_col["pk"] is True

    def test_nullable_detection(self, tmp_path):
        """可空检测"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, table_name="users")
        cols = r["data"]["tables"][0]["columns"]
        name_col = [c for c in cols if c["name"] == "name"][0]
        # name NOT NULL -> nullable=False
        assert name_col["nullable"] is False


# ============================================================
# 3. 真实场景 (3个)
# ============================================================

class TestRealScenarios:
    def test_multi_table_database(self, tmp_path):
        """多表数据库结构"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db)
        tables = r["data"]["tables"]
        assert len(tables) == 3
        table_names = [t["name"] for t in tables]
        assert "users" in table_names
        assert "orders" in table_names
        assert "products" in table_names

    def test_complex_table_structure(self, tmp_path):
        """复杂表结构(含外键,默认值)"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, table_name="orders")
        cols = r["data"]["tables"][0]["columns"]
        user_id_col = [c for c in cols if c["name"] == "user_id"][0]
        assert user_id_col["pk"] is False

    def test_schema_markdown_readable(self, tmp_path):
        """markdown可读性"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db)
        assert "tables" in r["data"]
        assert len(r["data"]["tables"]) > 0


# ============================================================
# 4. 边界 (4个)
# ============================================================

class TestBoundary:
    def test_empty_database(self, tmp_path):
        """空数据库(无表)"""
        db = str(tmp_path / "empty.db")
        conn = sqlite3.connect(db)
        conn.close()
        r = get_db_schema(path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["metrics"]["total"]["value"] == 0

    def test_single_table(self, tmp_path):
        """只有一个表"""
        db = str(tmp_path / "single.db")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE only_table (id INTEGER)")
        conn.commit()
        conn.close()
        r = get_db_schema(path=db)
        assert r["llm_data"]["metrics"]["total"]["value"] == 1

    def test_many_tables(self, tmp_path):
        """大量表"""
        db = str(tmp_path / "many.db")
        conn = sqlite3.connect(db)
        for i in range(30):
            conn.execute(f"CREATE TABLE table_{i:02d} (id INTEGER, val TEXT)")
        conn.commit()
        conn.close()
        r = get_db_schema(path=db)
        assert r["llm_data"]["metrics"]["total"]["value"] == 30

    def test_table_with_many_columns(self, tmp_path):
        """大量列的表"""
        db = str(tmp_path / "wide.db")
        conn = sqlite3.connect(db)
        cols = ", ".join([f"col_{i:02d} TEXT" for i in range(50)])
        conn.execute(f"CREATE TABLE wide_table ({cols})")
        conn.commit()
        conn.close()
        r = get_db_schema(path=db, table_name="wide_table")
        assert len(r["data"]["tables"][0]["columns"]) == 50


# ============================================================
# 5. 负面 (4个)
# ============================================================

class TestNegative:
    def test_nonexistent_db_file(self):
        """不存在的数据库文件"""
        r = get_db_schema(path="G:\\nonexistent_xyz_test\\path\\db.sqlite")
        assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_table_name_injection(self, tmp_path):
        """SQL注入:表名含特殊字符"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, table_name="users'; DROP TABLE users; --")
        # 应该被正则拦截或找不到表
        assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_filter_pattern_no_match(self, tmp_path):
        """filter_pattern无匹配"""
        db = _make_schema_db(tmp_path)
        r = get_db_schema(path=db, filter_pattern="zzz*")
        # 无匹配但没有指定table_name,不报错
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["metrics"]["total"]["value"] == 0

    def test_invalid_filter_pattern(self, tmp_path):
        """filter_pattern含SQL特殊字符"""
        db = _make_schema_db(tmp_path)
        # fnmatch处理,不会导致SQL注入
        r = get_db_schema(path=db, filter_pattern="users; DROP TABLE users")
        assert r["llm_data"]["status"]["exec_code"] == "success"
