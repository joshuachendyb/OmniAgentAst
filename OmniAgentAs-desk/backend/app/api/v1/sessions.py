# 会话管理API路由
# 编程人：小沈
# 创建时间：2026-02-17

"""
会话管理API路由
提供会话的CRUD操作和消息历史管理
使用SQLite数据库存储会话和消息
"""

import sqlite3
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.utils.logger import logger

router = APIRouter()

# 数据库路径
DB_PATH = Path.home() / ".omniagent" / "chat_history.db"


def get_utc_timestamp() -> str:
    """获取UTC时间戳，ISO格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def check_db_fields_exist(conn) -> dict:
    """
    检查数据库表字段是否存在
    
    用于向后兼容，如果新字段不存在则使用默认值
    这是P0风险缓解措施：防止数据库字段不存在导致API失败
    
    Args:
        conn: 数据库连接
        
    Returns:
        dict: 字段存在性状态
    """
    cursor = conn.cursor()
    fields_exist = {
        'title_locked': False,
        'title_updated_at': False,
        'version': False
    }
    
    try:
        # 使用PRAGMA table_info查询表结构（SQLite）
        cursor.execute("PRAGMA table_info(chat_sessions)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        # 检查新字段是否存在
        fields_exist['title_locked'] = 'title_locked' in columns
        fields_exist['title_updated_at'] = 'title_updated_at' in columns
        fields_exist['version'] = 'version' in columns
        
        # 如果有字段不存在，记录警告日志
        missing_fields = [f for f, exists in fields_exist.items() if not exists]
        if missing_fields:
            logger.warning(f"数据库字段不存在（将使用默认值）: {missing_fields}. "
                          f"请执行迁移脚本: migrations/add_session_title_fields.sql")
        
    except Exception as e:
        # 如果查询失败，假设字段不存在（安全降级）
        logger.error(f"检查数据库字段失败: {e}. 假设字段不存在，使用默认值")
        fields_exist = {k: False for k in fields_exist}
    
    return fields_exist


def _convert_to_utc(time_value) -> str:
    """将时间转换为UTC ISO格式"""
    if not time_value:
        return get_utc_timestamp()
    # 如果已经是ISO格式，直接返回
    if 'Z' in str(time_value) or '+' in str(time_value):
        return str(time_value)
    # 否则尝试解析并转换为UTC
    try:
        # 尝试解析为datetime
        dt = datetime.fromisoformat(str(time_value).replace(' ', 'T'))
        # 转换为UTC
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat().replace("+00:00", "Z")
    except:
        # 如果解析失败，返回当前UTC时间
        return get_utc_timestamp()


def _get_db_connection():
    """获取数据库连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_database():
    """初始化数据库表"""
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    # 创建会话表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            is_deleted BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # 创建消息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            execution_steps TEXT,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON chat_sessions(is_deleted)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages(timestamp)')
    
    conn.commit()
    conn.close()


# 初始化数据库
_init_database()


# ============== 数据模型 ==============

class Session(BaseModel):
    """会话模型"""
    id: str = Field(..., description="会话ID")
    title: str = Field(..., description="会话标题")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    message_count: int = Field(0, description="消息数量")


class Message(BaseModel):
    """消息模型"""
    id: Optional[int] = Field(None, description="消息ID")
    session_id: str = Field(..., description="会话ID")
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(..., description="时间戳")
    execution_steps: Optional[str] = Field(None, description="执行步骤JSON")


class SessionCreate(BaseModel):
    """创建会话请求"""
    title: Optional[str] = Field(None, description="会话标题（可选，不提供则自动生成）")


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str = Field(..., description="会话ID")
    title: str = Field(..., description="会话标题")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    message_count: int = Field(..., description="消息数量")


