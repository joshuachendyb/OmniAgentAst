# execute_sql安全检查方案

**签名**: 北京老陈 2026-06-27

---

## 1. 现状分析

### 1.1 当前实现

**文件**: `backend/app/tools/dataanalysis/execute_sql.py`

**现有安全措施**：
1. 危险模式检测：`_check_sql_safety()`（第21-36行）
   - 检测`DROP`、`TRUNCATE`、`ALTER`、`CREATE`、`GRANT`、`REVOKE`
   - 检测`DELETE`/`UPDATE`无`WHERE`条件
2. 影响行数限制：超过10000行自动回滚（第125-129行）
3. dry_run支持：预演模式（第81-107行）

**参数**：
- `sql`: SQL语句
- `connection_type`: 连接类型
- `dry_run`: 是否预演

### 1.2 风险点

**风险1**: DROP TABLE删除表
- **例子**: `execute_sql("DROP TABLE users")`
- **后果**: 数据表被删除

**风险2**: DELETE无WHERE删除全表
- **例子**: `execute_sql("DELETE FROM users")`
- **后果**: 全表数据被删除

**风险3**: UPDATE无WHERE更新全表
- **例子**: `execute_sql("UPDATE users SET password='123'")`
- **后果**: 全表密码被修改

**风险4**: SQL注入
- **例子**: `execute_sql(f"DELETE FROM users WHERE id={user_input}")`
- **后果**: 恶意SQL注入

---

## 2. 设计方案

### 2.1 核心原则

**原则1**: 现有安全措施已足够
- 危险模式检测已覆盖DROP/TRUNCATE/ALTER/CREATE
- 无WHERE检测已覆盖DELETE/UPDATE
- 影响行数限制已覆盖批量操作

**原则2**: 增强SQL注入检测
- 检测字符串拼接SQL

**原则3**: 分级检查
- **HIGH**: DROP/TRUNCATE/无WHERE → 拒绝执行（已实现）
- **MEDIUM**: ALTER/CREATE/批量操作 → 允许执行+WARNING（已实现）
- **LOW**: 正常INSERT/UPDATE → 允许执行

### 2.2 SQL注入检测

```python
def _check_sql_injection(sql: str) -> Optional[str]:
    """SQL注入检测"""
    # 检测字符串拼接
    if re.search(r'["\'].*\+.*["\']', sql):
        return "检测到字符串拼接，可能存在SQL注入风险"
    
    # 检测f-string（Python层面，SQL中无法检测）
    # 由LLM层面保证不使用字符串拼接
    
    return None
```

---

## 3. 实施方案

**结论**: 现有安全措施已足够，无需额外设计。

**现有安全措施**:
1. `_check_sql_safety()` - 危险模式检测
2. 影响行数限制 - 批量操作保护
3. dry_run支持 - 预演模式
4. 事务回滚 - 失败自动回滚

**建议增强**:
- 在LLM层面教育不要使用字符串拼接SQL
- 使用参数化查询

---

## 4. 总结

**结论**: execute_sql已有完善的安全检查，无需额外设计。

**现有安全措施已覆盖**:
1. DROP/TRUNCATE/ALTER/CREATE检测
2. DELETE/UPDATE无WHERE检测
3. 影响行数限制
4. dry_run预演
5. 事务回滚