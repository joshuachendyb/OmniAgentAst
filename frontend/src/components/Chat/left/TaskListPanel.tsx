/**
 * TaskListPanel - 左侧任务清单面板（left slot，4.3.2）
 *
 * 【小欧 2026-08-26 8.2】时间+类型徽标(context_link_mode)+状态+耗时；
 * 当前任务高亮、点击联动右侧查看区（7.5）；不展示 token（4.5.1 三分归位）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Badge, Tag, Tooltip, Typography } from 'antd';
import type { SessionTaskItem } from '../../../services/api';

interface TaskListPanelProps {
  tasks: SessionTaskItem[];
  activeTaskId: string | null;
  onSelect: (taskId: string) => void;
}

/** 实测枚举（storage.py:467 初始 executing / :128 终态四值），未知值兜底灰色 */
const STATUS_MAP: Record<
  string,
  { text: string; color: 'processing' | 'success' | 'error' | 'default' | 'warning' }
> = {
  executing: { text: '执行中', color: 'processing' },
  paused: { text: '已暂停', color: 'warning' },
  completed: { text: '完成', color: 'success' },
  failed: { text: '失败', color: 'error' },
  cancelled: { text: '已取消', color: 'default' },
};

const TaskListPanel: React.FC<TaskListPanelProps> = ({
  tasks,
  activeTaskId,
  onSelect,
}) => {
  if (tasks.length === 0) {
    return (
      <Typography.Text type="secondary" style={{ fontSize: 12, padding: 8 }}>
        暂无任务
      </Typography.Text>
    );
  }
  return (
    <div style={{ overflowY: 'auto', height: '100%' }}>
      {tasks.map((t) => {
        const st = STATUS_MAP[t.status] ?? { text: t.status, color: 'default' as const };
        const active = t.task_id === activeTaskId;
        return (
          <div
            key={t.task_id}
            onClick={() => onSelect(t.task_id)}
            style={{
              padding: '6px 8px',
              cursor: 'pointer',
              background: active ? '#e6f4ff' : 'transparent',
              borderLeft: active ? '3px solid #1890ff' : '3px solid transparent',
              wordBreak: 'break-all', // 不截断可折返
            }}
          >
            <div style={{ fontSize: 12, color: '#595959' }}>
              {t.created_at}
              {t.context_link_mode && (
                <Tag
                  style={{ marginLeft: 6 }}
                  color={t.context_link_mode === 'linked' ? 'blue' : 'green'}
                >
                  {t.context_link_mode === 'linked' ? '续聊' : '新任务'}
                </Tag>
              )}
            </div>
            <div style={{ fontSize: 12 }}>
              <Badge status={st.color} text={st.text} />
              {t.duration != null && (
                <Tooltip title="耗时(秒)">
                  <span style={{ marginLeft: 8, color: '#999' }}>
                    {Math.round(t.duration)}s
                  </span>
                </Tooltip>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export { TaskListPanel };
