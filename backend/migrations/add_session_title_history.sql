-- 标题历史表创建迁移脚本
-- 功能：记录会话标题的所有修改历史，用于追踪和恢复
-- 创建时间：2026-02-25
-- 编写人：小沈（后端开发）
-- 优先级：P2-中

-- 创建标题历史表
CREATE TABLE IF NOT EXISTS chat_session_title_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,  -- 修改者（用户ID或'system'）
    change_reason TEXT,  -- 修改原因（'user_edit', 'auto_update', 'initial'等）
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

-- 创建索引：加速按session_id和created_at查询
-- 这个索引用于快速获取某个会话的标题历史
CREATE INDEX IF NOT EXISTS idx_session_title_history 
    ON chat_session_title_history(session_id, created_at DESC);

-- 为version字段添加说明（SQLite不支持注释，这里用说明）
-- version字段已在add_session_title_fields.sql中添加
-- 这个字段用于乐观锁版本控制，每次修改会话时version += 1

-- 验证表创建
-- 可以通过以下SQL验证表是否创建成功：
-- SELECT name FROM sqlite_master WHERE type='table' AND name='chat_session_title_history';
-- SELECT * FROM pragma_index_list('chat_session_title_history');

-- 使用说明：
-- 1. 当用户手动修改标题时，在update_session接口中记录历史
-- 2. 当系统自动更新标题时（如第一条消息），也记录历史
-- 3. 历史表通过CASCADE自动删除，不会产生孤儿记录
