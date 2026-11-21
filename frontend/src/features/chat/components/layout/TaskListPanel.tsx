// 编辑历史: 2026-10-06 小欧 - MarkdownSlot 上移中立层后改指 @/components/markdown/MarkdownSlot(原 ../pipeline/MarkdownSlot), 内容未改。 — 小欧-2026-10-06
// 编辑历史: 2026-08-26 小欧 - 修复C3: 左列created_at格式化为月/日 时:分(7.2时间显示)
// 编辑历史: 2026-08-27 小欧 - 任务项新增response全文显示（设计文档4.8.2要求user_input+response双列）
// 编辑历史: 2026-08-27 小欧 - 复核修复: 任务项div补role/tabIndex/aria/keyDown无障碍可达; 边距6px8px→8px; 选中蓝#1890ff→#1677ff; 滚动容器加minHeight0/scrollbarWidth; focus浅蓝外晕与选中态隔离
// 编辑历史: 2026-08-28 小欧 - 去双重滚动(外层保留), 选中去#e6f4ff填色改2px左线透明体系
// 编辑历史: 2026-08-28 小欧 - 补user_input双列+Tag→点+Text轻量化, 字阶11→12, 截断lineClamp2
// 编辑历史: 2026-09-01 小欧 - 方案C: 新任务被滚动容器隐藏修复(北京老陈反馈)。监听latestTaskId变化→scrollIntoView(block:'nearest')将最新任务带进可视区; 仅新任务诞生时触发, 可视区内不动, 不打断用户上翻历史 - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 修复任务完成后左列"跳回第一个任务": 根因=刷新时loading=true使组件切Skeleton(旧列表卸载), 滚动容器内容高度骤降→scrollTop被浏览器clamp归零, 刷新完成列表回归但scrollTop仍停在顶部。修复=仅当"loading且无已有任务"才显Skeleton(首次加载), 否则保留旧列表渲染, 滚动位置不丢失(复核: 不打断刷新中UI, 首次加载行为不变) - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - task005修复(北京老陈定案): scrollIntoView 包 requestAnimationFrame——确保 React 提交 DOM(ref挂载)后视口就绪再滚动, 消除 latestTaskId 变化与 render 同批处理时 ref 未更新仍试图滚动的竞态; 不改触发条件/block, 行为不进反退 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - rAF保存ID+卸载cancel防泄漏 — 小欧-2026-09-02
// 编辑历史: 2026-09-09 小欧 - UI视觉优化(北京老陈定案): ①选中态背景#e6f4ff+左侧3px蓝线+微圆角; ②回复区域背景#fafafa+左边框2px; ③元信息行(时间/模型/状态)置顶; ④间距优化: 内边距8→10px, 项间距4→2px; ⑤放弃序号标签(视觉噪音)和Tooltip方案(遮挡凌乱) - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 新增复制按钮(北京老陈定案): 用户输入和回复区域右上角分别添加复制按钮, hover时显示, 点击复制对应文本, message.success提示 - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 修复formatTime导入缺失(formatTime is not defined) + message.success/error改用showSuccess/handleError(lint规范) + t.response非空断言(TS2345) - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 模型标签条件显示provider前缀: rightOpen=true(右侧展开)只显示model, rightOpen=false(右侧折叠)显示provider/model - 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 步数标签改轮次标签: total_steps→llm_call_count, "步"→"轮", 与TaskInfoBar一致; 模型/轮次标签颜色TERTIARY(#999)→PRIMARY(#595959)提亮 - 小欧-2026-09-09
// 编辑历史: 2026-09-28 小欧 - 活跃任务注入: 加merged_inputs折叠块(默认收起,展开看全文) — 小欧-2026-09-28
// 编辑历史: 2026-09-30 小欧 - 修复: 状态标签按后端 status 字段正确映射
//   (completed→已完成/executing→执行中/paused→已暂停/failed→失败/cancelled→已取消)，
//   原实现`t.status==='failed'?'失败':'成功'`把 executing/paused/cancelled 全标成"成功" — 小欧-2026-09-30
// 编辑历史: 2026-10-03 小欧 - 新增上下文链接链号徽标 —— 按
//   context_root_task_id 归链(升序首遇链根递增), 仅链长>1 才编号与渲染(判据合一, 消断号), 配色改
//   Colors.INFO 达 WCAG AA; 并纠正下方头注释"类型徽标(context_link_mode)"之过时描述(本文件该字段零使用) — 小欧-2026-10-03
// 编辑历史: 2026-10-03 小欧 - 视觉修正: 链号徽标背景 #e6f4ff 与激活行背景(#e6f4ff)撞色, 激活行上徽标底色融入行背景丢分层
//   → 徽标背景改 #f5f5f5 与同行轮次标签一致, 字色保留 Colors.INFO(#096dd9 on #f5f5f5 ≈ 4.9:1, 达 WCAG AA) — 小欧-2026-10-03
// 编辑历史: 2026-10-05 小欧 - 左列 task 卡 response 接 Markdown: 传 renderExpanded 使展开态排版、折叠态维持原首2行纯文本;
//   恒 markdown=true 不受设置开关控制(仅受折叠开关控制) — 小欧-2026-10-05
// 编辑历史: 2026-10-08 小欧 - 追加注入消息逐条独立成块(原先 marginTop:4 共用一条竖线, 多条连成一串无间隔)
// 编辑历史: 2026-10-21 小杨 - 新增推荐行与引用台账行（可选，缺省不渲染）：
//   推荐=本轮被工具动过 ≥2 次且可预览的文件；台账=本任务引用过的文件（现场重读恢复，不存旧快照）；
//   键口径改与后端一致（绝对→相对 root、反斜杠→正斜杠），否则推荐恒空 — 小杨-2026-10-21
// 编辑历史: 2026-10-21 小杨 - 推荐只收文本预览；台账按 taskId 精确取，删最新批次兜底 — 小杨-2026-10-21
// 编辑历史: 2026-10-23 小欧 - 推荐行 Tag 改显 r.path 全路径：与足迹面板口径一致（同源三处：树●/足迹/推荐），
//   推荐行无目录上下文，同名不同目录文件靠文件名无法区分 — 小欧-2026-10-23
// 编辑历史: 2026-10-28 小欧 - 插话并入滚动定位+自动展开(方案A, 北京老陈反馈): 监听 task_merged 事件, 插话并入现有任务时
//   滚动到该任务并自动展开其追加块(上方滚动守卫只认 latestTaskId 变化, 并入不产生新任务→条纹丝不动), 见 L231 区块 — 小欧-2026-10-28
// 编辑历史: 2026-10-30 小欧 - 引用提示统一走 quoteWithToast(成功/超限/读取失败三分支唯一实现); 成功不弹
//   (随后直接导航, 原页 toast 无意义), 失败由它统一点名(含"超上限", 原实现漏该分支误报"读取失败") — 小欧-2026-10-30
// 编辑历史: 2026-11-13 商量 - 新增"续跑"徽标: creation_source=system_resume 时显示, 区分后台命令完成唤醒的任务 — 商量-2026-11-13
// 编辑历史: 2026-11-13 商量 - 用户问题区域按系统通知样式渲染: 续跑任务的消息体是系统通知
//   (msg_kind=system_notice ⇔ creation_source=system_resume, 两维标记),
//   灰字+SUCCESS左条+浅底, 不再按用户问题强样式渲染
// 编辑历史: 2026-11-13 商量 - 字号/字重归位令牌: 12→FontSize.SECONDARY(4处)/11→SMALL(2处)/10→CAPTION(4处)
//   /fontWeight 500→MEDIUM/400→REGULAR, 遵守 2026-11-12 stepStyles 7档阶梯"唯一真源"铁律(11-12整改只收了13px, 本文件漏网);
//   fontSize:6 状态点●为装饰图形非文字, 不入阶梯(加注释说明); lineHeight 无令牌暂留数字 — 商量-2026-11-13
// 编辑历史: 2026-11-14 商量 - merged_inputs 契约升级 {content,msg_kind}[] 后同槽异标(「系统通知」/「插话」),
//   头/尾加「系统通知 · 续跑」小标; 系统通知判定收敛为单一谓词; 更正旧「msg_kind=system_notice ⇔
//   creation_source=system_resume」等价误述(任务来源仍 user 但消息 msg_kind=system_notice) — 商量-2026-11-14
// 编辑历史: 2026-11-14 商量 - 按用户反馈移除追加块内「系统通知」/「插话」两个冗余小标:
//   系统通知正文自带「[系统通知]」前缀(消息头)可区分, 追加块上下文已明示为追加输入, 双标签意义不大;
//   谓词 isNoticeInput/isInjectionInput 失去唯一消费点一并删除, 续跑徽标「系统通知 · 续跑」保留 — 商量-2026-11-14
// 编辑历史: 2026-11-16 小欧 - [45]会话列表性能优化: 抽离 TaskItem 组件包 React.memo(字段级比较),
//   TaskListPanel 外层包 memo, ledger/推荐行预计算到 useMemo(消除 render 期间每任务同步调 store),
//   SSE 流式/父级高频重渲时既得任务不再全量重建 DOM。行为零逻辑变更 — 小欧-2026-11-16
// 编辑历史: 2026-11-17 小欧 - [46b] P2b 任务列表数据契约对齐: 台账行双源(store 实时优先, 冷启动取接口 ref_ledger 快照兜底, 根治冷启动台账缺失);
//   roundHits 双源(steps 实时优先, steps 无产出时取接口 tool_paths 快照兜底, 冷启动推荐行恢复, steps 有产出时避免同路径双源重复计数) — 小欧-2026-11-17
// 编辑历史: 2026-11-18 小欧 - [46b] 会审整改: 推荐行快照源只取最新任务的 tool_paths(原全会话累加,
//   旧任务触达凑数), 并去掉"实时源为空才用快照"的全有全无闸门, 改按路径各判 — 小欧-2026-11-18
// 编辑历史: 2026-11-18 opencode - 台账行响应式: 插话追加引用不产生新任务、不触发 tasks 刷新,
//   原 memo 依赖 [sessionId, tasks] 不重算 → 插话引用/图片行不出现; 改订阅快照台账(引用变化才重渲) — opencode-2026-11-18
// 编辑历史: 2026-11-18 opencode - 台账行三处真问题: ①与 ref_ledger 快照按 path+lineRange 合并
//   (原 live 非空即全量覆盖, 丢快照里 live 未复现的条目); ②url 条目点击开外链(原来当文件重读必失败) — opencode-2026-11-18
// 编辑历史: 2026-11-20 小欧 - 修"复制失败" bug: 原 handleCopy 用裸 navigator.clipboard.writeText, 嵌入式浏览器/权限被拒/文档未聚焦时
//   抛 NotAllowedError 必报"复制失败"(实测复现 Document is not focused); 改走统一 copyTextToClipboard(内建 execCommand 降级) — 小欧-2026-11-20
// 编辑历史: 2026-11-21 小欧 - 后台完成通知正文前缀由「[系统通知]」改为「[后台通知]」: 上文 11-14 条目所称
//   "正文自带前缀可区分"改以新前缀为准; 消息种类判定仍走 msg_kind=system_notice, 本文件零逻辑变更 — 小欧-2026-11-21

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
import { Empty, Skeleton, Tag, Typography } from 'antd';
import {
  CopyOutlined,
  CaretDownOutlined,
  FileOutlined,
  PaperClipOutlined,
} from '@ant-design/icons';
import { useOptionalNavigate } from '@/hooks/useOptionalNavigate';
import { useProjectRoot } from '@/hooks/useProjectRoot';
// 2026-10-22 小欧 - 路径判据收敛到 utils/projectPath（唯一真源）
import { toRelativePath } from '@/utils/projectPath';

