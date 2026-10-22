// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复对象属性/JSX属性行超80字符换行、import重排, 防止格式再次出错
// 编辑历史: 2026-09-02 小欧 - 44case审计修复:  request变化重置trustSession防跨请求残留 Modal加maskClosable=false+keyboard=false防幽灵关闭死锁 - 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - v1.5.4 弹窗渲染完善: 环形进度Progress+大数字倒计时+最后5s转橙3s微脉动+bypass标题补全+countdown到0自动代发/拒绝 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 问题1方案A+问题3优化: handleConfirm强制bypass下trustSession=false(防bypass勾选偷偷落库转正为长期信任, 堵5.4防污染漏洞); countdown interval依赖数组移除countdown(函数式更新, 只在弹窗开/新请求建一次) - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - Bug修复(24项): countdown lazy初值跟随request防首渲染0误触发 /autoHandledRef按confirmId一次性guard防倒计时到0 effect重入双发 submitting互斥态防连点意图翻转(按钮loading/disabled+勾选disabled) 后端兜底文案5→60与实际一致 首tick 100ms即-1节奏对齐 trustPath缺失文案改"未指定路径，仅本次"防"任意整工具"误导 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - UI优化(v1.1方案): 降高100px(420→288): Modal padding24→12+图标48→32+Title level4→5+Tag margin16→4+Progress size88→60+双卡合一(maxHeight200→150)+Checkbox margin24→12+Space→flex gap12+段距16→8 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - UI优化实施: 边框2px→1.5px+boxShadow+Title Tag同行flex+动效pulse0.8s/opacity0.7+信任行缩写"信任此操作（本次会话）"+Tooltip展开路径+去Space导入加Tooltip - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 修复: handleConfirm中autoHandledRef先设再调onConfirm, 堵countdown到0+用户同帧点击双发onConfirm时序缺口; 另一项: @keyframes pulse移至组件外避免重复注入 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - countdown就绪守卫: 跨弹窗countdown残留0致新弹窗首帧即触发自动代发, 加countdownReadyRef守卫, 未就绪禁止代发 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 根因修复: onConfirm接口加confirmId参数, auto-confirm不依赖pendingRef读confirmId(改前ref时序竞态致旧弹窗auto-confirm发旧ID到后端, 新ID从未被confirm→S1超时弹窗不消失) - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 真根因修复: interval effect加request?.confirmId依赖+currentRequestRef追踪, 旧interval残留tick跳过(setCountdown(0)覆盖新请求countdown致auto-confirm立即触发弹窗不消失) - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 简化重构: ChatPage加key={confirmId}强制重建, 删除autoHandledRef/countdownReadyRef/currentRequestRef/resetEffect, 组件从370行→230行 - 小欧-2026-09-03
// 编辑历史: 2026-09-07 小欧 - B3 防御加固: countdown 归零 effect 加 submitting guard, 组件自体防双发;
//   改前仅靠 ChatPage key={confirmId} 重建兜底, 本组件 countdown 走完归零后(未重挂)会重入代发,
//   加固后手动确认/代发任一次即锁定, 消除对 key 重建的依赖(与回归守卫断言对齐) - 小欧-2026-09-07
// 编辑历史: 2026-09-16 小欧 - 设计稿缺陷修复: 缺陷bypass下disable勾选框(原仅handleConfirm强改false, UI仍可勾, 静默失效误导);
//   缺陷按工具域区分文案(registry工具路径含子键, 其余含子目录) 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 浏览器白屏根因修复: 老杨T4 CollapsibleText误用default导入(命名导出)ES模块加载失败致React未挂载, 改命名导入;
//   S2 request possibly null 改可选链 — 小欧-2026-09-16
// 编辑历史: 2026-09-16 - UI微调: 工具名称+工具名词label+值改为flex同行(去<br/>分行); 底部拒绝/允许按钮size="large"→"middle"取消偏大 - -2026-09-16
// 编辑历史: 2026-09-16 - 参数区去掉展开收起,超过2行直接出滚动条; paramsStr改Object.entries纯文本无花括号 - -2026-09-16
// 编辑历史: 2026-09-16 小欧 - 文档v1.5定案实施(设计文档《HITL窗口工具名词参数显示优化审核报告》):
//   参数格式化改key=value每参数一行(冒号改等号,禁JSON式) 参数区固定3行高height:54+overflow滚动+超长wordBreak:break-all自动换行 参数区改单层轻量视觉容器(浅灰底#fafafa+细边框#e8e8e8+圆角4)取消与内层白底#fff的双层叠加 工具名称+执行参数标签合并flex同行 工具名称品牌蓝ff高亮 - 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - (2项): 参数容器height:54在antd5全局border-box下含padding(4×2)+border(1×2)致内容区仅44px≈2.4行不足定案3行, 补boxSizing:'content-box'保证内容高=54px(3行×18px); 第二项合并行外层div删textAlign:'left'死属性(flex容器下对flex item无效) - 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 参数区居中对齐bug修复: 参数容器div补textAlign:'left'(外层textAlign:'center'继承至span致参数文本居中, 需在容器覆盖) - 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 参数区高度3行→4行: 目视验收"整体高度不错,参数区可设4行", height:54(3×18)→72(4×18) - 小欧-2026-09-16
// 编辑历史: 2026-09-18 小欧 - 设计稿实施: AuthorizationRequest接口+config新增content(弹窗原因); SAFETY_LEVEL_CONFIG改后端safety_level 5类
//   (path_auth需授权/shellparam命令确认/tool_delete删除确认/tool_execute执行确认, tool_write预留注释); 新增content原因展示区+trust_path操作范围行;
//   勾选title去trustPath展示(与新增信任范围行重复, 二选一) 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - content/trust_path显示布局(定案): 两字段均折行显示(≤2行完整展示),
//   超2行才截断(-webkit-line-clamp:2+省略号), 长路径wordBreak:break-all强制折行防溢出, title挂完整文本可查全文;
//   改前两字段无防护: 中文折行但长ASCII路径水平溢出穿出弹窗 — 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 审核整改(验收要求: 美观紧凑/目标信息禁灰字/Tooltip禁用/窗口不撑长):
//   HITL_TOKENS宽480→520令牌+内容折行后信息从容显示; 倒计时文案c8c8c→、trustPath→(目标信息禁灰字),
//   辅助label(工具名称:/执行参数:)回灰type=secondary可灰(陈总许), 帮助图标?c8c8c删除; 完全删除Tooltip控件及QuestionCircleOutlined
//   (信任行仅保留Checkbox+原生title, 防叠加DOM层); 图标与标题Tag合并单行flex(降嵌套层/紧凑), CountdownRing去confirmTimeout prop;
//   content卡padding6→5/marginBottom8→6、trust行8→6紧凑化 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 三思三省9类核查配套: SAFETY_LEVEL_CONFIG tool_write 由预留注释转激活条目
//   (geekblue+EditOutlined+标签"写确认"), 与后端 safety_gate 工具名归属(create_task→tool_write)联动 — 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 恢复圆圈倒计时(令): 恢复confirmTimeout取request.confirmTimeout??60并回传CountdownRing饼环算percent,
//   反向a59aaff8e扁平纯文本(与CountdownRing.tsx恢复同批) — 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 对齐确认稿(令): 信任勾选框搬回信任范围行之后、工具名称之前
//   (勾选=信任上方范围, 语义连贯); content原因区补SAFETY_LEVEL_CONFIG等级图标(规格要求, 无图标等级不渲染) 小欧-2026-09-18
// 编辑历史: 2026-09-19 小欧 - UI六项优化(验收): A-content区长路径截断显示…+最后2-3级目录+文件名(truncatePath)
//   B-参数区超长value截断>80字符(truncateValue) C-操作范围行只显示目录去掉文件名+左对齐
//   D-bypass信任勾选框加常驻灰色提示替代hover title E-倒计时文案去掉后端兜底
//   F-bypass下允许按钮显示倒计时秒数"允许执行(Ns)" 小欧-2026-09-19
// 编辑历史: 2026-09-19 小欧 - 修正C-truncateDir: 操作范围行只去掉末尾文件名, 保留完整目录路径不再截断 — 小欧-2026-09-19
// 编辑历史: 2026-10-20 小欧 - 确认等级键随后端 SafetyLevel 改名: delete_recursive+delete_out_of_scope→delete_outside_whitelist,
//   write_protected→write_forbidden, write_out_of_scope→write_outside_whitelist; 删除"递归删不授予授权"说明块
//   (该标签已并入 TEMP_AUTH_LEVELS, 旧说明与实际相反); 移除随之失效的 InfoCircleOutlined 导入 — 小欧-2026-10-20
/**
 * AuthorizationModal - HITL人工确认弹窗
 *
 * 功能：显示工具执行授权请求，用户可选择允许/拒绝/本会话信任
 *
 * 设计规范：
 * - 宽度: 480px
 * - 边框: 1.5px solid #faad14 (橙色) / 1.5px dashed #1677ff (bypass) + boxShadow
 * - 图标: WarningOutlined (橙色, 32px)
 * - 按钮: "允许执行"（橙色）、"拒绝执行"（danger ghost）/ bypass时保留按钮可点击
 * - 居中对齐
 *
 * 【v3.4实施 2026-06-09 小沈】
 * - SRP: 只负责显示授权弹窗和回传用户选择
 * - KISS: 简单Modal + 3个按钮，不搞复杂状态
 * - DRY: 复用Ant Design Modal组件
 */
