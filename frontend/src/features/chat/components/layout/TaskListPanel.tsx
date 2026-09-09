// 编辑历史: 2026-08-26 小欧 - 修复C3: 左列created_at格式化为月/日 时:分(7.2时间显示)
// 编辑历史: 2026-08-27 小欧 - 任务项新增response全文显示（设计文档4.8.2要求user_input+response双列）
// 编辑历史: 2026-08-27 小欧 - 三堂会审P0-5: 任务项div补role/tabIndex/aria/keyDown无障碍可达; 边距6px8px→8px; 选中蓝#1890ff→#1677ff; 滚动容器加minHeight0/scrollbarWidth; focus浅蓝外晕与选中态隔离
// 编辑历史: 2026-08-28 小欧 - ③A/a1: 去双重滚动(外层保留), 选中去#e6f4ff填色改2px左线透明体系
// 编辑历史: 2026-08-28 小欧 - ③B/b1: 补user_input双列+Tag→点+Text轻量化, 字阶11→12, 截断lineClamp2
// 编辑历史: 2026-09-01 小欧 - 方案C: 新任务被滚动容器隐藏修复(北京老陈反馈)。监听latestTaskId变化→scrollIntoView(block:'nearest')将最新任务带进可视区; 仅新任务诞生时触发, 可视区内不动, 不打断用户上翻历史 - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 修复任务完成后左列"跳回第一个任务": 根因=刷新时loading=true使组件切Skeleton(旧列表卸载), 滚动容器内容高度骤降→scrollTop被浏览器clamp归零, 刷新完成列表回归但scrollTop仍停在顶部。修复=仅当"loading且无已有任务"才显Skeleton(首次加载), 否则保留旧列表渲染, 滚动位置不丢失(三堂会审: 不打断刷新中UI, 首次加载行为不变) - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - task005会审P8修复(北京老陈定案): scrollIntoView 包 requestAnimationFrame——确保 React 提交 DOM(ref挂载)后视口就绪再滚动, 消除 latestTaskId 变化与 render 同批处理时 ref 未更新仍试图滚动的竞态; 不改触发条件/block, 行为不进反退 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: TL-01 rAF保存ID+卸载cancel防泄漏 — 小欧-2026-09-02
// 编辑历史: 2026-09-09 小欧 - UI视觉优化(北京老陈定案): ①选中态背景#e6f4ff+左侧3px蓝线+微圆角; ②回复区域背景#fafafa+左边框2px; ③元信息行(时间/模型/状态)置顶; ④间距优化: 内边距8→10px, 项间距4→2px; ⑤放弃序号标签(视觉噪音)和Tooltip方案(遮挡凌乱) - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 新增复制按钮(北京老陈定案): 用户输入和回复区域右上角分别添加复制按钮, hover时显示, 点击复制对应文本, message.success提示 - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 修复formatTime导入缺失(formatTime is not defined) + message.success/error改用showSuccess/handleError(lint规范) + t.response非空断言(TS2345) - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 模型标签条件显示provider前缀: rightOpen=true(右侧展开)只显示model, rightOpen=false(右侧折叠)显示provider/model - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 步数标签改轮次标签: total_steps→llm_call_count, "步"→"轮", 与TaskInfoBar一致; 模型/轮次标签颜色TERTIARY(#999)→PRIMARY(#595959)提亮 - 小欧-2026-09-09
/**
 * TaskListPanel - 左侧任务清单面板（left slot，4.3.2）
 *
 * 【小欧 2026-08-26 8.2】时间+类型徽标(context_link_mode)+状态+耗时；
 * 当前任务高亮、点击联动右侧查看区（7.5）；不展示 token（4.5.1 三分归位）。
 *
 * 【小欧 2026-09-01 方案C】新任务在数组末尾+左列滚动容器→被隐藏。依赖外部 latestTaskRef
 * 挂到最新任务项, 监听 latestTaskId 变化时 scrollIntoView(nearest) 带进视野(见 4.3.2)。
 *
 * 【小欧 2026-09-09 UI优化】选中态背景色+左侧边框加粗+微圆角; 回复区域背景色+左边框加粗;
 * 元信息行(时间/模型/状态)置顶; 间距优化; 放弃序号标签和Tooltip方案。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useCallback, useEffect, useRef } from 'react';
import { Empty, Skeleton, Typography } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import type { SessionTaskItem } from '../../../../services/api/task.api';
import { Colors } from '@/utils/stepStyles';
import { formatTime } from '@/utils/time';
import { showSuccess, handleError } from '@/services/error/handler';
import { CollapsibleText } from '../pipeline/CollapsibleText';

interface TaskListPanelProps {
  tasks: SessionTaskItem[];
  activeTaskId: string | null;
  onSelect: (taskId: string) => void;
  loading?: boolean;
  // 2026-09-01 小欧 方案C: 最新任务锚点(后端latest_task_id) + 挂到最新任务项的ref(滚动定位用)
  latestTaskId?: string | null;
  latestTaskRef?: React.MutableRefObject<HTMLDivElement | null>;
  // 2026-09-09 小欧: 右侧展开状态, 折叠时模型标签显示provider前缀
  rightOpen?: boolean;
}

const TaskListPanel: React.FC<TaskListPanelProps> = ({
  tasks,
  activeTaskId,
  onSelect,
  loading = false,
  latestTaskId = null,
  latestTaskRef,
  rightOpen = true,
}) => {
  // 2026-09-09 小欧 复制按钮: 点击复制文本到剪贴板, 显示成功提示
  const handleCopy = useCallback(
    async (text: string, type: '问题' | '回复') => {
      try {
        await navigator.clipboard.writeText(text);
        showSuccess(`${type}已复制`);
      } catch {
        handleError({ message: '复制失败' });
      }
    },
    []
  );

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
        gap: 2, // 2026-09-09 小欧 优化: 项间距4→2px，紧凑但不拥挤
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
            className={`task-list-item${active ? ' active' : ''}`}
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
              padding: '10px 12px', // 2026-09-09 小欧 优化: 内边距8→10px/12px，呼吸感适中
              cursor: 'pointer',
              backgroundColor: active ? '#e6f4ff' : 'transparent', // 2026-09-09 小欧 优化: 选中态浅蓝背景
              borderLeft: active
                ? `3px solid ${Colors.PRIMARY}` // 2026-09-09 小欧 优化: 选中左边框2→3px，更醒目
                : '3px solid transparent', // 非选中: 透明占位保持对齐
              borderRadius: active ? '0 4px 4px 0' : 0, // 2026-09-09 小欧 优化: 选中态微圆角
              overflowWrap: 'break-word',
              wordBreak: 'break-word',
              textAlign: 'left',
              outline: 'none',
            }}
          >
            {/* 2026-09-09 小欧 优化: 元信息行(时间/模型/状态)置顶，先概览后详情 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 6, // 与问题区域间距
                flexWrap: 'wrap', // 窄屏时换行
              }}
            >
              {/* 时间标签 */}
              <span style={{ fontSize: 11, color: Colors.TEXT.TERTIARY }}>
                {formatTime(t.created_at)}
              </span>

              {/* 模型标签: 右侧折叠时显示provider前缀, 展开时只显示model */}
              {t.model && (
                <span
                  style={{
                    fontSize: 10,
                    color: Colors.TEXT.PRIMARY,
                    backgroundColor: '#f5f5f5',
                    padding: '1px 5px',
                    borderRadius: 3,
                  }}
                >
                  {!rightOpen && t.provider ? `${t.provider}/` : ''}
                  {t.model}
                </span>
              )}

              {/* 状态标签 */}
              <span
                style={{
                  fontSize: 11,
                  color:
                    t.status === 'failed' ? '#ff4d4f' : Colors.TEXT.TERTIARY,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                }}
              >
                <span style={{ fontSize: 6 }}>●</span>
                {t.status === 'failed' ? '失败' : '成功'}
              </span>

              {/* 轮次标签（显示LLM调用轮次） */}
              {t.llm_call_count > 0 && (
                <span
                  style={{
                    fontSize: 10,
                    color: Colors.TEXT.PRIMARY,
                    backgroundColor: '#f5f5f5',
                    padding: '1px 5px',
                    borderRadius: 3,
                  }}
                >
                  {t.llm_call_count}轮
                </span>
              )}
            </div>

            {/* 用户问题区域 */}
            {t.user_input && (
              <div
                className="task-text-block" // position:relative由CSS .task-text-block定义，不重复内联(DRY)
                style={{
                  fontSize: 12,
                  color: Colors.TEXT.STRONG, // 强文本，问题突出
                  fontWeight: 500, // 中等加粗
                  lineHeight: 1.5,
                  wordBreak: 'break-word',
                }}
              >
                <CollapsibleText text={t.user_input} />
                {/* 2026-09-09 小欧 复制按钮: 用户输入右上角, hover时显示 */}
                <button
                  className="task-copy-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCopy(t.user_input, '问题');
                  }}
                  aria-label="复制问题"
                >
                  <CopyOutlined />
                </button>
              </div>
            )}

            {/* 回复区域 */}
            {t.response && (
              <div
                className="task-text-block" // position:relative由CSS .task-text-block定义，不重复内联(DRY)
                style={{
                  marginTop: 8, // 与问题区域保持间距
                  paddingLeft: 10, // 左侧缩进
                  borderLeft: '2px solid #d9d9d9', // 2026-09-09 小欧 优化: 左边框加粗1→2px
                  backgroundColor: '#fafafa', // 2026-09-09 小欧 优化: 浅灰背景，层次清晰
                  borderRadius: '0 3px 3px 0', // 微圆角
                  padding: '8px 10px', // 内边距，内容不贴边
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: Colors.TEXT.PRIMARY, // 主文本，比问题稍浅
                    lineHeight: 1.6, // 回复正文行高略大，阅读舒适
                    wordBreak: 'break-word',
                  }}
                >
                  <CollapsibleText text={t.response} />
                </div>
                {/* 2026-09-09 小欧 复制按钮: 回复区域右上角, hover时显示 */}
                <button
                  className="task-copy-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCopy(t.response!, '回复');
                  }}
                  aria-label="复制回复"
                >
                  <CopyOutlined />
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export { TaskListPanel };