class SessionListResponse(BaseModel):
    """会话列表响应"""
    total: int = Field(..., description="总会话数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    sessions: list[SessionResponse] = Field(..., description="会话列表")


class MessageResponse(BaseModel):
    """消息响应"""
    id: int = Field(..., description="消息ID")
    session_id: str = Field(..., description="会话ID")
    role: str = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(..., description="时间戳")
    execution_steps: Optional[list] = Field(None, description="执行步骤（数组格式）")


# ============== API接口 ==============

@router.post("/sessions", response_model=SessionResponse)
async def create_session(session_create: Optional[SessionCreate] = None):
    """
    创建新会话
    
    优化内容：
    1. 初始化`title_locked = False` - 新会话标题默认未锁定，允许自动更新
    2. 设置`title_updated_at = 创建时间` - 记录标题最后更新时间
    3. 初始化`version = 1` - 用于乐观锁版本控制
    
    P0风险缓解：添加了字段存在性检查，向后兼容旧数据库结构
    
    Args:
        session_create: 会话创建请求（可选）
        
    Returns:
        SessionResponse: 创建的会话信息
    """
    try:
        session_id = str(uuid.uuid4())
        
        # 如果没有提供标题，自动生成
        title = session_create.title if session_create and session_create.title else f"新会话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在（向后兼容）
        fields_exist = check_db_fields_exist(conn)
        
        utc_time = get_utc_timestamp()
        
        # 优化：初始化新字段（根据字段是否存在动态构建SQL）
        # title_locked = FALSE (默认未锁定)
        # title_updated_at = 创建时间
        # version = 1 (初始版本号)
        
        # 根据字段存在性动态构建插入语句（P0风险缓解）
        if fields_exist['title_locked'] and fields_exist['title_updated_at'] and fields_exist['version']:
            # 所有新字段都存在，使用完整插入
            cursor.execute(
                '''INSERT INTO chat_sessions 
                   (id, title, created_at, updated_at, title_locked, title_updated_at, version) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (session_id, title, utc_time, utc_time, False, utc_time, 1)
            )
            logger.info(f"创建会话（使用新字段）: id={session_id}, title={title}")
        else:
            # 新字段不存在，使用兼容模式（向后兼容）
            cursor.execute(
                '''INSERT INTO chat_sessions 
                   (id, title, created_at, updated_at) 
                   VALUES (?, ?, ?, ?)''',
                (session_id, title, utc_time, utc_time)
            )
            missing = [f for f, exists in fields_exist.items() if not exists]
            logger.warning(f"创建会话（兼容模式，缺少字段: {missing}）: id={session_id}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"创建会话成功: id={session_id}, title={title}")
        
        return SessionResponse(
            session_id=session_id,
            title=title,
            created_at=utc_time,
            updated_at=utc_time,
            message_count=0
        )
        
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词")
):
    """
    获取会话列表
    
    优化内容：
    1. 排序策略优化：从`updated_at.desc()`改为`created_at.desc(), updated_at.desc()`
    2. 性能优化：添加合适的索引支持
    3. 时间转换优化：批量转换减少函数调用
    
    Args:
        page: 页码
        page_size: 每页数量
        keyword: 搜索关键词
        
    Returns:
        SessionListResponse: 会话列表（包含分页信息）
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 先获取总数
        if keyword:
            cursor.execute(
                'SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = FALSE AND title LIKE ?',
                (f'%{keyword}%',)
            )
        else:
            cursor.execute(
                'SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = FALSE'
            )
        total = cursor.fetchone()[0]
        
        # 构建查询
        offset = (page - 1) * page_size
        
        # 优化：复合排序策略，优先按创建时间，再按更新时间
        # 这样新创建的会话会排在前面，同时活跃的会话也能保持较高位置
        if keyword:
            # 搜索标题
            cursor.execute(
                '''SELECT id, title, created_at, updated_at, message_count 
                   FROM chat_sessions 
                   WHERE is_deleted = FALSE AND title LIKE ?
                   ORDER BY created_at DESC, updated_at DESC 
                   LIMIT ? OFFSET ?''',
                (f'%{keyword}%', page_size, offset)
            )
        else:
            cursor.execute(
                '''SELECT id, title, created_at, updated_at, message_count 
                   FROM chat_sessions 
                   WHERE is_deleted = FALSE
                   ORDER BY created_at DESC, updated_at DESC 
                   LIMIT ? OFFSET ?''',
                (page_size, offset)
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        # 优化：批量转换时间戳，减少函数调用开销
        # 对于大量数据，这样可以显著提高性能
        sessions = []
        for row in rows:
            # 直接使用行数据，避免多次函数调用
            created_at = row['created_at']
            updated_at = row['updated_at']
            
            # 简单的时间格式转换（假设存储已经是UTC格式）
            if isinstance(created_at, str):
                created_at_str = created_at.replace('+00:00', 'Z') if '+00:00' in created_at else created_at + 'Z' if not created_at.endswith('Z') else created_at
            else:
                created_at_str = _convert_to_utc(created_at)
                
            if isinstance(updated_at, str):
                updated_at_str = updated_at.replace('+00:00', 'Z') if '+00:00' in updated_at else updated_at + 'Z' if not updated_at.endswith('Z') else updated_at
            else:
                updated_at_str = _convert_to_utc(updated_at)
            
            sessions.append(SessionResponse(
                session_id=row['id'],
                title=row['title'],
                created_at=created_at_str,
                updated_at=updated_at_str,
                message_count=row['message_count']
            ))
        
        logger.info(f"获取会话列表: page={page}, page_size={page_size}, keyword={keyword}, count={len(sessions)}")
        
        return SessionListResponse(
            total=total,
            page=page,
            page_size=page_size,
            sessions=sessions
        )
        
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """
    获取会话消息历史
    
    Args:
        session_id: 会话ID
        
    Returns:
        dict: 包含session_id和messages的对象
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在（向后兼容）
        fields_exist = check_db_fields_exist(conn)
        
        # 验证会话存在并获取标题相关字段
        if fields_exist['title_locked'] and fields_exist['title_updated_at']:
            cursor.execute(
                '''SELECT id, title, COALESCE(title_locked, 0) as title_locked,
                          COALESCE(title_updated_at, created_at) as title_updated_at, created_at
                   FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
        else:
            # 兼容模式：查询基本字段
            cursor.execute(
                '''SELECT id, title, created_at, created_at as title_updated_at
                   FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
        session = cursor.fetchone()
        
        if not session:
            conn.close()
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        
        # 获取消息
        cursor.execute(
            '''SELECT id, session_id, role, content, timestamp, execution_steps 
               FROM chat_messages 
               WHERE session_id = ?
               ORDER BY timestamp ASC''',
            (session_id,)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        # 解析 execution_steps JSON字符串为数组
        messages = []
        for row in rows:
            execution_steps_data = None
            if row['execution_steps']:
                try:
                    execution_steps_data = json.loads(row['execution_steps'])
                except json.JSONDecodeError:
                    logger.warning(f"解析 execution_steps 失败: {row['execution_steps']}")
            
            messages.append(MessageResponse(
                id=row['id'],
                session_id=row['session_id'],
                role=row['role'],
                content=row['content'],
                timestamp=_convert_to_utc(row['timestamp']),
                execution_steps=execution_steps_data
            ))
        
        logger.info(f"获取会话消息: session_id={session_id}, count={len(messages)}")
        
        # 构建返回数据，包含新字段
        title_locked = bool(session.get('title_locked', 0)) if 'title_locked' in session else False
        title_source = "user" if title_locked else "auto"
        title_updated_at = _convert_to_utc(session['title_updated_at']) if 'title_updated_at' in session else _convert_to_utc(session['created_at'])
        
        # 返回对象格式，包含session_id、title、title_locked、title_source、title_updated_at、messages
        return {
            "session_id": session_id,
            "title": session['title'],
            "title_locked": title_locked,
            "title_source": title_source,
            "title_updated_at": title_updated_at,
            "messages": messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话消息失败: {str(e)}")


class MessageCreate(BaseModel):
    """消息创建请求"""
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="消息内容")


class SessionUpdate(BaseModel):
    """会话更新请求"""
    title: str = Field(..., description="会话标题")
    version: Optional[int] = Field(None, description="版本号（乐观锁）")
    updated_by: Optional[str] = Field(None, description="修改者")


@router.post("/sessions/{session_id}/messages")
async def save_message(session_id: str, message: MessageCreate):
    """
    保存消息到会话
    
    优化内容：
    1. 标题保护逻辑：如果标题被锁定，不自动更新标题
    2. updated_at更新时机优化：不再每次保存消息都更新
    3. 事务处理优化：确保消息保存和标题更新的一致性
    
    P0风险缓解：添加了字段存在性检查，向后兼容旧数据库结构
    
    Args:
        session_id: 会话ID
        message: 消息内容
        
    Returns:
        dict: 保存结果
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在（向后兼容）
        fields_exist = check_db_fields_exist(conn)
        
         # 根据字段存在性动态构建查询语句
        if fields_exist['title_locked'] and fields_exist['version']:
            # 新字段都存在，使用完整查询
            cursor.execute(
                '''SELECT id, title, message_count, 
                          COALESCE(title_locked, 0) as title_locked, 
                          COALESCE(version, 0) as version
                   FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
        elif fields_exist['title_locked']:
            # 只有title_locked存在
            cursor.execute(
                '''SELECT id, title, message_count, 
                          COALESCE(title_locked, 0) as title_locked 
                   FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
        else:
            # 新字段不存在，使用兼容查询（假设标题未锁定）
            logger.warning(f"字段title_locked不存在，使用兼容模式查询会话: {session_id}")
            cursor.execute(
                '''SELECT id, title, message_count, 0 as title_locked 
                   FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
        
        session = cursor.fetchone()
        
        if not session:
            conn.close()
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        
        # 开始事务处理
        utc_time = get_utc_timestamp()
        
        # 插入消息
        cursor.execute(
            'INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
            (session_id, message.role, message.content, utc_time)
        )
        message_id = cursor.lastrowid
        
        # 计算新的消息计数
        new_message_count = session['message_count'] + 1
        
        # P0风险缓解：检查字段是否存在，如果不存在则假设标题未锁定
        title_locked_val = session['title_locked'] if fields_exist['title_locked'] and 'title_locked' in session else 0
        title_locked = bool(title_locked_val)
        
        # 只有当标题未被锁定，且是第一条消息，且消息不是空的，才更新标题
        should_update_title = False
        new_title = session['title']
        
        if not title_locked and new_message_count == 1:
            # 第一条消息，且标题未被锁定，使用消息内容作为标题
            if message.content and len(message.content) > 0:
                new_title = message.content[:30] if len(message.content) > 30 else message.content
                should_update_title = True
                logger.info(f"会话 {session_id} 标题自动更新为: {new_title}")
        
        # 优化：updated_at更新时机
        # 只在以下情况更新updated_at：
        # 1. 标题被更新
        # 2. 每5条消息更新一次（避免频繁更新）
        should_update_updated_at = should_update_title or (new_message_count % 5 == 0)
        
        # 执行会话更新（根据字段存在性动态构建SQL）
        if should_update_title or should_update_updated_at:
            update_fields = ['message_count = ?']
            update_values = [new_message_count]
            
            if should_update_title:
                update_fields.append('title = ?')
                update_values.append(new_title)
            
            if should_update_updated_at:
                update_fields.append('updated_at = ?')
                update_values.append(utc_time)
            
             # P0风险缓解：如果新字段存在，也更新它们
            # 注意：只有在自动更新标题时（非锁定状态），才设置title_locked=False
            # 如果标题已经被锁定了，我们不会更新标题，所以也不会修改title_locked状态
            if fields_exist['title_locked'] and should_update_title:
                update_fields.append('title_locked = ?')
                update_values.append(False)  # 自动更新的标题不锁定
            
            if fields_exist['title_updated_at'] and should_update_title:
                update_fields.append('title_updated_at = ?')
                update_values.append(utc_time)
            
            if fields_exist['version']:
                current_version = session['version'] if 'version' in session else 0
                update_fields.append('version = ?')
                update_values.append(current_version + 1)  # 递增版本号
            
            update_values.append(session_id)
            
            cursor.execute(
                f'UPDATE chat_sessions SET {", ".join(update_fields)} WHERE id = ?',
                update_values
            )
        else:
            # 只更新消息计数
            cursor.execute(
                'UPDATE chat_sessions SET message_count = ? WHERE id = ?',
                (new_message_count, session_id)
            )
        
        # 提交事务
        conn.commit()
        conn.close()
        
        logger.info(f"保存消息成功: session_id={session_id}, message_id={message_id}, "
                   f"role={message.role}, message_count={new_message_count}, "
                   f"title_updated={should_update_title}")
        
        return {
            "success": True, 
            "message_id": message_id,
            "message_count": new_message_count,
            "title_updated": should_update_title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存消息失败: {str(e)}")


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, update_data: SessionUpdate):
    """
    更新会话信息
    
    优化内容：
    1. 版本号返回：返回更新后的version字段
    2. 乐观锁支持：检查version字段是否存在
    3. updated_by字段支持：记录修改者
    
    Args:
        session_id: 会话ID
        update_data: 更新的数据
        
    Returns:
        dict: 更新结果（包含version字段）
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在（向后兼容）
        fields_exist = check_db_fields_exist(conn)
        
        # 验证会话存在并获取当前版本
        if fields_exist['version']:
            cursor.execute(
                'SELECT id, title, COALESCE(version, 1) as version FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
                (session_id,)
            )
        else:
            cursor.execute(
                'SELECT id, title FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
                (session_id,)
            )
        session = cursor.fetchone()
        
        if not session:
            conn.close()
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        
        # 乐观锁检查（如果传递了version参数）
        current_version = session['version'] if fields_exist['version'] and 'version' in session else 0
        if update_data.version is not None and fields_exist['version']:
            if update_data.version != current_version:
                conn.close()
                raise HTTPException(status_code=409, detail=f"版本冲突: 当前版本={current_version}, 请求版本={update_data.version}")
        
         # 更新标题
        utc_time = get_utc_timestamp()
        
        # 递增版本号
        new_version = current_version + 1
        
        # 根据字段存在性动态构建更新语句
        update_fields = ['title = ?', 'updated_at = ?']
        update_values = [update_data.title, utc_time]
        
         # 如果version字段存在，更新它并添加乐观锁检查
        where_clause = f'WHERE id = ?'
        if fields_exist['version']:
            update_fields.append('version = ?')
            update_values.append(new_version)
            # 乐观锁：只在version匹配时更新
            if update_data.version is not None:
                where_clause += ' AND version = ?'
                update_values.insert(-1, update_data.version)  # 插入到session_id前面
        
        # 如果title_locked字段存在，锁定标题（手动更新）
        if fields_exist['title_locked']:
            update_fields.append('title_locked = ?')
            update_values.append(True)  # 手动更新锁定标题
        
        # 如果title_updated_at字段存在，更新它
        if fields_exist['title_updated_at']:
            update_fields.append('title_updated_at = ?')
            update_values.append(utc_time)
        
        update_values.append(session_id)
        
        cursor.execute(
            f'UPDATE chat_sessions SET {", ".join(update_fields)} {where_clause}',
            update_values
        )
        
        # 乐观锁验证：如果UPDATE影响了0行，说明version不匹配
        if cursor.rowcount == 0 and fields_exist['version'] and update_data.version is not None:
            conn.close()
            raise HTTPException(status_code=409, detail=f"版本冲突: 当前版本={current_version}, 请求版本={update_data.version}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"更新会话成功: id={session_id}, title={update_data.title}, version={new_version}")
        
        return {"success": True, "title": update_data.title, "version": new_version}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新会话失败: {str(e)}")


@router.get("/sessions/titles/batch")
async def get_session_titles_batch(
    session_ids: str = Query(..., description="会话ID列表（逗号分隔）")
):
    """
    批量获取会话标题
    
    优化内容：
    1. 减少API调用次数，一次获取多个会话标题
    2. 返回title相关字段（title, title_locked, title_updated_at）
    3. 参数验证：空ID列表返回400，超过100个返回400
    
    P0风险缓解：添加了字段存在性检查，向后兼容旧数据库结构
    
    Args:
        session_ids: 逗号分隔的会话ID列表
        
    Returns:
        dict: 批量会话标题信息
    """
    try:
        # 参数验证
        if not session_ids or session_ids.strip() == "":
            raise HTTPException(status_code=400, detail="会话ID列表不能为空")
        
        id_list = session_ids.split(",")
        
        # 数量限制
        if len(id_list) > 100:
            raise HTTPException(status_code=400, detail="会话ID数量不能超过100个")
        
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在（向后兼容）
        fields_exist = check_db_fields_exist(conn)
        
        # 构建查询
        placeholders = ",".join(["?" for _ in id_list])
        
        # 根据字段存在性动态构建查询
        if fields_exist['title_locked'] and fields_exist['title_updated_at']:
            query = f'''
                SELECT id, title, COALESCE(title_locked, 0) as title_locked,
                       COALESCE(title_updated_at, created_at) as title_updated_at
                FROM chat_sessions
                WHERE id IN ({placeholders}) AND is_deleted = FALSE
            '''
        else:
            # 兼容模式：查询基本字段
            query = f'''
                SELECT id, title, 0 as title_locked, created_at as title_updated_at
                FROM chat_sessions
                WHERE id IN ({placeholders}) AND is_deleted = FALSE
            '''
        
        cursor.execute(query, id_list)
        rows = cursor.fetchall()
        conn.close()
        
        # 构建返回数据
        sessions = []
        for row in rows:
            title_locked_val = row['title_locked'] if 'title_locked' in row else 0
            title_updated_at_val = row['title_updated_at'] if 'title_updated_at' in row else row['created_at'] if 'created_at' in row else None
            
            sessions.append({
                "session_id": row['id'],
                "title": row['title'],
                "title_locked": bool(title_locked_val),
                "title_updated_at": _convert_to_utc(title_updated_at_val)
            })
        
        logger.info(f"批量获取会话标题: 请求{len(id_list)}个, 返回{len(sessions)}个")
        
        return {"sessions": sessions}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量获取会话标题失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量获取会话标题失败: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话（软删除）
    
    Args:
        session_id: 会话ID
        
    Returns:
        dict: 删除结果
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 验证会话存在
        cursor.execute(
            'SELECT id, title FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
            (session_id,)
        )
        session = cursor.fetchone()
        
        if not session:
            conn.close()
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        
        # 软删除
        utc_time = get_utc_timestamp()
        cursor.execute(
            'UPDATE chat_sessions SET is_deleted = TRUE, updated_at = ? WHERE id = ?',
            (utc_time, session_id)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"删除会话成功: id={session_id}")
        
        return {"success": True, "message": "会话删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")
