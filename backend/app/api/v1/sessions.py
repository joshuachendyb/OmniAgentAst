# 会话管理API路由
# 编程人：小沈
# 创建时间：2026-02-17

"""
会话管理API路由
提供会话的CRUD操作和消息历史管理
使用SQLite数据库存储会话和消息
"""

# 【新增 2026-03-16】存储每个session的消息ID
# key: session_id, value: user_message_id 或 assistant_message_id
_user_message_ids: dict = {}
_assistant_message_ids: dict = {}
import threading
_message_ids_lock = threading.Lock()

import sqlite3
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
from contextlib import contextmanager
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

# 【小沈重构 2026-05-22】数据库配置迁移至 app/db/
from app.db.chat_db import get_connection
from app.db.models.chat_models import (
    Session,
    Message,
    SessionCreate,
    SessionResponse,
    SessionListResponse,
    BatchTitleResponse,
    MessageResponse,
)


@contextmanager
def get_db_connection() -> Iterator[sqlite3.Connection]:
    """消除DB连接管理(conn→cursor→try→except→finally)的重复

    使用场景: sessions.py中所有DB操作
    使用示例: with get_db_connection() as conn: cursor = conn.cursor(); cursor.execute("SELECT ...")
    返回数据说明: yield sqlite3.Connection对象，with块结束后自动关闭

    @author 小健 2026-05-25
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = get_connection()
        yield conn
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_utc_timestamp() -> str:
    """获取UTC时间戳，ISO格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def get_timestamp_ms() -> int:
    """【小沈修复 2026-03-31】获取毫秒时间戳，避免时间戳存储为ISO字符串导致前端解析错误"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


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
        
        conn = get_connection()
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
    conn = None
    try:
        conn = get_connection()
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
        
        # 【小强修复 2026-03-31】优化排序策略：
        # 1. 优先返回有消息的会话（message_count > 0）
        # 2. 再按更新时间降序排列
        # 3. 最后按创建时间降序
        # 原因：空会话（message_count=0）会排在有消息的会话后面
        # 效果：加载最近会话时，会优先返回有消息的会话
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
        
        # 优化：批量转换时间戳，减少函数调用开销
        # 对于大量数据，这样可以显著提高性能
        sessions = []
        for row in rows:
            # 直接使用行数据，避免多次函数调用
            created_at = row['created_at']
            updated_at = row['updated_at']
            
            # 【小沈修复 2026-03-31】统一转换为ISO格式字符串返回给前端
            # 处理两种情况：1. ISO格式字符串 2. 毫秒时间戳（int/float）
            if isinstance(created_at, (int, float)):
                # 毫秒时间戳转换为ISO格式
                created_at_str = datetime.fromtimestamp(created_at / 1000, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
            elif isinstance(created_at, str):
                created_at_str = created_at.replace('+00:00', 'Z') if '+00:00' in created_at else created_at + 'Z' if not created_at.endswith('Z') else created_at
            else:
                created_at_str = _convert_to_utc(created_at)
                
            # 【小沈修复 2026-03-31】统一转换为ISO格式字符串返回给前端
            # 处理两种情况：1. ISO格式字符串 2. 毫秒时间戳（int/float）
            if isinstance(updated_at, (int, float)):
                # 毫秒时间戳转换为ISO格式
                updated_at_str = datetime.fromtimestamp(updated_at / 1000, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
            elif isinstance(updated_at, str):
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
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


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
    
    失败返回 None 并记录警告，供 get_session_messages 和 list_sessions 复用
    """
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning(f"JSON解析失败 [{label}]: {json_str[:100]}")
        return None


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话消息历史（21.3 重构，小沈 2026-05-25 实施）"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        fields_exist = check_db_fields_exist(conn)

        if fields_exist['title_locked'] and fields_exist['title_updated_at'] and fields_exist['version']:
            cursor.execute('''SELECT id, title, COALESCE(title_locked, 0) as title_locked,
                              COALESCE(title_updated_at, created_at) as title_updated_at,
                              COALESCE(version, 1) as version, COALESCE(is_valid, 1) as is_valid
                           FROM chat_sessions WHERE id = ? AND is_deleted = FALSE''', (session_id,))
        else:
            cursor.execute('''SELECT id, title, 0 as title_locked, created_at as title_updated_at,
                               1 as version, 1 as is_valid
                           FROM chat_sessions WHERE id = ? AND is_deleted = FALSE''', (session_id,))

        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

        cursor.execute('''SELECT id, session_id, role, content, timestamp, execution_steps, display_name
                       FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC''', (session_id,))

        messages = []
        for row in cursor.fetchall():
            steps = _safe_parse_json(row['execution_steps'], label="execution_steps")
            display_name = row['display_name']
            if not display_name and steps:
                display_name = extract_display_name_from_steps(steps)

            messages.append(MessageResponse(
                id=row['id'], session_id=row['session_id'],
                role=row['role'], content=row['content'],
                timestamp=_ensure_ts_milliseconds(row['timestamp']),
                execution_steps=steps, display_name=display_name,
            ))

        title_locked = bool(session['title_locked'])
        return {
            "session_id": session_id, "title": session['title'],
            "title_locked": title_locked,
            "title_source": "user" if title_locked else "auto",
            "title_updated_at": _convert_to_utc(session['title_updated_at']),
            "version": session['version'], "is_valid": session['is_valid'],
            "messages": messages,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话消息失败: {str(e)}")
    finally:
        if conn:
            try: conn.close()
            except Exception: pass





class MessageCreate(BaseModel):
    """创建消息请求"""
    role: str = Field(..., description="角色：user/assistant/system")
    content: str = Field(..., description="消息内容")
    display_name: Optional[str] = Field(None, description="模型显示名称（可选，记录消息收发时使用的模型）")
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    # 客户端信息（小沈 2026-03-24）
    client_os: Optional[str] = Field(None, description="客户端操作系统")
    browser: Optional[str] = Field(None, description="浏览器类型")
    device: Optional[str] = Field(None, description="设备类型")
    network: Optional[str] = Field(None, description="网络类型")

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
    conn = None
    try:
        conn = get_connection()
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
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        
        # 【小沈修复 2026-03-31】使用毫秒时间戳
        utc_time = get_timestamp_ms()
        
        # ⭐ 【小沈添加 2026-03-03】从缓存获取 display_name（如果是AI回复且前端未提供）
        display_name_to_save = message.display_name
        if message.role == "assistant" and not display_name_to_save:
            display_name_to_save = get_cached_display_name(session_id)
            logger.debug(f"从缓存获取 display_name: session_id={session_id}, display_name={display_name_to_save}")
        
        # 插入消息（添加 display_name 和 execution_steps 字段）
        execution_steps_json = json.dumps(message.execution_steps) if message.execution_steps else None
        cursor.execute(
            'INSERT INTO chat_messages (session_id, role, content, timestamp, display_name, execution_steps, client_os, browser, device, network) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (session_id, message.role, message.content, utc_time, display_name_to_save, execution_steps_json, 
             message.client_os, message.browser, message.device, message.network)
        )
        message_id = cursor.lastrowid
        
        # 【新增 2026-03-16】保存用户消息ID到内存字典，用于生成AI消息ID
        if message.role == 'user':
            with _message_ids_lock:
                _user_message_ids[session_id] = message_id
            logger.info(f"[保存用户消息ID] message_id={message_id}, session_id={session_id}")
        
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
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


