# -*- coding: utf-8 -*-
"""
insert_assistant_message — 从 conversation.py 拷出

拷贝来源: conversation.py 第115-131行
"""

from typing import Optional
from sqlite3 import Connection

from app.utils.logger import logger
from app.utils.time_utils import get_timestamp_ms


def insert_assistant_message(
    conn: Connection, message_id: int, session_id: str,
    display_name: Optional[str], update_data,
) -> None:
    """拷贝自 conversation.py 第115-131行"""
    cursor = conn.cursor()
    utc_time = get_timestamp_ms()
    initial_content = update_data.content or ""
    cursor.execute(
        """INSERT INTO chat_messages
           (id, session_id, role, content, timestamp, display_name) VALUES (?, ?, ?, ?, ?, ?)""",
        (message_id, session_id, "assistant", initial_content, utc_time, display_name),
    )
    logger.info(f"新消息创建: message_id={message_id}, session_id={session_id}, display_name={display_name}")
