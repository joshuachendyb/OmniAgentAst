# -*- coding: utf-8 -*-
"""
update_message_fields — 从 conversation.py 拷出

拷贝来源: conversation.py 第134-156行
"""

import json
from sqlite3 import Connection


def update_message_fields(
    conn: Connection, message_id: int,
    update_data, display_name: str,
) -> None:
    """拷贝自 conversation.py 第134-156行"""
    cursor = conn.cursor()
    fields: list = []
    values: list = []
    if update_data.execution_steps:
        fields.append("execution_steps = ?")
        values.append(json.dumps(update_data.execution_steps))
    if update_data.content is not None:
        fields.append("content = ?")
        values.append(update_data.content)
    if fields:
        values.append(message_id)
        cursor.execute(
            f'UPDATE chat_messages SET {", ".join(fields)} WHERE id = ?',
            values,
        )