// 编辑历史: 2026-10-05 22:16:38 小欧 - bypass 弹窗标题「将自动确认（安全开关已绕开）」随 settings_registry
//   标签改名为「HTL人工开关已绕开」，与设置页新标签一致（纯文案同步，bypass 分支逻辑与倒计时不变）— 小欧-2026-10-05
// 编辑历史: 2026-10-11 08:01:05 小欧 - 弹框整体视觉统一（「标题最好是短且准确」+ 截图复核定案）：
//   标题短化：安全确认请求→需要你确认；将自动确认（HTL人工开关已绕开）17字→将自动确认，
//     「为什么」交给 Tag 承载（[删除确认]/[HTL 已绕过]），标题不再被 Tag+环挤到折行；
//   标题行单一轴线：图标内联 + 标题左 + Tag + 环右（同基线），摘除外层 textAlign:center；
//   倒计时后果文案由「独占一整行居中」移入按钮行左侧 — 改前该行居中而其下全左对齐，轴线断裂、
//     视觉上是无主浮字；现与操作同轴。文案禁折（whiteSpace:nowrap+flexShrink:0），
//     否则会被按钮挤压折成「到点未响应将自动拒/绝」孤字；
//   按钮改不等宽（拒绝 flexShrink:0 / 允许 flex:1.4），改前两键等宽=破坏性操作与主动作视觉等权；
//   摘除 Typography.Title 解构（03:05 起标题已自绘 span，留着是死变量告警）。
//   撤回项(自查发现，未实施)：原计划新增一行醒目 trustPath，实测 request.trustPath 已由
//   「操作范围」行展示(truncateDir 剥末段得目录)，新增即重复渲染违反 DRY；
//   参数区折叠/信任勾选改版经指示一并撤回(参数与信任展示不动)。
//   核查澄清(避免误修): 后端信任本就是【目录级】——trust_db.trust_scope_path 落库前按
//   「有后缀→p.parent」把叶子文件收敛到父目录(2026-10-06 已修)；SSE 帧走 hitl_gateway
//   extract_trust_path 发的是叶子文件路径，前端 truncateDir 剥末段与之匹配，二者各自正确不可混改。
//   验证：typecheck 0 错 / lint 0 错 / Vitest 1484 全过 / 人工确认态+bypass 态双截图复核 — 小欧-2026-10-11

