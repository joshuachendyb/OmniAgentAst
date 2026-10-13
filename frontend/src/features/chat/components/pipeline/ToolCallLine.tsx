// 编辑历史: 2026-08-26 小欧 - 修复B1: 观察摘要优先tool_result(4.9.3),兜底summary/content
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 删tool_params误用(8)/摘要tool_result优先(9)/展开渲染tool_result优先(10)
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距/去框: margin6px0→8px0; 常态去radius改borderLeft2px#e8e8e8左线分态(highlight才#faad14+radius6); 主色#1890ff→#1677ff
// 编辑历史: 2026-08-27 小欧 - 修复chat-C: 新契约 tool_result 数组取首项 summary/llm_data.summary, 不再回落字面量[工具结果]
// 编辑历史: 2026-08-28 小强 - 修复: getObsSummary空数组回落丢失, parts为空时fallback到o.summary/content - 小强-2026-08-28
// 编辑历史: 2026-08-28 小强 - 修复: tool_result含空数组走错分支, 改条件为数组且长度>0 - 小强-2026-08-28
// 编辑历史: 2026-08-28 小欧 - ④A/a2: 高亮1px→2px + WARNING_BG令牌化, 左线统一2px
// 编辑历史: 2026-08-29 小强 - 修复#22: 展开观察区支持字符串tool_result渲染(与数组/兜底content并列) - 小强-2026-08-29
// 编辑历史: 2026-08-30 小欧 - 设计文档实施(设计文档落码, 北京老陈 2026-08-30 批准): 全文件魔法数字收敛——margin(MD)/padding(XS·MD组合=4/8/4/10)/marginLeft(SM)/展开区 marginTop(XS)+paddingLeft(LG)+marginBottom(XS)/观察块 marginTop(XS) 全部落 Spacing; 常态去掉自带左线(borderLeft=undefined, 去双线, 流水线容器左线唯一), HITL 高亮态 THIN 黄线保留 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 折叠展开内(展开区 marginTop/参数标头 marginBottom/观察块 marginTop/观察标头 marginBottom)一律 Spacing.XS-2=2, 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 间距统一收口: 工具行自身 margin Spacing.MD(8)→stepMargin(false)(=MD-2=6), 与思考/正文/状态 step 段距同值, 杜绝工具行与文本行段距不一致 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案(字体留白全0 + 行高=字号+4): 根容器 lineHeight=字号+Spacing.XS(4) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案: 字体留白全0 / step间6(SM) / step内文字4(XS折不折同) / obs标签4(XS) / 段内折不折2(XS-2): 观察块间4 标签4 段内2，工具行段距 SM6 - 小欧-2026-08-30
// 编辑历史: 2026-09-01 小欧 - 工具观察按工具维度组织: 单/多统一结构, 第一行集合名+同行工具名列表, 内层每工具子行(独立参数+状态+摘要, 按索引与tool_result配对); 修多工具只显首项结果; 修参数结果挤一行 - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 修复重构退化(BUG#22): 展开区兜底恢复字符串tool_result渲染(与数组ToolResultRenderer/兜底content并列, 恢复2026-08-29 #22修复逻辑), results仅认数组致字符串tool_result被忽略 - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 统一折叠三角：▲▼改▸▾、大小14(PRIMARY)、颜色PRIMARY、位置参数后，方法补role/aria/keyboard与TrustPanel一致 - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①合并多observation(flatMap)防首项丢失② JSON.stringify加try/catch防循环引用白屏③ expanded随action重置防跨任务泄漏④tParamText加try/catch — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - 工具执行UI优化(设计文档v1.8): 摘要头先显, 同容器挂齿轮+扳手组合动画(results===0)与工具子行(results>0)互斥, 覆盖动画位置
// 编辑历史: 2026-09-03 小欧 - Bug修复: ②results兼容字符串tool_result(防齿轮常驻) ③等待30s超时兜底降级提示(动画不再无限旋转) ④tools空/结果空显示占位防空壳 ⑧整批observation涌入前minHeight:32占位防页面晃动
// 编辑历史: 2026-09-03 小欧 D2-04: hasResult/tools空分支计数改hasResult口径(字符串场景0→1)
// 编辑历史: 2026-09-03 小欧 D2-05: timedOut计时改hasResult口径防字符串空转，D2-06: 依赖action→action.step防频繁重建
// 编辑历史: 2026-09-03 小欧/老杨 17.2: 去冗余三元hasResult?(results.length||1):0 → results.length||1（外层已保真）
// 编辑历史: 2026-09-03 小欧 修复: 超时文案由"工具执行超时未返回结果,请重试或查看日志"改为"工具执行等待超时(30s),结果可能仍在处理中", 分流LLM ReadTimeout与前端30s计时器
// 编辑历史: 2026-09-03 小欧 修复: 并行工具子行按tool_name配对查找结果, 乱序到达不串味, 无tool_name回退索引
// 编辑历史: 2026-09-03 小欧/北京老陈 v5.1 删timedOut状态和超时分支, 扳手只靠!hasResult&&tools.length>0
// 编辑历史: 2026-09-03 小欧/北京老陈 v5.1 删超时文案"工具执行等待超时(30s)"分支, 只保留扳手动画
// 编辑历史: 2026-09-06 小欧 - B2时序(北京老陈定案): interrupted 语义覆盖 blocked(被安全拦截也无 obs), 灰字文案改"未获用户允许/被安全拦截/确认超时" - 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(北京老陈裁定): 新增 replay prop(回放免齿轮动画——历史数据不需要齿轮转动), 齿轮分支条件补 !replay - 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2(北京老陈定案: 灰字不醒目): 占位与中断两处提示文字改 Colors.ORANGE_RED 火山橘红#fa541c(未执行/被安全拦截/确认超时), 与 AuthorizationModal 告急色一致, 与齿轮橘同色带 — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - 北京老陈要求"去掉扳手留齿轮": 等待动画 SVG 由"齿轮+扳手组合"改标准单齿轮(Feather settings)——
//   stroke线框风格/橙#fa8c16/1em旋转CSS(.tool-waiting-cursor)全部不变, 仅去掉扳手 path 换纯齿轮图标 — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4, 北京老陈裁定 被拒工具 UI 灰字): 新增 deniedTools prop(本执行轮被拒
//   工具点名条 [{tool,reason}]), 对被拒工具显火山橘红灰字点名单(对齐子行缩进/分支线, reason=拒绝理由);
//   有结果时在 tools.map 后收尾、无结果时独立成行——全拒/部分拒被拒工具均点名留痕; 点名接管时占位/聚合灰字隐藏不重复 — 小欧-2026-09-06
// 编辑历史: 2026-09-08 小欧 - 图标换型(北京老陈令): 齿轮(settings)旋转视觉不明显→换Feather loader弧段,
//   三段弧非对称旋转位置变化幅度大, 感知清晰; stroke线框橙#fa8c16/1s逆时针不变, 尺寸由index.css统一控 1.1em(≈15px) — 小欧-2026-09-08
// 编辑历史: 2026-09-13 小欧 - 内联橙色loader SVG提取为WaitingIcons/ToolWaitingIcon控件, 行为零变化(同SVG同CSS类), 注释统一用组件名 — 小欧-2026-09-13
// 编辑历史: 2026-09-15 小欧 - 第一阶段: 三级折叠三角▲▼→CircleArrow(20px/PRIMARY#595959/静止animated=false), 复用组件消三角字符 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 老杨 - 水滴图标 DropletIcon/DropletStatus 替代成功/失败字符符号, 复用组件消字符 — 老杨-2026-09-15
// 编辑历史: 2026-09-17 小欧 - 统一拒绝事件 type="rejected": ①deniedTools 类型新增 reject_type 字段; ②根据 reject_type 显示不同图标+文字标签(🔒[安全]/⏱️[超时]/🚫[拒绝]/🛡️[沙箱]); ③拒绝工具不再显示水滴图标; ④视觉分层优化(标签橘红/工具名深灰加粗/原因浅灰弱化) - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 会审V3整改(#6/#8): 拒绝图标 emoji→antd SVG(按全局定案禁emoji, 无圆底), 标签/图标映射提取为模块级导出常量 REJECT_LABEL_MAP/REJECT_ICON_MAP(防重建+测试断言真实映射) - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 - 实施: 新增 waitClock prop, 齿轮 ToolWaitingIcon 挂钟面并存(回放/中断/有结果守卫条件不变) - 小欧-2026-09-17
// 编辑历史: 2026-09-30 14:30 小欧 - deniedEntries 内联类型 tool/reason 转可选，以承载 tool 缺失的拒绝记录
// 编辑历史: 2026-10-13 小欧 - 文档[29]参数区 UI 优化落地(工具调用行侧 6 处):
//   ①import 补 ParamsTree/ParamsPanel/FloatingEntry/CodeOutlined/Size;②新增模块级 PARAMS_CARD_STYLE
//   (fit-content + minWidth 320 + maxWidth min(640,100vw-32px) + padding 0, 后者抵消 antd Popover 的 12px 内距防"框中框");
//   ③删 paramsOpen/PARAMS_FOLD_THRESHOLD 死状态, 增 openPanelIndex 作浮层单例互斥(DC-07/DC-18);
//   ④删 tools.map 内的 paramRows 派生(渲染期 JSON.stringify 归零, 序列化下沉子组件 SLAP);
//   ⑤工具行尾部追加「浮层参数」按钮(D2 乙): FloatingEntry 传 trigger=['click'] 去悬停弹出与 B5 首击被吃(D-7),
//     按钮文字色走 var(--taskinfo-entry-active, 状态色) 复刻系统既有机制(保 T20 状态编码又不压掉 hover 反馈),
//     CodeOutlined 内联 transform:none 抵住 .taskinfo-entry[data-open] 的 180° 翻转(T35), 外裹 flexShrink:0 保外层盒子;
//   ⑥删内联参数区(:361-437)并把 ParamsTree 挂到 role="button" 容器**之外**(D-1 结构性根治 B1, 点节点不再误折叠整行) — 小欧-2026-10-13
// 编辑历史: 2026-10-13 小欧 - 结果摘要 sum 由 CSS 单行省略改为**折行完整显示**(北京老陈裁定「不许截断」):
//   删 overflow:hidden + textOverflow:ellipsis + whiteSpace:nowrap, 补 minWidth:0 + pre-wrap + break-word。
//   注: 本条与文档[29]§2.6「结果摘要单行省略为保留不动项」冲突, 属需用户确认的越界改动, 已单独报备 — 小欧-2026-10-13
/**
 * ToolCallLine - 工具调用内联弱化行 + HITL 高亮边框
 *
 * 【小欧 2026-08-26 8.4.11】4.4.3 工具调用行内联弱化：工具名 + 参数摘要 + 结果摘要
 * 一行弱化(灰小字)，不再卡片包裹；点开展开 params/observation 详情；命中 HITL 挂起
 * 时整行呼吸边框(.hitl-border)。ToolResultRenderer 已去卡片边框(4.9.1③)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useState } from 'react';
import type { ExecutionStep } from '../../../../types/execution';
import { CollapsibleText } from './CollapsibleText';
import ToolResultRenderer from '../ToolResultRenderer';
// 2026-10-13 小欧 - 文档[29]§4.6: 新增两组件与浮层壳/尺寸令牌 — 小欧 2026-10-13
import { ParamsTree } from './ParamsTree';
import { ParamsPanel } from './ParamsPanel';
import { FloatingEntry } from '../taskinfo/FloatingEntry';
import { CircleArrow } from '@/components/CircleArrow'; // 2026-09-15 小欧: 复用折叠箭头组件 — 小欧-2026-09-15
import { DropletIcon } from '@/components/DropletIcon'; // 2026-09-15 老杨: 水滴图标替代字符符号 — 老杨-2026-09-15
import { GearIcon } from '@/components/GearIcon'; // 2026-09-15 老杨: 齿轮图标替代🔧emoji — 老杨-2026-09-15
import {
  LockOutlined,
  ClockCircleOutlined,
  StopOutlined,
  SafetyCertificateOutlined,
  CodeOutlined,
} from '@ant-design/icons'; // 2026-09-17 小欧 会审V3(#6): 拒绝图标按全局定案用 antd SVG — 小欧-2026-09-17
import {
  Colors,
  BorderWidth,
  FontSize,
  FontWeight,
  Spacing,
  stepMargin,
  Size,
} from '@/utils/stepStyles';
import { ToolWaitingIcon } from '@/components/WaitingIcons'; // 2026-09-13 小欧: ToolWaitingIcon 从内联提取为独立控件 — 小欧-2026-09-13
import type { ClockSignals } from '@/types/sse'; // 2026-09-17 小欧 实施: 钟面信号类型 — 小欧-2026-09-17

interface ToolCallLineProps {
  action: ExecutionStep; // type=action
  observations?: ExecutionStep[]; // type=observation
  highlight?: boolean; // HITL 联动高亮
  interrupted?: boolean; // 2026-09-06 小欧 B2: 用户拒绝/确认超时且无结果——停齿轮(替换等待动画) — 小欧-2026-09-06
  replay?: boolean; // 2026-09-06 小欧 B2(北京老陈裁定): 历史回放标志——历史数据不需要齿轮转动, 免齿轮动画 — 小欧-2026-09-06
  // 2026-09-30 小欧 - tool/reason 转可选以匹配上游 deniedEntries（单一真源）类型；
  //   无名条目已由 PipelineRenderer 渲染前 .filter(e => e.tool) 拦掉，此处只需类型一致。
  deniedTools?: Array<{ tool?: string; reason?: string; reject_type?: string }>; // 2026-09-06 小欧 B2(6.4, 北京老陈裁定): 本执行轮被拒工具点名条(带拒绝理由), 对被拒工具显橘红灰字留痕 — 小欧-2026-09-06
  waitClock?: ClockSignals; // 2026-09-17 小欧 实施: 钟面信号(与齿轮并存) — 小欧-2026-09-17
}

// 2026-09-17 小欧 会审V3(#8): 拒绝标签/图标从 .map 内联提取为模块级持久常量(避免每次拒绝行渲染重建对象),
//   (#6): 按项目全局定案(infoMaps.tsx 注释"过程事件统一 antd SVG 图标、禁 emoji")emoji 换 antd SVG 图标,
//   无圆底(开发文档声称的圆底从未实现, 以实际实现为准) — 小欧-2026-09-17
// 导出版本供测试断言真实映射(替代测试内本地模拟, 防实现与断言脱钩)
export const REJECT_LABEL_MAP: Readonly<Record<string, string>> = {
  safety: '安全',
  timeout: '超时',
  user: '拒绝',
  sandbox: '沙箱',
};
export const REJECT_DEFAULT_LABEL = '拒绝';
export const REJECT_ICON_MAP: Readonly<Record<string, React.ReactNode>> = {
  safety: <LockOutlined />,
  timeout: <ClockCircleOutlined />,
  user: <StopOutlined />,
  sandbox: <SafetyCertificateOutlined />,
};
export const REJECT_DEFAULT_ICON = <StopOutlined />;

// 2026-10-13 小欧 - 文档[29]§4.6/§4.5: 浮层卡片纯 CSS 响应式三件套(替代断点矩阵 JS 方案 D-5)
//   width 撑满上限 + maxWidth 随视口收 + minWidth 保底; 无 resize 监听、无重渲染 — 小欧 2026-10-13
const PARAMS_CARD_STYLE: React.CSSProperties = {
  // 2026-10-13 小欧 - 北京老陈裁定: 面板宽改为**按内容收缩**, 上限 640。
  //   原固定 640 时, 短参数(如 6 个短键)只用到 ~450px, 右侧空 30% 视觉重心偏左。
  //   fit-content = min(内容宽, 可用宽); 上限取 min(640, 视口-32) 一次表达两个约束;
  //   下限仍 320(§3.4.3 窄屏口径)。
  width: 'fit-content',
  minWidth: Size.PARAMS_PANEL_MIN_W,
  maxWidth: `min(${Size.PARAMS_PANEL_MAX_W}px, calc(100vw - 32px))`,
  // 2026-10-13 小欧 - 文档[29]D-11: antd 5.29.3 的 .ant-popover-inner 自带 `padding: 12px`
  //   (node_modules/antd/es/popover/style/index.js:59, `innerPadding: wireframe ? 0 : 12`),
  //   而本面板自带卡片底/边框/圆角(DC-19)与自身内距, 不归零就会出现「白边 + 灰卡片」的框中框,
  //   与 §3.5.1 结构图不符 → 此处把外壳内距归零, 内距统一由面板自身的 padding 承担。
  padding: 0,
};

const ToolCallLine: React.FC<ToolCallLineProps> = ({
  action,
  observations = [],
  highlight = false,
  interrupted = false,
  replay = false,
  deniedTools, // 2026-09-06 小欧 B2(6.4)
  waitClock, // 2026-09-17 小欧 实施
}) => {
  // 2026-09-01 小欧: 每工具独立展开状态(数组), 点某工具行任意位置只展开/收起该工具(北京老陈定案: 完全独立展开+独立观察)
  const [expanded, setExpanded] = useState<boolean[]>([]);
  // 2026-10-13 小欧 - 文档[29]§3.2: 顶层"参数(N项)"折叠已被 ParamsTree 的"顶层键默认折叠"
  //   取代(DC-04), paramsOpen/PARAMS_FOLD_THRESHOLD 一并删除(死状态 YAGNI);
  //   新增 openPanelIndex 作浮层单例互斥(DC-07), 与 expanded 互不牵连(DC-18) — 小欧 2026-10-13
  const [openPanelIndex, setOpenPanelIndex] = useState<number | null>(null);
  useEffect(() => {
    setExpanded([]);
    setOpenPanelIndex(null); // 切任务时二者同清(唯一同时清理的场景, §3.2)
  }, [action]);
  const tools = action.tools || [];
  // 2026-09-03 小欧 重订(KISS/SLAP/DRY): 字符串 tool_result 不并入 results(保持数组契约),
  //   results 仍只收对象结果供子行/展开区配对; 字符串是否已达由 hasResult 单独判定以控制动画卸载与子行渲染,
  //   两职责分离 —— 不把字符串包成 {data_text} 对象(改前产生折叠摘要+展开区双重渲染致 getByText 多匹配)
  const results = observations.flatMap((obs) => {
    const tr = (obs as ExecutionStep | undefined)?.tool_result;
    if (Array.isArray(tr)) {
      return tr as Array<Record<string, unknown>>;
    }
    return [];
  }) as Array<Record<string, unknown>>;
  // 2026-09-03 小欧 修复: 是否有任一结果(数组含对象 / 非空字符串), 供动画卸载与子行渲染判定
  const hasResult = observations.some((obs) => {
    const tr = (obs as ExecutionStep | undefined)?.tool_result;
    if (Array.isArray(tr)) return tr.length > 0;
    return typeof tr === 'string' && tr.length > 0;
  });
  const obsStep = observations[0];
  const isMulti = action.exec_type === 'multi';
  const toolCount = tools.length;
  const collectionLabel = isMulti
    ? `并行 ${toolCount} 个工具`
    : `调用 1 个工具`;
  const toolNameList = tools.map((t) => t.tool).join(', ');
  const firstLine = `${collectionLabel}  [${toolNameList}]`;
  // 2026-09-06 小欧 B2(6.4): 被拒工具点名条(本执行轮被拒工具名+理由), 对被拒工具显橘红灰字留痕 — 小欧-2026-09-06
  const deniedList = Array.isArray(deniedTools) ? deniedTools : [];
  const deniedCount = deniedList.length;
  // 2026-10-04 小欧 修同名工具串味(文档[8]第六章第3条): 改为按数组下标配对, 删按 tool_name find —
  //   后端保证 tool_result[i] ↔ action.tools[i] 严格对齐(tool_runner 按下标回填 + zip_longest 位置配对, 文档[8]§3.4),
  //   按名 find 在并行同名工具(如两个 read)时两个子行都命中首个 → 串味显示别人的结果。
  const getResultForIndex = (
    idx: number
  ): Record<string, unknown> | undefined => results[idx];
  // 每工具结果行文本（按数组下标配对, 2026-10-04）
  // 2026-10-12 小欧 - content 一句一行替代 summary：后端保证 content 行数 == tool_result 元素数
  //   且同序；空 content 即无文本（不回落 summary，禁 backward）— 小欧-2026-10-12
  const contentLines = observations.flatMap((obs) => {
    const c = (obs as ExecutionStep | undefined)?.content;
    return typeof c === 'string' && c ? c.split('\n') : [];
  });
  const getResultLine = (i: number): string => contentLines[i] ?? '';
  const getResultStatus = (
    i: number
  ): 'success' | 'error' | 'warning' | undefined => {
    const r = getResultForIndex(i);
    if (!r) return undefined;
    const llm = (r.llm_data || r.llmData) as
      | Record<string, unknown>
      | undefined;
    const status = (llm?.status || {}) as Record<string, unknown>;
    const code = status.exec_code as string;
    return ['success', 'error', 'warning'].includes(code)
      ? (code as 'success' | 'error' | 'warning')
      : undefined;
  };
  const retryCount = action.action_retry_count;
  const attemptLabel =
    retryCount != null && retryCount > 0 ? `(重试${retryCount})` : '';

  return (
    <div
      className={highlight ? 'hitl-border' : undefined}
      style={{
        fontSize: FontSize.PRIMARY,
        color: Colors.TEXT.PRIMARY,
        lineHeight: `${FontSize.PRIMARY + Spacing.XS}px`,
        // 2026-09-03 小欧 修复: minHeight 占位稳定高度, 动画与子行切换(0行→N行/整批涌入)不引起页面高度突变晃动
        minHeight: 32,
        margin: stepMargin(false),
        // 2026-10-07 小欧 - 左内边距 10 → 0(北京老陈: 缩进不好看/图标列不许犬牙交错)。
        //   原 `4/6/4/10` 的左侧 10px 使本行图标盒左比 .thinking-stream(推理内容行)右移 10px,
        //   实测两列盒左 25 vs 15 → 图标左边缘锯齿。垂直内边距(4/6)保留不动。
        padding: `${Spacing.XS}px ${Spacing.SM}px ${Spacing.XS}px 0px`,
        borderRadius: highlight ? 6 : 0,
        // 13.10.4: 常态去掉自带左线(去双线, 容器总轴线唯一); HITL 高亮态 THIN 黄线保留
        borderLeft: highlight
          ? `${BorderWidth.THIN}px solid ${Colors.WARNING}`
          : undefined,
        background: highlight ? Colors.WARNING_BG : 'transparent',
      }}
    >
      {/* 2026-09-01 小欧(北京老陈定案: 完全独立展开+独立观察): 第一行集合行纯文本展示, 无全局展开按钮; 每工具子行独立展开/收起, 点子行任意位置toggle该工具; 展开区只显示该工具完整observation(ToolResultRenderer), 不再有"参数:全集"重复 */}
      <div>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: Spacing.SM,
          }}
        >
          <GearIcon />
          {firstLine} {attemptLabel}
        </span>
        {/* 2026-09-03 小欧(北京老陈定案): 摘要头先显; action 等待期摘要头下同容器挂齿轮+扳手组合动画; 工具子行(参数+结果+展开)等 observation 到达(全部N个结果一起)才渲染; 单/并行统一 */}
        <div style={{ marginTop: Spacing.XS }}>
          {/* 执行等待动画(results 空=action 已到未执行完); observation 到即卸载, 同容器被子行盖住 */}
          {/* 2026-09-03 小欧 修复: 动画仅 tools 非空且结果未达(results空)显示; 超时降级灰字提示; tools 空/结果空显占位防空壳 */}
          {!hasResult && tools.length === 0 && deniedCount === 0 && (
            <span
              style={{ color: Colors.ORANGE_RED, fontSize: FontSize.SECONDARY }}
            >
              工具调用无结果(已全部被安全拦截或未返回)
            </span>
          )}
          {!hasResult &&
            tools.length > 0 &&
            interrupted &&
            deniedCount === 0 && (
              <span
                style={{
                  color: Colors.ORANGE_RED,
                  fontSize: FontSize.SECONDARY,
                }}
              >
                未执行：未获用户允许／被安全拦截／确认超时
              </span>
            )}
          {!hasResult && tools.length > 0 && !interrupted && !replay && (
            <ToolWaitingIcon
              waitClock={waitClock}
            /> /* 2026-09-17 小欧: 齿轮与钟面并存(追加) — 小欧-2026-09-17 */
          )}
          {/* 工具子行(results 非空); observation 到 → 子行在同容器盖住动画位置 */}
          {hasResult && tools.length === 0 && (
            <span
              style={{
                color: Colors.TEXT.SECONDARY,
                fontSize: FontSize.SECONDARY,
              }}
            >
              收到 {results.length || 1} 条观察结果但无工具定义
            </span>
          )}
          {hasResult &&
            tools.length > 0 &&
            tools.map((t, i) => {
              // 2026-10-13 小欧 - 文档[29]§3.3: 只传原始入参, 序列化/格式化下沉到子组件(SLAP) — 小欧 2026-10-13
              const paramEntries = Object.entries(
                (t.params ?? {}) as Record<string, unknown>
              );
              const sum = getResultLine(i);
              const st = getResultStatus(i);
              const isOpen = !!expanded[i];
              const _resForTool = getResultForIndex(i);
              const singleResult = _resForTool ? [_resForTool] : [];
              const singleStep = {
                ...(obsStep as ExecutionStep),
                tool_result: singleResult,
              };
              const toggleTool = () => {
                setExpanded((prev) => {
                  const next = [...prev];
                  next[i] = !prev[i];
                  return next;
                });
              };
              // 2026-10-13 小欧 - 浮层开合(DC-07 单例互斥 + DC-18 不牵连 expanded) — 小欧 2026-10-13
              const onPanelOpenChange = (o: boolean) =>
                setOpenPanelIndex(o ? i : null);
              const closePanel = () => setOpenPanelIndex(null);
              return (
                <div
                  key={t.tool ? `${t.tool}-${i}` : `tool-${i}`}
                  style={{ marginTop: Spacing.XS }} // 2026-10-07 小欧 - 删 paddingLeft: Spacing.SM 缩进
                  //   (北京老陈: 缩进不好看): 工具子行图标与标题行图标同列, 左边缘/盒子/文字起始x 全对齐 — 小欧-2026-10-07
                >
                  <div
                    role="button"
                    tabIndex={0}
                    aria-expanded={isOpen}
                    style={{ cursor: 'pointer' }}
                    onClick={toggleTool}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggleTool();
                      }
                    }}
                  >
                    {/* 水滴图标+工具名+结果摘要：左右对齐 */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: Spacing.SM,
                      }}
                    >
                      {/* 水滴图标：成功绿/失败红/警告黄(尺寸走 Icon.BOX, 与标题行图标同列同宽) */}
                      <DropletIcon status={st ?? 'success'} />
                      {/* 工具名：左列 */}
                      <span
                        style={{ color: Colors.TEXT.PRIMARY, flexShrink: 0 }}
                      >
                        {t.tool}
                      </span>
                      {/* 结果摘要：右列, flexGrow 填满
                          2026-10-04 小欧 文档[8]§5.4.2 第1条: 删 sum.slice(0,60) 硬截(半句切断) — 小欧 2026-10-04
                          2026-10-13 北京老陈裁定: 摘要**不许截断**, 长了折行完整显示。
                            原为 CSS 单行省略(overflow:hidden + textOverflow:ellipsis + whiteSpace:nowrap),
                            与「参数区不许截断」口径不一致(同屏两行文字一个截一个不截), 现统一折行。 */}
                      {sum && (
                        <span
                          style={{
                            color: Colors.TEXT.SECONDARY,
                            flexGrow: 1,
                            // flex 内折行必需: minWidth:0 允许收缩, 否则长内容会撑破工具行
                            minWidth: 0,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            fontSize: FontSize.SECONDARY,
                          }}
                        >
                          {sum}
                        </span>
                      )}
                      {/* 展开箭头 */}
                      <CircleArrow
                        size={16}
                        color={Colors.TEXT.PRIMARY}
                        expanded={isOpen}
                        animated={false}
                      />
                      {/* 2026-10-13 小欧 - 文档[29]§3.6/D-6/D-7 + R2 订正(第八轮核查):
                          浮层参数按钮固定在工具行行尾(D2 乙); trigger 传 ['click'] 去掉悬停弹出与 B5 首击被吃(D-7);
                          R2 根因订正: .taskinfo-entry 自身 display:inline-flex + min-width:32px(index.css:253-259)
                          自带下限, 按钮不会被挤没; 真正被压缩的是 FloatingEntry 最外层**无类名 block div**
                          (:55-62), 压缩后按钮盒外溢、热区与视觉错位, 故外裹一层 flexShrink:0 保住外层盒子
                          (超出视口部分由右栏 overflowX:hidden 裁剪 SessionLayout.tsx:99,126);
                          文案「浮层参数」避开与展开区撞名(D3), 图标用 CodeOutlined 不用 GearIcon(语义=等待中 DC-22);
                          2026-10-13 小欧 - **订正本段早期结论**: 曾写"FloatingEntry 自带 stopPropagation 故置于此安全",
                          该假设不成立 —— Popover content 是 portal 的, React 事件按组件树冒泡, 路径不经过 trigger,
                          点浮层内 ✕ 会直达下面工具行 onClick={toggleTool} 连带展开 JSON 树(已实测复现)。
                          现由 FloatingEntry 在卡片根统一拦截(FloatingEntry.tsx:95), 宿主行无需再各自设防 */}
                      <span style={{ flexShrink: 0, display: 'inline-flex' }}>
                        <FloatingEntry
                          open={openPanelIndex === i}
                          onOpenChange={onPanelOpenChange}
                          placement="bottomRight"
                          trigger={['click']}
                          cardId={`params-panel-${t.tool ?? 'tool'}-${i}`}
                          ariaLabel={`${t.tool} 参数`}
                          cardStyle={PARAMS_CARD_STYLE}
                          content={
                            <ParamsPanel
                              toolName={t.tool ?? 'tool'}
                              params={
                                (t.params ?? {}) as Record<string, unknown>
                              }
                              onClose={closePanel}
                            />
                          }
                        >
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: Spacing.XS,
                              // 2026-10-13 小欧 - B4 决策: 字号锁定 SECONDARY(12), 与**同行**摘要 12px 同层
                              //   (就近基准)。系统另两档: G6 MetricItem label=11/数值=12、G8=10;
                              //   若改 10/11 会比旁边摘要小一号、视觉失衡, 故取 12
                              fontSize: FontSize.SECONDARY,
                              // 2026-10-13 小欧 - 八轮核查 + 九轮复核: .taskinfo-entry 硬写 color:#999 / hover #1677ff
                              //   (index.css:261,269), 直接内联硬色会**压掉 hover 反馈**(内联优先级高于 class)
                              //   → 照搬系统既有机制(MetricItem.tsx:56-58 同款): color 走 CSS 变量,
                              //   .taskinfo-entry:hover 注入 --taskinfo-entry-active 即覆盖, 无 !important。
                              //   关闭回落 SECONDARY、打开回落 PRIMARY(DC-12/T20), hover 仍变蓝与 G6/G8 一致
                              color: `var(--taskinfo-entry-active, ${
                                openPanelIndex === i
                                  ? Colors.PRIMARY
                                  : Colors.TEXT.SECONDARY
                              })`,
                            }}
                          >
                            {/* 2026-10-13 小欧 - 八轮核查: .taskinfo-entry[data-open='true'] svg 会 rotate(180deg)
                                  (index.css:272-274, 为 G6/G8 单图标入口设计), 本按钮 svg 会被翻转 → 内联压制,
                                  不改共享 CSS 以免影响 G6/G8(T35) */}
                            <CodeOutlined style={{ transform: 'none' }} />
                            浮层参数
                          </span>
                        </FloatingEntry>
                      </span>
                    </div>
                  </div>
                  {/* 2026-10-13 小欧 - 文档[29]§4.6.7/§2.7 I1 + D-1: 参数区**移出** role="button",
                      点节点不再误折叠整行(B1 结构性根治), 故无需 stopPropagation 补丁;
                      顶层键默认折叠 → 高度恒 (键数+1)×16px(C1/C2 根治) — 小欧 2026-10-13 */}
                  {isOpen && <ParamsTree entries={paramEntries} />}
                  {/* 展开区：该工具完整 observation */}
                  {isOpen && (
                    <div
                      style={{
                        marginTop: Spacing.XS - 2,
                        paddingLeft: Spacing.SM,
                      }}
                    >
                      {typeof obsStep?.tool_result === 'string' ? (
                        obsStep.tool_result ? (
                          <CollapsibleText
                            text={obsStep.tool_result as string}
                          />
                        ) : null
                      ) : singleResult.length > 0 ? (
                        <ToolResultRenderer step={singleStep} />
                      ) : null}
                      {/* 2026-10-04 小欧 文档[8]§4.1.4: 原两处兜底 CollapsibleText(text=obsStep.content),
                          该字段恒等于 summary 副本(名不副实, 正文真身是 tool_result[i].data_text), 已随 sseParser 一并删除;
                          无结果时不再渲空折叠块 — 小欧-2026-10-04 */}
                    </div>
                  )}
                </div>
              );
            })}
          {/* 2026-09-06 小欧 B2(6.4, 北京老陈裁定): 被拒工具点名橘红灰字行——tools.map 之后收尾(有结果时),
            全拒无结果时独立成行; 与执行工具子行同缩进/分支线, reason=拒绝理由链(用户拒绝/拦截/超时) — 小欧-2026-09-06 */}
          {deniedCount > 0 &&
            deniedList.map((d) => {
              // 2026-09-17 小欧 会审V3(#8): 由模块级常量映射取标签/图标(不再每次渲染重建) — 小欧-2026-09-17
              const rejectLabel =
                REJECT_LABEL_MAP[d.reject_type ?? ''] ?? REJECT_DEFAULT_LABEL;
              const rejectIcon =
                REJECT_ICON_MAP[d.reject_type ?? ''] ?? REJECT_DEFAULT_ICON;
              return (
                <div
                  key={`denied-${d.tool}`}
                  style={{ marginTop: Spacing.XS }} // 2026-10-07 小欧 - 删 paddingLeft: Spacing.SM 缩进,
                  //   被拒工具行的图标同样归入统一图标列 — 小欧-2026-10-07
                >
                  <div
                    style={{
                      fontSize: FontSize.PRIMARY,
                      lineHeight: `${FontSize.PRIMARY + Spacing.XS}px`,
                      display: 'flex',
                      alignItems: 'center',
                      gap: Spacing.SM,
                    }}
                  >
                    {/* 图标：橘红色 antd SVG */}
                    <span
                      style={{
                        color: Colors.ORANGE_RED,
                        fontSize: FontSize.PRIMARY,
                      }}
                    >
                      {rejectIcon}
                    </span>
                    {/* 标签：橘红色小字 */}
                    <span
                      style={{
                        color: Colors.ORANGE_RED,
                        fontSize: FontSize.SECONDARY,
                        fontWeight: FontWeight.MEDIUM,
                      }}
                    >
                      [{rejectLabel}]
                    </span>
                    {/* 工具名：深色加粗 */}
                    <span
                      style={{
                        color: Colors.TEXT.STRONG,
                        fontWeight: FontWeight.MEDIUM,
                      }}
                    >
                      {d.tool}
                    </span>
                    {/* 未执行+原因：灰色弱化 */}
                    <span
                      style={{
                        color: Colors.TEXT.SECONDARY,
                        fontSize: FontSize.SECONDARY,
                      }}
                    >
                      未执行：{d.reason}
                    </span>
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
};

export { ToolCallLine };