import type { SessionTaskItem } from '../../../../services/api/task.api';
import type { ExecutionStep } from '@/types/execution';
import { Colors, FontSize, FontWeight } from '@/utils/stepStyles';
import { formatTime } from '@/utils/time';
// 统一剪贴板工具(含 execCommand 降级) — 小欧-2026-11-20
import { copyTextToClipboard } from '@/utils/clipboard';
import { showSuccess, handleError } from '@/services/error/handler';
// 2026-10-21 小杨 - 推荐行 + 引用台账行
import { chatStreamStore } from '../../streams/chatStreamStore';
// 2026-10-22 小欧 - 引用入口统一（选区走 quoteSelection，与文件页口径一致）
import { quoteWithToast } from '@/features/refs/quoteToast';
import { labelOf, refKeyOf } from '@/features/refs/identity';
import type { SentRefLedgerEntry } from '../../streams/chatStreamTypes'; // 台账条目类型(与 store 备份同源, 类型源已随 notice 改造更名 chatStreamTypes) — opencode-2026-11-19
import { useRecentFiles } from '@/hooks/useRecentFiles';
import { chatTokens } from '@/theme/tokens';
import { CollapsibleText } from '../pipeline/CollapsibleText';
// 2026-10-05 小欧 北京老陈指令(左列 task 卡 response 接 Markdown): 展开态渲染器, 恒开不受设置开关控制
//   (用户明示"task 下的 mark 显示不受设置的开关的控制") —— 直接传 markdown={true} 绕过 MD_IMPL 之外的开关
import { MarkdownSlot } from '@/components/markdown/MarkdownSlot';

