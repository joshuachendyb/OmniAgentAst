// 编辑历史: 2026-08-26 小欧 - 修复C3: 左列created_at格式化为月/日 时:分(7.2时间显示)
// 编辑历史: 2026-08-27 小欧 - 任务项新增response全文显示（设计文档4.8.2要求user_input+response双列）
// 编辑历史: 2026-08-27 小欧 - 三堂会审P0-5: 任务项div补role/tabIndex/aria/keyDown无障碍可达; 边距6px8px→8px; 选中蓝#1890ff→#1677ff; 滚动容器加minHeight0/scrollbarWidth; focus浅蓝外晕与选中态隔离
// 编辑历史: 2026-08-28 小欧 - ③A/a1: 去双重滚动(外层保留), 选中去#e6f4ff填色改2px左线透明体系
// 编辑历史: 2026-08-28 小欧 - ③B/b1: 补user_input双列+Tag→点+Text轻量化, 字阶11→12, 截断lineClamp2
// 编辑历史: 2026-09-01 小欧 - 方案C: 新任务被滚动容器隐藏修复(北京老陈反馈)。监听latestTaskId变化→scrollIntoView(block:'nearest')将最新任务带进可视区; 仅新任务诞生时触发, 可视区内不动, 不打断用户上翻历史 - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 修复任务完成后左列"跳回第一个任务": 根因=刷新时loading=true使组件切Skeleton(旧列表卸载), 滚动容器内容高度骤降→scrollTop被浏览器clamp归零, 刷新完成列表回归但scrollTop仍停在顶部。修复=仅当"loading且无已有任务"才显Skeleton(首次加载), 否则保留旧列表渲染, 滚动位置不丢失(三堂会审: 不打断刷新中UI, 首次加载行为不变) - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - task005会审P8修复(北京老陈定案): scrollIntoView 包 requestAnimationFrame——确保 React 提交 DOM(ref挂载)后视口就绪再滚动, 消除 latestTaskId 变化与 render 同批处理时 ref 未更新仍试图滚动的竞态; 不改触发条件/block, 行为不进反退 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: TL-01 rAF保存ID+卸载cancel防泄漏 — 小欧-2026-09-02
/**
 * TaskListPanel - 左侧任务清单面板（left slot，4.3.2）
 *
 * 【小欧 2026-08-26 8.2】时间+类型徽标(context_link_mode)+状态+耗时；
 * 当前任务高亮、点击联动右侧查看区（7.5）；不展示 token（4.5.1 三分归位）。
 *
 * 【小欧 2026-09-01 方案C】新任务在数组末尾+左列滚动容器→被隐藏。依赖外部 latestTaskRef
 * 挂到最新任务项, 监听 latestTaskId 变化时 scrollIntoView(nearest) 带进视野(见 4.3.2)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useRef } from 'react';
import { Empty, Skeleton, Typography } from 'antd';
import type { SessionTaskItem } from '../../../../services/api/task.api';
import { Colors } from '@/utils/stepStyles';
import { CollapsibleText } from '../pipeline/CollapsibleText';

interface TaskListPanelProps {
  tasks: SessionTaskItem[];
  activeTaskId: string | null;
  onSelect: (taskId: string) => void;
  loading?: boolean;
  // 2026-09-01 小欧 方案C: 最新任务锚点(后端latest_task_id) + 挂到最新任务项的ref(滚动定位用)
  latestTaskId?: string | null;
  latestTaskRef?: React.MutableRefObject<HTMLDivElement | null>;
}

const TaskListPanel: React.FC<TaskListPanelProps> = ({
  tasks,
  activeTaskId,
  onSelect,
  loading = false,
  latestTaskId = null,
  latestTaskRef,
}) => {
  // 2026-09-01 小欧 方案C: 无外部ref时退化为自建内部ref, 保证定位逻辑始终可用
  const internalRef = useRef<HTMLDivElement | null>(null);
  const anchorRef = latestTaskRef ?? internalRef;

  // 2026-09-01 小欧 方案C: 新任务诞生(latestTaskId变化)且不在可视区时, 滚动带进视野; 可视区内不动不打扰
  const prevLatestIdRef = useRef<string | null>(null);
  const rafIdRef = useRef<number | null>(null);
  useEffect(() => {
    if (!latestTaskId) return;
    if (prevLatestIdRef.current === latestTaskId) return; // 非新任务, 不滚动
    prevLatestIdRef.current = latestTaskId;
    // 2026-09-02 小欧 task005会审P8(北京老陈定案): rAF 确保React提交DOM(ref挂载)后滚动, 消 latestTaskId 与 render 同批处理时 ref 未更新竞态 — 小欧 2026-09-02
    rafIdRef.current = requestAnimationFrame(() => {
      // scrollIntoView 沿祖先滚动链自动定位到最近滚动容器(SessionLayout左列overflowY:auto), 无需改布局骨架
      anchorRef.current?.scrollIntoView({ block: 'nearest' });
    });
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, [latestTaskId, anchorRef]);
  if (loading && tasks.length === 0) {
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
        description={
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            暂无任务
          </Typography.Text>
        }
        style={{ padding: '24px 0' }}
      />
    );
  }
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        padding: '4px 0',
      }}
    >
      {tasks.map((t) => {
        const active = t.task_id === activeTaskId;
        const isLatest = t.task_id === latestTaskId; // 2026-09-01 小欧 方案C: 最新任务项挂锚点ref(供滚动定位)
        return (
          <div
            key={t.task_id}
            ref={isLatest ? anchorRef : undefined}
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
              borderLeft: active
                ? `2px solid ${Colors.PRIMARY}`
                : '2px solid transparent',
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
                <span style={{ fontSize: 11, color: Colors.TEXT.TERTIARY }}>
                  回复
                </span>
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
