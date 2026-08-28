// 编辑历史: 2026-08-26 小欧 - 修复C3: 左列created_at格式化为月/日 时:分(7.2时间显示)
// 编辑历史: 2026-08-27 小欧 - 任务项新增response全文显示（设计文档4.8.2要求user_input+response双列）
// 编辑历史: 2026-08-27 小欧 - 三堂会审P0-5: 任务项div补role/tabIndex/aria/keyDown无障碍可达; 边距6px8px→8px; 选中蓝#1890ff→#1677ff; 滚动容器加minHeight0/scrollbarWidth; focus浅蓝外晕与选中态隔离
// 编辑历史: 2026-08-28 小欧 - ③A/a1: 去双重滚动(外层保留), 选中去#e6f4ff填色改2px左线透明体系
// 编辑历史: 2026-08-28 小欧 - ③B/b1: 补user_input双列+Tag→点+Text轻量化, 字阶11→12, 截断lineClamp2
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
import { Empty, Skeleton, Typography } from 'antd';
import type { SessionTaskItem } from '../../../services/api';
import { Colors } from '@/utils/stepStyles';
import { CollapsibleText } from '../pipeline/CollapsibleText';

interface TaskListPanelProps {
  tasks: SessionTaskItem[];
  activeTaskId: string | null;
  onSelect: (taskId: string) => void;
  loading?: boolean;
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

const TaskListPanel: React.FC<TaskListPanelProps> = ({
  tasks,
  activeTaskId,
  onSelect,
  loading = false,
}) => {
  if (loading) {
    return (
      <div style={{ padding: '16px 8px' }}>
        <Skeleton active paragraph={{ rows: 3 }} />
      </div>
    );
  }
  if (tasks.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={<Typography.Text type="secondary" style={{ fontSize: 12 }}>暂无任务</Typography.Text>}
        style={{ padding: '24px 0' }}
      />
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '4px 0' }}>
      {tasks.map((t) => {
        const active = t.task_id === activeTaskId;
        return (
          <div
            key={t.task_id}
            className="task-list-item"
            role="button"
            tabIndex={0}
            aria-pressed={active}
            aria-label={`任务 ${t.task_id} ${t.status}`}
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
              background: 'transparent',
              borderLeft: active ? `2px solid ${Colors.PRIMARY}` : '2px solid transparent',
              borderRadius: 0,
              overflowWrap: 'break-word',
              wordBreak: 'break-word',
              textAlign: 'left',
              outline: 'none',
            }}
          >
            {t.user_input && (
              <div
                style={{
                  fontSize: 12,
                  color: Colors.TEXT.STRONG,
                  fontWeight: 500,
                  marginTop: 4,
                  lineHeight: 1.4,
                  wordBreak: 'break-word',
                }}
              >
                <CollapsibleText text={t.user_input} />
              </div>
            )}
            {t.response && (
              <div
                style={{
                  marginTop: 2,
                  paddingLeft: 8,
                  borderLeft: `1px solid ${Colors.BORDER.LIGHT}`,
                }}
              >
                <span style={{ fontSize: 11, color: Colors.TEXT.TERTIARY }}>回复</span>
                <div
                  style={{
                    fontSize: 12,
                    color: Colors.TEXT.PRIMARY,
                    marginTop: 2,
                    lineHeight: 1.5,
                    wordBreak: 'break-word',
                  }}
                >
                  <CollapsibleText text={t.response} />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export { TaskListPanel };
