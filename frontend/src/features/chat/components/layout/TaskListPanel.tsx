// 编辑历史: 2026-08-26 小欧 - 修复C3: 左列created_at格式化为月/日 时:分(7.2时间显示)
// 编辑历史: 2026-08-27 小欧 - 任务项新增response全文显示（设计文档4.8.2要求user_input+response双列）
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 任务项div补role/tabIndex/aria/keyDown无障碍可达; 边距6px8px→8px; 选中蓝#1890ff→#1677ff; 滚动容器加minHeight0/scrollbarWidth; focus浅蓝外晕与选中态隔离
// 编辑历史: 2026-08-28 小欧 - ③A/a1: 去双重滚动(外层保留), 选中去#e6f4ff填色改2px左线透明体系
// 编辑历史: 2026-08-28 小欧 - ③B/b1: 补user_input双列+Tag→点+Text轻量化, 字阶11→12, 截断lineClamp2
// 编辑历史: 2026-09-01 小欧 - 方案C: 新任务被滚动容器隐藏修复(北京老陈反馈)。监听latestTaskId变化→scrollIntoView(block:'nearest')将最新任务带进可视区; 仅新任务诞生时触发, 可视区内不动, 不打断用户上翻历史 - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 修复任务完成后左列"跳回第一个任务": 根因=刷新时loading=true使组件切Skeleton(旧列表卸载), 滚动容器内容高度骤降→scrollTop被浏览器clamp归零, 刷新完成列表回归但scrollTop仍停在顶部。修复=仅当"loading且无已有任务"才显Skeleton(首次加载), 否则保留旧列表渲染, 滚动位置不丢失(三堂会审: 不打断刷新中UI, 首次加载行为不变) - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - task005会审修复(北京老陈定案): scrollIntoView 包 requestAnimationFrame——确保 React 提交 DOM(ref挂载)后视口就绪再滚动, 消除 latestTaskId 变化与 render 同批处理时 ref 未更新仍试图滚动的竞态; 不改触发条件/block, 行为不进反退 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: TL-01 rAF保存ID+卸载cancel防泄漏 — 小欧-2026-09-02
// 编辑历史: 2026-09-09 小欧 - UI视觉优化(北京老陈定案): ①选中态背景#e6f4ff+左侧3px蓝线+微圆角; ②回复区域背景#fafafa+左边框2px; ③元信息行(时间/模型/状态)置顶; ④间距优化: 内边距8→10px, 项间距4→2px; ⑤放弃序号标签(视觉噪音)和Tooltip方案(遮挡凌乱) - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 新增复制按钮(北京老陈定案): 用户输入和回复区域右上角分别添加复制按钮, hover时显示, 点击复制对应文本, message.success提示 - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 修复formatTime导入缺失(formatTime is not defined) + message.success/error改用showSuccess/handleError(lint规范) + t.response非空断言(TS2345) - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 模型标签条件显示provider前缀: rightOpen=true(右侧展开)只显示model, rightOpen=false(右侧折叠)显示provider/model - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 步数标签改轮次标签: total_steps→llm_call_count, "步"→"轮", 与TaskInfoBar一致; 模型/轮次标签颜色TERTIARY(#999)→PRIMARY(#595959)提亮 - 小欧-2026-09-09
// 编辑历史: 2026-09-28 小欧 - 活跃任务注入(设计文档[76] 6.11): 加merged_inputs折叠块(默认收起,展开看全文) — 小欧-2026-09-28
// 编辑历史: 2026-09-30 小欧 - [81]v1.4-H18修复: 状态标签按后端 status 字段正确映射
//   (completed→已完成/executing→执行中/paused→已暂停/failed→失败/cancelled→已取消)，
//   原实现`t.status==='failed'?'失败':'成功'`把 executing/paused/cancelled 全标成"成功" — 小欧-2026-09-30
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.18 + 5.10.5 + 5.10.8: 新增上下文链接链号徽标 —— 按
//   context_root_task_id 归链(升序首遇链根递增), 仅链长>1 才编号与渲染(判据合一, 消断号), 配色改
//   Colors.INFO 达 WCAG AA; 并纠正下方头注释"类型徽标(context_link_mode)"之过时描述(本文件该字段零使用) — 小欧-2026-10-03
// 编辑历史: 2026-10-03 小欧 - 视觉修正: 链号徽标背景 #e6f4ff 与激活行背景(#e6f4ff)撞色, 激活行上徽标底色融入行背景丢分层
//   → 徽标背景改 #f5f5f5 与同行轮次标签一致, 字色保留 Colors.INFO(#096dd9 on #f5f5f5 ≈ 4.9:1, 达 WCAG AA) — 小欧-2026-10-03
/**
 * TaskListPanel - 左侧任务清单面板（left slot，4.3.2）
 *
 * 【小欧 2026-08-26 8.2】时间+状态徽标+耗时(原注释称"类型徽标(context_link_mode)"，该字段本文件零使用、实际从未渲染);
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
import { CopyOutlined, CaretDownOutlined } from '@ant-design/icons';
import type { SessionTaskItem } from '../../../../services/api/task.api';
import { Colors } from '@/utils/stepStyles';
import { formatTime } from '@/utils/time';
import { showSuccess, handleError } from '@/services/error/handler';
import { CollapsibleText } from '../pipeline/CollapsibleText';

// 2026-09-30 小欧 [81]v1.4-H18: 左列任务状态标签——按后端 status 枚举正确显示。
//   DB 合法值: completing→completed/executing/paused/failed/cancelled（db_initializer 默认 'executing'）
const TASK_STATUS_LABEL: Record<string, { name: string; color: string }> = {
  completed: { name: '已完成', color: Colors.TEXT.TERTIARY },
  executing: { name: '执行中', color: Colors.PRIMARY },
  paused: { name: '已暂停', color: Colors.WARNING },
  failed: { name: '失败', color: '#ff4d4f' },
  cancelled: { name: '已取消', color: Colors.TEXT.TERTIARY },
};

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

  // 2026-09-28 小欧: 追加注入消息折叠块展开状态(每任务独立)
  const [expandedTasks, setExpandedTasks] = React.useState<Set<string>>(
    new Set()
  );
  const toggleExpanded = (taskId: string) => {
    setExpandedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  // 2026-09-01 小欧 方案C: 新任务诞生(latestTaskId变化)且不在可视区时, 滚动带进视野; 可视区内不动不打扰
  const prevLatestIdRef = useRef<string | null>(null);
  const rafIdRef = useRef<number | null>(null);
  useEffect(() => {
    if (!latestTaskId) return;
    if (prevLatestIdRef.current === latestTaskId) return; // 非新任务, 不滚动
    prevLatestIdRef.current = latestTaskId;
    // 2026-09-02 小欧 task005会审(北京老陈定案): rAF 确保React提交DOM(ref挂载)后滚动, 消 latestTaskId 与 render 同批处理时 ref 未更新竞态 — 小欧 2026-09-02
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

  // 上下文链接分组——按 t.context_root_task_id 归链(缺省=自身, 独立任务自成链),
  //   升序(旧→新)首次遇到链根即分配组号。5.10.5: 只对链长>1 的根编号, 否则独立任务也占号,
  //   用户会看到"链2"却无"链1"(空洞); 渲染判据同步改为"无组号不渲染", 与分配判据合一(单一判据)。
  const chainSizeOf = new Map<string, number>();
  for (const t of tasks) {
    const root = t.context_root_task_id ?? t.task_id;
    chainSizeOf.set(root, (chainSizeOf.get(root) ?? 0) + 1);
  }
  const groupNoOf = new Map<string, number>();
  for (const t of tasks) {
    const root = t.context_root_task_id ?? t.task_id;
    if ((chainSizeOf.get(root) ?? 0) > 1 && !groupNoOf.has(root)) {
      groupNoOf.set(root, groupNoOf.size + 1);
    }
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
              {/* 2026-09-30 小欧 [81]v1.4-H18: 按 TASK_STATUS_LABEL 映射，未知状态兜底回退展示原始值 */}
              {(() => {
                const st = TASK_STATUS_LABEL[t.status];
                return (
                  <span
                    style={{
                      fontSize: 11,
                      color: st ? st.color : Colors.TEXT.TERTIARY,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                    }}
                  >
                    <span style={{ fontSize: 6 }}>●</span>
                    {st ? st.name : t.status}
                  </span>
                );
              })()}

              {/* 上下文链接链号徽标(仅链长>1时显示, 独立任务不成链不贴标) */}
              {(() => {
                const root = t.context_root_task_id ?? t.task_id;
                const groupNo = groupNoOf.get(root);
                if (groupNo === undefined) return null; // 独立任务不成链, 不贴标
                return (
                  <span
                    style={{
                      fontSize: 10,
                      // 2026-10-03 小欧 视觉修正: 原背景 #e6f4ff 与激活行背景同色(#e6f4ff),
                      // 激活行上徽标底色与行背景融为一体、丢了分层感 → 改与同行轮次标签一致 #f5f5f5,
                      // 字色仍用 Colors.INFO(#096dd9) 强调"链"语义; 对比度 #096dd9 on #f5f5f5 ≈ 4.9:1 达 WCAG AA
                      color: Colors.INFO,
                      backgroundColor: '#f5f5f5',
                      padding: '1px 5px',
                      borderRadius: 3,
                    }}
                  >
                    链{groupNo}
                  </span>
                );
              })()}

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

            {/* 2026-09-28 小欧: 追加注入消息 — 语义属输入侧, 故置于问题区与回复区之间;
                默认收起(不撑条目高度), 展开看全文。 */}
            {t.merged_inputs && t.merged_inputs.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleExpanded(t.task_id);
                  }}
                  aria-expanded={expandedTasks.has(t.task_id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    fontSize: 12,
                    color: Colors.TEXT.TERTIARY,
                  }}
                >
                  <CaretDownOutlined
                    rotate={expandedTasks.has(t.task_id) ? 180 : 0}
                  />{' '}
                  ↳ 追加 {t.merged_inputs.length} 条
                </button>
                {expandedTasks.has(t.task_id) &&
                  t.merged_inputs.map((m, i) => (
                    <div
                      key={i}
                      style={{
                        marginTop: 4,
                        paddingLeft: 10,
                        borderLeft: '2px solid #d9d9d9',
                      }}
                    >
                      <CollapsibleText text={m} />
                    </div>
                  ))}
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
