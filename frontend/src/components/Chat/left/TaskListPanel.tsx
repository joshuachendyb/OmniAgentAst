// 编辑历史: 2026-08-26 小欧 - 修复C3: 左列created_at格式化为月/日 时:分(7.2时间显示)
// 编辑历史: 2026-08-27 小欧 - 任务项新增response全文显示（设计文档4.8.2要求user_input+response双列）
// 编辑历史: 2026-08-27 小欧 - 三堂会审P0-5: 任务项div补role/tabIndex/aria/keyDown无障碍可达; 边距6px8px→8px; 选中蓝#1890ff→#1677ff; 滚动容器加minHeight0/scrollbarWidth; focus浅蓝外晕与选中态隔离
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

/** 【小欧 2026-08-26 修复 C3】ISO 时间格式化为 月/日 时:分，避免原始串溢出 */
export const formatTime = (s?: string): string => {
  if (!s) return '-';
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/** 实测枚举（storage.py:467 初始 executing / :128 终态四值），未知值兜底灰色 */
const STATUS_MAP: Record<
  string,
  {
    text: string;
    color: 'processing' | 'success' | 'error' | 'default' | 'warning';
  }
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
    <div style={{ overflowY: 'auto', overflowX: 'hidden', minHeight: 0, scrollbarWidth: 'thin' }}>
      {tasks.map((t) => {
        const st = STATUS_MAP[t.status] ?? {
          text: t.status,
          color: 'default' as const,
        };
        const active = t.task_id === activeTaskId;
        return (
          <div
            key={t.task_id}
            className="task-list-item"
            role="button"
            tabIndex={0}
            aria-pressed={active}
            aria-label={`任务 ${t.task_id} ${st.text}`}
            onClick={() => onSelect(t.task_id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect(t.task_id);
              }
            }}
            style={{
              padding: '8px',
              cursor: 'pointer',
              background: active ? '#e6f4ff' : 'transparent',
              borderLeft: active
                ? '3px solid #1677ff'
                : '3px solid transparent',
              overflowWrap: 'break-word',
              wordBreak: 'break-word',
              outline: 'none',
            }}
          >
            <div style={{ fontSize: 12, color: '#595959' }}>
               {formatTime(t.created_at)}
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
            {t.response && (
              <div
                style={{
                  fontSize: 11,
                  color: '#8c8c8c',
                  marginTop: 2,
                  lineHeight: 1.4,
                  whiteSpace: 'pre-wrap',
                  overflowWrap: 'break-word',
                  maxHeight: '5.3em',
                  overflow: 'auto',
                }}
              >
                {t.response}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export { TaskListPanel };
