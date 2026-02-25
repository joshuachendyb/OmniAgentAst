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
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 检查数据库字段是否存在
        fields_exist = check_db_fields_exist(conn)
        
        utc_time = get_utc_timestamp()
        
        # 验证会话存在
        if fields_exist['version']:
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
                
                # 更新标题
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
        logger.error(f"更新会话失败: session_id={session_id}, title={update_data.title}, error={str(e)}")
        raise HTTPException(status_code=500, detail="更新会话失败，请重试")