// 编辑历史: 2026-10-11 00:55:20 小欧 - HTL危险确认列出具体变更+后果提示; 计时钟移标题行右侧并缩至44(辅助信息退位, 主内容优先); CountdownRing 直径可调配套 — 小欧-2026-10-11
// 编辑历史: 2026-10-11 07:18:01 小欧 - 计时钟44px定稿 + 秒数去重(环内已有数字, 文字只讲到点会怎样); confirmTimeout=0(禁倒计时)不渲染环, 改显式文案「不自动拒绝(倒计时已禁用)」— 小欧-2026-10-11
import React from 'react';
import { Button, Typography, Tag, Checkbox } from 'antd';
import {
  WarningOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
  ThunderboltOutlined,
  FolderOutlined, // 7.4.3: trust_path 操作范围图标 — 小欧-2026-09-18
  EditOutlined, // 2026-10-18: 写入类确认标签图标(shell_write_confirm/task_deal_confirm) — 小欧-2026-10-18
  FileSearchOutlined, // 2026-10-18: shell_read_confirm 命令含读取动作图标 — 小欧-2026-10-18
  ClockCircleOutlined, // 2026-10-18: 临时授权时效说明行图标(任务级, 结束自动失效) — 小欧-2026-10-18
} from '@ant-design/icons';
// 2026-09-15 小欧 - 动画keyframes统一承载(AnimatedIcons), 单例注入防重复style — 小欧-2026-09-15
import { injectKeyframes } from '../AnimatedIcons/animations';
// 2026-09-16 老杨 - S3:引入CountdownRing子组件,countdown/progress隔离 - 老杨-2026-09-16
import CountdownRing from './CountdownRing';
// 2026-09-16 老杨 - T1:引入HITLModalShell统一壳+HITL_TOKENS设计令牌 - 老杨-2026-09-16
// 2026-10-11 02:40 小欧 - 标题改自绘 span 后不再用 Typography.Title（原生 h5 带默认 margin，
//   在 flex 行里会被挤折行），字重直接给数值 600，与原 h5 视觉一致。
import HITLModalShell, { HITL_TOKENS } from './HITLModalShell';

