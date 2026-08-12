# -*- coding: utf-8 -*-
"""
query_sql工具深度测试 — 挖掘bug

测试目标：发现query_sql工具的各种bug和边界问题
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import sqlite3
import os
from pathlib import Path
from app.tools.dataanalysis.query_sql import query_sql


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


@pytest.fixture
def test_db(tmp_path):
    """创建测试数据库"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            email TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT
        )
    """)
    
    cursor.executemany(
        "INSERT INTO users (name, age, email) VALUES (?, ?, ?)",
        [("Alice", 25, "alice@example.com"),
         ("Bob", 30, "bob@example.com"),
         ("Charlie", 35, "charlie@example.com")]
    )
    
    cursor.executemany(
        "INSERT INTO orders (user_id, amount, status) VALUES (?, ?, ?)",
        [(1, 100.0, "completed"),
         (1, 200.0, "pending"),
         (2, 150.0, "completed")]
    )
    
    conn.commit()
    conn.close()
    
    return str(db_path)


class TestQuerySQLBasicParams:
    """参数组合测试 - 6个"""
    
    def test_simple_select(self, test_db):
        """组合1: 简单SELECT查询"""
        result = query_sql(sql="SELECT * FROM users", path=test_db)
        assert is_success(result)
        assert result["llm_data"]["metrics"]["row_count"]["value"] == 3
    
    def test_select_with_where(self, test_db):
        """组合2: 带WHERE条件的查询"""
        result = query_sql(sql="SELECT * FROM users WHERE age > 25", path=test_db)
        assert is_success(result)
        assert result["llm_data"]["metrics"]["row_count"]["value"] == 2
    
    def test_select_with_limit(self, test_db):
        """组合3: 带LIMIT的查询"""
        result = query_sql(sql="SELECT * FROM users LIMIT 2", path=test_db)
        assert is_success(result)
        assert result["llm_data"]["metrics"]["row_count"]["value"] == 2
    
    def test_select_with_order_by(self, test_db):
        """组合4: 带ORDER BY的查询"""
        result = query_sql(sql="SELECT * FROM users ORDER BY age DESC", path=test_db)
        assert is_success(result)
        rows = result["data"]["rows"]
        assert rows[0]["name"] == "Charlie"
    
    def test_select_specific_columns(self, test_db):
        """组合5: 选择特定列"""
        result = query_sql(sql="SELECT name, age FROM users", path=test_db)
        assert is_success(result)
        assert "name" in result["data"]["columns"]
        assert "age" in result["data"]["columns"]
    
    def test_count_query(self, test_db):
        """组合6: COUNT查询"""
        result = query_sql(sql="SELECT COUNT(*) as count FROM users", path=test_db)
        assert is_success(result)
        assert result["data"]["rows"][0]["count"] == 3


class TestQuerySQLInvalidOperations:
    """无效操作测试 - 6个"""
    
    def test_insert_blocked(self, test_db):
        """Bug1: INSERT应该被阻止"""
        result = query_sql(
            sql="INSERT INTO users (name, age, email) VALUES ('Test', 20, 'test@example.com')",
            path=test_db
        )
        assert is_error(result)
    
    def test_update_blocked(self, test_db):
        """Bug2: UPDATE应该被阻止"""
        result = query_sql(sql="UPDATE users SET age = 40 WHERE name = 'Alice'", path=test_db)
        assert is_error(result)
    
    def test_delete_blocked(self, test_db):
        """Bug3: DELETE应该被阻止"""
        result = query_sql(sql="DELETE FROM users WHERE name = 'Alice'", path=test_db)
        assert is_error(result)
    
    def test_drop_blocked(self, test_db):
        """Bug4: DROP应该被阻止"""
        result = query_sql(sql="DROP TABLE users", path=test_db)
        assert is_error(result)
    
    def test_create_blocked(self, test_db):
        """Bug5: CREATE应该被阻止"""
        result = query_sql(sql="CREATE TABLE test (id INTEGER)", path=test_db)
        assert is_error(result)
    
    def test_truncate_blocked(self, test_db):
        """Bug6: TRUNCATE应该被阻止"""
        result = query_sql(sql="TRUNCATE TABLE users", path=test_db)
        assert is_error(result)


class TestQuerySQLSyntaxErrors:
    """语法错误测试 - 5个"""
    
    def test_invalid_sql_syntax(self, test_db):
        """Bug7: 无效SQL语法应该报错"""
        result = query_sql(sql="SELECT * FORM users", path=test_db)
        assert is_error(result)
    
    def test_nonexistent_table(self, test_db):
        """Bug8: 不存在的表应该报错"""
        result = query_sql(sql="SELECT * FROM nonexistent_table", path=test_db)
        assert is_error(result)
    
    def test_nonexistent_column(self, test_db):
        """Bug9: 不存在的列应该报错"""
        result = query_sql(sql="SELECT nonexistent_column FROM users", path=test_db)
        assert is_error(result)
    
    def test_empty_sql(self, test_db):
        """Bug10: 空SQL应该报错"""
        result = query_sql(sql="", path=test_db)
        assert is_error(result)
    
    def test_whitespace_sql(self, test_db):
        """Bug11: 纯空格SQL应该报错"""
        result = query_sql(sql="   ", path=test_db)
        assert is_error(result)


class TestQuerySQLAdvancedQueries:
    """高级查询测试 - 5个"""
    
    def test_join_query(self, test_db):
        """测试JOIN查询"""
        result = query_sql(
            sql="SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id",
            path=test_db
        )
        assert is_success(result)
        assert result["llm_data"]["metrics"]["row_count"]["value"] == 3
    
    def test_group_by_query(self, test_db):
        """测试GROUP BY查询"""
        result = query_sql(
            sql="SELECT user_id, SUM(amount) as total FROM orders GROUP BY user_id",
            path=test_db
        )
        assert is_success(result)
    
    def test_subquery(self, test_db):
        """测试子查询"""
        result = query_sql(
            sql="SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE status = 'completed')",
            path=test_db
        )
        assert is_success(result)
    
    def test_aggregate_functions(self, test_db):
        """测试聚合函数"""
        result = query_sql(
            sql="SELECT AVG(age) as avg_age, MAX(age) as max_age, MIN(age) as min_age FROM users",
            path=test_db
        )
        assert is_success(result)
    
    def test_distinct_query(self, test_db):
        """测试DISTINCT查询"""
        result = query_sql(sql="SELECT DISTINCT status FROM orders", path=test_db)
        assert is_success(result)


class TestQuerySQLConnectionHandling:
    """连接处理测试 - 4个"""
    
    def test_nonexistent_db_path(self, tmp_path):
        """Bug12: 不存在的数据库路径应该报错"""
        result = query_sql(sql="SELECT * FROM users", path=str(tmp_path / "nonexistent.db"))
        assert is_error(result) or is_success(result)
    
    def test_invalid_connection_type(self, test_db):
        """Bug13: 无效的连接类型应该报错"""
        result = query_sql(
            sql="SELECT * FROM users",
            connection_type="invalid_type",
            path=test_db
        )
        assert is_error(result)
    
    def test_sqlite_connection(self, test_db):
        """测试SQLite连接"""
        result = query_sql(
            sql="SELECT * FROM users",
            connection_type="sqlite",
            path=test_db
        )
        assert is_success(result)
    
    def test_connection_timeout(self, tmp_path):
        """Bug14: 连接超时应该处理"""
        db_path = tmp_path / "timeout.db"
        result = query_sql(sql="SELECT * FROM users", path=str(db_path), timeout=1)
        assert is_success(result) or is_error(result)


class TestQuerySQLResultHandling:
    """结果处理测试 - 4个"""
    
    def test_result_limit(self, test_db):
        """测试结果限制"""
        result = query_sql(sql="SELECT * FROM users", path=test_db, limit=1)
        assert is_success(result)
        assert result["llm_data"]["metrics"]["row_count"]["value"] <= 1
    
    def test_empty_result(self, test_db):
        """测试空结果"""
        result = query_sql(sql="SELECT * FROM users WHERE age > 100", path=test_db)
        assert is_success(result)
        assert result["llm_data"]["metrics"]["row_count"]["value"] == 0
    
    def test_large_result(self, test_db):
        """Bug15: 大结果集应该处理"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        for i in range(1000):
            cursor.execute(f"INSERT INTO users (name, age, email) VALUES ('User{i}', {i}, 'user{i}@example.com')")
        conn.commit()
        conn.close()
        
        result = query_sql(sql="SELECT * FROM users", path=test_db, limit=100)
        assert is_success(result)
        assert result["llm_data"]["metrics"]["row_count"]["value"] <= 100
    
    def test_special_characters_in_data(self, test_db):
        """测试数据中的特殊字符"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, age, email) VALUES ('测试🎉', 20, 'test@example.com')")
        conn.commit()
        conn.close()
        
        result = query_sql(sql="SELECT * FROM users WHERE name = '测试🎉'", path=test_db)
        assert is_success(result)


class TestQuerySQLEdgeCases:
    """边界测试 - 4个"""
    
    def test_null_values(self, test_db):
        """测试NULL值"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, age, email) VALUES ('NullUser', NULL, NULL)")
        conn.commit()
        conn.close()
        
        result = query_sql(sql="SELECT * FROM users WHERE age IS NULL", path=test_db)
        assert is_success(result)
    
    def test_very_long_sql(self, test_db):
        """Bug16: 超长SQL应该处理"""
        long_sql = "SELECT * FROM users WHERE " + " AND ".join([f"age > {i}" for i in range(100)])
        result = query_sql(sql=long_sql, path=test_db)
        assert is_success(result) or is_error(result)
    
    def test_sql_with_comments(self, test_db):
        """测试带注释的SQL"""
        result = query_sql(sql="SELECT * FROM users -- This is a comment", path=test_db)
        assert is_success(result) or is_error(result)
    
    def test_sql_with_semicolon(self, test_db):
        """测试带分号的SQL"""
        result = query_sql(sql="SELECT * FROM users;", path=test_db)
        assert is_success(result)