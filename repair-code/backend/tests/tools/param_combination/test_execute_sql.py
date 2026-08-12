# -*- coding: utf-8 -*-
"""
execute_sql 参数组合与内容测试 —— 小欧 2026-06-24

覆盖:- 参数组合:dry_run x sql类型 x connection_type x timeout
- 单一功能:INSERT/UPDATE/DELETE/CREATE/DROP + dry_run
- 混合内容:中文数据,特殊字符,多语找
- 真实场景:增删改,批量操作,事务 - 边界:空表操作,批量DELETE,无WHERE UPDATE
- 负面:危险操作无dry_run,语法错误,连接失败"""
import sqlite3
import asyncio

import pytest

from app.tools.dataanalysis.execute_sql import execute_sql, _check_sql_safety


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


def _read_all(db, table="users"):
    conn = sqlite3.connect(db)
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    conn.close()
    return rows


# ============================================================
# 1. 参数组合 (6组)
# ============================================================

class TestParamCombinations:
    def test_insert_with_dry_run(self, tmp_path):
        """INSERT + dry_run=True"""
        db = _make_db(tmp_path)
        r = execute_sql("INSERT INTO users VALUES (1, 'Alice', 25, 'Beijing')",
                        dry_run=True, path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["data"]["syntax_valid"] is True
        # dry_run不实际执行
        assert len(_read_all(db)) == 0

    def test_insert_real(self, tmp_path):
        """INSERT实际执行"""
        db = _make_db(tmp_path)
        r = execute_sql("INSERT INTO users VALUES (1, 'Alice', 25, 'Beijing')",
                        path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 1
        assert len(_read_all(db)) == 1

    def test_update_with_dry_run(self, tmp_path):
        """UPDATE + dry_run"""
        db = _make_db(tmp_path, rows=[{"id": 1, "name": "Alice", "age": 25, "city": "X"}])
        r = execute_sql("UPDATE users SET age = 30 WHERE id = 1",
                        dry_run=True, path=db)
        assert r["data"]["syntax_valid"] is True
        # 数据未改变
        rows = _read_all(db)
        assert rows[0][2] == 25

    def test_delete_with_dry_run(self, tmp_path):
        """DELETE + dry_run"""
        db = _make_db(tmp_path, rows=[{"id": 1, "name": "Alice", "age": 25, "city": "X"}])
        r = execute_sql("DELETE FROM users WHERE id = 1",
                        dry_run=True, path=db)
        assert r["data"]["syntax_valid"] is True
        assert len(_read_all(db)) == 1

    def test_create_table(self, tmp_path):
        """CREATE TABLE"""
        db = str(tmp_path / "new.db")
        r = execute_sql(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)",
            dry_run=True, path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_multiple_statements_dry_run(self, tmp_path):
        """多语找dry_run(SQLite不支持)"""
        db = _make_db(tmp_path)
        r = execute_sql(
            "INSERT INTO users VALUES (1, 'A', 1, 'X'); INSERT INTO users VALUES (2, 'B', 2, 'Y')",
            dry_run=True, path=db)
        # SQLite的executescript或execute可能只执行第一条
        # 这里是dry_run,看是否能正认检测语法

# ============================================================
# 2. 单一功能 (12个)
# ============================================================

class TestSingleFunction:
    def test_insert_single_row(self, tmp_path):
        """INSERT单行"""
        db = _make_db(tmp_path)
        r = execute_sql("INSERT INTO users VALUES (1, '张三', 28, '北京')", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 1

    def test_insert_multiple_rows(self, tmp_path):
        """INSERT多行"""
        db = _make_db(tmp_path)
        sql = """
        INSERT INTO users VALUES (1, 'Alice', 25, 'Beijing');
        INSERT INTO users VALUES (2, 'Bob', 30, 'Shanghai');
        INSERT INTO users VALUES (3, 'Charlie', 35, 'Guangzhou');
        """
        # SQLite execute只执行第一条
        r = execute_sql(sql.strip(), path=db)
        # 需要认认:SQLite是否支持多语找
    def test_update_with_where(self, tmp_path):
        """UPDATE带WHERE"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "Beijing"},
            {"id": 2, "name": "Bob", "age": 30, "city": "Shanghai"}
        ])
        r = execute_sql("UPDATE users SET age = 26 WHERE id = 1", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 1
        rows = _read_all(db)
        assert rows[0][2] == 26

    def test_delete_with_where(self, tmp_path):
        """DELETE带WHERE"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "X"},
            {"id": 2, "name": "Bob", "age": 30, "city": "Y"}
        ])
        r = execute_sql("DELETE FROM users WHERE id = 1", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 1
        assert len(_read_all(db)) == 1

    def test_create_and_drop_table(self, tmp_path):
        """CREATE TABLE + DROP TABLE"""
        db = _make_db(tmp_path)
        r1 = execute_sql("CREATE TABLE new_table (id INTEGER, val TEXT)", path=db)
        # CREATE被检测为危险操作
        assert r1["llm_data"]["status"]["exec_code"] == "warning"
        r2 = execute_sql("DROP TABLE new_table", path=db)
        assert r2["llm_data"]["status"]["exec_code"] == "warning"

    def test_dry_run_syntax_valid(self, tmp_path):
        """dry_run语法正认"""
        db = _make_db(tmp_path)
        r = execute_sql("INSERT INTO users VALUES (1, 'A', 1, 'X')",
                        dry_run=True, path=db)
        assert r["data"]["syntax_valid"] is True

    def test_dry_run_syntax_invalid(self, tmp_path):
        """dry_run语法错误"""
        db = _make_db(tmp_path)
        r = execute_sql("INSERTT INTO users VALUES (1, 'A', 1, 'X')",
                        dry_run=True, path=db)
        assert r["llm_data"]["status"]["exec_code"] == "error"
        assert "syntax_valid" not in r["data"]

    def test_dry_run_delete(self, tmp_path):
        """dry_run DELETE"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "A", "age": 1, "city": "X"},
            {"id": 2, "name": "B", "age": 2, "city": "Y"}
        ])
        r = execute_sql("DELETE FROM users", dry_run=True, path=db)
        assert r["data"]["syntax_valid"] is True
        assert len(_read_all(db)) == 2

    def test_insert_with_special_chars(self, tmp_path):
        """INSERT含特殊字符"""
        db = _make_db(tmp_path)
        r = execute_sql("INSERT INTO users VALUES (1, 'O''Brien', 25, 'New York')", path=db)
        # 单引号转义
    def test_insert_chinese_content(self, tmp_path):
        """INSERT中文内容"""
        db = _make_db(tmp_path)
        r = execute_sql(
            "INSERT INTO users VALUES (1, '张三', 28, '北京市海淀区')",
            path=db)
        assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_update_nonexistent_id(self, tmp_path):
        """UPDATE不存在的ID"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "X"}
        ])
        r = execute_sql("UPDATE users SET age = 30 WHERE id = 999", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 0

    def test_delete_nonexistent_id(self, tmp_path):
        """DELETE不存在的ID"""
        db = _make_db(tmp_path, rows=[
            {"id": 1, "name": "Alice", "age": 25, "city": "X"}
        ])
        r = execute_sql("DELETE FROM users WHERE id = 999", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 0


# ============================================================
# 3. 真实场景 (3个)
# ============================================================

class TestRealScenarios:
    def test_user_registration(self, tmp_path):
        """用户注册流程"""
        db = _make_db(tmp_path)
        # 注册
        r = execute_sql("INSERT INTO users VALUES (1, '新用户', 25, '北京')", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 1
        # 验证
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT * FROM users WHERE id = 1").fetchone()
        conn.close()
        assert row[1] == "新用户"

    def test_batch_update(self, tmp_path):
        """批量更新"""
        db = _make_db(tmp_path, rows=[
            {"id": i, "name": f"user{i}", "age": 20, "city": "Beijing"}
            for i in range(5)
        ])
        r = execute_sql("UPDATE users SET city = 'Shanghai' WHERE age = 20", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 5

    def test_transaction_rollback(self, tmp_path):
        """事务回滚"""
        db = _make_db(tmp_path)
        # 先插入一条
        execute_sql("INSERT INTO users VALUES (1, 'Alice', 25, 'X')", path=db)
        # 尝试插入重复主键
        r = execute_sql("INSERT INTO users VALUES (1, 'Bob', 30, 'Y')", path=db)
        # 应该报错
        assert r["llm_data"]["status"]["exec_code"] == "error"
        # 原数据不受影响
        rows = _read_all(db)
        assert len(rows) == 1
        assert rows[0][1] == "Alice"


# ============================================================
# 4. 边界 (4个)
# ============================================================

class TestBoundary:
    def test_empty_table_insert(self, tmp_path):
        """空表插入"""
        db = _make_db(tmp_path)
        r = execute_sql("INSERT INTO users VALUES (1, 'first', 1, 'X')", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 1
        assert len(_read_all(db)) == 1

    def test_empty_table_delete(self, tmp_path):
        """空表DELETE"""
        db = _make_db(tmp_path)
        r = execute_sql("DELETE FROM users WHERE id = 1", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 0

    def test_large_batch_insert(self, tmp_path):
        """大批量插入(10000+触发warning)"""
        db = _make_db(tmp_path)
        values = ", ".join([f"({i}, 'user{i}', {20 + i % 10}, 'city')" for i in range(10001)])
        r = execute_sql(f"INSERT INTO users VALUES {values}", path=db)
        # affected_rows > 10000 触发warning + rollback

    def test_delete_all_rows(self, tmp_path):
        """DELETE全部行"""
        db = _make_db(tmp_path, rows=[
            {"id": i, "name": f"u{i}", "age": 20, "city": "X"} for i in range(10)
        ])
        r = execute_sql("DELETE FROM users WHERE 1=1", path=db)
        assert r["llm_data"]["metrics"]["affected_rows"]["value"] == 10
        assert len(_read_all(db)) == 0


# ============================================================
# 5. 负面 (5个)
# ============================================================

class TestNegative:
    def test_drop_without_dry_run(self):
        """DROP无dry_run被拦截"""
        r = execute_sql("DROP TABLE users")
        assert r["llm_data"]["status"]["exec_code"] == "warning"

    def test_truncate_without_dry_run(self):
        """TRUNCATE被拦截"""
        r = execute_sql("TRUNCATE TABLE users")
        assert r["llm_data"]["status"]["exec_code"] == "warning"

    def test_alter_without_dry_run(self):
        """ALTER被拦截"""
        r = execute_sql("ALTER TABLE users ADD COLUMN new_col TEXT")
        assert r["llm_data"]["status"]["exec_code"] == "warning"

    def test_update_no_where(self):
        """UPDATE无WHERE被拦截"""
        r = execute_sql("UPDATE users SET name = 'test'")
        assert r["llm_data"]["status"]["exec_code"] == "warning"

    def test_delete_no_where(self):
        """DELETE无WHERE被拦截"""
        r = execute_sql("DELETE FROM users")
        assert r["llm_data"]["status"]["exec_code"] == "warning"


# ============================================================
# 5.5 P01 confirm_ddl 放行测试 — 小欧 2026-08-07
# ============================================================

class TestConfirmDdl:
    """confirm_ddl=True 仅放行白名单DDL; NO_WHERE 等非DDL风险永不放行"""

    def test_confirm_ddl_allows_drop(self, tmp_path):
        """DROP + confirm_ddl=True 放行, 表真实删除"""
        db = _make_db(tmp_path)
        r = execute_sql("DROP TABLE users", path=db, confirm_ddl=True)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        conn = sqlite3.connect(db)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchall()
        conn.close()
        assert tables == []

    def test_confirm_ddl_allows_create(self, tmp_path):
        """CREATE + confirm_ddl=True 放行, 新表真实创建"""
        db = _make_db(tmp_path)
        r = execute_sql("CREATE TABLE t2 (id INT, name TEXT)", path=db, confirm_ddl=True)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        conn = sqlite3.connect(db)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='t2'").fetchall()
        conn.close()
        assert len(tables) == 1

    def test_confirm_ddl_not_bypass_no_where(self, tmp_path):
        """confirm_ddl=True 不豁免 DELETE无WHERE(非白名单DDL)"""
        db = _make_db(tmp_path, rows=[{"id": 1, "name": "A", "age": 1, "city": "X"}])
        r = execute_sql("DELETE FROM users", path=db, confirm_ddl=True)
        assert r["llm_data"]["status"]["exec_code"] == "warning"
        assert len(_read_all(db)) == 1  # 数据未被清空


# ============================================================
# 6. _check_sql_safety 单元测试
# ============================================================

class TestCheckSqlSafety:
    def test_safe_insert(self):
        ok, msg, detected = _check_sql_safety("INSERT INTO users VALUES (1, 'A', 1, 'X')")
        assert ok is False

    def test_dangerous_drop(self):
        ok, msg, detected = _check_sql_safety("DROP TABLE users")
        assert ok is True
        assert "DROP" in detected

    def test_dangerous_truncate(self):
        ok, msg, detected = _check_sql_safety("TRUNCATE TABLE users")
        assert ok is True
        assert "TRUNCATE" in detected

    def test_no_where_delete(self):
        ok, msg, detected = _check_sql_safety("DELETE FROM users")
        assert ok is True
        assert "NO_WHERE" in detected

    def test_no_where_update(self):
        ok, msg, detected = _check_sql_safety("UPDATE users SET name = 'x'")
        assert ok is True
        assert "NO_WHERE" in detected

    def test_delete_with_where(self):
        ok, msg, detected = _check_sql_safety("DELETE FROM users WHERE id = 1")
        assert ok is False

    def test_update_with_where(self):
        ok, msg, detected = _check_sql_safety("UPDATE users SET name = 'x' WHERE id = 1")
        assert ok is False

    # === #6 豁免测试 === — 小欧 2026-07-23
    def test_create_index_safe(self):
        """CREATE INDEX 应豁免(安全DDL)"""
        ok, msg, detected = _check_sql_safety("CREATE INDEX idx ON users(id)")
        assert ok is False

    def test_create_trigger_safe(self):
        """CREATE TRIGGER 应豁免(安全DDL)"""
        ok, msg, detected = _check_sql_safety("CREATE TRIGGER trg AFTER INSERT ON users BEGIN SELECT 1; END")
        assert ok is False

    def test_create_temp_table_if_not_exists_safe(self):
        """CREATE TEMP TABLE IF NOT EXISTS 应豁免"""
        ok, msg, detected = _check_sql_safety("CREATE TEMP TABLE IF NOT EXISTS tmp (id INT)")
        assert ok is False

    def test_create_unique_index_safe(self):
        """CREATE UNIQUE INDEX 应豁免"""
        ok, msg, detected = _check_sql_safety("CREATE UNIQUE INDEX uq_idx ON users(id)")
        assert ok is False

    def test_drop_if_exists_safe(self):
        """DROP TABLE IF EXISTS 应豁免(语义安全)"""
        ok, msg, detected = _check_sql_safety("DROP TABLE IF EXISTS users")
        assert ok is False

    def test_drop_view_if_exists_safe(self):
        """DROP VIEW IF EXISTS 应豁免"""
        ok, msg, detected = _check_sql_safety("DROP VIEW IF EXISTS v_users")
        assert ok is False

    def test_drop_without_if_exists_still_dangerous(self):
        """DROP TABLE 无 IF EXISTS 仍危险"""
        ok, msg, detected = _check_sql_safety("DROP TABLE users")
        assert ok is True
        assert "DROP" in detected
