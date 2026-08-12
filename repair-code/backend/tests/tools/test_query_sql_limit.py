# -*- coding: utf-8 -*-
# 测试 query_sql limit 参数改动 — 小欧 2026-07-21
# 2026-07-21 - 小欧 - 新增truncated/truncated_reason字段测试(复核发现Bug5)
"""
覆盖:
1. Schema: limit 字段存在, ge=1, le=200
2. Schema: limit 默认为 None(LLM不传走函数默认50)
3. 函数: 默认 limit=50
4. 函数: limit 范围校验(1~200)
5. 函数: 正常 limit=10 返回10行
6. JSON Schema 包含 limit
7. truncated/truncated_reason 字段存在性和正确性
"""
import sqlite3
import tempfile
import os
from typing import Dict, Any

import pytest
from pydantic import ValidationError

from app.tools.dataanalysis.query_sql import query_sql
from app.tools.dataanalysis.dataanalysis_schema import QuerySqlInput
from app.tools.tool_constants import OBS_MAX_DISPLAY_ITEMS


@pytest.fixture
def test_db_path():
    """创建测试数据库并插入201行数据"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO test_table VALUES (0, 'zero')")
    for i in range(1, 201):
        conn.execute(f"INSERT INTO test_table VALUES ({i}, 'row_{i}')")
    conn.commit()
    conn.close()
    yield tmp.name
    os.unlink(tmp.name)


# ============================================================
# 1. Schema 字段存在性
# ============================================================

def test_schema_has_limit_field():
    """Schema 包含 limit 字段"""
    fields = list(QuerySqlInput.model_fields.keys())
    assert "limit" in fields


def test_schema_limit_ge():
    """limit ge=1"""
    f = QuerySqlInput.model_fields["limit"]
    from pydantic.fields import FieldInfo
    for meta in f.metadata:
        if hasattr(meta, 'ge'):
            assert meta.ge == 1
            return
    # 也可能在 json_schema_extra
    raise AssertionError("ge constraint not found on limit field")


def test_schema_limit_le():
    """limit le=1000"""
    f = QuerySqlInput.model_fields["limit"]
    for meta in f.metadata:
        if hasattr(meta, 'le'):
            assert meta.le == 1000
            return
    raise AssertionError("le constraint not found on limit field")


def test_schema_limit_default_none():
    """limit 默认 None(LLM不传时走函数默认)"""
    assert QuerySqlInput.model_fields["limit"].default is None


def test_schema_limit_optional():
    """limit 是 Optional[int]"""
    assert QuerySqlInput.model_fields["limit"].annotation == int | None


# ============================================================
# 2. Schema 值校验
# ============================================================

def test_schema_limit_valid_10():
    """limit=10 通过校验"""
    m = QuerySqlInput(sql="SELECT 1", path=":memory:", limit=10)
    assert m.limit == 10


def test_schema_limit_valid_200():
    """limit=200 通过校验"""
    m = QuerySqlInput(sql="SELECT 1", path=":memory:", limit=200)
    assert m.limit == 200


def test_schema_limit_valid_1():
    """limit=1 通过校验"""
    m = QuerySqlInput(sql="SELECT 1", path=":memory:", limit=1)
    assert m.limit == 1


def test_schema_limit_invalid_0():
    """limit=0 报错(ge=1)"""
    with pytest.raises(ValidationError):
        QuerySqlInput(sql="SELECT 1", path=":memory:", limit=0)


def test_schema_limit_invalid_1001():
    """limit=1001 报错(le=1000)"""
    with pytest.raises(ValidationError):
        QuerySqlInput(sql="SELECT 1", path=":memory:", limit=1001)


def test_schema_limit_invalid_negative():
    """limit=-1 报错(ge=1)"""
    with pytest.raises(ValidationError):
        QuerySqlInput(sql="SELECT 1", path=":memory:", limit=-1)


# ============================================================
# 3. 函数默认值
# ============================================================

def test_func_default_limit(test_db_path):
    """不传 limit 时默认返回50行"""
    result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path)
    assert len(result["data"]["rows"]) == 50


# ============================================================
# 4. 函数范围校验
# ============================================================

def test_func_limit_valid_10(test_db_path):
    """limit=10 返回10行"""
    result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=10)
    assert len(result["data"]["rows"]) == 10


def test_func_limit_valid_200(test_db_path):
    """limit=200 返回200行"""
    result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=200)
    assert len(result["data"]["rows"]) == 200


def test_func_limit_valid_1(test_db_path):
    """limit=1 返回1行"""
    result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=1)
    assert len(result["data"]["rows"]) == 1


def test_func_limit_0_error(test_db_path):
    """limit=0 报错"""
    result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=0)
    assert result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


def test_func_limit_1001_error(test_db_path):
    """limit=1001 报错"""
    result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=1001)
    assert result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


def test_func_limit_negative_error(test_db_path):
    """limit=-1 报错"""
    result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=-1)
    assert result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


def test_func_limit_less_than_rows(test_db_path):
    """limit 小于数据总量时截断"""
    for l in [3, 10, 50, 100, 150]:
        result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=l)
        assert len(result["data"]["rows"]) == l, f"limit={l} 期望{l}行, 实际{len(result['data']['rows'])}行"


# ============================================================
# 5. JSON Schema 包含 limit
# ============================================================

def test_json_schema_has_limit():
    """JSON Schema 包含 limit 字段"""
    schema = QuerySqlInput.model_json_schema()
    assert "limit" in schema.get("properties", {})


def test_json_schema_limit_not_required():
    """limit 不在 JSON Schema required 列表中"""
    schema = QuerySqlInput.model_json_schema()
    assert "limit" not in schema.get("required", [])


def test_json_schema_limit_minimum():
    """JSON Schema limit minimum=1"""
    schema = QuerySqlInput.model_json_schema()
    props = schema.get("properties", {}).get("limit", {})
    # minimum 在 anyOf 里层
    anyof = props.get("anyOf", [])
    int_spec = [s for s in anyof if s.get("type") == "integer"]
    assert int_spec, f"integer type spec not found in anyOf: {props}"
    assert int_spec[0].get("minimum") == 1


def test_json_schema_limit_maximum():
    """JSON Schema limit maximum=OBS_MAX_DISPLAY_ITEMS"""
    schema = QuerySqlInput.model_json_schema()
    props = schema.get("properties", {}).get("limit", {})
    anyof = props.get("anyOf", [])
    int_spec = [s for s in anyof if s.get("type") == "integer"]
    assert int_spec, f"integer type spec not found in anyOf: {props}"
    assert int_spec[0].get("maximum") == 1000


# ============================================================
# 7. truncated/truncated_reason 字段验证
# ============================================================

def test_func_truncated_true_when_limit_less_than_rows(test_db_path):
    """limit < total rows → data.truncated=True"""
    result = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=10)
    assert result["data"]["truncated"] is True
    assert result["data"]["truncated_reason"] != ""


def test_func_truncated_false_when_limit_ge_rows(test_db_path):
    """limit(200) >= total rows(150) → data.truncated=False"""
    result = query_sql("SELECT * FROM test_table WHERE id < 150 ORDER BY id", path=test_db_path, limit=200)
    assert len(result["data"]["rows"]) == 150
    assert result["data"]["truncated"] is False
    assert result["data"]["truncated_reason"] == ""


def test_func_truncated_exact_match_no_false_positive(test_db_path):
    """limit=200, data=200行 → truncated=False（Bug3: 先判断后append防误报）"""
    result = query_sql("SELECT * FROM test_table WHERE id < 200 ORDER BY id", path=test_db_path, limit=200)
    assert len(result["data"]["rows"]) == 200
    assert result["data"]["truncated"] is False


def test_func_truncated_fields_exist(test_db_path):
    """data 始终包含 truncated 和 truncated_reason 字段"""
    r1 = query_sql("SELECT * FROM test_table ORDER BY id", path=test_db_path, limit=10)
    assert "truncated" in r1["data"]
    assert "truncated_reason" in r1["data"]
    r2 = query_sql("SELECT * FROM test_table WHERE id < 200 ORDER BY id", path=test_db_path, limit=200)
    assert "truncated" in r2["data"]
    assert "truncated_reason" in r2["data"]
