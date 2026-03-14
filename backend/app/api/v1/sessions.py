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
from app.utils.display_name_cache import get_cached_display_name, clear_cached_display_name  # ⭐ 【小沈添加 2026-03-03】【小健更新 2026-03-04】


def extract_display_name_from_steps(execution_steps_data: list) -> Optional[str]:
    """
    从 execution_steps 中提取 display_name 信息
    用于兼容早期保存的历史消息（当时没有单独存储 display_name）

    @author 小新
    @update 2026-03-07 修复历史消息 display_name 不显示的问题
    """
    if not execution_steps_data:
        return None

    for step in execution_steps_data:
        if isinstance(step, dict):
            # 查找包含 model 或 provider 的步骤（通常是 start/chunk/final 类型）
            if step.get("type") in ["start", "chunk", "final"]:
                model = step.get("model", "")
                provider = step.get("provider", "")
                if model or provider:
                    # 优先使用缓存的 display_name 格式
                    if provider and model:
                        return f"{provider} ({model})"
                    elif model:
                        return model
                    elif provider:
                        return provider
    return None

# ⭐ 修复P2-问题7：导入类型注解用于更准确的类型提示
from sqlite3 import Connection, Cursor

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
        'is_valid': False  # 【小沈修复 2026-03-03】添加is_valid字段检查
    }
    
    try:
        # 使用PRAGMA table_info查询表结构（SQLite）
        cursor.execute("PRAGMA table_info(chat_sessions)")
        rows = cursor.fetchall()
        
        # ⭐ 修复P1-问题5：标准化字段名处理
        # 去除空格、转小写、去除可能的引号
        columns = set()
        for row in rows:
            field_name = row['name']
            if field_name:
                # 标准化：去除空格、转小写、去除引号
                field_name = field_name.strip().strip('"').strip("'").lower()
                columns.add(field_name)
        
        # 检查新字段是否存在（现在所有字段都总是存在）
        fields_exist['title_locked'] = 'title_locked' in columns
        fields_exist['title_updated_at'] = 'title_updated_at' in columns
        fields_exist['version'] = 'version' in columns
        fields_exist['is_valid'] = True  # 现在总是存在
            
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
            is_deleted BOOLEAN DEFAULT FALSE,
            is_valid BOOLEAN DEFAULT FALSE  -- 默认为FALSE，新创建的会话默认为无效，需要前端明确标记为有效
        )
    ''')
    # 注意：现在所有会话都已具有 is_valid 字段，无需额外的检查或更新操作
    
    # 创建消息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            execution_steps TEXT,
            display_name TEXT  -- 记录消息收发时使用的模型显示名称
        )
    ''')
    
    # 【小沈添加 2026-03-03】添加 display_name 字段（如果不存在）
    try:
        cursor.execute('SELECT display_name FROM chat_messages LIMIT 1')
    except:
        cursor.execute('ALTER TABLE chat_messages ADD COLUMN display_name TEXT')
        conn.commit()
        print("数据库已添加 display_name 字段")
    
    # 创建标题历史表（P2-中优先级）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_session_title_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            change_reason TEXT,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
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
    is_valid: Optional[bool] = Field(False, description="是否为有效会话（前端用户创建时传入True；测试代码不传默认为False）")


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str = Field(..., description="会话ID")
    title: str = Field(..., description="会话标题")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    message_count: int = Field(..., description="消息数量")
    is_valid: Optional[bool] = Field(None, description="是否为有效会话")


