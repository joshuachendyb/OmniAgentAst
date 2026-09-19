// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复对象属性/JSX属性行超80字符换行、import重排, 防止格式再次出错
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①AM-01 request变化重置trustSession防跨请求残留②AM-02 Modal加maskClosable=false+keyboard=false防幽灵关闭死锁 - 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - v1.5.4 弹窗渲染完善: 环形进度Progress+大数字倒计时+最后5s转橙3s微脉动+bypass标题补全+countdown到0自动代发/拒绝 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 三堂会审问题1方案A+问题3优化: ①handleConfirm强制bypass下trustSession=false(防bypass勾选偷偷落库转正为长期信任, 堵5.4防污染漏洞); ②countdown interval依赖数组移除countdown(函数式更新, 只在弹窗开/新请求建一次) - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - Bug修复(24项): ⑪countdown lazy初值跟随request防首渲染0误触发 ⑬/⑲autoHandledRef按confirmId一次性guard防倒计时到0 effect重入双发 ⑰submitting互斥态防连点意图翻转(按钮loading/disabled+勾选disabled) ⑳后端兜底文案5→60与实际一致 ㉑首tick 100ms即-1节奏对齐 ㉘trustPath缺失文案改"未指定路径，仅本次"防"任意整工具"误导 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - UI优化(v1.1方案): 降高100px(420→288): Modal padding24→12+图标48→32+Title level4→5+Tag margin16→4+Progress size88→60+双卡合一(maxHeight200→150)+Checkbox margin24→12+Space→flex gap12+段距16→8 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - UI优化第四章实施: 边框2px→1.5px+boxShadow+Title Tag同行flex+动效pulse0.8s/opacity0.7+信任行缩写"信任此操作（本次会话）"+Tooltip展开路径+去Space导入加Tooltip - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - P1修复: handleConfirm中autoHandledRef先设再调onConfirm, 堵countdown到0+用户同帧点击双发onConfirm时序缺口; P3: @keyframes pulse移至组件外避免重复注入 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - countdown就绪守卫: 跨弹窗countdown残留0致新弹窗首帧即触发自动代发, 加countdownReadyRef守卫, 未就绪禁止代发 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 根因修复: onConfirm接口加confirmId参数, auto-confirm不依赖pendingRef读confirmId(改前ref时序竞态致旧弹窗auto-confirm发旧ID到后端, 新ID从未被confirm→S1超时弹窗不消失) - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 真根因修复: interval effect加request?.confirmId依赖+currentRequestRef追踪, 旧interval残留tick跳过(setCountdown(0)覆盖新请求countdown致auto-confirm立即触发弹窗不消失) - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 简化重构: ChatPage加key={confirmId}强制重建, 删除autoHandledRef/countdownReadyRef/currentRequestRef/resetEffect, 组件从370行→230行 - 小欧-2026-09-03
// 编辑历史: 2026-09-07 小欧 - B3 防御加固: countdown 归零 effect 加 submitting guard, 组件自体防双发;
//   改前仅靠 ChatPage key={confirmId} 重建兜底, 本组件 countdown 走完归零后(未重挂)会重入代发,
//   加固后手动确认/代发任一次即锁定, 消除对 key 重建的依赖(与回归守卫 BUG-13/BUG-11 断言对齐) - 小欧-2026-09-07
// 编辑历史: 2026-09-16 小欧 - 文档[44]5.6 缺陷①③修复: 缺陷①bypass下disable勾选框(原仅handleConfirm强改false, UI仍可勾, 静默失效误导);
//   缺陷③按工具域区分文案(registry工具路径含子键, 其余含子目录) — 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 浏览器白屏根因修复: 老杨T4 CollapsibleText误用default导入(命名导出)ES模块加载失败致React未挂载, 改命名导入;
//   S2 request possibly null 改可选链 — 小欧-2026-09-16
// 编辑历史: 2026-09-16 老陈 - UI微调: ①工具名称+工具名词label+值改为flex同行(去<br/>分行); ②底部拒绝/允许按钮size="large"→"middle"取消偏大 - 老陈-2026-09-16
// 编辑历史: 2026-09-16 老陈 - 参数区去掉展开收起,超过2行直接出滚动条; paramsStr改Object.entries纯文本无花括号 - 老陈-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 文档v1.5定案实施(设计文档《HITL窗口工具名词参数显示优化审核报告》):
//   ①参数格式化改key=value每参数一行(冒号改等号,禁JSON式) ②参数区固定3行高height:54+overflow滚动+超长wordBreak:break-all自动换行 ③参数区改单层轻量视觉容器(浅灰底#fafafa+细边框#e8e8e8+圆角4)取消与内层白底#fff的双层叠加 ④工具名称+执行参数标签合并flex同行 ⑤工具名称品牌蓝#1677ff高亮 - 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 三堂会审修复(2项): ①参数容器height:54在antd5全局border-box下含padding(4×2)+border(1×2)致内容区仅44px≈2.4行不足定案3行, 补boxSizing:'content-box'保证内容高=54px(3行×18px); ②P2合并行外层div删textAlign:'left'死属性(flex容器下对flex item无效) - 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 参数区居中对齐bug修复: 参数容器div补textAlign:'left'(外层textAlign:'center'继承至span致参数文本居中, 需在容器覆盖) - 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 参数区高度3行→4行: 北京老陈目视验收"整体高度不错,参数区可设4行", height:54(3×18)→72(4×18) - 小欧-2026-09-16
// 编辑历史: 2026-09-18 小欧 - 第7章实施([50]7.4.3): ①AuthorizationRequest接口+config新增content(弹窗原因); ②SAFETY_LEVEL_CONFIG改后端safety_level 5类
//   (path_auth需授权/shellparam命令确认/tool_delete删除确认/tool_execute执行确认, tool_write预留注释); ③新增content原因展示区+trust_path操作范围行;
//   ④勾选title去trustPath展示(与新增信任范围行重复, 二选一) — 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - content/trust_path显示布局(北京老陈定案): 两字段均折行显示(≤2行完整展示),
//   超2行才截断(-webkit-line-clamp:2+省略号), 长路径wordBreak:break-all强制折行防溢出, title挂完整文本可查全文;
//   改前两字段无防护: 中文折行但长ASCII路径水平溢出穿出弹窗 — 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 审核整改(北京老陈验收要求: 美观紧凑/目标信息禁灰字/Tooltip禁用/窗口不撑长):
//   ①HITL_TOKENS宽480→520令牌+内容折行后信息从容显示; ②倒计时文案#8c8c8c→#262626、trustPath#595959→#262626(目标信息禁灰字),
//   辅助label(工具名称:/执行参数:)回灰type=secondary可灰(陈总许), 帮助图标?#8c8c8c删除; ③完全删除Tooltip控件及QuestionCircleOutlined
//   (信任行仅保留Checkbox+原生title, 防叠加DOM层); ④图标与标题Tag合并单行flex(降嵌套层/紧凑), CountdownRing去confirmTimeout prop;
//   ⑤content卡padding6→5/marginBottom8→6、trust行8→6紧凑化 — 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 三思三省9类核查配套: SAFETY_LEVEL_CONFIG tool_write 由预留注释转激活条目
//   (geekblue+EditOutlined+标签"写确认"), 与后端 safety_gate 工具名归属(create_task→tool_write)联动 — 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 恢复圆圈倒计时(北京老陈令): 恢复confirmTimeout取request.confirmTimeout??60并回传CountdownRing饼环算percent,
//   反向a59aaff8e扁平纯文本(与CountdownRing.tsx恢复同批) — 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 对齐[50]§6.3.2确认稿(北京老陈令): ①信任勾选框搬回信任范围行之后、工具名称之前
//   (勾选=信任上方范围, 语义连贯); ②content原因区补SAFETY_LEVEL_CONFIG等级图标(§6.3.3规格, 无图标等级不渲染) — 小欧-2026-09-18
// 编辑历史: 2026-09-19 小欧 - UI六项优化(北京老陈验收): ①A-content区长路径截断显示…+最后2-3级目录+文件名(truncatePath)
//   ②B-参数区超长value截断>80字符(truncateValue) ③C-操作范围行只显示目录去掉文件名+左对齐
//   ④D-bypass信任勾选框加常驻灰色提示替代hover title ⑤E-倒计时文案去掉后端兜底
//   ⑥F-bypass下允许按钮显示倒计时秒数"允许执行(Ns)" — 小欧-2026-09-19
/**
 * AuthorizationModal - HITL人工确认弹窗
 *
 * 功能：显示工具执行授权请求，用户可选择允许/拒绝/本会话信任
 *
 * 设计规范（参考DangerConfirmModal）：
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

import React from 'react';
import { Button, Typography, Tag, Checkbox } from 'antd';
import {
  WarningOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
  ThunderboltOutlined,
  FolderOutlined, // 7.4.3: trust_path 操作范围图标 — 小欧-2026-09-18
  EditOutlined, // 2026-09-18: tool_write 写确认图标 — 小欧-2026-09-18
} from '@ant-design/icons';
// 2026-09-15 小欧 - 动画keyframes统一承载(AnimatedIcons), 单例注入防重复style — 小欧-2026-09-15
import { injectKeyframes } from '../AnimatedIcons/animations';
// 2026-09-16 老杨 - S3:引入CountdownRing子组件,countdown/progress隔离 - 老杨-2026-09-16
import CountdownRing from './CountdownRing';
// 2026-09-16 老杨 - T1:引入HITLModalShell统一壳+HITL_TOKENS设计令牌 - 老杨-2026-09-16
import HITLModalShell, { HITL_TOKENS } from './HITLModalShell';

const { Text, Title } = Typography;

export interface AuthorizationRequest {
  confirmId: string;
  toolName: string;
  params: Record<string, unknown>;
  content?: string; // 7.4.3: 弹窗原因(后端 ConfirmSpec.content) — 小欧-2026-09-18
  safetyLevel: string;
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
  path_auth: { color: 'orange', label: '需授权', icon: <WarningOutlined /> },
  shellparam: {
    color: 'orange',
    label: '命令确认',
    icon: <ExclamationCircleOutlined />,
  },
  // 2026-09-18 小欧 三思三省: tool_write 由预留转激活(create_task CONFIRM_TOOLS 确认现归 tool_write, 后端已补) — 小欧-2026-09-18
  tool_write: { color: 'geekblue', label: '写确认', icon: <EditOutlined /> },
  tool_delete: { color: 'red', label: '删除确认', icon: <StopOutlined /> },
  tool_execute: {
    color: 'volcano',
    label: '执行确认',
    icon: <ExclamationCircleOutlined />,
  },
};

const truncatePath = (p: string): string => {
  if (!p) return p;
  const norm = p.replace(/\\/g, '/');
  const parts = norm.split('/').filter(Boolean);
  if (parts.length <= 3) return norm;
  return `…/${parts.slice(-3).join('/')}`;
};

// 操作范围行只显示目录(去掉文件名), 保留最后2级目录
const truncateDir = (p: string): string => {
  if (!p) return p;
  const norm = p.replace(/\\/g, '/');
  const dir = norm.replace(/\/[^/]*$/, ''); // 去掉末尾文件名, 取目录部分
  const parts = dir.split('/').filter(Boolean);
  if (parts.length <= 2) return dir || norm;
  return `…/${parts.slice(-2).join('/')}`;
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
  // 2026-09-03 小欧 Bug-11: countdown 用 lazy 初值(跟随新 request), 避免默认 0 触发首渲染自动代发/拒绝
  const [trustSession, setTrustSession] = React.useState(false);
  const [countdown, setCountdown] = React.useState(
    () => request?.confirmTimeout ?? 0
  );
  const onConfirmRef = React.useRef(onConfirm);
  // 2026-09-03 小欧 Bug-17: submitting 互斥态, 提交中禁用按钮/勾选, 防连点意图翻转
  const [submitting, setSubmitting] = React.useState(false);
  const isBypass = Boolean(request?.autoConfirm);
  onConfirmRef.current = onConfirm;

  // 2026-09-16 老陈 - 纯文本显示,去掉{}花括号
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
    // 2026-09-03 小欧 Bug-21: 首 tick 100ms 内即刻 -1(节奏对齐), 再走 1s interval; 依赖无 countdown(函数式更新)
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
    // 2026-09-03 小欧/北京老陈: 传confirmId参数, 不依赖pendingRef时序(根因修复)
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

  // 2026-09-18 小欧 - 恢复圆圈倒计时(北京老陈令): 恢复confirmTimeout供CountdownRing饼环算percent - 小欧-2026-09-18
  const confirmTimeout = request.confirmTimeout ?? 60;

  // 小欧 2026-09-03 三堂会审问题1方案A: bypass(安全开关绕开)模式下即使勾选"信任此操作"也不产生信任,
  //   强制 trustSession=false(防绕过5.4防污染: bypass期间勾出的信任切回enabled:true后转正为长期豁免)
  const handleConfirm = (confirmed: boolean) => {
    if (submitting) return;
    setSubmitting(true);
    // 2026-09-03 小欧/北京老陈: 传confirmId参数, 不依赖pendingRef时序(根因修复)
    onConfirm(confirmed, isBypass ? false : trustSession, request.confirmId);
    setTrustSession(false);
  };

  return (
    <HITLModalShell open={visible} isBypass={isBypass}>
      <div style={{ textAlign: 'center' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            marginBottom: 2,
          }}
        >
          {isBypass ? (
            <ThunderboltOutlined
              style={{ fontSize: HITL_TOKENS.ICON_SIZE, color: '#1677ff' }}
            />
          ) : (
            <WarningOutlined
              style={{ fontSize: HITL_TOKENS.ICON_SIZE, color: '#faad14' }}
            />
          )}
          <Title level={5} style={{ marginBottom: 0 }}>
            {isBypass ? '将自动确认（安全开关已绕开）' : '安全确认请求'}
          </Title>
          <Tag
            color={safetyConfig.color}
            style={{ marginBottom: 0, fontSize: 14 }}
          >
            {safetyConfig.label}
          </Tag>
        </div>

        {/* 2026-09-18 小欧 - 恢复圆圈倒计时(北京老陈令): 回传confirmTimeout供饼环进度 - 小欧-2026-09-18 */}
        <CountdownRing countdown={countdown} confirmTimeout={confirmTimeout} />
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: '#262626',
            marginBottom: 6,
          }}
        >
          {/* 2026-09-03 小欧 Bug-20: 后端兜底原文案 5s 与实际 60s 不符(useAuthorization 兜底即 60), 统一为 60 防文案欺骗 */}
          {isBypass
            ? `将在 ${countdown}s 后自动确认`
            : `未响应将在 ${countdown}s 后自动拒绝`}
        </div>

        {/* content 原因展示区: 倒计时下方, 告知用户"为什么要问" — 小欧-2026-09-18 */}
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
              {/* §6.3.3规格: content区图标复用 SAFETY_LEVEL_CONFIG — 小欧-2026-09-18 */}
              {safetyConfig.icon && (
                <span style={{ marginRight: 6 }}>{safetyConfig.icon}</span>
              )}
              {request.content}
            </span>
          </div>
        )}

        {/* trust_path 操作范围展示: 操作目标路径(仅目录, 去文件名) — 小欧-2026-09-18 */}
        {request.trustPath && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              marginBottom: 6,
              fontSize: 12,
              color: '#262626',
              textAlign: 'left',
            }}
          >
            <FolderOutlined style={{ color: '#faad14', flexShrink: 0 }} />
            <span
              title={`操作范围: ${request.toolName} › ${request.trustPath}${
                request.toolName.startsWith('registry')
                  ? '，含子键'
                  : '，含子目录'
              }`}
              style={{
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                wordBreak: 'break-all',
              }}
            >
              操作范围: {truncateDir(request.trustPath)}
              {request.toolName.startsWith('registry')
                ? '，含子键'
                : '，含子目录'}
            </span>
          </div>
        )}

        {/* §6.3.2确认稿: 信任勾选紧跟信任范围行、工具名称之前(勾选=信任上方范围, 语义连贯) — 小欧-2026-09-18 */}
        <div style={{ marginBottom: 6, textAlign: 'left', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Checkbox
            checked={trustSession}
            disabled={submitting || isBypass} // 2026-09-16 小欧 缺陷①修复: bypass 禁用勾选框, 防静默失效误导(原仅 handleConfirm 强改 false, UI 仍可勾) — 小欧-2026-09-16
            onChange={(e) => setTrustSession(e.target.checked)}
            title={
              isBypass
                ? undefined
                : '信任后：同会话同工具+下方操作范围免弹框'
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

        {/* 2026-09-16 小欧 文档v1.5定案: 去外层灰底盒子(取消双层叠加), 工具名称+执行参数标签合并flex同行(P2) + 参数区单层轻量视觉容器(P0/P1b/P3) — 小欧-2026-09-16 */}
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

        <div style={{ display: 'flex', gap: 8, width: '100%' }}>
          <Button
            onClick={() => handleConfirm(false)}
            size="middle"
            disabled={submitting}
            danger
            ghost
            style={{ flex: 1 }}
            aria-label="拒绝执行此工具操作"
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
              flex: 1,
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
