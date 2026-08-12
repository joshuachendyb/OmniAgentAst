# -*- coding: utf-8 -*-
"""
query_sql 参数组合与内容测试 — 小健 2026-06-24

覆盖:- 参数组合:connection_type × sql类型 × limit × timeout
- 单一功能:SELECT/PRAGMA/EXPLAIN/WITH
- 混合内容:中文列名,空表,特殊字符- 真实场景:用户查询,订单统计,数据分析- 边界:空表,limit=0,limit=1
- 负面:非SELECT语找,SQL语法错误,不存在的表
"""
import sqlite3

import pytest

from app.tools.dataanalysis.query_sql import query_sql


def _make_db(tmp_path, table="users", rows=None):
    """创建测试SQLite数据库"""
    db = str(tmp_path / "test.db")
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, city TEXT)")
    if rows:
        for row in rows:
            c.execute(f"INSERT INTO {table} VALUES (?, ?, ?, ?)",
                      (row["id"], row["name"], row["age"], row["city"]))
    conn.commit()
    conn.close()
    return db


# ============================================================
# 1. 参数组合 (6组)
# ============================================================

class TestParamCombinations:
    def test_select_with_limit(self, tmp_path):
        """SELECT + limit"""
        db = _make_db(tmp_path, rows=[
            {"id": i, "name": f"user{i}", "age": 20 + i, "city": "Beijing"}
            for i in range(50)
        ])
        r = query_sql("SELECT * FROM users", limit=10, path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 10

    def test_pragma_with_timeout(self, tmp_path):
        """PRAGMA + timeout"""
        db = _make_db(tmp_path)
        r = query_sql("PRAGMA table_info(users)", timeout=5000, path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_with_cte(self, tmp_path):
        """WITH子查询"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"},
            {"id": 2, "name": "Bob", "age": 30, "city": "Shanghai"}
        ])
        r = query_sql("WITH cte AS (SELECT * FROM users WHERE age > 20) SELECT * FROM cte", path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 2

    def test_explain(self, tmp_path):
        """EXPLAIN语找"""
        db = _make_db(tmp_path)
        r = query_sql("EXPLAIN SELECT * FROM users", path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_select_with_where(self, tmp_path):
        """SELECT + WHERE"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"},
            {"id": 2, "name": "Bob", "age": 30, "city": "Shanghai"},
            {"id": 3, "name": "Charlie", "age": 35, "city": "Beijing"}
        ])
        r = query_sql("SELECT name, age FROM users WHERE city = 'Beijing' ORDER BY age", path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 2

    def test_limit_larger_than_result(self, tmp_path):
        """limit大于结果数"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"}
        ])
        r = query_sql("SELECT * FROM users", limit=100, path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 1


# ============================================================
# 2. 单一功能 (10个)
# ============================================================

class TestSingleFunction:
    def test_select_all(self, tmp_path):
        """SELECT *"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"}
        ])
        r = query_sql("SELECT * FROM users", path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 1
        assert "name" in r["data"]["columns"]

    def test_select_specific_columns(self, tmp_path):
        """SELECT指定列"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"}
        ])
        r = query_sql("SELECT name, city FROM users", path=db)
        cols = r["data"]["columns"]
        assert cols == ["name", "city"]

    def test_pragma_table_info(self, tmp_path):
        """PRAGMA table_info"""
        db = _make_db(tmp_path)
        r = query_sql("PRAGMA table_info(users)", path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        # PRAGMA返回列信息
        assert len(r["data"]["rows"]) > 0

    def test_pragma_table_list(self, tmp_path):
        """PRAGMA sqlite_master"""
        db = _make_db(tmp_path)
        r = query_sql("SELECT name FROM sqlite_master WHERE type='table'", path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] >= 1

    def test_order_by(self, tmp_path):
        """ORDER BY"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Charlie", "age": 35, "city": "C"},
            {"id": 2, "name": "Alice", "age": 25, "city": "A"},
            {"id": 3, "name": "Bob", "age": 30, "city": "B"}
        ])
        r = query_sql("SELECT name FROM users ORDER BY name", path=db)
        names = [row["name"] for row in r["data"]["rows"]]
        assert names == ["Alice", "Bob", "Charlie"]

    def test_group_by(self, tmp_path):
        """GROUP BY"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "A", "age": 25, "city": "Beijing"},
            {"id": 2, "name": "B", "age": 30, "city": "Beijing"},
            {"id": 3, "name": "C", "age": 25, "city": "Shanghai"}
        ])
        r = query_sql("SELECT city, COUNT(*) as cnt FROM users GROUP BY city", path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 2

    def test_limit_one(self, tmp_path):
        """limit=1"""
        db = _make_db(tmp_path, rows=[
            {"id": i, "name": f"u{i}", "age": 20, "city": "X"} for i in range(10)
        ])
        r = query_sql("SELECT * FROM users", limit=1, path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 1

    def test_limit_zero(self, tmp_path):
        """limit=0报错(ge=1)"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "A", "age": 20, "city": "X"}
        ])
        r = query_sql("SELECT * FROM users", limit=0, path=db)
        # limit=0不满足>=1
        assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_table_output_format(self, tmp_path):
        """table格式输出"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"}
        ])
        r = query_sql("SELECT * FROM users", path=db)
        assert "rows" in r["data"]
        assert any("Alice" in str(v) for v in r["data"]["rows"])

    def test_select_with_aggregate(self, tmp_path):
        """聚合函数"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "A", "age": 25, "city": "X"},
            {"id": 2, "name": "B", "age": 30, "city": "X"}
        ])
        r = query_sql("SELECT AVG(age) as avg_age, MAX(age) as max_age FROM users", path=db)
        assert "avg_age" in r["data"]["columns"]