class AssistantMessageIdAllocator:
    """为assistant消息分配唯一ID。save_execution_steps和save_message复用

    使用场景: save_execution_steps中为新的assistant消息分配ID; save_message中复用同一ID分配逻辑
    使用示例: allocator = AssistantMessageIdAllocator(_user_message_ids, _message_ids_lock); message_id, is_new = allocator.allocate(session_id, conn)
    返回数据说明: allocate返回Tuple[int, bool]，(消息ID, 是否为新消息)

    @author 小健 2026-05-25
    """
    def __init__(self, user_ids: Dict[str, int], lock: threading.Lock):
        self._user_ids = user_ids
        self._assistant_ids: Dict[str, int] = {}
        self._lock = lock

    def allocate(self, session_id: str, conn: sqlite3.Connection) -> Tuple[int, bool]:
        """返回 (message_id, is_new)"""
        with self._lock:
            user_id = self._user_ids.get(session_id)

        if user_id is not None:
            expected = user_id + 1
        else:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM chat_messages WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
            row = cursor.fetchone()
            expected = (row["id"] + 1) if row else 1

        cursor = conn.cursor()
        cursor.execute("SELECT id, role FROM chat_messages WHERE id=?", (expected,))
        existing = cursor.fetchone()
        if existing and existing["role"] == "assistant":
            return expected, False
        if existing and existing["role"] != "assistant":
            cursor.execute(
                "SELECT id FROM chat_messages WHERE session_id=? ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
            max_row = cursor.fetchone()
            expected = (max_row["id"] + 1) if max_row else 1

        with self._lock:
            self._assistant_ids[session_id] = expected
        return expected, True


def extract_metadata(execution_steps: Optional[List[Dict[str, Any]]]) -> Dict[str, Optional[str]]:
    """从execution_steps的start步骤提取model/provider/display_name

    使用场景: save_execution_steps中提取metadata用于display_name
    使用示例: metadata = extract_metadata(update_data.execution_steps)
    返回数据说明: {"model": str|None, "provider": str|None, "display_name": str|None}

    @author 小健 2026-05-25
    """
    if not execution_steps:
        return {"model": None, "provider": None, "display_name": None}
    for step in execution_steps:
        if step.get("type") == "start":
            model = step.get("model")
            provider = step.get("provider")
            display_name = step.get("display_name")
            if not display_name and provider and model:
                display_name = f"{provider} ({model})"
            return {"model": model, "provider": provider, "display_name": display_name}
    return {"model": None, "provider": None, "display_name": None}


def _ensure_session_exists(session_id: str, conn: sqlite3.Connection) -> None:
    """检查会话是否存在，不存在则抛出HTTPException

    @author 小健 2026-05-25
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE id=? AND is_deleted=FALSE", (session_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")


def _insert_assistant_message(
    conn: sqlite3.Connection, message_id: int, session_id: str,
    display_name: Optional[str], update_data: "ExecutionStepsUpdate",
) -> None:
    """插入新的assistant消息

    @author 小健 2026-05-25
    """
    cursor = conn.cursor()
    utc_time = get_timestamp_ms()
    initial_content = update_data.content or ""
    cursor.execute(
        """INSERT INTO chat_messages
           (id, session_id, role, content, timestamp, display_name) VALUES (?, ?, ?, ?, ?, ?)""",
        (message_id, session_id, "assistant", initial_content, utc_time, display_name),
    )
    logger.info(f"🆕 [新消息创建] message_id={message_id}, session_id={session_id}, display_name={display_name}")


def _update_message_fields(
    conn: sqlite3.Connection, message_id: int,
    update_data: "ExecutionStepsUpdate", display_name: Optional[str],
) -> None:
    """动态构建并执行消息字段更新

    @author 小健 2026-05-25
    """
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


def _update_session_message_count(
    conn: sqlite3.Connection, session_id: str, increment: bool,
) -> None:
    """更新会话message_count（仅首次创建+1）和updated_at

    @author 小健 2026-05-25
    """
    cursor = conn.cursor()
    utc_time = get_timestamp_ms()
    if increment:
        cursor.execute(
            "UPDATE chat_sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
            (utc_time, session_id),
        )
    else:
        cursor.execute(
            "UPDATE chat_sessions SET updated_at=? WHERE id=?",
            (utc_time, session_id),
        )


class ExecutionStepsUpdate(BaseModel):
    """
    更新执行步骤请求
    
    @author 小沈
    @update 2026-03-16 v11.0修复：增加content参数，解决前端调用时传递content参数被忽略的问题
    
    修复的问题：
    - 缺陷1：API参数不匹配 - 后端saveExecutionSteps只有execution_steps参数，没有content参数
    - 缺陷5：visibilitychange调用无效 - 前端传递content参数但API不支持
    - 缺陷6：无法判断新一轮对话 - 添加reply_to_message_id参数用于校验
    """
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    content: Optional[str] = Field(None, description="AI生成的文本内容，用于实时保存流式输出的内容")
    reply_to_message_id: Optional[int] = Field(None, description="回复的用户消息ID，用于校验和创建正确的AI消息ID")


@router.post("/sessions/{session_id}/execution_steps")
async def save_execution_steps(session_id: str, update_data: ExecutionStepsUpdate):
    """保存/更新会话的执行步骤（智能UPSERT）

    重构：259行大函数拆分为骨架+Allocator+辅助函数
    @author 小沈, 小健 2026-05-25
    """
    allocator = AssistantMessageIdAllocator(_user_message_ids, _message_ids_lock)
    try:
        with get_db_connection() as conn:
            _ensure_session_exists(session_id, conn)
            message_id, is_new = allocator.allocate(session_id, conn)
            metadata = extract_metadata(update_data.execution_steps)
            display_name = metadata.get("display_name")
            if is_new:
                _insert_assistant_message(conn, message_id, session_id, display_name, update_data)
            _update_message_fields(conn, message_id, update_data, display_name)
            _update_session_message_count(conn, session_id, is_new)
            conn.commit()
        logger.info(f"保存执行步骤成功: session_id={session_id}, message_id={message_id}, is_new={is_new}")
        return {"success": True, "message_id": message_id, "is_new_message": is_new}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存执行步骤失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存执行步骤失败: {str(e)}")


def _get_sql_mode(mode: str, fields_exist: dict) -> str:
    """将外层mode映射为_build_update_sql所需的sql_mode

    使用场景: update_session中决策SQL构建模式
    使用示例: _get_sql_mode("select_then_update", fields) → "compat"或"legacy"
    返回数据说明: "optimistic"/"compat"/"legacy"

    @author 小健 2026-05-25
    """
    if mode == "optimistic":
        return "optimistic"
    if mode == "select_then_update" and fields_exist["version"]:
        return "compat"
    return "legacy"


def _resolve_update_mode(
    fields_exist: dict, update_data: SessionUpdate,
    cursor, session_id: str, utc_time: str,
) -> Tuple[str, str, Tuple]:
    """判断UPDATE模式：optimistic/compat/legacy，compat/legacy时先SELECT验证

    使用场景: update_session中3路分支决策
    使用示例: mode, _, params = _resolve_update_mode(fields, data, cur, sid, utc)
    返回数据说明: (mode, where_extra, params)
        mode="optimistic": params=()；mode="select_then_update": params=(session, current_version)

    @author 小健 2026-05-25
    """
    if fields_exist["version"]:
        if update_data.version is not None:
            return "optimistic", "", ()
        cursor.execute(
            """SELECT id, title, COALESCE(version, 1) as version,
                      COALESCE(title_locked, 0) as title_locked
               FROM chat_sessions WHERE id = ? AND is_deleted = FALSE""",
            (session_id,),
        )
    else:
        cursor.execute(
            """SELECT id, title, 1 as version, 0 as title_locked
               FROM chat_sessions WHERE id = ? AND is_deleted = FALSE""",
            (session_id,),
        )
    session = cursor.fetchone()
    if not session:
        return "not_found", "", (None, 0)
    return "select_then_update", "", (session, session["version"])


def _build_update_params(
    mode: str, update_data: SessionUpdate,
    utc_time: str, session_id: str,
) -> tuple:
    """根据模式构建UPDATE SQL的参数元组

    使用场景: update_session中配合_build_update_sql使用
    使用示例: params = _build_update_params("optimistic", data, utc, sid)
    返回数据说明: UPDATE语句的参数元组（不含session_id和version）

    @author 小健 2026-05-25
    """
    if mode == "optimistic":
        return (update_data.title, utc_time, 1, utc_time, session_id, update_data.version)
    if mode == "compat":
        return (update_data.title, utc_time, 1, utc_time, session_id)
    return (update_data.title, utc_time, session_id)


def _build_update_sql(mode: str) -> Tuple[str, str]:
    """根据模式构建SET子句和version WHERE子句

    使用场景: update_session中3路UPDATE SQL统一构建
    使用示例: _build_update_sql("optimistic") → ("SET title=?, ...", "AND version=?")
    返回数据说明: (set_clause, version_where_clause)

    @author 小健 2026-05-25
    """
    base_set = "title = ?, updated_at = ?"
    if mode == "optimistic":
        return (
            f"SET {base_set}, title_locked = ?, title_updated_at = ?, version = version + 1",
            "AND is_deleted = FALSE AND version = ?",
        )
    if mode == "compat":
        return (
            f"SET {base_set}, title_locked = ?, title_updated_at = ?, version = version + 1",
            "AND is_deleted = FALSE",
        )
    return f"SET {base_set}", "AND is_deleted = FALSE"


def _raise_session_error(
    conn: sqlite3.Connection, status_code: int, msg: str,
):
    """统一回滚+关闭+抛出HTTPException，消除重复

    使用场景: update_session中404/409等错误退出
    使用示例: _raise_session_error(conn, 404, "会话不存在")
    返回数据说明: 不返回，直接raise HTTPException

    @author 小健 2026-05-25
    """
    try:
        conn.rollback()
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass
    raise HTTPException(status_code=status_code, detail=msg)


_TITLE_HISTORY_TABLE_EXISTS: Optional[bool] = None


def _record_title_history(
    cursor, session_id: str, old_title: Optional[str],
    utc_time: str, updated_by: str = "user",
):
    """记录标题变更历史，首次探测DDL后缓存结果

    使用场景: update_session中插入chat_session_title_history
    使用示例: _record_title_history(cursor, sid, "旧标题", utc_time, "user")
    返回数据说明: 无返回，直接执行INSERT

    @author 小健 2026-05-25
    """
    global _TITLE_HISTORY_TABLE_EXISTS
    if _TITLE_HISTORY_TABLE_EXISTS is None:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_session_title_history'"
        )
        _TITLE_HISTORY_TABLE_EXISTS = cursor.fetchone() is not None
    if _TITLE_HISTORY_TABLE_EXISTS and old_title:
        cursor.execute(
            """INSERT INTO chat_session_title_history
               (session_id, title, created_at, updated_by, change_reason)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, old_title, utc_time, updated_by, "user_edit"),
        )
        logger.info(f"记录标题历史: session_id={session_id}, old_title={old_title}")


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, update_data: SessionUpdate):
    """更新会话标题（乐观锁+标题历史+降级兼容）

    重构：189行→≤60行骨架+_build_update_sql+_raise_session_error+_record_title_history
    @author 小沈, 小健 2026-05-25
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            logger.debug(f"开始事务: session_id={session_id}, operation=update_title")
            fields_exist = check_db_fields_exist(conn)
            utc_time = get_utc_timestamp()
            mode, _, params = _resolve_update_mode(fields_exist, update_data, cursor, session_id, utc_time)
            if mode == "not_found":
                _raise_session_error(conn, 404, f"会话不存在: {session_id}")
            sql_mode = _get_sql_mode(mode, fields_exist)
            set_clause, where_clause = _build_update_sql(sql_mode)
            update_params = _build_update_params(sql_mode, update_data, utc_time, session_id)
            cursor.execute(f"UPDATE chat_sessions {set_clause} WHERE id = ? {where_clause}", update_params)
            if mode == "optimistic":
                if cursor.rowcount == 0:
                    logger.warning(f"版本冲突: session_id={session_id}, client_version={update_data.version}")
                    _raise_session_error(conn, 409, "会话已被其他用户修改，请刷新后重试")
                cursor.execute("SELECT id, title, version FROM chat_sessions WHERE id = ?", (session_id,))
                session = cursor.fetchone()
                current_version = session["version"]
            else:
                session, current_version = params
            old_title = session["title"] if session else ""
            new_version = current_version + 1
            _record_title_history(cursor, session_id, old_title, utc_time, update_data.updated_by or "user")
            cursor.execute("COMMIT")
        logger.info(f"更新会话成功: id={session_id}, title={update_data.title}, version={new_version}")
        return {"success": True, "title": update_data.title, "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: session_id={session_id}, error={str(e)}")
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
        conn = get_connection()
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
    conn = None
    try:
        # 解析会话ID列表
        id_list = [sid.strip() for sid in session_ids.split(',') if sid.strip()]

        if not id_list:
            raise HTTPException(status_code=400, detail="会话ID列表不能为空")

        if len(id_list) > 100:
            raise HTTPException(status_code=400, detail="最多一次查询100个会话")

        conn = get_connection()
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
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
