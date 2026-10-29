// 编辑历史: 2026-08-26 小欧 - 修复A3(接受detail派生历史任务动态信息/7.6+4.5.1)+B2(执行中实时计时/7.6②)+C2(上下文截断文字/7.9)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.4 useRef仅首次锚定start, 去frames.startTimestamp防抖动, 切换复位
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框/边距: 去整框留淡底(border→none,background#fafafa,radius6,padding8px); 内层过程区加滚动细线borderTop#f5f5f5+scrollbarWidth; 外层gap2→8主节奏
// 编辑历史: 2026-08-28 小欧 - ①C/c1: 去胶囊改透明+borderTop#f0f0f0, gap12→8, 数值加粗#595959 500, Tag→Text轻量化
// 编辑历史: 2026-08-30 小欧 - 13.14 8处Typography.Text→span+双组token本轮/任务累计(P/C/T后端直发) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 13.14 TrustPanel移至TaskInfoBar第一行尾部集成（第一行尾巴） - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修复×不显眼: DeleteOutlined→文本×、色#999→#595959、字号12→14加粗 - 小欧-2026-08-30
// 编辑历史: 2026-09-01 小欧 - TaskInfoBar一线三组最佳重排: 左主节奏(状态/耗时/步轮·重试) 中Token合一T(P/C) 右信任/收起 gap12/8 减半宽 - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 去尾部"收起/展开"文字按钮(北京老陈驱动: 冒泡至整行onClick致setCollapsed两次切换抵消=点了没反应; 且与整行点击重复): 面板折叠仅保留整行点击(:139), 信任独立三角stopPropagation - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 设计文档落码(工具结果显示与taskinfo显示分析与设计-小欧-2026-09-01.md): Props六参补
//   liveErrorText(位4 error 实时源) + 组件解构同步 + useTaskInfo 五参调用 + 第一行去掉旧"· 重试N"累计(:163-168,
//   来源stats.retry_count, 无内容看不懂——北京老陈质疑)与截断独立段(:174-178, 并入位4) + 位4渲染段(🔁/🛑/⚠
//   图标映射, 置于 步骤/轮次 之后、·疑似卡死 之前; 新覆盖旧无优先级) - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: TB-02 revokeTrust加try/catch防unhandledrejection上浮 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 会话信任功能修复 v1.5⑤⑥(北京老陈定案"tool+path才是准确对象", 后端定案): TrustedTool带path升级一行一变——
//   trustTools行键改 `${toolName}:${path}`、显示 {toolName} › {path ?? '任意'}(空=工具级通配)、revokeTrust签名带path精确撤销、Tooltip文案改"会话级 tool+path 免审白名单"(目标路径及其子目录免弹框) — 小欧-2026-09-02
// 编辑历史: 2026-09-06 小欧 - 秒表与徽标解耦(B1实证修复, 见 doc-9月优化/错误弹窗与TaskInfoBar计时器干扰问题-验证分析与解决方案): 秒表interval运行条件去badge依赖改为
//   receiving&&!detail(实时流在就走表, 错误信号不再清零停表/业务恢复不再回跳); shownElapsed实时态一律liveElapsed, 非实时/历史回退elapsedSec;
//   else分支原样保留(归零+startRef复位, 保终态duration显示与新任务归零) — 小欧-2026-09-06
// 编辑历史: 2026-09-08 小欧 - 六章6.3.4(北京老陈定案): prop 第7位 liveErrorText✗ string 改 liveError?: LiveError|null
//   (数据源对象形态, useChatPanels 透传) + 位4 图标分层——执行级 error 用 CloseCircleFilled(红圆底白×,
//   替原🛑, ·/着色 Colors.ERROR) + 请求级 error 用 ⛔(后端业务错误如"消息列表为空"); retrying🔁/truncated⚠ 不变 — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - v4.1+v4.2: 探针删除/折叠态机删除(信息带恒定1行)/图标全antd SVG/对比度分级/ Token两段式MetricItem/上下文4态/换行/分隔线归属input/令牌化/事件时间轴/徽标迁infoMaps/耗时等宽/G6上下文+G8事件双浮层经FloatingEntry复用(G8双写修复) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - v4.4 修复: 断点矩阵落地(useInfoBreakpoint 1280/960/768)——G2/G3 xsmall 合并(G3 含耗时段)、
//   G3 mid/narrow 收窄(仅数字+Tooltip 展开全文本)、G4 narrow/xsmall 省略(maxWidth200+ellipsis+Tooltip 全文)、G5 累计段收窄(明细进 MetricItem Tooltip 轻浮层)、
//   G7 narrow/xsmall 仅计数(TrustPanel compact)、G6/G8 恒完整(FloatingEntry 基础行数字+▸+明细进浮层① 已满足矩阵) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-B2: 秒表interval的frames.startTimestamp有意不入依赖数组(定时器防每帧重置去抖, 见:122注释),
//   加eslint-disable+理由注释 — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 位4错误信息字符级截断(北京老陈令): renderLiveMeta 文本超 LIVE_META_TEXT_MAX(20)截断加…,
//   宽/中屏超长时 Tooltip 全文(窄屏沿用 G4 EllipsisTip maxWidth200, 不叠双层Tooltip), 杜绝超长 error_message 撑爆第一行;
//   G6上下文卡片标签"上下文详情"→"历史上下文"(ariaLabel+卡片标题同步, 北京老陈令), 摘要移除 slice(0,60) 截断改完整显示 — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 北京老陈纠正定案: 第一行 G6 上下文标签"上下文"→"历史上下文"(隐藏于 FloatingEntry 的 MetricItem label),
//   MetricItem label 恒直出 + 浮层摘要全文显示(非截断), 两块均与"上下文详情→历史上下文"命名一致 — 小欧-2026-09-09
// 编辑历史: 2026-09-14 小欧 改动点①(方案A, 北京老陈批准): useTaskInfo 改四参签名 (steps, frames, detail, liveError)
//   ——receiving 不再透传徽标派生(断连窗由 startinfo 门承接), 组件自身 receiving prop 保留(秒表 interval 启停, D3 契约) — 小欧-2026-09-14
// 编辑历史: 2026-09-14 小欧 删第二个变量(北京老陈令): receiving prop 整体删除——秒表启停改由 frames 权威信号驱动:
//   走廊判定=startInfo非空(已开始)&&finalStats空(未终态落库); 实时走廊走表(语义等价旧receiving), 断连窗/错误中间态继续走表(旧
//   receiving=false缺陷窗口=进化, 09-08同源根治), final到达(hasFinalStats)停表回退duration(终态准确), 未开始startInfo空
//   不走表(旧receiving=true提前走表窗口=修正); shownElapsed同步: detail→elapsedSec / 走廊→liveElapsed / 终态→elapsedSec;
//   deps 保持派生布尔(跨帧值稳定), frames对象有意不入deps(防每帧重置去抖); useChatPanels 透传一并删除, 连接级isReceiving
//   只留ChatInput消费 — 小欧-2026-09-14
// 编辑历史: 2026-09-15 小欧 - 北京老陈定案(整体视觉): 纯白页面中 taskinfo 白条无分隔看不清——
//   加底色 Colors.BG.LIGHT(#fafafa) 整条通栏平铺(无圆角卡片, 全页无卡片语法), 与纯白输入区形成明暗层次,
//   分隔线仍走输入框上沿(定案B), 色块下沿即贴 1px #f0f0f0 线衔接 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 北京老陈令(长方形封边): taskinfo 色块顶部补 1px #f0f0f0 上边框线,
//   与输入框上沿线同色, 色块成完整"长方形"框感(顶线+底面), 与上方中部滚动区白底分隔 — 小欧-2026-09-15
// 编辑历史: 2026-09-17 小沈 - 耗时+步轮从左组移至右组信任前面: 左组原 Badge+耗时+步轮+liveMeta 改为 Badge+liveMeta,
//   耗时(G2)与步轮(G3)整块迁至右组 TrustPanel 前, 断点矩阵逻辑(xsmall/mid/narrow/wide)不变 — 小沈-2026-09-17
// 编辑历史: 2026-09-17 小沈 - 事件列表两项优化: ①空列表时显示"暂无事件"提示(原 null 导致 Popover 弹空白);
//   ②事件排序改为正序(最早在上), 配合 useTaskInfo 去除 .reverse() — 小沈-2026-09-17
// 编辑历史: 2026-09-18 小欧 - 北京老陈令(taskinfo部分小改动): ①G5"累计"标签改"任务"(tooltip同步),
//   ②耗时 G2 秒值改"时分秒"结构(formatDurationHMS, 如 00:07:43), ③G3 步轮组三档重排——
//   宽: 轮数:N · 步骤:M / 窄: 轮:N · 步:M(或保持紧凑) / 极窄(xsmall): 随耗时合并为 耗时 h:mm:ss · 轮:N · 步:M,
//   语义补正: 数3000+实为业务步骤数(后端total_steps, 非消息数/非发送次数) — 小欧-2026-09-18
// 编辑历史: 2026-10-04 小欧 - 文档[6]: G6 上下文浮层卡片抽为 ContextOverviewCard(删本文件内 78 行内联 IIFE
//   及其 CONTEXT_STATE_MAP/mapStatus/FloatingEntry 导入与 ctxOpen 状态, 卡片自持折叠态; 行为等价)
// 编辑历史: 2026-10-04 小欧 - token 两项改版: 序改 P/C/T(P 加粗)、行内折 K/M、tooltip 原始值且不折行、
//   无数据显示 –; G3 轮步拆两段移到「任务」前(删 xsmall 合并串, 耗时位置未动); 分隔点统一「•」(BORDER.ACCENT);
//   新增「占窗率 = 本轮P/窗口」置于「任务」前(缺窗口不显); 断点门统一 isNarrow, 删 isMid
// 编辑历史: 2026-10-06 小欧 - 增 storeStatus 入参(useTaskInfo 补第 5 参), 用于取消终态帧没送达时的徽标兜底。 — 小欧-2026-10-06
// 编辑历史: 2026-10-11 10:13:16 小欧 - 北京老陈令「final 的时候回填事件列表」: 新增 taskId prop(取值与组件 key 同源 activeTaskId ?? serverTaskId, 不新造标识); final 到达时调 saveTaskProcessEvents 回传快照(_sentRef 幂等只发一次, _latestRef 读最新值避 exhaustive-deps, effect 首行 if (detail) return 防历史态误回填覆盖/跨任务污染; 失败只 console.warn 不阻断) — 小欧-2026-10-11
// 编辑历史: 2026-10-25 小欧 - 通知信封图标映射启用: import NOTICE_CONFIG; 事件时间轴渲染 notice 条目时按 kind+phase 查 NOTICE_CONFIG, 未命中回退 EVENT_ICON_MAP.notice — 小欧-2026-10-25
// 编辑历史: 2026-10-26 小沈 - renderLiveMeta支持notice: start=SyncOutlined spinner+橙色, failed=WarningOutlined+红色; 位4双渲染完成 — 小沈-2026-10-26
// 编辑历史: 2026-10-26 小沈 - 卡死预警接入位2动态状态: LIVE_META_TEXT_MAX 60→20, 事件时间轴截断 13→20, 事件浮层宽 520→220; stuckWarning 不再独立渲染, 由 liveMeta(kind='warning')承载; 新增11位置对照表 — 小沈-2026-10-26
// 编辑历史: 2026-10-28 小欧 - 位2动态状态+事件列表文本截断改**显示宽度**省略(北京老陈令):
//   原按 20 字符 slice 截断——20 个英文仅占约一半显示宽(英文半角≈0.5汉字宽), 剩一半空白严重不合理;
//   改 CSS text-overflow:ellipsis 按真实渲染宽度截断, 中/英/数字各填满, 自动省略号, 全文 hover/Tooltip 可见;
//   位2 宽屏 maxWidth=20×FontSize.SECONDARY≈240px(20汉字), 窄屏 200px; 事件列表 flex 收缩省略;
//   删 briefMeta/LIVE_META_TEXT_MAX, 删未用 Tooltip import — 小欧-2026-10-28
// 编辑历史: 2026-10-29 小欧 - 位2动态状态宽度+事件浮层加宽+事件文本折行+两处宽度拆分:
//   位2与事件浮层原共用 LIVE_META_MAX_W, 拆为两个独立常量各管各的:
//   LIVE_META_MAX_W=20 汉字宽(240px) 位2截断专用(EllipsisTip+ellipsis);
//   EVENT_CARD_W=40 汉字宽(480px) 事件浮层宽度专用, 事件文本折行不截断(whiteSpace:normal+wordBreak:break-word) — 小欧-2026-10-29
// 编辑历史: 2026-10-29 小欧 - 北京老陈令「上下文挪至耗时后、信任前」: 上下文(ContextOverviewCard)自中组末尾
//   迁至右组耗时后、信任前(位号 8→9 对调, 耗时 9→8); 中组删其前分隔点(7任务token收尾), 右组耗时后补分隔点;
//   11位置对照表同步。 小欧-2026-10-29
// 编辑历史: 2026-10-29 小欧 - 北京老陈令「占窗率挪至上下文后、信任前」: 占窗率(G8)自中组迁至右组上下文后、
//   信任前; 序号同步 任务token6/耗时7/上下文8/占窗率9; 11位置对照表同步。 小欧-2026-10-29
// 11位置对照表(当前实际布局, 从左到右):
//   1 徽标      2 动态状态(含卡死预警 warning)
//   3 轮次      4 本轮token 5 步数
//   6 任务token
//   7 耗时     8 上下文  9 占窗率  10 信任    11 事件
/**
 * TaskInfoBar - 输入框上方任务信息条（taskinfo slot，当前任务动态实时唯一位置）
 *
 * 【小欧 2026-08-26 8.6】7 项信息点（7.6 目标）：①状态徽标(startinfo)②耗时③轮次
 * ④token实时累计(usage)⑤装入历史对话水位(history_context)⑥过程状态条(start已开始/
 * paused/resumed/retrying)+取消终态⑦truncated提示。可折叠；纯 SSE 收流。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import type { CSSProperties } from 'react';
import React, { useEffect, useState, useRef } from 'react';
import { Badge } from 'antd';
import {
  CloseCircleFilled,
  DownOutlined,
  StopOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons'; // G4/G8 全 antd SVG
import type { ExecutionStep } from '../../../../types/execution';
import type { TaskMetaFrames, LiveError } from '@/types/sse';
// 2026-10-11 小欧 北京老陈令「final 的时候回填事件列表」: 回传用(仅取 executionApi.saveTaskProcessEvents)
//   与上方 import type 合并成单条 import(同模块, 避免重复 import 声明)
import {
  executionApi,
  type TaskDetail,
} from '../../../../services/api/task.api';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles'; // 硬码数字全令牌化
import { formatTimeHMS, formatDurationHMS } from '@/utils/time'; // 3.6 时间轴 HH:MM:SS; 2026-09-18 耗时时分秒 — 小欧-2026-09-18
import { useTaskInfo, type LiveMeta } from '../../hooks/useTaskInfo';
import { useInfoBreakpoint } from '../../hooks/useInfoBreakpoint'; // 3.9 断点矩阵(见 v4.4 修复#3)
import { TrustPanel } from '../config/TrustPanel';
import { EllipsisTip } from './EllipsisTip';
import { MetricItem } from './MetricItem';
import { FloatingEntry } from './FloatingEntry'; // v4.2: G6/G8 双浮层入口公共壳(见 6.5.2.4)
import {
  BADGE_MAP,
  EVENT_ICON_MAP,
  NOTICE_CONFIG,
  TABULAR_NUMS,
  formatTokenK,
} from './infoMaps';
// 2026-10-04 小欧: 上下文浮层卡片已抽至 ContextOverviewCard, 故不再需 CONTEXT_STATE_MAP/mapStatus
//   (FloatingEntry 仍在, G8 事件浮层在用)
import { ContextOverviewCard } from './ContextOverviewCard';

// 2026-10-28 小欧 - 位2 动态状态文本**显示宽度**上限(按像素, 非字符数): 20 × FontSize.SECONDARY=12px ≈ 240px(20汉字宽) — 小欧-2026-10-28
//   2026-10-29 小欧 - 位2与事件浮层宽度拆分(原共用 LIVE_META_MAX_W): 位2截断恢复 20 汉字宽(240px);
//   事件浮层独立用 EVENT_CARD_W=40 汉字宽(480px) + 文本折行不截断, 两处各管各的 — 小欧-2026-10-29
const LIVE_META_MAX_W = 20 * FontSize.SECONDARY; // 位2 截断: 20 汉字宽 ≈ 240px
const EVENT_CARD_W = 40 * FontSize.SECONDARY; // 事件浮层宽: 40 汉字宽 ≈ 480px

// 2026-10-04 小欧: 分隔点与轮/步两段共用样式(DRY, 原为 5 份逐字重复的对象字面量);
//   点用淡蓝 BORDER.ACCENT(明显但不抢, 避开绿=成功/红=失败语义色), 字符取真圆点"•"、字号 SECONDARY,
//   原"·"+CAPTION 10px 太小看不见(北京老陈令)
const DOT_STYLE: CSSProperties = {
  fontSize: FontSize.SECONDARY,
  color: Colors.BORDER.ACCENT,
};
const STAT_STYLE: CSSProperties = {
  fontSize: FontSize.SECONDARY,
  color: Colors.TEXT.SECONDARY,
  ...TABULAR_NUMS,
};

// BADGE_MAP 由 6.5.2.1 infoMaps.ts 定义，本文件经 import 使用（6.5.3.2），不再内联定义

interface TaskInfoBarProps {
  steps: ExecutionStep[];
  frames: TaskMetaFrames; // 统计类元信息帧（8.4.14）
  detail?: TaskDetail | null; // 【A3】选中历史任务时由其详情派生动态信息
  sessionId?: string | null; // 13.14 TrustPanel第一行尾部需会话ID
  liveError?: LiveError | null; // 小欧 2026-09-02+09-08: 位4 error 实时源(LiveError 对象, useChatPanels 透传) — 小欧-2026-09-08
  // 2026-10-06 22:52 小欧 - storeStatus：chatStreamStore 会话状态，取消终态帧未送达时的 badge 兜底
  storeStatus?: string;
  // 2026-10-11 小欧 北京老陈令「final 的时候回填事件列表」: 回填端点需要 task_id。
  //   历史态为 null(快照已在库中, 无需回填); 实时态由 useChatPanels 传 activeTaskId ?? serverTaskId,
  //   与本组件 key 同源(useChatPanels:300), 不新造任务标识状态。
  taskId?: string | null;
}

const TaskInfoBar: React.FC<TaskInfoBarProps> = ({
  steps,
  frames,
  detail,
  sessionId,
  liveError,
  storeStatus,
  taskId,
}) => {
  // v4.1: 取消整行折叠, collapsed 状态机/localStorage 键已删除
  // 新增: eventsOpen useState(false)(见 6.5.3.4 / 6.5.3.8), 随组件轻量瞬态, 不持久化
  // 2026-10-04 小欧: ctxOpen/setCtxOpen 随上下文浮层卡片迁至 ContextOverviewCard
  const [eventsOpen, setEventsOpen] = useState(false);
  // 2026-09-14 小欧 改动点①(方案A, 北京老陈批准): useTaskInfo 改四参签名, receiving prop 本身保留
  //   (秒表 interval 启停仍以 receiving 为准, D3 契约); 仅不再透传给徽标派生 — 小欧-2026-09-14
  const info = useTaskInfo(steps, frames, detail, liveError, storeStatus);
  const b = BADGE_MAP[info.badge];

  // 2026-10-11 小欧 北京老陈令「final 的时候回填事件列表」—— 收到 final 帧即回传事件列表快照。
  //   判据复用 steps 里既有的 type==='final'(不新造终态判据, 与 useTaskInfo 同源)。
  //   快照取 info.processEventsSnapshot(已排除 heartbeat, 全链路唯一过滤在 useTaskInfo 内)。
  //   失败只记 console 不回滚 —— 北京老陈定案「回填失败就失败, 不紧要」,
  //   且绝不让快照写入失败打断任务收尾(此处不 throw, 不影响渲染)。
  //
  //   幂等 + 依赖极小化(Rules of Hooks / 性能): effect 依赖**只挂标量 taskId**, 不挂
  //   processEventsSnapshot 数组 —— 后者每次 useMemo 重算都是新引用, 挂上去会让 effect
  //   每次渲染都重跑, 靠 _sentRef 拦 POST 是治标(重渲染开销仍在)。改成标量闸:
  //   _sentRef 命中即直接 return, 该 effect 实际只在 taskId 变化时执行一次。
  //
  //   ⚠️ detail 非空 = 当前在看**历史任务**(useTaskInfo 历史分支)。此时必须 return:
  //   ①历史快照已在库中, 回填=用空数组覆盖真实数据(数据丢失);
  //     ②steps 传的是实时 executionSteps, 若残留上一实时任务(含final)的 steps,
  //       会把**别的任务的事件写进本任务**(跨任务污染)。
  //     两条都由这一行 `if (detail) return` 一次性挡住。
  //
  //   依赖**刻意不含 info.processEventsSnapshot**: 它每次 useMemo 重算都是新引用, 挂上依赖
  //   会让 effect 每次渲染都重跑(靠 _sentRef 拦 POST 是治标, 重渲染开销仍在)。
  //   改用 _latestRef 承载最新快照: effect 内读 ref 拿到的即本次渲染的最新值,
  //   既不需要把它挂进依赖(exhaustive-deps 自然干净, 无需 eslint-disable), 也确实拿到新值。
  //   (React 官方 ref-latest 模式; 依赖 _hasFinal 时该值已收齐 —— final 是终态事件。)
  const _sentRef = useRef<string | null>(null);
  const _latestRef = useRef(info.processEventsSnapshot);
  _latestRef.current = info.processEventsSnapshot;
  const _hasFinal = steps.some((s) => s.type === 'final');
  useEffect(() => {
    if (detail) return;
    if (!taskId || !_hasFinal) return;
    if (_sentRef.current === taskId) return;
    _sentRef.current = taskId;
    executionApi
      .saveTaskProcessEvents(taskId, _latestRef.current)
      .catch((e) => {
        console.warn('[TaskInfoBar] 事件列表快照回填失败(不阻断):', e);
      });
  }, [taskId, _hasFinal, detail]);
  // 2026-10-04 小欧: 占窗率=本轮 P / 运行时窗口(usage 帧的 context_window); 窗口缺失(历史任务/未收到帧)→ null 不显
  const windowUsePct =
    info.contextWindow && info.roundUsage
      ? Math.round((info.roundUsage.prompt / info.contextWindow) * 100)
      : null;
  // 3.9 断点矩阵（v4.4 修复#3）：wide≥1280 / mid 1280~960 / narrow 960~768 / xsmall<768
  const bp = useInfoBreakpoint();
  const isNarrow = bp === 'narrow' || bp === 'xsmall';
  // 2026-10-04 小欧: 极窄档(<768)备用, 当前两项收窄门统一用 isNarrow; 保留待极窄档单独策略时直接用(北京老陈令留)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- 有意保留的备用断点档, 非死代码
  const isXSmall = bp === 'xsmall';
  // 2026-10-04 小欧: 删 isMid(步轮拆独立两段后无调用方, YAGNI)
  // 【2026-09-03 小欧 复用TrustPanel】信任查询/刷新/撤销/折叠逻辑已移入 TrustPanel 组件(TaskInfoBar 删除内联重复, DRY)

  // 【小欧 2026-08-26 修复 B2】实时计时：实时流期间按 start 时刻走表
  // （2026-09-06 不再挂靠徽标 running, 错误/失败态下秒表继续走不零不回跳），
  // 历史任务(detail)用后端 duration，不计时。
  // 2026-09-14 小欧 删第二个变量(北京老陈令): receiving prop 删除——秒表启停改由 frames 权威信号驱动:
  //   startInfo 非空(任务已开始) && finalStats 空(尚未终态落库)=执行中走廊, 走表;
  //   断连窗/错误中间态(旧 receiving=false 缺陷窗口)继续走表=进化, final 到达(hasFinalStats)归零回退 duration;
  //   与 RightViewer hasFinalStats/isCurrentLive 同源, 连接级 isReceiving 只留 ChatInput 消费 — 小欧-2026-09-14
  const taskStarted = frames.startInfo !== null;
  const taskFinished = !!frames.finalStats;
  const [liveElapsed, setLiveElapsed] = useState(0);
  const startRef = useRef<number | null>(null); // 2026-08-27 小欧 三堂会审: 仅首次锚定start, 防计时抖动
  useEffect(() => {
    if (!detail && taskStarted && !taskFinished) {
      // 2026-09-06 小欧 去 info.badge==='running' 依赖 — 小欧-2026-09-06
      if (startRef.current == null) {
        startRef.current = frames.startTimestamp || Date.now(); // 2026-08-27 小欧 三堂会审: 首次锚定
      }
      const start = startRef.current;
      const t = setInterval(
        () =>
          setLiveElapsed(Math.max(0, Math.round((Date.now() - start) / 1000))),
        1000
      );
      return () => clearInterval(t);
    }
    setLiveElapsed(0);
    startRef.current = null; // 2026-08-27 小欧 三堂会审: 任务切换复位startRef
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- taskStarted/taskFinished 为帧派生布尔(跨帧值稳定), 有意不入frames防每帧重置(去抖) — 小欧-2026-09-09
  }, [detail, taskStarted, taskFinished]); // 2026-09-06 小欧 deps 保持稳定(派生布尔); frames.startTimestamp 有意不入 deps 防每帧重置(去抖动, 变更记录见上方注释) — 小欧-2026-09-09
  const shownElapsed = detail
    ? info.elapsedSec
    : taskStarted && !taskFinished // 2026-09-06 小欧 执行中走廊一律走 liveElapsed(错误态继续走表); 终态/未开始回退 elapsedSec(终态 duration) — 小欧-2026-09-06
      ? liveElapsed
      : info.elapsedSec;

  // eventsTimeline(v4.1, v4.2 经 FloatingEntry 注入): 渲染于 G8 卡片 content(6.5.3.4), 无折叠态条件
  const eventsTimeline =
    info.processEvents.length > 0 ? (
      <div
        role="log"
        aria-live="polite" // 3.6: 新事件实时播报
        style={{
          maxHeight: '40vh', // v4.1: 浮层卡片内滚, 不撑 TaskInfoBar 高度
          overflowY: 'auto',
          scrollbarWidth: 'thin',
        }}
      >
        {info.processEvents.map((e) => (
          <div
            key={`${e.time}-${e.kind}`} // 唯一 key, 弃索引 {i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: Spacing.MD,
              fontSize: FontSize.SECONDARY,
              lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
            }}
          >
            {/* 左列: 时间 HH:MM:SS + 均长竖线(3.6 定案, 不编码间隔) */}
            <span
              style={{
                fontSize: FontSize.SMALL, // 11px
                color: Colors.TEXT.SECONDARY,
                ...TABULAR_NUMS, // 等宽防抖动
                width: 56,
                textAlign: 'right',
                flexShrink: 0,
              }}
            >
              {formatTimeHMS(e.time)}
            </span>
            <span style={{ color: Colors.BORDER.LIGHT }}>│</span>
            {/* 右列: antd SVG 图标 + 文本; 图标即 3.6 "● 节点", 不另加 ● 文本符 */}
            <span
              style={{
                color: Colors.TEXT.TERTIARY,
                minWidth: 0,
                flex: 1,
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {e.kind === 'notice'
                ? (NOTICE_CONFIG[`${e.notice_kind}_${e.notice_phase}`] ??
                  EVENT_ICON_MAP.notice)
                : EVENT_ICON_MAP[e.kind]}
              {/* 2026-10-29 小欧 - 事件文本改折行显示(原 nowrap+ellipsis 截断): 浮层加宽到 480px(EVENT_CARD_W) 后
                  长文本折行完整可见, 不再省略; wordBreak 确保长英文/路径可断 — 小欧-2026-10-29 */}
              <span
                style={{
                  marginLeft: Spacing.XS,
                  minWidth: 0,
                  whiteSpace: 'normal',
                  wordBreak: 'break-word',
                }}
                title={e.text}
              >
                {e.text}
              </span>
            </span>
          </div>
        ))}
      </div>
    ) : (
      <div
        style={{
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.TERTIARY,
          textAlign: 'center',
          padding: `${Spacing.MD}px 0`,
        }}
      >
        暂无事件
      </div>
    );

  // renderLiveMeta(3.9 重用 + 2026-10-28 显示宽度截断): 文本统一由 EllipsisTip 按真实渲染宽度省略, 全文进 Tooltip — 小欧-2026-10-28
  const renderLiveMeta = (m: LiveMeta) => (
    <span
      style={{
        fontSize: FontSize.SECONDARY,
        fontWeight: FontWeight.MEDIUM, // 加 500
        color:
          m.kind === 'error'
            ? m.requestLevel
              ? Colors.TEXT.SECONDARY // 请求级: StopOutlined 灰
              : Colors.ERROR // 执行级: CloseCircleFilled 红
            : m.kind === 'notice' && m.notice_phase === 'failed'
              ? Colors.ERROR // notice failed: 红色
              : Colors.WARNING, // retrying/truncated/warning/notice-start: #AD6800 (对比度≥4.5:1)
        marginLeft: Spacing.XS,
      }}
    >
      {m.kind === 'retrying' ? (
        <SyncOutlined spin /> // 🔁 → SyncOutlined spin
      ) : m.kind === 'notice' ? (
        m.notice_phase === 'start' ? (
          <SyncOutlined spin /> // notice start: spinner
        ) : (
          <WarningOutlined /> // notice failed: warning
        )
      ) : m.kind === 'error' ? (
        m.requestLevel ? (
          <StopOutlined /> // ⛔ → StopOutlined
        ) : (
          <CloseCircleFilled
            style={{ fontSize: FontSize.SECONDARY, color: Colors.ERROR }}
          />
        )
      ) : (
        <WarningOutlined /> // ⚠ → WarningOutlined (truncated/warning)
      )}{' '}
      {m.text}
    </span>
  );

  // 3.1.3 方案A: 文字样式(PRIMARY + 500)提示可点
  // 2026-09-15 小欧 北京老陈定案: 整条压回真一行——外层 padding 8px 顶→4px(Spacing.XS),
  //   超一半留白主要来自此处 8px+热区32px(min-height 已并降到20), 两处合并后高度≈24px 恰一行;
  //   渗透加固(整体视觉): 加底色 Colors.BG.LIGHT 通栏平铺, 白条不可见问题根治 — 小欧-2026-09-15
  return (
    <div
      style={{
        // 2026-09-15 小欧: #fafafa 通栏底色——白底页面中界定任务信息条, 与输入区白色/上沿1px #f0f0f0 分线形成层次 — 小欧-2026-09-15
        background: Colors.BG.LIGHT,
        // 2026-09-15 小欧 北京老陈令(长方形闭环): 色块顶部补 1px 上边框线, 与输入框上沿 #f0f0f0 同色,
        //   taskinfo 成完整"长方形"框感(顶线+底面), 与上方中部滚动区白底分隔; 定案B下沿线仍在输入框 — 小欧-2026-09-15
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
        padding: `${Spacing.XS}px 0 0`, // 8px → Spacing.MD; 2026-09-15 小欧: MD→XS 压回一行 — 小欧-2026-09-15
        display: 'flex',
        flexDirection: 'column',
        gap: Spacing.MD,
        textAlign: 'left',
      }}
    >
      {/* v4.1: 信息带恒定 1 行, 整行折叠态机已删除; G1~G6 渲染其中, 无整行点击 */}
      {/* v4.4: 接线 .taskinfo-bar(G5 可换行, 消死 CSS) — 小欧-2026-09-09 */}
      <div
        className="taskinfo-bar"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.LG,
          cursor: 'default',
          flexWrap: 'wrap',
          userSelect: 'text', // 3.9: 文本可选中, 点击不触发任何折叠
        }}
      >
        <div
          className="taskinfo-token"
          style={{
            display: 'flex',
            alignItems: 'center',
            // v4.4: gap 硬码 8 → Spacing.MD — 小欧-2026-09-09
            gap: Spacing.MD,
            flexShrink: 0,
          }}
        >
          {/* ── 左组: 1徽标 2动态状态(含卡死预警 warning) ── */}
          {/* 1-徽标(状态指示) */}
          <Badge status={b.status} text={b.text} />

          {/* 2-动态状态: 位置固定, 收 retrying/error/truncated/warning/notice, 无优先级; warning=卡死预警 */}
          {/* 小欧 2026-09-02: 第一行位4(位置固定, 新覆盖旧; 只收 retrying/error/truncated 无优先级; 去旧"重试N"累计与截断独立段) - 北京老陈拍板 */}

          {/* 3.9 断点矩阵: 各档统一 EllipsisTip 按显示宽度省略(2026-10-28 小欧: 原窄屏 200/宽屏 JS 字符截断, 改统一 CSS 像素级省略) — 小欧-2026-10-28 */}
          {info.liveMeta && (
            <EllipsisTip
              text={info.liveMeta.text}
              tooltip={info.liveMeta.text}
              maxWidth={isNarrow ? 200 : LIVE_META_MAX_W}
            >
              {renderLiveMeta(info.liveMeta)}
            </EllipsisTip>
          )}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: Spacing.MD,
            flex: 1,
            minWidth: 0,
            justifyContent: 'center',
            flexWrap: 'wrap',
          }}
        >
          {/* ── 中组: 3轮次 4本轮token 5步数 6任务token ── */}
          {/* 3-轮次 */}
          {/* G3 步轮: 2026-10-04 小欧 拆为轮/步两段独立 span, 删 xsmall "耗时·轮·步" 合并串(北京老陈: 不要纠缠在一起) */}
          <span style={STAT_STYLE}>轮:{info.llmCallCount}</span>
          <span style={DOT_STYLE}>•</span>
          {/* 4-本轮token(P/C/T) — G5: P加粗+C/T中灰, 序P/C/T, 折K(M); narrow起C/T收进tooltip; 无数据显示– */}
          {/* G5 本轮/任务: P 加粗 + C/T 中灰, 序 P/C/T, 折 K(M); narrow 起 C/T 收进 tooltip; 无数据显示 –;
              本轮项不显标签(北京老陈令), 轮已前移至其前 — 小欧 2026-10-04 */}
          <MetricItem
            value={`P ${formatTokenK(info.roundUsage?.prompt)}`}
            detail={
              isNarrow
                ? undefined
                : `/ C ${formatTokenK(info.roundUsage?.completion)} / T ${formatTokenK(info.roundUsage?.total)}`
            }
            tooltip={`本轮 P ${info.roundUsage?.prompt ?? 0} / C ${info.roundUsage?.completion ?? 0} / T ${info.roundUsage?.total ?? 0}`}
          />
          <span style={DOT_STYLE}>•</span>
          {/* 5-步数 */}
          <span style={STAT_STYLE}>步:{info.stepCount}</span>
          <span style={DOT_STYLE}>•</span>
          {/* 6-任务token(P/C/T累计) — 标签"任务" */}
          <MetricItem
            label="任务"
            value={`P ${formatTokenK(
              info.taskAccumulated?.prompt_tokens ?? info.usage.prompt
            )}`}
            detail={
              isNarrow
                ? undefined
                : `/ C ${formatTokenK(info.taskAccumulated?.completion_tokens ?? info.usage.completion)} / T ${formatTokenK(info.taskAccumulated?.total_tokens ?? info.usage.total)}`
            }
            // 收窄档 tooltip 是唯一明细源 — 小欧-2026-10-29
            tooltip={`任务 P ${info.taskAccumulated?.prompt_tokens ?? info.usage.prompt} / C ${info.taskAccumulated?.completion_tokens ?? info.usage.completion} / T ${info.taskAccumulated?.total_tokens ?? info.usage.total}`}
          />
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: Spacing.MD,
            flexShrink: 0,
            marginLeft: 'auto',
          }}
        >
          {/* ── 右组: 7耗时 8上下文 9占窗率 10信任 11事件 ── */}
          {/* 7-耗时 — G2: 时分秒格式, 各档常显 */}
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.PRIMARY,
              fontWeight: FontWeight.BOLD,
              ...TABULAR_NUMS,
            }}
          >
            耗时 {formatDurationHMS(shownElapsed)}
          </span>
          {/* 8-上下文 — G6: 浮层①入口锚点, 内容抽至ContextOverviewCard */}
          <span style={DOT_STYLE}>•</span>
          <ContextOverviewCard
            overview={info.overview}
            isLiveContext={info.isLiveContext}
            contextWindow={info.contextWindow}
          />
          {/* 9-占窗率 — G8: 本轮P/窗口, 恒≤100%; DOT 在条件内, null 时不渲染防悬空 */}
          {windowUsePct != null && (
            <>
              <span style={DOT_STYLE}>•</span>
              <MetricItem
                label="占窗率"
                value={`${windowUsePct}%`}
                tooltip={`本轮 P ${info.roundUsage?.prompt ?? 0} / 窗口 ${info.contextWindow ?? 0} = ${windowUsePct}%`}
              />
              <span style={DOT_STYLE}>•</span>
            </>
          )}
          {/* 10-信任 — G7: TrustPanel触发按钮, 窄档仅计数 */}
          {/* G7 信任: 内为 TrustPanel 触发按钮(6.5.4.3 改 Drawer 打开), 不承担折叠; 3.9 窄档仅计数 */}
          <TrustPanel sessionId={sessionId} compact={isNarrow} />
          {/* 11-事件 — G8: 浮层②事件卡片, 热区32×32, 开合唯一真源=trigger+onOpenChange */}
          {/* G8 事件入口(v4.1/v4.2, v4.2 经 FloatingEntry 实现): 浮层② 事件卡片, 热区 32×32, hover 规格 2, 3.8 键盘 */}
          {/* v4.2 双写修复: 删 onClick 手动 setEventsOpen toggle(与 antd trigger click 双重写入), 开合唯一真源为 trigger + onOpenChange, 与 G6 对齐 */}
          <FloatingEntry
            open={eventsOpen}
            onOpenChange={setEventsOpen}
            placement="bottomRight" // v4.1: 右缘对齐 G8, 向左展开(3.9)(antd 真值, 见 FloatingEntry)
            cardId="taskinfo-events-card"
            ariaLabel="事件序列"
            cardStyle={{ width: EVENT_CARD_W, maxWidth: '90vw' }}
            content={eventsTimeline} // 6.5.3.10 移入: role="log" + aria-live + maxHeight 40vh 内滚
          >
            <span style={{ fontSize: FontSize.CAPTION }}>
              <DownOutlined style={{ fontSize: FontSize.CAPTION }} />{' '}
              {/* v4.1: 方向=弹出语义 */}
              事件
              {/* 2026-10-04 小欧: 事件计数胶囊(北京老陈令): 橘底(Colors.ACCENT_ORANGE #d4380d)白字加粗, 白字对比约4.8:1达AA,
                  亮橘 #fa8c16 配白字仅 2.4:1 故弃用; 0 条不显, 数据源 useTaskInfo.processEventCount(未截断真值) — 小欧 2026-10-04 */}
              {info.processEventCount > 0 && (
                <Badge
                  count={info.processEventCount}
                  overflowCount={99}
                  style={{
                    marginLeft: Spacing.XS,
                    fontSize: FontSize.CAPTION,
                    fontWeight: FontWeight.BOLD,
                    color: '#fff',
                    backgroundColor: Colors.ACCENT_ORANGE,
                    height: 14,
                    lineHeight: '14px',
                    paddingInline: 4,
                  }}
                />
              )}
            </span>
          </FloatingEntry>
        </div>
      </div>
    </div>
  );
};

export { TaskInfoBar };
