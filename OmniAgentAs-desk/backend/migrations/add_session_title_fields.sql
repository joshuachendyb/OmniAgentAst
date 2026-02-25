-- 会话管理API优化数据库迁移脚本
-- 创建时间: 2026-02-25
-- 执行人: 小沈
-- 监督人: 小健
-- 关联优化: API内部逻辑优化（前端无感知）

-- 迁移说明:
-- 本次迁移为会话管理API内部优化添加必要的数据库字段
-- 这些字段用于：
-- 1. title_locked: 标题锁定状态，防止用户修改的标题被自动覆盖
-- 2. title_updated_at: 标题最后更新时间，用于追踪标题修改历史
-- 3. version: 乐观锁版本号，用于并发控制

-- ⚠️ 重要提示:
-- 1. 此迁移必须在部署API优化代码前执行
-- 2. 执行前请备份数据库
-- 3. 所有新增字段都有合理的默认值，向后兼容

-- ========================================
-- 第一步：添加 title_locked 字段
-- ========================================
-- 用途: 标记标题是否被用户锁定，锁定的标题不会被自动更新
-- 默认值: FALSE (新会话默认未锁定，允许自动更新标题)
-- 数据类型: BOOLEAN

ALTER TABLE chat_sessions 
ADD COLUMN title_locked BOOLEAN DEFAULT FALSE;

-- 为现有数据设置默认值（如果表中有数据）
-- UPDATE chat_sessions SET title_locked = FALSE WHERE title_locked IS NULL;

-- ========================================
-- 第二步：添加 title_updated_at 字段
-- ========================================
-- 用途: 记录标题最后一次修改的时间戳
-- 默认值: 当前时间（对于新记录）
-- 数据类型: TIMESTAMP

ALTER TABLE chat_sessions 
ADD COLUMN title_updated_at TIMESTAMP;

-- 为现有数据设置默认值（使用创建时间作为初始值）
-- UPDATE chat_sessions SET title_updated_at = created_at WHERE title_updated_at IS NULL;

-- ========================================
-- 第三步：添加 version 字段
-- ========================================
-- 用途: 乐观锁版本号，用于并发控制
-- 默认值: 1 (初始版本号)
-- 数据类型: INTEGER

ALTER TABLE chat_sessions 
ADD COLUMN version INTEGER DEFAULT 1;

-- 为现有数据设置默认值
-- UPDATE chat_sessions SET version = 1 WHERE version IS NULL;

-- ========================================
-- 第四步：添加索引优化
-- ========================================
-- 为新字段添加索引，提高查询性能

-- title_locked 字段索引（用于筛选锁定/未锁定的会话）
CREATE INDEX IF NOT EXISTS idx_sessions_title_locked 
ON chat_sessions(title_locked);

-- title_updated_at 字段索引（用于按标题更新时间排序）
CREATE INDEX IF NOT EXISTS idx_sessions_title_updated 
ON chat_sessions(title_updated_at DESC);

-- version 字段索引（乐观锁使用）
CREATE INDEX IF NOT EXISTS idx_sessions_version 
ON chat_sessions(version);

-- ========================================
-- 第五步：数据验证
-- ========================================
-- 验证迁移结果

-- 检查新字段是否存在
SELECT 
    COUNT(*) as total_sessions,
    COUNT(title_locked) as with_title_locked,
    COUNT(title_updated_at) as with_title_updated_at,
    COUNT(version) as with_version
FROM chat_sessions;

-- 验证默认值设置正确
SELECT 
    session_id,
    title,
    title_locked,
    title_updated_at,
    version
FROM chat_sessions
LIMIT 5;

-- ========================================
-- 迁移完成
-- ========================================

-- 记录迁移日志
-- INSERT INTO migration_log (migration_name, executed_at, executed_by, status)
-- VALUES ('add_session_title_fields', datetime('now'), '小沈', 'SUCCESS');

-- ⚠️ 迁移后检查清单:
-- □ 执行验证查询，确认所有新字段存在
-- □ 检查默认值是否正确设置
-- □ 测试API优化代码是否能正常工作
-- □ 监控生产环境是否有错误日志
-- □ 准备回滚脚本（如果需要）

-- 如有问题，请联系：
-- 开发人员：小沈
-- 监督人员：小健
-- 报告时间：2026-02-25