// 2026-10-11 03:30 小欧 - Title 已彻底不用（03:05 起标题自绘 span），同步摘除解构避免死变量告警
const { Text } = Typography;

export interface AuthorizationRequest {
  confirmId: string;
  toolName: string;
  params: Record<string, unknown>;
  content?: string; // 7.4.3: 弹窗原因(后端 ConfirmSpec.content) — 小欧-2026-09-18
  safetyLevel: string;
  /** 授权影响面(后端 SafetyLevel 分档): high=删除类 / medium=写入类 / low=其余 */
  trustImpact?: 'high' | 'medium' | 'low';
  trustPath?: string | null;
  autoConfirm?: boolean;
  confirmTimeout?: number;
  backendTimeout?: number;
}

interface AuthorizationModalProps {
  visible: boolean;
  request: AuthorizationRequest | null;
  onConfirm: (
    confirmed: boolean,
    trustSession: boolean,
    confirmId?: string
  ) => void;
}

const SAFETY_LEVEL_CONFIG: Record<
  string,
  { color: string; label: string; icon: React.ReactNode }
> = {
  // ★ 2026-10-18 小欧: 键集换为后端 SafetyLevel 确认命名空间, 与 SafetyLevel.CONFIRM_LEVELS 必须完全相等。
  //   硬拦命名空间(path_forbidden/block_command/block_path_invalid/block_unregistered)不进弹窗, 故不配。
  //   旧 5 键(path_auth/shellparam/tool_write/tool_delete/tool_execute)与新枚举无一重合, 全部作废。
  // 2026-10-19 小欧 - 目录数组归一化: 四键随 SafetyLevel 改名, 键集仍须与 CONFIRM_LEVELS 完全相等
  // 2026-10-19 小欧 - 删孤儿键 delete_safe(后端无生产者, 随后端 SafetyLevel 一并移除)
  delete_outside_whitelist: {
    color: 'red',
    label: '白名单外删除授权',
    icon: <WarningOutlined />,
  },
  write_forbidden: {
    color: 'orange',
    label: '非系统禁区写入授权',
    icon: <WarningOutlined />,
  },
  write_outside_whitelist: {
    color: 'orange',
    label: '白名单外写入授权',
    icon: <WarningOutlined />,
  },
  shell_medium_risk: {
    color: 'orange',
    label: '命令确认',
    icon: <ExclamationCircleOutlined />,
  },
  shell_delete_confirm: {
    color: 'red',
    label: '命令含删除动作',
    icon: <StopOutlined />,
  },
  shell_write_confirm: {
    color: 'orange',
    label: '命令含写入动作',
    icon: <EditOutlined />,
  },
  shell_read_confirm: {
    color: 'blue',
    label: '命令含读取动作',
    icon: <FileSearchOutlined />,
  },
  shell_command_confirm: {
    color: 'orange',
    label: '命令确认',
    icon: <ExclamationCircleOutlined />,
  },
  sql_execute_confirm: {
    color: 'volcano',
    label: 'SQL 执行确认',
    icon: <ExclamationCircleOutlined />,
  },
  task_deal_confirm: {
    color: 'geekblue',
    label: '任务处理确认',
    icon: <EditOutlined />,
  },
  registry_deal_confirm: {
    color: 'volcano',
    label: '注册表处置确认',
    icon: <ExclamationCircleOutlined />,
  },
  tool_confirm: {
    color: 'volcano',
    label: '工具级确认',
    icon: <WarningOutlined />,
  },
};