// 2026-09-30 小欧 - 左列任务状态标签——按后端 status 枚举正确显示。
//   DB 合法值: completing→completed/executing/paused/failed/cancelled（db_initializer 默认 'executing'）
const TASK_STATUS_LABEL: Record<string, { name: string; color: string }> = {
  completed: { name: '已完成', color: Colors.TEXT.TERTIARY },
  executing: { name: '执行中', color: Colors.PRIMARY },
  paused: { name: '已暂停', color: Colors.WARNING },
  failed: { name: '失败', color: '#ff4d4f' },
  cancelled: { name: '已取消', color: Colors.TEXT.TERTIARY },
};

// 2026-11-14 商量: 系统通知判定单一谓词 — 全文件收敛于此, 禁止散写判定
const isSystemResumeTask = (t: SessionTaskItem) =>
  t.creation_source === 'system_resume'; // B1b 主判定

interface TaskListPanelProps {
  tasks: SessionTaskItem[];
  activeTaskId: string | null;
  onSelect: (taskId: string) => void;
  loading?: boolean;
  latestTaskId?: string | null;
  latestTaskRef?: React.MutableRefObject<HTMLDivElement | null>;
  rightOpen?: boolean;
  // 2026-10-21 小杨 - 新增两项（可选，缺省即不渲染这两行）
  /** 会话 id（取 recent-files 与引用台账） */
  sessionId?: string | null;
  /** 本轮 steps（计算「被工具动过 ≥2 次」） */
  steps?: ExecutionStep[];
}