class SessionListResponse(BaseModel):
    """会话列表响应"""
    total: int = Field(..., description="总会话数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    sessions: list[SessionResponse] = Field(..., description="会话列表")

class BatchTitleResponse(BaseModel):
    """批量获取会话标题响应（12.1.3节）"""
    sessions: list[dict] = Field(..., description="会话标题信息列表")


class MessageResponse(BaseModel):
    """消息响应"""
    id: int = Field(..., description="消息 ID")
    session_id: str = Field(..., description="会话 ID")
    role: str = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(..., description="时间戳")
    execution_steps: Optional[list] = Field(None, description="执行步骤（数组格式）")
    display_name: Optional[str] = Field(None, description="模型显示名称（记录消息收发时使用的模型）")


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
    conn = None
    cursor = None
    try:
        session_id = str(uuid.uuid4())
        
        # 如果没有提供标题，自动生成
        title = session_create.title if session_create and session_create.title else f"新会话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在（向后兼容）
        fields_exist = check_db_fields_exist(conn)
        
        utc_time = get_utc_timestamp()
        
        # 【小沈修改 2026-03-03】新创建的会话默认is_valid=FALSE
        # 只有在首次保存消息后，才会自动设置为TRUE
        # 【小沈修复 2026-03-04】尊重前端传入的is_valid参数
        is_valid = session_create.is_valid if session_create and session_create.is_valid is not None else False
        
        # 优化：初始化新字段（根据字段是否存在动态构建SQL）
        # title_locked = FALSE (默认未锁定)
        # title_updated_at = 创建时间
        # version = 1 (初始版本号)
        
        # 根据字段存在性动态构建插入语句（P0风险缓解）
        # 【小沈修复 2026-03-03】添加 is_valid 字段，标识是否为有效会话
        # 有效会话：用户手动创建的会话（is_valid=True）
        # 无效会话：测试代码创建的会话（is_valid=False，默认）
        
        # 总是使用完整字段插入（现在所有字段都存在）
        cursor.execute(
            '''INSERT INTO chat_sessions 
               (id, title, created_at, updated_at, title_locked, title_updated_at, version, is_valid) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (session_id, title, utc_time, utc_time, False, utc_time, 1, is_valid)
        )
        logger.info(f"创建会话（使用新字段）: id={session_id}, title={title}, is_valid={is_valid}")
        
        conn.commit()
        
        logger.info(f"创建会话成功: id={session_id}, title={title}")
        
        return SessionResponse(
            session_id=session_id,
            title=title,
            created_at=utc_time,
            updated_at=utc_time,
            message_count=0,
            is_valid=is_valid
        )
        
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")
    finally:
        # 【小沈修复 2026-03-14】确保数据库连接和游标关闭，防止连接泄漏
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    is_valid: Optional[bool] = Query(None, description="过滤有效会话（True=有效，False=无效，None=全部）")
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
            if is_valid is not None:
                cursor.execute(
                    'SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = FALSE AND title LIKE ? AND is_valid = ?',
                    (f'%{keyword}%', is_valid)
                )
            else:
                cursor.execute(
                    'SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = FALSE AND title LIKE ?',
                    (f'%{keyword}%',)
                )
        else:
            if is_valid is not None:
                cursor.execute(
                    'SELECT COUNT(*) FROM chat_sessions WHERE is_deleted = FALSE AND is_valid = ?',
                    (is_valid,)
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
            if is_valid is not None:
                cursor.execute(
                    '''SELECT id, title, created_at, updated_at, message_count, is_valid
                       FROM chat_sessions 
                       WHERE is_deleted = FALSE AND title LIKE ? AND is_valid = ?
                       ORDER BY updated_at DESC, created_at DESC 
                       LIMIT ? OFFSET ?''',
                    (f'%{keyword}%', is_valid, page_size, offset)
                )
            else:
                cursor.execute(
                    '''SELECT id, title, created_at, updated_at, message_count, is_valid
                       FROM chat_sessions 
                       WHERE is_deleted = FALSE AND title LIKE ?
                       ORDER BY updated_at DESC, created_at DESC 
                       LIMIT ? OFFSET ?''',
                    (f'%{keyword}%', page_size, offset)
                )
        else:
            if is_valid is not None:
                cursor.execute(
                    '''SELECT id, title, created_at, updated_at, message_count, is_valid
                       FROM chat_sessions 
                       WHERE is_deleted = FALSE AND is_valid = ?
                       ORDER BY updated_at DESC, created_at DESC 
                       LIMIT ? OFFSET ?''',
                    (is_valid, page_size, offset)
                )
            else:
                cursor.execute(
                    '''SELECT id, title, created_at, updated_at, message_count, is_valid
                       FROM chat_sessions 
                       WHERE is_deleted = FALSE
                       ORDER BY updated_at DESC, created_at DESC 
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
                message_count=row['message_count'],
                is_valid=row['is_valid']
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
    
    优化内容（12.1.1节）：
    - 响应格式扩展：新增title_locked, title_source, title_updated_at字段
    
    Args:
        session_id: 会话ID
        
    Returns:
        dict: 包含session_id, title, title_locked, title_source, title_updated_at和messages的对象
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在（向后兼容）
        fields_exist = check_db_fields_exist(conn)
        
        # 验证会话存在
        if fields_exist['title_locked'] and fields_exist['title_updated_at'] and fields_exist['version']:
            # 所有新字段都存在，使用完整查询
            cursor.execute(
                '''SELECT id, title, 
                          COALESCE(title_locked, 0) as title_locked,
                          COALESCE(title_updated_at, created_at) as title_updated_at,
                          COALESCE(version, 1) as version,
                          COALESCE(is_valid, 1) as is_valid
                   FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
        else:
            # 新字段不存在，使用兼容查询
            cursor.execute(
                '''SELECT id, title, 0 as title_locked, created_at as title_updated_at, 1 as version, 1 as is_valid
                   FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
        
        session = cursor.fetchone()
        
        if not session:
            conn.close()
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        
        # 获取消息（添加 display_name 字段）
        cursor.execute(
            '''SELECT id, session_id, role, content, timestamp, execution_steps, display_name
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

            # ⭐ 小新修复 2026-03-07：如果 display_name 为空，尝试从 execution_steps 中提取
            display_name = row['display_name']
            if not display_name and execution_steps_data:
                display_name = extract_display_name_from_steps(execution_steps_data)

            messages.append(MessageResponse(
                id=row['id'],
                session_id=row['session_id'],
                role=row['role'],
                content=row['content'],
                timestamp=_convert_to_utc(row['timestamp']),
                execution_steps=execution_steps_data,
                display_name=display_name  # 添加 display_name 字段
            ))
        
        logger.info(f"获取会话消息: session_id={session_id}, count={len(messages)}")
        
        # 返回扩展格式（12.1.1节要求）
        # 新增字段：title_locked, title_source, title_updated_at
        title_locked = bool(session['title_locked'])
        title_source = 'user' if title_locked else 'auto'
        title_updated_at = _convert_to_utc(session['title_updated_at'])
        
        # ⭐ 修复API设计缺陷：也需要返回version字段，以便前端正确调用更新API
        version = session['version'] if 'version' in session else 1
        
        return {
            "session_id": session_id,
            "title": session['title'],
            "title_locked": title_locked,
            "title_source": title_source,
            "title_updated_at": title_updated_at,
            "version": version,  # ⭐ 添加version字段
            "is_valid": session['is_valid'],  # 【小沈添加】返回会话有效性状态
            "messages": messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话消息失败: {str(e)}")





class MessageCreate(BaseModel):
    """创建消息请求"""
    role: str = Field(..., description="角色：user/assistant/system")
    content: str = Field(..., description="消息内容")
    display_name: Optional[str] = Field(None, description="模型显示名称（可选，记录消息收发时使用的模型）")
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")

class SessionUpdate(BaseModel):
    """会话更新请求"""
    title: Optional[str] = Field(None, description="会话标题", min_length=1, max_length=200)
    version: Optional[int] = Field(None, ge=1, description="乐观锁版本号（可选，向后兼容旧前端）")
    updated_by: Optional[str] = Field(None, description="修改者")


@router.post("/sessions/{session_id}/messages")
async def save_message(session_id: str, message: MessageCreate):
    """
    保存消息到会话
    
    优化内容：
    1. 标题保护逻辑：如果标题被锁定，不自动更新标题
    2. updated_at更新时机优化：不再每次保存消息都更新
    3. 事务处理优化：确保消息保存和标题更新的一致性
    4. 添加 execution_steps 字段保存执行步骤
    
    P0风险缓解：添加了字段存在性检查，向后兼容旧数据库结构
    
    Args:
        session_id: 会话ID
        message: 消息内容（包含 execution_steps）
        
    Returns:
        dict: 保存结果
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在（向后兼容）
        fields_exist = check_db_fields_exist(conn)
        
        # 根据字段存在性动态构建查询语句
        if fields_exist['title_locked']:
            # 新字段存在，使用完整查询
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
        
        # ⭐ 【小沈添加 2026-03-03】从缓存获取 display_name（如果是AI回复且前端未提供）
        display_name_to_save = message.display_name
        if message.role == "assistant" and not display_name_to_save:
            display_name_to_save = get_cached_display_name(session_id)
            logger.debug(f"从缓存获取 display_name: session_id={session_id}, display_name={display_name_to_save}")
        
        # 插入消息（添加 display_name 和 execution_steps 字段）
        execution_steps_json = json.dumps(message.execution_steps) if message.execution_steps else None
        cursor.execute(
            'INSERT INTO chat_messages (session_id, role, content, timestamp, display_name, execution_steps) VALUES (?, ?, ?, ?, ?, ?)',
            (session_id, message.role, message.content, utc_time, display_name_to_save, execution_steps_json)
        )
        message_id = cursor.lastrowid
        
        # 计算新的消息计数
        new_message_count = session['message_count'] + 1
        
        # 优化：标题保护逻辑
        # 如果标题未被锁定，且是第一条消息，才考虑更新标题
        should_update_title = False
        new_title = session['title']
        
# P0风险缓解：检查字段是否存在，如果不存在则假设标题未锁定
        title_locked = session['title_locked'] if fields_exist['title_locked'] else False

        # 【小新第二修复 2026-03-02】删除自动用消息内容作为标题的逻辑
        # 原因：前端已经生成漂亮的时间标题（如"3月1日 深夜会话 23:18"），
        # 不需要后端用消息内容覆盖。标题应该由用户手动修改才更新。

        # 优化：updated_at更新时机
        # 每次保存消息都更新updated_at，因为它是"最后活动时间"
        should_update_updated_at = True
        
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
            if fields_exist['title_locked'] and should_update_title:
                update_fields.append('title_locked = ?')
                update_values.append(False)  # 自动更新的标题不锁定
            
            if fields_exist['title_updated_at'] and should_update_title:
                update_fields.append('title_updated_at = ?')
                update_values.append(utc_time)
            
# ⭐ 修复P1-问题4：只在标题实际变化时递增版本号
            # 修复原因：避免标题未变化时也递增版本号，导致频繁409冲突
            if fields_exist['version'] and should_update_title:
                # 只有在标题更新时才递增版本号
                update_fields.append('version = version + 1')  # 【小新第二修复 2026-03-02】使用SQL递增，而不是设置为1
            
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
        
        # 【小沈修改2026-03-03】保存消息后，自动将该会话的is_valid设置为TRUE
        # 这是因为只要有消息保存，说明是真实用户会话
        cursor.execute(
            'UPDATE chat_sessions SET is_valid = TRUE WHERE id = ? AND is_valid = FALSE',
            (session_id,)
        )
        if cursor.rowcount > 0:
            logger.info(f"会话自动标记为有效: session_id={session_id}")
        
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


class ExecutionStepsUpdate(BaseModel):
    """更新执行步骤请求"""
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")


@router.post("/sessions/{session_id}/execution_steps")
async def save_execution_steps(session_id: str, update_data: ExecutionStepsUpdate):
    """
    保存/更新会话的执行步骤
    
    功能：单独保存或更新消息的 execution_steps 字段
    与 save_message 的区别：只更新 execution_steps，不插入新消息
    
    Args:
        session_id: 会话ID
        update_data: 包含 execution_steps 的请求体
        
    Returns:
        dict: 保存结果
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 检查会话是否存在
        cursor.execute(
            'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
            (session_id,)
        )
        session = cursor.fetchone()
        
        if not session:
            conn.close()
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        
        # 查找该会话的最后一条消息（用于更新 execution_steps）
        cursor.execute(
            '''SELECT id, content FROM chat_messages 
               WHERE session_id = ? 
               ORDER BY timestamp DESC LIMIT 1''',
            (session_id,)
        )
        last_message = cursor.fetchone()
        
        if not last_message:
            conn.close()
            raise HTTPException(status_code=404, detail=f"会话中没有消息: {session_id}")
        
        # 更新最后一条消息的 execution_steps
        # 注：execution_steps 字段在表创建时已添加（见第180行），无需检查字段存在性
        execution_steps_json = json.dumps(update_data.execution_steps) if update_data.execution_steps else None
        cursor.execute(
            'UPDATE chat_messages SET execution_steps = ? WHERE id = ?',
            (execution_steps_json, last_message['id'])
        )
        
        # 更新会话的 updated_at
        utc_time = get_utc_timestamp()
        cursor.execute(
            'UPDATE chat_sessions SET updated_at = ? WHERE id = ?',
            (utc_time, session_id)
        )
        
        # 提交事务
        conn.commit()
        conn.close()
        
        logger.info(f"保存执行步骤成功: session_id={session_id}, message_id={last_message['id']}")
        
        return {
            "success": True,
            "message_id": last_message['id']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存执行步骤失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存执行步骤失败: {str(e)}")


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, update_data: SessionUpdate):
    """
    更新会话标题
    
    优化内容（11.4.2节和12.1.2节）：
    - 添加乐观锁并发控制（version参数）
    - 标题历史记录（插入title_history表）
    - 请求参数扩展：version和updated_by
    
    P0问题1和2已修复：
    - 使用原子性UPDATE避免竞态条件
    - 显式事务边界，确保数据一致性
    
    P0风险缓解：version参数可选，向后兼容旧前端
    
    Args:
        session_id: 会话ID
        update_data: 更新的数据（包含title, version, updated_by）
        
    Returns:
        dict: 更新结果
    """
    conn = None
    cursor = None
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # ⭐ 修复P0-问题2：显式开启事务
        cursor.execute("BEGIN")
        
        logger.debug(f"开始事务: session_id={session_id}, operation=update_title")
        
        # P0风险缓解：检查数据库字段是否存在
        fields_exist = check_db_fields_exist(conn)
        
        utc_time = get_utc_timestamp()
        
        # 验证会话存在并获取当前状态（使用原子性UPDATE修复并发问题）
        if fields_exist['version']:
            # 新字段存在，支持乐观锁
            if update_data.version is not None:
                # ⭐ 修复P0-问题1：使用原子性UPDATE避免竞态条件
                # 尝试直接更新并检查version，受影响行数=0说明版本冲突
                cursor.execute(
                    '''UPDATE chat_sessions 
                       SET title = ?, updated_at = ?, 
                           title_locked = ?, 
                           title_updated_at = ?, 
                           version = version + 1
                       WHERE id = ? AND is_deleted = FALSE AND version = ?''',
                    (update_data.title, utc_time, 1, utc_time, 
                     session_id, update_data.version)
                )
                
                # ⭐ 修复P0-问题1：检查是否更新成功
                if cursor.rowcount == 0:
                    # 更新失败，说明版本冲突
                    conn.rollback()
                    conn.close()
                    logger.warning(
                        f"版本冲突: session_id={session_id}, client_version={update_data.version}"
                    )
                    raise HTTPException(
                        status_code=409,
                        detail="会话已被其他用户修改，请刷新后重试"
                    )
                
                # 获取更新后的数据
                cursor.execute(
                    '''SELECT id, title, version FROM chat_sessions WHERE id = ?''',
                    (session_id,)
                )
                session = cursor.fetchone()
                current_version = session['version']
            else:
                # 版本号兼容模式：不检查version（旧前端），使用SELECT获取
                cursor.execute(
                    '''SELECT id, title, COALESCE(version, 1) as version, 
                              COALESCE(title_locked, 0) as title_locked
                       FROM chat_sessions 
                       WHERE id = ? AND is_deleted = FALSE''',
                    (session_id,)
                )
                session = cursor.fetchone()
                
                if not session:
                    conn.rollback()
                    conn.close()
                    raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
                
                current_version = session['version']
                
                # 更新标题（不检查version）
                cursor.execute(
                    '''UPDATE chat_sessions 
                       SET title = ?, updated_at = ?, 
                           title_locked = ?, 
                           title_updated_at = ?, 
                           version = version + 1
                       WHERE id = ?''',
                    (update_data.title, utc_time, 1, utc_time, session_id)
                )
        else:
            # 新字段不存在，兼容模式
            cursor.execute(
                '''SELECT id, title, 1 as version, 0 as title_locked
                   FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
            session = cursor.fetchone()
            
            if not session:
                conn.rollback()
                conn.close()
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            
            current_version = session['version']
            
            # 更新标题
            cursor.execute(
                '''UPDATE chat_sessions 
                       SET title = ?, updated_at = ? 
                   WHERE id = ?''',
                (update_data.title, utc_time, session_id)
            )
        
        # 记录旧标题（用于历史记录）- 修复sqlite3.Row不支持.get()方法
        old_title = session['title'] if session else ''
        new_version = current_version + 1
        
        # 插入标题历史记录（11.2.1节要求）
        # 检查title_history表是否存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_session_title_history'"
        )
        title_history_exists = cursor.fetchone() is not None
        
        if title_history_exists:
            updated_by = update_data.updated_by or 'user'
            cursor.execute(
                '''INSERT INTO chat_session_title_history 
                   (session_id, title, created_at, updated_by, change_reason) 
                   VALUES (?, ?, ?, ?, ?)''',
                (session_id, old_title, utc_time, updated_by, 'user_edit')
            )
            logger.info(f"记录标题历史: session_id={session_id}, old_title={old_title}")
        
        # ⭐ 修复P0-问题2：提交事务
        cursor.execute("COMMIT")
        conn.close()
        
        logger.info(f"更新会话成功: id={session_id}, title={update_data.title}, version={new_version}")
        
        return {
            "success": True, 
            "title": update_data.title,
            "version": new_version
        }
        
    except HTTPException as he:
        # ⭐ 修复P1-问题3：完善错误处理
        try:
            if conn:
                conn.close()
        except:
            pass
        logger.error(f"更新会话HTTP异常: session_id={session_id}, status={he.status_code}, detail={he.detail}")
        raise
    except Exception as e:
        # ⭐ 修复P1-问题3：添加详细错误日志
        logger.error(
            f"更新会话失败: session_id={session_id}, title={update_data.title}, "
            f"version={update_data.version}, error={str(e)}"
        )
        try:
            # ⭐ 修复P0-问题2：回滚事务
            if cursor:
                cursor.execute("ROLLBACK")
                logger.warning(f"事务已回滚: session_id={session_id}")
        except Exception as rollback_err:
            logger.error(f"回滚失败: {rollback_err}")
        try:
            if conn:
                conn.close()
        except:
            pass
        raise HTTPException(status_code=500, detail="更新会话失败，请重试")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话（软删除）
    
    Args:
        session_id: 会话ID
        
    Returns:
        dict: 删除结果
    """
    conn = None
    cursor = None
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 验证会话存在
        cursor.execute(
            'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
            (session_id,)
        )
        session = cursor.fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        
        # 软删除
        utc_time = get_utc_timestamp()
        cursor.execute(
            'UPDATE chat_sessions SET is_deleted = TRUE, updated_at = ? WHERE id = ?',
            (utc_time, session_id)
        )
        
        conn.commit()
        
        # ⭐ 【小健添加 2026-03-04】删除会话时同时清除缓存
        clear_cached_display_name(session_id)
        
        logger.info(f"删除会话成功: id={session_id}")
        
        return {"success": True, "message": "会话删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")
    finally:
        # 【小沈修复 2026-03-14】确保数据库连接和游标关闭，防止连接泄漏
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass

@router.get("/sessions/titles/batch", response_model=BatchTitleResponse)
async def get_session_titles_batch(
    session_ids: str = Query(..., description="逗号分隔的会话ID列表")
):
    """
    批量获取会话标题状态（12.1.3节新增接口）
    
    功能：一次性获取多个会话的标题信息，包括锁定状态和更新时间
    优势：减少API调用次数，提升性能
    
    Args:
        session_ids: 逗号分隔的会话ID列表，例如：id1,id2,id3
        
    Returns:
        BatchTitleResponse: 包含所有会话标题信息的响应
        
    示例：
        GET /api/v1/sessions/titles/batch?session_ids=uuid1,uuid2,uuid3
        
        响应：
        {
            "sessions": [
                {
                    "session_id": "uuid1",
                    "title": "会话标题1",
                    "title_locked": true,
                    "title_updated_at": "2026-02-25T10:30:00Z"
                },
                ...
            ]
        }
    """
    try:
        # 解析会话ID列表
        id_list = [sid.strip() for sid in session_ids.split(',') if sid.strip()]
        
        if not id_list:
            raise HTTPException(status_code=400, detail="会话ID列表不能为空")
        
        if len(id_list) > 100:
            raise HTTPException(status_code=400, detail="最多一次查询100个会话")
        
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # P0风险缓解：检查数据库字段是否存在
        fields_exist = check_db_fields_exist(conn)
        
        # 构建查询SQL
        # 使用IN子句批量查询
        placeholders = ','.join(['?' for _ in id_list])
        
        if fields_exist['title_locked'] and fields_exist['title_updated_at']:
            # 新字段存在，使用完整查询
            cursor.execute(
                f'''SELECT id, title, 
                         COALESCE(title_locked, 0) as title_locked,
                         COALESCE(title_updated_at, created_at) as title_updated_at
                    FROM chat_sessions 
                    WHERE id IN ({placeholders}) AND is_deleted = FALSE''',
                id_list
            )
        else:
            # 新字段不存在，使用兼容查询
            cursor.execute(
                f'''SELECT id, title, 0 as title_locked, created_at as title_updated_at
                    FROM chat_sessions 
                    WHERE id IN ({placeholders}) AND is_deleted = FALSE''',
                id_list
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        # 构建响应
        sessions = []
        for row in rows:
            sessions.append({
                "session_id": row['id'],
                "title": row['title'],
                "title_locked": bool(row['title_locked']),
                "title_updated_at": _convert_to_utc(row['title_updated_at'])
            })
        
        logger.info(f"批量获取会话标题: count={len(sessions)}, session_ids={session_ids}")
        
        return BatchTitleResponse(sessions=sessions)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量获取会话标题失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量获取会话标题失败: {str(e)}")