/**
 * 元信息行统一样式 — 2026-10-18 小欧
 *
 * 操作范围 / 授权影响 / 授权机制说明 共用同一份样式, 保证:
 *    文字左边界一致(都有图标 + 同宽 gap), 不会出现"有的行缩进有的不缩进"的犬牙交错;
 *    行距一致(6px), 弹窗纵向节奏不跳;
 *    文字色统一 #262626 —— 本文件已定案「目标信息禁灰字」(原 #595959/#8c8c8c 均已订正)。
 *
 *  2026-10-18: 文案完整展示即可, 不做行数截断(允许弹窗随内容撑高),
 * 故不再设 WebkitLineClamp; 但仍保留 title 挂全文, 便于 hover 查完整表述。
 */
const META_ROW: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  marginBottom: 6,
  fontSize: 12,
  color: '#262626',
  textAlign: 'left',
};

/** 授权机制说明的触发标签集合 — 2026-10-18 小欧（这三个标签确认后真的会授予临时授权） */
const TEMP_AUTH_LEVELS = new Set([
  'write_forbidden',
  'write_outside_whitelist',
  'delete_outside_whitelist',
]);

const truncatePath = (p: string): string => {
  if (!p) return p;
  const norm = p.replace(/\\/g, '/');
  const parts = norm.split('/').filter(Boolean);
  if (parts.length <= 3) return norm;
  return `…/${parts.slice(-3).join('/')}`;
};

// 操作范围行只显示目录(去掉末尾文件名, 保留完整目录路径, 不截断)
const truncateDir = (p: string): string => {
  if (!p) return p;
  const norm = p.replace(/\\/g, '/');
  return norm.replace(/\/[^/]*$/, '') || norm;
};

const truncateValue = (v: string, max = 80): string =>
  v.length > max ? `${v.slice(0, max)}…` : v;