// ──────────────────────────────────────────────────────────────
// TaskItem — 单任务项（memo 化，仅在自身数据变化时重渲）
// 2026-11-16 小欧 - [45] P0: 从 TaskListPanel 的 tasks.map 内抽离, 包 React.memo +
//   字段级自定义比较; SSE 流式/父级高频重渲时既得任务不再全量重建 DOM — 小欧-2026-11-16
// ──────────────────────────────────────────────────────────────
interface TaskItemProps {
  task: SessionTaskItem;
  active: boolean;
  isLatest: boolean;
  rightOpen: boolean;
  groupNo: number | undefined;
  expanded: boolean;
  onToggleExpanded: (taskId: string) => void;
  onSelect: (taskId: string) => void;
  onCopy: (text: string, type: '问题' | '回复') => void;
  anchorRef?: React.MutableRefObject<HTMLDivElement | null>;
  // 推荐行与台账行: 由外层预计算后传入(避免每个 TaskItem 都调 hook/store)
  recommendTags?: React.ReactNode;
  ledgerTags?: React.ReactNode;
}

const TaskItem: React.FC<TaskItemProps> = ({
  task: t,
  active,
  isLatest,
  rightOpen,
  groupNo,
  expanded,
  onToggleExpanded,
  onSelect,
  onCopy,
  anchorRef,
  recommendTags,
  ledgerTags,
}) => {
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
        padding: '8px 10px', // 2026-10-27 小欧 v1.1: 10px/12px→8px/10px，更紧凑
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
          gap: 6, // 2026-10-27 小欧 v1.1: 8→6，更紧凑
          marginBottom: 4, // 2026-10-27 小欧 v1.1: 6→4，更紧凑
          flexWrap: 'wrap', // 窄屏时换行
        }}
      >
        {/* 时间标签 */}
        <span style={{ fontSize: FontSize.SMALL, color: Colors.TEXT.TERTIARY }}>
          {formatTime(t.created_at)}
        </span>

        {/* 模型标签: 右侧折叠时显示provider前缀, 展开时只显示model */}
        {t.model && (
          <span
            style={{
              fontSize: FontSize.CAPTION,
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
        {/* 2026-09-30 小欧 - 按 TASK_STATUS_LABEL 映射，未知状态兜底回退展示原始值 */}
        {(() => {
          const st = TASK_STATUS_LABEL[t.status];
          return (
            <span
              style={{
                fontSize: FontSize.SMALL,
                color: st ? st.color : Colors.TEXT.TERTIARY,
                display: 'flex',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <span
                style={{
                  fontSize: 6 /* 状态点装饰图形, 非文字, 不入字号阶梯 */,
                }}
              >
                ●
              </span>
              {st ? st.name : t.status}
            </span>
          );
        })()}

        {/* 上下文链接链号徽标(仅链长>1时显示, 独立任务不成链不贴标) */}
        {(() => {
          if (groupNo === undefined) return null; // 独立任务不成链, 不贴标
          return (
            <span
              style={{
                fontSize: FontSize.CAPTION,
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

        {/* 续跑徽标(后台命令完成自动唤醒的任务) — 商量-2026-11-13 */}
        {isSystemResumeTask(t) && (
          <span
            style={{
              fontSize: FontSize.CAPTION,
              color: Colors.SUCCESS,
              backgroundColor: '#f5f5f5',
              padding: '1px 5px',
              borderRadius: 3,
            }}
          >
            续跑
          </span>
        )}

        {/* 轮次标签（显示LLM调用轮次） */}
        {t.llm_call_count > 0 && (
          <span
            style={{
              fontSize: FontSize.CAPTION,
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
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.STRONG, // 强文本，问题突出
            fontWeight: FontWeight.MEDIUM,
            lineHeight: 1.5,
            wordBreak: 'break-word',
            // 2026-11-14 商量: 续跑任务(creation_source=system_resume)按系统通知样式渲染;
            //   注意 system_notice 与 system_resume 非等价 — 任务来源仍 user 但消息 msg_kind=system_notice
            ...(isSystemResumeTask(t)
              ? {
                  color: Colors.TEXT.SECONDARY,
                  fontWeight: FontWeight.REGULAR,
                  padding: '4px 8px',
                  backgroundColor: '#fafafa',
                  borderLeft: `2px solid ${Colors.SUCCESS}`,
                  borderRadius: '0 3px 3px 0',
                }
              : {}),
          }}
        >
          {isSystemResumeTask(t) && (
            <span
              style={{
                fontSize: FontSize.CAPTION,
                color: Colors.TEXT.TERTIARY,
                display: 'block',
                marginBottom: 2,
              }}
            >
              系统通知 · 续跑
            </span>
          )}
          <CollapsibleText text={t.user_input} />
          {/* 2026-09-09 小欧 复制按钮: 用户输入右上角, hover时显示 */}
          <button
            className="task-copy-btn"
            onClick={(e) => {
              e.stopPropagation();
              onCopy(t.user_input, '问题');
            }}
            aria-label="复制问题"
          >
            <CopyOutlined />
          </button>
          {isSystemResumeTask(t) && (
            <span
              style={{
                fontSize: FontSize.CAPTION,
                color: Colors.TEXT.TERTIARY,
                display: 'block',
              }}
            >
              — 系统通知 · 续跑 —
            </span>
          )}
        </div>
      )}

      {/* 2026-09-28 小欧: 追加注入消息 — 语义属输入侧, 故置于问题区与回复区之间;
          默认收起(不撑条目高度), 展开看全文。 */}
      {t.merged_inputs && t.merged_inputs.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleExpanded(t.task_id);
            }}
            aria-expanded={expanded}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.TERTIARY,
            }}
          >
            <CaretDownOutlined rotate={expanded ? 180 : 0} /> ↳ 追加{' '}
            {t.merged_inputs.length} 条
          </button>
          {expanded &&
            t.merged_inputs.map((m, i) => (
              <div
                key={i}
                style={{
                  // 2026-10-08 小欧 - 逐条独立成块, 多条不连成串
                  marginTop: 6,
                  padding: '4px 8px',
                  // 2026-11-14 商量 - 追加块正文定阶 SECONDARY(12): 不设则继承默认14(PRIMARY)偏大,
                  //   且与「↳追加N条」按钮、上方用户问题区(SECONDARY)一致, 输入侧次要与密集区协调
                  fontSize: FontSize.SECONDARY,
                  backgroundColor: '#fafafa',
                  borderLeft: '2px solid #d9d9d9',
                  borderRadius: '0 3px 3px 0',
                }}
              >
                {/* 2026-11-14 商量 - 追加块内不再标「系统通知」/「插话」小标: 系统通知正文自带
                    「[系统通知]」前缀可区分, 追加块上下文已明示为追加输入, 双标签冗余(用户反馈) */}
                <CollapsibleText text={m.content} />
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
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.PRIMARY, // 主文本，比问题稍浅
              lineHeight: 1.6, // 回复正文行高略大，阅读舒适
              wordBreak: 'break-word',
            }}
          >
            {/* 2026-10-05 小欧 北京老陈指令: response 展开态按 Markdown 渲染, 折叠态维持原首2行纯文本。
                renderExpanded 只在"已展开"时被 CollapsibleText 调用(不传则原样显示全文),
                故折叠表现与改动前逐字一致; markdown 恒 true —— 本处不受「思考排版」设置开关控制。 */}
            <CollapsibleText
              text={t.response}
              renderExpanded={(expandedText) => (
                <MarkdownSlot text={expandedText} markdown scene="task" />
              )}
            />
          </div>
          {/* 2026-09-09 小欧 复制按钮: 回复区域右上角, hover时显示 */}
          <button
            className="task-copy-btn"
            onClick={(e) => {
              e.stopPropagation();
              onCopy(t.response!, '回复');
            }}
            aria-label="复制回复"
          >
            <CopyOutlined />
          </button>
        </div>
      )}

      {/* 2026-10-21 小杨 - 推荐行 + 引用台账行（由外层预计算传入） */}
      {recommendTags}
      {ledgerTags}
    </div>
  );
};

// 2026-11-16 小欧 - 自定义比较: 覆盖全部展示字段(优先级优先于引用比较) + 交互态;
//   任一展示字段变化才重渲, 不被父组件因其它状态(SSE 流式/右侧/工具执行)变化波及 — 小欧-2026-11-16
// 2026-11-17 小欧 - 补齐回调与 ref 比较(共 21 项): 四项均为恒定引用, 比较零成本,
//   但回调一旦变为带依赖的 useCallback 就自动重渲, 不依赖外部契约才能保证不陈旧 — 小欧-2026-11-17
const TaskItemMemo = React.memo(TaskItem, (prev, next) => {
  const pt = prev.task;
  const nt = next.task;
  if (pt.task_id !== nt.task_id) return false;
  if (pt.response !== nt.response) return false;
  if (pt.status !== nt.status) return false;
  if (pt.user_input !== nt.user_input) return false;
  if (pt.llm_call_count !== nt.llm_call_count) return false;
  if (pt.merged_inputs !== nt.merged_inputs) return false;
  if (pt.created_at !== nt.created_at) return false;
  if (pt.model !== nt.model) return false;
  if (pt.provider !== nt.provider) return false;
  if (pt.creation_source !== nt.creation_source) return false;
  if (prev.active !== next.active) return false;
  if (prev.isLatest !== next.isLatest) return false;
  if (prev.rightOpen !== next.rightOpen) return false;
  if (prev.groupNo !== next.groupNo) return false;
  if (prev.expanded !== next.expanded) return false;
  if (prev.recommendTags !== next.recommendTags) return false;
  if (prev.ledgerTags !== next.ledgerTags) return false;
  if (prev.onToggleExpanded !== next.onToggleExpanded) return false;
  if (prev.onSelect !== next.onSelect) return false;
  if (prev.onCopy !== next.onCopy) return false;
  if (prev.anchorRef !== next.anchorRef) return false;
  return true;
});

const TaskListPanel: React.FC<TaskListPanelProps> = ({
  tasks,
  activeTaskId,
  onSelect,
  loading = false,
  latestTaskId = null,
  latestTaskRef,
  rightOpen = true,
  // 2026-10-21 小杨 - 推荐行 + 引用台账行
  sessionId = null,
  steps = [],
}) => {
  // 2026-10-21 小杨 - 跳转输入框
  //   ⚠ 用 useOptionalNavigate：TaskListPanel 的既有单测**直接渲染本组件（无 Router 上下文）**，
  //   直接用 useNavigate 会抛 "useNavigate() may be used only in the context of a <Router>" → 整块崩。
  const navigate = useOptionalNavigate();
  // 2026-10-21 小杨 - 数据源与规则
  //   ① roundHits = 本轮 steps 里工具动过的 path 计数（tools[].params.path）
  //   ② 推荐 = 被动过 ≥2 次 且 preview 可预览 的文件，取最近 3 条（与足迹面板同一数据源，走共享 hook）
  const { files: recentFiles } = useRecentFiles(sessionId);
  // 2026-10-21 小杨 - 修复（高危）：**键口径必须与后端一致**
  //   roundHits 原用 tool.params.path 原样值（Windows 上多为 "F:\proj\a.py" 或 "backend\a.py"），
  //   而 recentFiles[].path 是后端归一后的**相对 posix 路径** → 键对不上 → roundHits 恒 miss
  //   → recommend 恒为空 → **推荐行永远不渲染**（功能未交付）。
  //   现用与后端同口径的归一（绝对→相对 root、反斜杠→正斜杠）后再计数。
  const projectRoot = useProjectRoot();
  // [46b] P2b 小欧 2026-11-17: 双源——①实时源: 本轮 steps(store 内存态, 任务运行中即时,
  //   与原口径一致: 被工具动过次数); ②快照源: 最新任务的 tool_paths(冷启动 store 无 steps 时
  //   接口兜底, 后端收尾已同口径派生归一)。
  // 2026-11-18 小欧 会审整改: ①快照源只取最新任务 —— 原遍历全会话所有任务的 tool_paths 累加,
  //   同一路径在几个旧任务出现过就凑够 2 次进推荐, 与"本轮触达"语义不符(推荐行本来只对最新任务显示);
  //   ②去掉 m.size===0 的全有全无闸门 —— 只要有一条实时路径, 快照源就整片失效, 冷启动任务
  //   永远补不齐; 现按路径各判: 实时已知次数以次数为准, 实时无此路径而快照有时按"本轮触达"计入。
  const roundHits = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const s of steps) {
      if (s.type !== 'action') continue;
      for (const tool of s.tools ?? []) {
        const raw = tool.params?.path;
        if (typeof raw !== 'string' || !raw) continue;
        const p = toRelativePath(raw, projectRoot);
        if (!p) continue;
        m.set(p, (m.get(p) ?? 0) + 1);
      }
    }
    return m;
  }, [steps, projectRoot]);
  /** 最新任务已触达路径快照(无次数信息): 冷启动/切换后 steps 为空时的推荐依据 */
  const latestTouchedPaths = React.useMemo(() => {
    const t = latestTaskId
      ? tasks.find((x) => x.task_id === latestTaskId)
      : undefined;
    return new Set<string>(t?.tool_paths ?? []);
  }, [tasks, latestTaskId]);
  const recommend = React.useMemo(
    () =>
      recentFiles
        .filter((x) => {
          if (x.preview !== 'text') return false;
          const hits = roundHits.get(x.path) ?? 0;
          // 两源同出 steps, 不叠加(相加等于重复计数): 实时已知次数以次数为准;
          // 实时未登记而快照有 → 本轮只触达过、次数不可知, 按命中计入
          return hits >= 2 || (hits === 0 && latestTouchedPaths.has(x.path));
        })
        .slice(0, 3),
    [recentFiles, roundHits, latestTouchedPaths]
  );
  /** 台账恢复：现场重读盘面 → push 引用（恢复的是引用意图，不是旧快照） */
  const quoteAfterReread = React.useCallback(
    async (path: string, lineRange?: { start: number; end: number }) => {
      // 2026-10-22 小欧 - 引用入口统一；恢复的是引用意图，不是旧快照 → 现场重读
      // 2026-10-30 小欧: 提示统一走 quoteWithToast; 成功不弹(随后直接导航, 原页 toast 无意义),
      //   失败由它统一点名(含"超上限", 原实现漏该分支误报"读取失败")
      const r = await quoteWithToast(path, lineRange, {
        label: labelOf(path),
        successText: '',
      });
      if (r.ok) navigate(`/?session_id=${encodeURIComponent(sessionId ?? '')}`);
    },
    [navigate, sessionId]
  );
  /** 推荐行只对"最新 1 条任务"显示（下一任务开始即移除上一条的推荐行） */
  const isLatestTaskId = (taskId: string) =>
    !latestTaskId || taskId === latestTaskId;

  // 2026-09-09 小欧 复制按钮: 点击复制文本到剪贴板, 显示成功提示
  // 2026-11-20 小欧 - 改走统一剪贴板工具(内建 execCommand 降级): 原裸 writeText 在权限被拒/文档未聚焦时抛
  //   NotAllowedError 报"复制失败", 嵌入式浏览器实测必现; 两法都失败才提示失败 — 小欧-2026-11-20
  const handleCopy = useCallback(
    async (text: string, type: '问题' | '回复') => {
      const { ok } = await copyTextToClipboard(text);
      if (ok) {
        showSuccess(`${type}已复制`);
      } else {
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
  // 2026-11-16 小欧 - [45] 包 useCallback 稳定化, 供 TaskItem 复用不触发额外重渲 — 小欧-2026-11-16
  const toggleExpanded = useCallback((taskId: string) => {
    setExpandedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }, []);

  // 2026-09-01 小欧 方案C: 新任务诞生(latestTaskId变化)且不在可视区时, 滚动带进视野; 可视区内不动不打扰
  const prevLatestIdRef = useRef<string | null>(null);
  const rafIdRef = useRef<number | null>(null);
  useEffect(() => {
    if (!latestTaskId) return;
    if (prevLatestIdRef.current === latestTaskId) return; // 非新任务, 不滚动
    prevLatestIdRef.current = latestTaskId;
    // 2026-09-02 小欧 task005修复(北京老陈定案): rAF 确保React提交DOM(ref挂载)后滚动, 消 latestTaskId 与 render 同批处理时 ref 未更新竞态 — 小欧 2026-09-02
    rafIdRef.current = requestAnimationFrame(() => {
      // scrollIntoView 沿祖先滚动链自动定位到最近滚动容器(SessionLayout左列overflowY:auto), 无需改布局骨架
      anchorRef.current?.scrollIntoView({ block: 'nearest' });
    });
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, [latestTaskId, anchorRef]);

  // 2026-10-28 小欧 - 插话并入滚动定位+自动展开(方案A, 北京老陈反馈):
  //   插话并入现有任务不产生新任务 → latestTaskId 不变 → 上方滚动守卫(非新任务不滚动)拦截 → 滚动条纹丝不动。
  //   改监听 useChatCallbacks.onMerged 派发的 task_merged 事件(精确信号, 唯一在插话并入瞬间触发,
  //   非历史加载/会话切换), 事件 detail.taskId = 被并入的目标任务; 触发后滚动到该任务并自动展开其追加块,
  //   使用户即时看到插话内容(默认收起 → 展开并入的追加输入)。复用 rAF + scrollIntoView(nearest) 机制。
  useEffect(() => {
    const onTaskMerged = (e: Event) => {
      const taskId = (e as CustomEvent<{ taskId: string | null }>).detail
        ?.taskId;
      const targetId = taskId ?? latestTaskId;
      if (!targetId) return;
      // 自动展开该任务追加块(插话内容即时可见)
      setExpandedTasks((prev) => {
        if (prev.has(targetId)) return prev;
        const next = new Set(prev);
        next.add(targetId);
        return next;
      });
      // 滚动到最新任务锚点(anchorRef 挂在 isLatest 任务项); nearest 已在可视区则不动, 不打扰上翻
      requestAnimationFrame(() => {
        anchorRef.current?.scrollIntoView({ block: 'nearest' });
      });
    };
    window.addEventListener('task_merged', onTaskMerged);
    return () => window.removeEventListener('task_merged', onTaskMerged);
  }, [latestTaskId, anchorRef]);

  // 2026-11-18 opencode - 台账响应式依赖: 插话追加引用不产生新任务, 也不会触发 tasks 刷新,
  //   原 memo 依赖 [sessionId, tasks] 不重算。订阅会话快照取台账数组(引用未变时引用相同 → 不重渲)。
  const liveLedger = React.useSyncExternalStore(
    React.useCallback(
      (cb: () => void) =>
        sessionId
          ? chatStreamStore.subscribe(sessionId, cb)
          : () => {
              /* 无会话不订阅 */
            },
      [sessionId]
    ),
    () =>
      sessionId ? chatStreamStore.getSnapshot(sessionId).sentRefLedger : null
  );

  // [45] P2 台账预计算(消除 render 期间每任务同步调 store): key=taskId, value=渲染节点;
  //   tasks 未变化时 useMemo 缓存命中, SSE 流式期间不再每 tick 重算 — 小欧-2026-11-16
  const ledgerByTask = React.useMemo(() => {
    if (!sessionId || !liveLedger) return new Map<string, React.ReactNode>();
    const m = new Map<string, React.ReactNode>();
    for (const t of tasks) {
      // [46b] P2b 小欧 2026-11-17: 台账双源——store 实时态优先(运行中即时),
      //   store 为空(冷启动/刷新)时取任务接口快照(46b 落库)兜底, 根治冷启动台账缺失
      // 2026-11-18 opencode - 双源合并(原"live 非空即全量覆盖"): 两者口径不同, 覆盖会丢
      //   快照里 live 未复现的条目(跨轮/跨端); 同 path+lineRange 以 live 为准, 顺序 live 在前。
      const live = liveLedger.filter((e) => e.taskId === t.task_id);
      const entries: SentRefLedgerEntry[] = [];
      const seen = new Set<string>();
      for (const e of [...live, ...(t.ref_ledger ?? [])]) {
        const k = refKeyOf(e);
        if (seen.has(k)) continue;
        seen.add(k);
        entries.push(e as SentRefLedgerEntry);
      }
      if (entries.length === 0) continue;
      m.set(
        t.task_id,
        <div style={{ fontSize: chatTokens.fontSM, marginTop: 2 }}>
          ↩ 本轮引用：
          {entries.map((e) => (
            <Tag
              key={e.path + e.ts}
              style={{ cursor: 'pointer' }}
              onClick={(ev) => {
                ev.stopPropagation();
                // 2026-11-18 opencode - URL 条目不是文件: 当文件重读必失败, 直接开外链
                //   (与 RefChip 的 URL 点击同口径)
                if (e.kind === 'url') {
                  window.open(e.path, '_blank', 'noopener');
                  return;
                }
                void quoteAfterReread(e.path, e.lineRange);
              }}
            >
              <FileOutlined style={{ marginRight: 4 }} /> {e.label}
              {e.lineRange ? ` L${e.lineRange.start}-${e.lineRange.end}` : ''}
            </Tag>
          ))}
        </div>
      );
    }
    return m;
  }, [sessionId, tasks, liveLedger, quoteAfterReread]);

  // [45] 推荐行预计算(只对最新任务): 稳定引用供 TaskItemMemo 比较 — 小欧-2026-11-16
  const recommendNode = React.useMemo(() => {
    if (!sessionId || recommend.length === 0 || !latestTaskId) return null;
    return (
      <div
        style={{
          color: Colors.TEXT.SECONDARY,
          fontSize: chatTokens.fontSM,
          marginTop: 4,
        }}
      >
        <PaperClipOutlined style={{ marginRight: 4 }} />{' '}
        本轮涉及的文件，点击作为引用继续追问：
        {recommend.map((r) => (
          <Tag
            key={r.path}
            style={{ cursor: 'pointer' }}
            onClick={(e) => {
              e.stopPropagation();
              void quoteAfterReread(r.path);
            }}
          >
            {r.path}
          </Tag>
        ))}
      </div>
    );
  }, [sessionId, recommend, latestTaskId, quoteAfterReread]);

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
          <Typography.Text
            type="secondary"
            style={{ fontSize: FontSize.SECONDARY }}
          >
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

  // [45] P0 渲染: map 内只调 TaskItemMemo, 不再内联全部 JSX — 小欧-2026-11-16
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2, // 2026-09-09 小欧 优化: 项间距4→2px，紧凑但不拥挤
        padding: '2px 0', // 2026-10-27 小欧 v1.1: 4px→2px，更紧凑
      }}
    >
      {tasks.map((t) => {
        const active = t.task_id === activeTaskId; // 2026-09-01 小欧 方案C: 最新任务项挂锚点ref(供滚动定位)
        const isLatest = t.task_id === latestTaskId;
        const root = t.context_root_task_id ?? t.task_id;
        const groupNo = groupNoOf.get(root);
        return (
          <TaskItemMemo
            key={t.task_id}
            task={t}
            active={active}
            isLatest={isLatest}
            rightOpen={rightOpen}
            groupNo={groupNo}
            expanded={expandedTasks.has(t.task_id)}
            onToggleExpanded={toggleExpanded}
            onSelect={onSelect}
            onCopy={handleCopy}
            anchorRef={isLatest ? anchorRef : undefined}
            recommendTags={
              isLatestTaskId(t.task_id) ? recommendNode : undefined
            }
            ledgerTags={ledgerByTask.get(t.task_id)}
          />
        );
      })}
    </div>
  );
};

// 2026-11-16 小欧 - [45] P0: 外层也包 memo, props 不变化时不重渲 — 小欧-2026-11-16
const TaskListPanelMemo = React.memo(TaskListPanel);

export { TaskListPanelMemo as TaskListPanel };