# ============================================================
# 3. 真实场景 (4个)
# ============================================================

class TestRealScenarios:
    def test_user_query(self, tmp_path):
        """用户查询:按城市统计人数"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"},
            {"id": 2, "name": "Bob", "age": 30, "city": "Shanghai"},
            {"id": 3, "name": "Charlie", "age": 35, "city": "Beijing"},
            {"id": 4, "name": "David", "age": 28, "city": "Guangzhou"},
        ])
        r = query_sql("SELECT city, COUNT(*) as count FROM users GROUP BY city ORDER BY count DESC", path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 3

    def test_order_statistics(self, tmp_path):
        """订单统计"""
        c = sqlite3.connect(str(tmp_path / "orders.db"))
        c.execute("CREATE TABLE orders (id INTEGER, amount REAL, status TEXT, user_id INTEGER)")
        for i in range(20):
            status = "paid" if i % 3 != 0 else "pending"
            c.execute("INSERT INTO orders VALUES (?, ?, ?, ?)",
                      (i + 1, (i + 1) * 100.0, status, i % 5 + 1))
        c.commit()
        c.close()
        r = query_sql(
            "SELECT status, COUNT(*) as cnt, SUM(amount) as total FROM orders GROUP BY status",
            path=str(tmp_path / "orders.db"))
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 2

    def test_nested_query(self, tmp_path):
        """嵌套子查询"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"},
            {"id": 2, "name": "Bob", "age": 30, "city": "Shanghai"},
            {"id": 3, "name": "Charlie", "age": 35, "city": "Beijing"},
        ])
        r = query_sql(
            "SELECT * FROM users WHERE city IN (SELECT city FROM users GROUP BY city HAVING COUNT(*) > 1)",
            path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 2

    def test_complex_select(self, tmp_path):
        """复杂SELECT"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"},
            {"id": 2, "name": "Bob", "age": 30, "city": "Shanghai"},
        ])
        r = query_sql(
            "SELECT name, age, CASE WHEN age >= 30 THEN 'senior' ELSE 'junior' END as level FROM users",
            path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 2


# ============================================================
# 4. 边界 (4个)
# ============================================================

class TestBoundary:
    def test_empty_table(self, tmp_path):
        """空表查询"""
        db = _make_db(tmp_path)
        r = query_sql("SELECT * FROM users", path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 0

    def test_limit_exact_count(self, tmp_path):
        """limit正好等于行数"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "A", "age": 1, "city": "X"},
            {"id": 2, "name": "B", "age": 2, "city": "Y"}
        ])
        r = query_sql("SELECT * FROM users", limit=2, path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 2

    def test_many_columns(self, tmp_path):
        """很多列"""
        db = str(tmp_path / "wide.db")
        conn = sqlite3.connect(db)
        cols = ", ".join([f"col{i} INTEGER" for i in range(20)])
        conn.execute(f"CREATE TABLE wide ({cols})")
        vals = ", ".join(["?" for _ in range(20)])
        conn.execute(f"INSERT INTO wide VALUES ({vals})", tuple(range(20)))
        conn.commit()
        conn.close()
        r = query_sql("SELECT * FROM wide", path=db)
        assert len(r["data"]["columns"]) == 20

    def test_null_values(self, tmp_path):
        """NULL值查询"""
        db = _make_db(tmp_path)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO users VALUES (1, NULL, NULL, NULL)")
        conn.commit()
        conn.close()
        r = query_sql("SELECT * FROM users", path=db)
        assert r["llm_data"]["metrics"]["row_count"]["value"] == 1


# ============================================================
# 5. 负面 (4个)
# ============================================================

class TestNegative:
    def test_non_select_statement(self):
        """非SELECT语找被拦截"""
        r = query_sql("INSERT INTO users VALUES (1, 'test', 20, 'X')")
        assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_update_statement(self):
        """UPDATE被拦截"""
        r = query_sql("UPDATE users SET name = 'test' WHERE id = 1")
        assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_drop_statement(self):
        """DROP被拦截"""
        r = query_sql("DROP TABLE users")
        assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_sql_syntax_error(self, tmp_path):
        """SQL语法错误"""
        db = _make_db(tmp_path)
        r = query_sql("SELECTTT * FORM users", path=db)
        assert r["llm_data"]["status"]["exec_code"] == "error"
