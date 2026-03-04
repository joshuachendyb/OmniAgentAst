import re

# 读取sessions.py
with open('backend/app/api/v1/sessions.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加类型导入（如果不存在）
if 'from sqlite3 import Connection, Cursor' not in content:
    # 在第18行之后添加
    content = content.replace(
        'from app.utils.logger import logger',
        'from app.utils.logger import logger\n\nfrom sqlite3 import Connection, Cursor'
    )

# 2. 添加SessionUpdate的version和updated_by字段
if 'version: Optional[int] = Field(None' not in content:
    content = content.replace(
        'class SessionUpdate(BaseModel):',
        'class SessionUpdate(BaseModel):\n    title: str = Field(..., description="会话标题")\n    version: Optional[int] = Field(None, description="版本号（乐观锁）")\n    updated_by: Optional[str] = Field(None, description="修改者")'
    )

# 3. 添加BatchTitleResponse模型
if 'class BatchTitleResponse(BaseModel):' not in content:
    # 在SessionListResponse之后添加
    content = content.replace(
        'class SessionListResponse(BaseModel):',
        'class SessionListResponse(BaseModel):'
    )
    content = content.replace(
        'sessions: list[SessionResponse] = Field(..., description="会话列表")\n\n',
        'sessions: list[SessionResponse] = Field(..., description="会话列表")\n\nclass BatchTitleResponse(BaseModel):\n    """批量获取会话标题响应（12.1.3节）"""\n    sessions: list[dict] = Field(..., description="会话标题信息列表")\n'
    )

# 4. 修改get_session_messages以返回新字段
# 查找函数中的return语句并修改
if 'title_source' not in content:
    # 在return之前添加新字段
    old_return = '''return {
            "session_id": session_id,
            "messages": messages
        }'''
    new_return = '''title_locked = bool(session.get('title_locked', False))
        title_source = 'user' if title_locked else 'auto'
        title_updated_at = _convert_to_utc(session.get('title_updated_at', session.get('created_at')))
        
        return {
            "session_id": session_id,
            "title": session['title'],
            "title_locked": title_locked,
            "title_source": title_source,
            "title_updated_at": title_updated_at,
            "messages": messages
        }'''
    content = content.replace(old_return, new_return)

# 5. 替换update_session函数
new_update_session = '''@router.put("/sessions/{session_id}")
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
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 检查数据库字段是否存在
        fields_exist = check_db_fields_exist(conn)
        
        utc_time = get_utc_timestamp()
        
        # 验证会话存在并获取当前状态（使用原子性UPDATE修复并发问题）
        if fields_exist.get('version', False):
            # 新字段存在，支持乐观锁
            if update_data.version is not None:
                # 乐观锁模式：使用原子性UPDATE检查version
                cursor.execute("BEGIN")
                
                # 尝试更新并检查version
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
                
                # 检查是否更新成功
                if cursor.rowcount == 0:
                    cursor.execute("ROLLBACK")
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
                    '''SELECT title, version FROM chat_sessions WHERE id = ?''',
                    (session_id,)
                )
                session = cursor.fetchone()
                old_title = session['title']
                new_version = session['version']
            else:
                # 兼容模式：不检查version（旧前端）
                cursor.execute("BEGIN")
                
                # 获取当前状态
                cursor.execute(
                    '''SELECT id, title, COALESCE(version, 1) as version, 
                              COALESCE(title_locked, 0) as title_locked
                       FROM chat_sessions 
                       WHERE id = ? AND is_deleted = FALSE''',
                    (session_id,)
                )
                session = cursor.fetchone()
                
                if not session:
                    cursor.execute("ROLLBACK")
                    conn.close()
                    raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
                
                old_title = session['title']
                current_version = session['version']
                new_version = current_version + 1
                
                # 更新标题（不检查version）
                cursor.execute(
                    '''UPDATE chat_sessions 
                       SET title = ?, updated_at = ?, 
                          title_locked = ?, 
                          title_updated_at = ?, 
                          version = ?
                       WHERE id = ?''',
                    (update_data.title, utc_time, 1, utc_time, 
                     new_version, session_id)
                )
        else:
            # 新字段不存在，完全兼容模式
            cursor.execute("BEGIN")
            
            cursor.execute(
                '''SELECT id, title FROM chat_sessions 
                   WHERE id = ? AND is_deleted = FALSE''',
                (session_id,)
            )
            session = cursor.fetchone()
            
            if not session:
                cursor.execute("ROLLBACK")
                conn.close()
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            
            old_title = session['title']
            new_version = 1  # 模拟版本号
            
            # 更新标题
            cursor.execute(
                '''UPDATE chat_sessions 
                   SET title = ?, updated_at = ? 
                   WHERE id = ?''',
                (update_data.title, utc_time, session_id)
            )
        
        # 插入标题历史记录（如果表存在）
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
        
        # 提交事务
        cursor.execute("COMMIT")
        conn.close()
        
        logger.info(f"更新会话成功: id={session_id}, title={update_data.title}, version={new_version}")
        
        return {
            "success": True, 
            "title": update_data.title,
            "version": new_version
        }
        
    except HTTPException as he:
        try:
            conn.close()
        except:
            pass
        logger.error(f"更新会话HTTP异常: session_id={session_id}, status={he.status_code}, detail={he.detail}")
        raise
    except Exception as e:
        logger.
