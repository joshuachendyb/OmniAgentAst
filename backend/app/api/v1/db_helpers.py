# 会话、消息、对话API共享的数据库工具函数
# 编程人：小沈
# 创建时间：2026-05-28

"""
会话、消息、对话API共享的数据库工具函数

提供：
1. get_db_connection - 统一的DB连接上下文管理器
2. check_db_fields_exist - 检查数据库表字段是否存在
3. _convert_to_utc - UTC时间转换函数
4. _safe_parse_json - 安全解析JSON字符串
5. _ensure_ts_milliseconds - 统一时间戳转毫秒整数
6. _get_timestamp_ms - 获取毫秒时间戳

使用场景: sessions.py, messages.py, conversation.py 共同使用
"""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional
from sqlite3 import Connection

from app.db.chat_db import get_connection as _get_connection
from app.utils.logger import logger


@contextmanager
def get_db_connection() -> Iterator[Connection]:
    """消除DB连接管理(conn→cursor→try→except→finally)的重复

    使用场景: sessions.py和messages.py中所有DB操作
    使用示例: with get_db_connection() as conn: cursor = conn.cursor(); cursor.execute("SELECT ...")
    返回数据说明: yield sqlite3.Connection对象，with块结束后自动关闭

    @author 小健 2026-05-25
    """
    conn: Optional[Connection] = None
    try:
        conn = _get_connection()
        yield conn
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def check_db_fields_exist(conn) -> dict:
    """
    检查数据库表字段是否存在

    用于向后兼容，如果新字段不存在则使用默认值
    这是P0风险缓解措施：防止数据库字段不存在导致API失败

    ⭐ 修复P1-问题5：更健壮的字段检查逻辑
    修复要点：
    - 标准化字段名（去除空格，转小写）
    - 检查字段名时去除可能的引号
    - 增强异常处理

    Args:
        conn: 数据库连接

    Returns:
        dict: 字段存在性状态
    """
    cursor = conn.cursor()
    fields_exist = {
        'title_locked': False,
        'title_updated_at': False,
        'version': False,
        'is_valid': False
    }

    try:
        cursor.execute("PRAGMA table_info(chat_sessions)")
        rows = cursor.fetchall()

        columns = set()
        for row in rows:
            field_name = row['name']
            if field_name:
                field_name = field_name.strip().strip('"').strip("'").lower()
                columns.add(field_name)

        fields_exist['title_locked'] = 'title_locked' in columns
        fields_exist['title_updated_at'] = 'title_updated_at' in columns
        fields_exist['version'] = 'version' in columns
        fields_exist['is_valid'] = True

        missing_fields = [f for f, exists in fields_exist.items() if not exists]
        if missing_fields:
            logger.warning(f"数据库字段不存在（将使用默认值）: {missing_fields}. "
                          f"请执行迁移脚本: migrations/add_session_title_fields.sql")

    except Exception as e:
        logger.error(f"检查数据库字段失败: {e}. 假设字段不存在，使用默认值")
        fields_exist = {k: False for k in fields_exist}

    return fields_exist


def _convert_to_utc(time_value) -> str:
    """将时间转换为UTC ISO格式"""
    if not time_value:
        return _get_utc_timestamp()
    if 'Z' in str(time_value) or '+' in str(time_value):
        return str(time_value)
    try:
        dt = datetime.fromisoformat(str(time_value).replace(' ', 'T'))
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat().replace("+00:00", "Z")
    except:
        return _get_utc_timestamp()


def _get_utc_timestamp() -> str:
    """获取UTC时间戳，ISO格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_ts_milliseconds(ts_value: Any) -> int:
    """统一时间戳转毫秒整数（21.3 组件1，小沈 2026-05-25 实施）

    支持 int/float（直取）、str（fromisoformat→ms）、失败兜底 UTC now
    """
    if isinstance(ts_value, (int, float)):
        return int(ts_value)
    try:
        return int(datetime.fromisoformat(str(ts_value).replace(' ', 'T')).timestamp() * 1000)
    except (ValueError, TypeError, OverflowError):
        logger.warning(f"时间戳转换失败，使用当前时间: {ts_value}")
        return int(datetime.now(timezone.utc).timestamp() * 1000)


def _safe_parse_json(json_str: Optional[str], label: str = "") -> Any:
    """安全解析 JSON 字符串（21.3 组件2，小沈 2026-05-25 实施）

    失败返回 None 并记录警告
    """
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning(f"JSON解析失败 [{label}]: {json_str[:100]}")
        return None


def _get_timestamp_ms() -> int:
    """获取毫秒时间戳，避免时间戳存储为ISO字符串导致前端解析错误"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)