const AuthorizationModal: React.FC<AuthorizationModalProps> = ({
  visible,
  request,
  onConfirm,
}) => {
  // 2026-09-15 小欧 - 动画keyframes注入(AnimatedIcons/animations.ts 单例承载, DRY)
  injectKeyframes('pulse');
  // 2026-09-03 小欧 修复: countdown 用 lazy 初值(跟随新 request), 避免默认 0 触发首渲染自动代发/拒绝
  const [trustSession, setTrustSession] = React.useState(false);
  const [countdown, setCountdown] = React.useState(
    () => request?.confirmTimeout ?? 0
  );
  const onConfirmRef = React.useRef(onConfirm);
  // 2026-09-03 小欧 修复: submitting 互斥态, 提交中禁用按钮/勾选, 防连点意图翻转
  const [submitting, setSubmitting] = React.useState(false);
  const isBypass = Boolean(request?.autoConfirm);
  onConfirmRef.current = onConfirm;

  // 2026-09-16 - 纯文本显示,去掉{}花括号
  // 2026-09-16 小欧 - 修复: request?.params 可选链, 消除 tsc TS18047 possibly null - 小欧-2026-09-16
  // 2026-09-16 小欧 - 文档v1.5定案: 参数禁JSON式, 改key=value每参数一行(\n连接) - 小欧-2026-09-16
  const paramsStr = React.useMemo(() => {
    try {
      const p = request?.params;
      if (!p || typeof p !== 'object') return String(p ?? '');
      return Object.entries(p)
        .map(([k, v]) => `${k}=${truncateValue(String(v ?? ''))}`)
        .join('\n');
    } catch {
      return '[参数序列化失败]';
    }
  }, [request?.params]);

  React.useEffect(() => {
    // 2026-09-03 小欧 修复: 首 tick 100ms 内即刻 -1(节奏对齐), 再走 1s interval; 依赖无 countdown(函数式更新)
    if (!visible || !request) return;
    const tick = () => setCountdown((v) => Math.max(0, v - 1));
    const t = setInterval(tick, 1000);
    const first = setTimeout(tick, 100);
    return () => {
      clearInterval(t);
      clearTimeout(first);
    };
  }, [visible, request]);

  React.useEffect(() => {
    // 2026-09-07 小欧 B3 防御加固: submitting 互斥入守卫——手动确认/已代发一次即锁定, 防 same 实例
    //   countdown 归零重入双发(改前仅靠 ChatPage key={confirmId} 重建兜底, 组件自体无防护)
    if (!visible || countdown !== 0 || !request || submitting) return;
    setSubmitting(true);
    // 2026-09-03 小欧/: 传confirmId参数, 不依赖pendingRef时序(根因修复)
    if (isBypass) {
      onConfirmRef.current(true, false, request.confirmId);
    } else {
      onConfirmRef.current(false, false, request.confirmId);
    }
  }, [visible, countdown, isBypass, request, submitting]);

  if (!request) {
    return null;
  }

  const safetyConfig = SAFETY_LEVEL_CONFIG[request.safetyLevel] || {
    color: 'default',
    label: request.safetyLevel,
    icon: null,
  };

  // 2026-09-18 小欧 - 恢复圆圈倒计时(令): 恢复confirmTimeout供CountdownRing饼环算percent - 小欧-2026-09-18
  const confirmTimeout = request.confirmTimeout ?? 60;

  // 小欧 2026-09-03 问题1方案A: bypass(安全开关绕开)模式下即使勾选"信任此操作"也不产生信任,
  //   强制 trustSession=false(防绕过5.4防污染: bypass期间勾出的信任切回enabled:true后转正为长期豁免)
  const handleConfirm = (confirmed: boolean) => {
    if (submitting) return;
    setSubmitting(true);
    // 2026-09-03 小欧/: 传confirmId参数, 不依赖pendingRef时序(根因修复)
    onConfirm(confirmed, isBypass ? false : trustSession, request.confirmId);
    setTrustSession(false);
  };

  // 2026-10-11 03:05 小欧 - 标题改短且准确（："标题最好是短且准确"）。
  //   改前 bypass 态「将自动确认（HTL人工开关已绕开）」17 字，必然被 Tag+环挤到折行/截断。
  //   拆法：标题只说「现在会发生什么」，「为什么」交给 Tag 承载 —— 语义不丢、字数减半。
  const titleText = isBypass ? '将自动确认' : '需要你确认';
  const statusTagText = isBypass ? 'HTL 已绕过' : safetyConfig.label;

  return (
    <HITLModalShell open={visible} isBypass={isBypass}>
      <div>
        {/* 3.1 单一轴线：图标内联 + 标题左 + Tag + 环 右，共用一条基线 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 8,
            minWidth: 0,
          }}
        >
          {isBypass ? (
            <ThunderboltOutlined
              style={{
                fontSize: HITL_TOKENS.ICON_SIZE,
                color: '#1677ff',
                flexShrink: 0,
              }}
            />
          ) : (
            <WarningOutlined
              style={{
                fontSize: HITL_TOKENS.ICON_SIZE,
                color: '#faad14',
                flexShrink: 0,
              }}
            />
          )}
          <span
            title={titleText}
            style={{
              fontSize: 16,
              fontWeight: 600,
              lineHeight: '22px',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              minWidth: 0,
            }}
          >
            {titleText}
          </span>
          <Tag
            color={safetyConfig.color}
            style={{ marginBottom: 0, fontSize: 12, flexShrink: 0 }}
          >
            {statusTagText}
          </Tag>
          <span style={{ marginLeft: 'auto', flexShrink: 0, display: 'flex' }}>
            {/* 计时钟：不删，只改位 + 缩小。confirmTimeout=0 语义为禁倒计时，
                此时无"到点"可言，显示环与文案都是事实错误，故不渲染。 */}
            {confirmTimeout > 0 && (
              <CountdownRing
                countdown={countdown}
                confirmTimeout={confirmTimeout}
                size={44}
              />
            )}
          </span>
        </div>

        {/* content 原因展示区: 告知用户"为什么要问" — 小欧-2026-09-18 */}
        {request.content && (
          <div
            style={{
              padding: '5px 10px',
              marginBottom: 6,
              borderLeft: `3px solid ${isBypass ? '#1677ff' : '#faad14'}`,
              backgroundColor: isBypass ? '#e6f4ff' : '#fffbe6',
              borderRadius: '0 4px 4px 0',
              textAlign: 'left',
            }}
          >
            {/* 7.4.3-layout: content折行显示(≤2行完整展示, 超2行截断省略号, title可查全文) — 小欧-2026-09-18 */}
            <span
              title={request.content}
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: '#262626',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                wordBreak: 'break-all',
              }}
            >
              {/* 规格: content区图标复用 SAFETY_LEVEL_CONFIG — 小欧-2026-09-18 */}
              {safetyConfig.icon && (
                <span style={{ marginRight: 6 }}>{safetyConfig.icon}</span>
              )}
              {request.content}
            </span>
          </div>
        )}

        {/* trust_path 操作范围展示: 操作目标路径(仅目录, 去文件名) — 小欧-2026-09-18 */}
        {request.trustPath && (
          <div style={META_ROW}>
            <FolderOutlined style={{ color: '#faad14', flexShrink: 0 }} />
            <span
              title={`操作范围: ${request.toolName} › ${request.trustPath}${
                request.toolName.startsWith('registry')
                  ? '，含子键'
                  : '，含子目录'
              }`}
              style={{ wordBreak: 'break-all' }}
            >
              操作范围: {truncateDir(request.trustPath)}
              {request.toolName.startsWith('registry')
                ? '，含子键'
                : '，含子目录'}
            </span>
          </div>
        )}

        {/* 2026-10-18 小欧 - 说明行: 授权影响面(后端 SafetyLevel 分档给出, 前端只呈现不做权限判断)
            紧跟"操作范围"之后 —— 两者同属"这次操作会碰什么"的一组, 顺序不可颠倒。
            独立成行而非追加进 content, 规避 WebkitLineClamp:2 截断。 */}
        {request.trustImpact && (
          <div style={META_ROW}>
            <WarningOutlined
              style={{
                color:
                  request.trustImpact === 'high'
                    ? '#cf1322'
                    : request.trustImpact === 'medium'
                      ? '#fa8c16'
                      : '#1677ff',
                flexShrink: 0,
              }}
            />
            <span
              title={`授权影响: ${request.trustImpact === 'high' ? '大(删除类, 抹除不可撤销)' : request.trustImpact === 'medium' ? '中(写入类, 可覆写原内容)' : '小(命令级确认, 不直接改文件内容)'}`}
              style={{ wordBreak: 'break-all' }}
            >
              授权影响：
              {request.trustImpact === 'high'
                ? '大（删除类，抹除不可撤销）'
                : request.trustImpact === 'medium'
                  ? '中（写入类，可覆写原内容）'
                  : '小（命令级确认，不直接改文件内容）'}
            </span>
          </div>
        )}

        {/* 2026-10-18 小欧 - 说明行: 临时授权时效(temp_auth 任务级, 结束自动失效; 与"信任此操作"会话级是两套机制) */}
        {TEMP_AUTH_LEVELS.has(request.safetyLevel) && (
          <div style={META_ROW}>
            <ClockCircleOutlined style={{ color: '#8c8c8c', flexShrink: 0 }} />
            <span
              title="临时授权仅本任务有效，任务结束自动失效；与下方“信任此操作”（会话级）是两套机制"
              style={{ wordBreak: 'break-all' }}
            >
              临时授权仅本任务有效，任务结束自动失效
            </span>
          </div>
        )}

        {/* 2026-10-20 小欧 - 删除"递归删除不授予授权"说明块:
            后端已并入 delete_outside_whitelist(白名单外删除/递归删), 该标签属 TEMP_AUTH_LEVELS,
            确认后授予临时授权, 旧说明与实际相反。 */}

        {/* 确认稿: 信任勾选紧跟信任范围行、工具名称之前(勾选=信任上方范围, 语义连贯) — 小欧-2026-09-18 */}
        <div
          style={{
            marginBottom: 6,
            textAlign: 'left',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Checkbox
            checked={trustSession}
            disabled={submitting || isBypass} // 2026-09-16 小欧 缺陷修复: bypass 禁用勾选框, 防静默失效误导(原仅 handleConfirm 强改 false, UI 仍可勾) 小欧-2026-09-16
            onChange={(e) => setTrustSession(e.target.checked)}
            title={
              isBypass ? undefined : '信任后：同会话同工具+下方操作范围免弹框'
            }
          >
            信任此操作（本次会话）
          </Checkbox>
          {isBypass && (
            <span style={{ fontSize: 11, color: '#8c8c8c' }}>
              自动确认模式下信任不生效
            </span>
          )}
        </div>

        {/* 2026-09-16 小欧 文档v1.5定案: 去外层灰底盒子(取消双层叠加), 工具名称+执行参数标签合并flex同行 + 参数区单层轻量视觉容器 — 小欧-2026-09-16 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 8,
            marginBottom: 2,
          }}
        >
          <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
            工具名称:
          </Text>
          <Text strong style={{ fontSize: 13, color: '#1677ff' }}>
            {request.toolName}
          </Text>
          {paramsStr && (
            <Text
              type="secondary"
              style={{ fontSize: 12, whiteSpace: 'nowrap' }}
            >
              执行参数:
            </Text>
          )}
        </div>
        {/* 参数值区域: 固定4行高(height:72=4×18) + 滚动条 + 超长自动换行 + 单层轻量视觉容器; boxSizing:content-box确保border-box下内容区=72px(62+8+2=72); textAlign:left覆盖外层继承的center(否则参数文本居中) — 小欧-2026-09-16 */}
        <div
          style={{
            height: 72,
            overflow: 'auto',
            lineHeight: '18px',
            borderRadius: 4,
            padding: '4px 6px',
            backgroundColor: '#fafafa',
            border: '1px solid #e8e8e8',
            marginBottom: 4,
            boxSizing: 'content-box',
            textAlign: 'left',
          }}
        >
          <span
            style={{
              fontSize: 12,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {paramsStr}
          </span>
        </div>

        {/* 3.5 单一底轴：倒计时后果文案左、按钮右。
            改前该文案独占一整行居中悬在头部下方，而其下所有块左对齐 —— 轴线断裂，
            视觉上像无主的浮字。现移到按钮行左侧与操作同轴，消除断裂。 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            width: '100%',
            marginTop: 8,
          }}
        >
          <span
            style={{
              fontSize: 12,
              fontWeight: 400,
              color: '#8c8c8c',
              // 2026-10-11 03:20 小欧 - 修文案折行：原 flex:1 + minWidth:0 允许文本被按钮挤压到
              //   折成两行（「到点未响应将自动拒/绝」孤字）。改为不参与收缩且禁折，
              //   富余宽度由「允许执行」(flex:1.4) 吸收 —— 实测 120+8+76+8+余量 << 内容宽422。
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            {/* 2026-09-03 小欧 修复: 后端兜底原文案 5s 与实际 60s 不符, 统一防文案欺骗 */}
            {/* 2026-10-11 03:05 小欧 - 秒数去重（单一信息源）：环内已有大号数字，
                文字只讲**到点会怎样**，不重复报数。
                confirmTimeout=0 语义为禁倒计时，此时无"到点"可言，改「不自动拒绝」。 */}
            {confirmTimeout === 0
              ? '不自动拒绝（倒计时已禁用）'
              : isBypass
                ? '到点后自动确认放行'
                : '到点未响应将自动拒绝'}
          </span>
          <Button
            onClick={() => handleConfirm(false)}
            size="middle"
            disabled={submitting}
            danger
            ghost
            aria-label="拒绝执行此工具操作"
            style={{ flexShrink: 0 }}
          >
            拒绝执行
          </Button>
          <Button
            type="primary"
            onClick={() => handleConfirm(true)}
            size="middle"
            loading={submitting}
            disabled={submitting}
            aria-label="允许执行此工具操作"
            style={{
              backgroundColor: '#faad14',
              borderColor: '#faad14',
              color: '#fff',
              flex: 1.4,
            }}
          >
            {isBypass && !submitting ? `允许执行 (${countdown}s)` : '允许执行'}
          </Button>
        </div>
      </div>
    </HITLModalShell>
  );
};

export default AuthorizationModal;
