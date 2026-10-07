// 编辑历史: 2026-09-13 小欧 - 新建等待图标控件组: ThoughtWaitingIcon/ToolWaitingIcon/ActionWaitingIcon从PipelineRenderer/ToolCallLine内联提取, 统一导出, DRY复用 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - ActionWaitingIcon换型(北京老陈令选title-icon-compare G波纹扩散): 蓝色270°弧线旋转改蓝核心圆+双层扩散波纹(SVG36x36, .action-ripple-1/.action-ripple-2, 1.8s不旋转) — 小欧-2026-09-13
// 编辑历史: 2026-09-14 小欧 - 漏洞2修复: 组件内5处硬编码SVG色令牌化(绿#52c41a→Colors.SUCCESS / 橙#fa8c16→Colors.WAIT_ACTION / 蓝#1677ff→Colors.PRIMARY), 零行为变化 — 小欧-2026-09-14
// 编辑历史: 2026-09-17 小欧 - 实施: 三角色等待图标接 waitClock 可选信号, 图标保留+钟面追加并存(Thought/Action→kind="llm", Tool→kind="tool") - 小欧-2026-09-17
// 编辑历史: 2026-10-05 小欧 - 新增 ReasoningIcon 眼睛(文档[9] §5.3) + dim prop: 三堂会审发现 .reasoning-icon-dim 只写在CSS 无组件挂载, 裁定两态零落地, 现按 dim 挂载 — 小欧-2026-10-05
// 编辑历史: 2026-10-07 小欧 - 新增4个备用图标(北京老陈令备用常驻, 想用即改 ReasoningIcon 别名取值):
//   SignalBarsIcon(43号信号柱)/SunIcon(58号太阳)/ApproachDotsIcon(65号对向双球)/SpinSquareIcon(13号方框旋转);
//   动画节奏统一在 index.css — 小欧-2026-10-07
// 编辑历史: 2026-10-07 小欧 - 原 ReasoningIcon 实体改名 EyeIcon 转备用; 别名行改指 SpinSquareIcon(北京老陈 2026-10-07 选定候选13号);
//   SpinSquareIcon 加 animating prop: 转/停只跟 SSE 时序, 与展开/收起解耦(北京老陈裁定) — 小欧-2026-10-07
// 编辑历史: 2026-10-07 小欧 - EyeIcon/SignalBarsIcon/SunIcon/ApproachDotsIcon 统一加 animating prop, EyeIcon 删 dim prop
//   (北京老陈裁定动画与展开/收起解耦后 dim 已无消费方); 5图标接口统一为 {size, animating},
//   换图标只改 ReasoningIcon 别名取值, 调用方零改动 — 小欧-2026-10-07
import React from 'react';
import { Colors, Icon } from '@/utils/stepStyles';
import { ClockStopwatch } from './clockStopwatch'; // 2026-09-17 小欧 实施: 微型钟面(追加并存) — 小欧-2026-09-17
import type { ClockSignals } from '@/types/sse'; // 2026-09-17 小欧 实施: 钟面信号类型 — 小欧-2026-09-17

/**
 * ThoughtWaitingIcon — 绿色270°弧线旋转
 * 用途：thought-start到达后、首个thinking chunk到达前的等待状态
 * 原位置：PipelineRenderer.tsx 内联 const WaitingIcon（私有）
 */
// 2026-09-17 小欧 实施: 等待图标(类型身份: 绿=思考) 与钟面(等待时长) 并存, 语义正交 — 小欧-2026-09-17
export const ThoughtWaitingIcon: React.FC<{ waitClock?: ClockSignals }> = ({
  waitClock,
}) => (
  <>
    <span className="waiting-cursor" aria-label="等待思考输出">
      <svg
        width="1.4em"
        height="1.4em"
        viewBox="0 0 24 24"
        fill="none"
        stroke={Colors.SUCCESS}
        strokeWidth={2}
        strokeLinecap="round"
      >
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </svg>
    </span>
    {waitClock && <ClockStopwatch {...waitClock} kind="llm" />}
  </>
);

/**
 * ToolWaitingIcon — 橙色8臂loader旋转
 * 用途：action步到达后、observation到达前的工具执行等待状态
 * 原位置：ToolCallLine.tsx 内联 <svg>（直接嵌JSX无封装）
 */
export const ToolWaitingIcon: React.FC<{ waitClock?: ClockSignals }> = ({
  waitClock,
}) => (
  <>
    <span className="tool-waiting-cursor" aria-label="等待工具完成">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke={Colors.WAIT_ACTION}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2v4" />
        <path d="M12 18v4" />
        <path d="M4.93 4.93l2.83 2.83" />
        <path d="M16.24 16.24l2.83 2.83" />
        <path d="M2 12h4" />
        <path d="M18 12h4" />
        <path d="M4.93 19.07l2.83-2.83" />
        <path d="M16.24 7.76l2.83-2.83" />
      </svg>
    </span>
    {waitClock && <ClockStopwatch {...waitClock} kind="tool" />}
  </>
);

/**
 * ActionWaitingIcon — 蓝色波纹扩散（G: 波纹扩散样式）
 * 用途：thinking内容显示完毕后、action步到达前的LLM决策等待状态
 * 新增位置：全新组件
 * 动画：蓝核心圆 + 两层扩散波纹，scale 0.5→1.4 + opacity 1→0，1.8s周期，不旋转
 */
export const ActionWaitingIcon: React.FC<{ waitClock?: ClockSignals }> = ({
  waitClock,
}) => (
  <>
    <span className="action-waiting-cursor" aria-label="等待action到达">
      <svg
        viewBox="0 0 36 36"
        width="1.4em"
        height="1.4em"
        fill="none"
        strokeWidth={2}
      >
        <circle cx="18" cy="18" r="6" stroke={Colors.PRIMARY} />
        <circle
          cx="18"
          cy="18"
          r="10"
          opacity="0.6"
          className="action-ripple-1"
          stroke={Colors.PRIMARY}
        />
        <circle
          cx="18"
          cy="18"
          r="10"
          opacity="0.6"
          className="action-ripple-2"
          stroke={Colors.PRIMARY}
        />
      </svg>
    </span>
    {waitClock && <ClockStopwatch {...waitClock} kind="llm" />}
  </>
);

/**
 * EyeIcon — 眼睛(备用候选, 可作 ReasoningIcon 取值)
 * 取形: 绿点瞳孔 + 半径 13 上弧眼睑, 三色依次扩散(遵 §3 继承规则: 禁颜色硬编码)
 * 动画: animating=true 挂 reasoning-beam1~3(beampulse 1.8s 依次扩散), false 不挂类即静止;
 *   节奏唯一真源 index.css, 组件无自身计时器(不内联样式)
 * 状态: 备用候选(与其余4图标同接口 {size, animating}), 换用时只改 ReasoningIcon 别名取值 — 小欧-2026-10-07
 * 对齐: viewBox 收为图形外接框(描边外缘 x5..31 / y4..21.5), 缩放后水平填满盒子、垂直居中,
 *   与 GearIcon 同一左边缘与中心线 — 小欧-2026-10-07
 */
export const EyeIcon: React.FC<{ size?: number; animating?: boolean }> = ({
  size = Icon.BOX,
  animating = false,
}) => (
  <svg
    viewBox="5 4 26 17.5"
    width={size}
    height={size}
    fill="none"
    strokeWidth={Icon.STROKE}
    strokeLinecap="round"
    style={{ flexShrink: 0 }}
    aria-hidden="true" // 装饰性图标, 不给读屏重复播报, 与折叠按钮文本并列
  >
    <circle cx="18" cy="18" r="2.5" fill={Colors.SUCCESS} />
    <path
      className={animating ? 'reasoning-beam1' : undefined}
      d="M6 18 A13 13 0 0 1 30 18"
      stroke={Colors.SUCCESS}
    />
    <path
      className={animating ? 'reasoning-beam2' : undefined}
      d="M6 18 A13 13 0 0 1 30 18"
      stroke={Colors.PRIMARY}
    />
    <path
      className={animating ? 'reasoning-beam3' : undefined}
      d="M6 18 A13 13 0 0 1 30 18"
      stroke={Colors.WAIT_ACTION}
    />
  </svg>
);

/**
 * SignalBarsIcon — 信号柱(候选43号, 备用未接线)
 * 取形: 四柱错峰长高(Primary/SUCCESS/WAIT_ACTION/ERROR 四色, 遵 §3 继承规则: 禁颜色硬编码)
 * 动画: animating=true 挂 bars-grow1~4(barsgrow 1.6s 错峰长高), false 不挂类即静止;
 *   节奏唯一真源 index.css, 组件无自身计时器(不内联样式)
 * 状态: 备用候选(与其余4图标同接口 {size, animating}), 换用时只改 ReasoningIcon 别名取值 — 小欧-2026-10-07
 */
export const SignalBarsIcon: React.FC<{
  size?: number;
  animating?: boolean;
}> = ({ size = Icon.BOX, animating = false }) => (
  <svg
    viewBox="5.5 8 24.5 22"
    width={size}
    height={size}
    fill="none"
    style={{ flexShrink: 0 }}
    aria-hidden="true"
  >
    <rect
      className={animating ? 'bars-grow1' : undefined}
      x="5.5"
      y="8"
      width="5"
      height="22"
      rx="1.5"
      fill={Colors.PRIMARY}
    />
    <rect
      className={animating ? 'bars-grow2' : undefined}
      x="12"
      y="8"
      width="5"
      height="22"
      rx="1.5"
      fill={Colors.SUCCESS}
    />
    <rect
      className={animating ? 'bars-grow3' : undefined}
      x="18.5"
      y="8"
      width="5"
      height="22"
      rx="1.5"
      fill={Colors.WAIT_ACTION}
    />
    <rect
      className={animating ? 'bars-grow4' : undefined}
      x="25"
      y="8"
      width="5"
      height="22"
      rx="1.5"
      fill={Colors.ERROR}
    />
  </svg>
);

/**
 * SunIcon — 太阳光芒(候选58号, 备用未接线)
 * 取形: 实心橙心 + 八向光芒短线, 整体旋转 1.5s(WAIT_ACTION 色)
 * 动画: animating=true 挂 icon-spin15(icon-spin 1.5s), false 不挂类即静止;
 *   节奏唯一真源 index.css, 组件无自身计时器
 * 状态: 备用候选(与其余4图标同接口 {size, animating}), 换用时只改 ReasoningIcon 别名取值 — 小欧-2026-10-07
 */
export const SunIcon: React.FC<{ size?: number; animating?: boolean }> = ({
  size = Icon.BOX,
  animating = false,
}) => (
  <svg
    viewBox="7.5 1.5 21 30.5"
    width={size}
    height={size}
    fill="none"
    stroke={Colors.WAIT_ACTION}
    strokeWidth={Icon.STROKE}
    strokeLinecap="round"
    className={animating ? 'icon-spin15' : undefined}
    style={{ flexShrink: 0 }}
    aria-hidden="true"
  >
    <circle cx="18" cy="18" r="5" fill={Colors.WAIT_ACTION} stroke="none" />
    <path d="M18 3.5 V7" />
    <path d="M22.4 5.6 L20.4 8.2" />
    <path d="M26.5 14.5 H23.5" />
    <path d="M26.5 21.5 H23.5" />
    <path d="M22.4 30.4 L20.4 27.8" />
    <path d="M13.6 30.4 L15.6 27.8" />
    <path d="M9.5 21.5 H12.5" />
    <path d="M9.5 14.5 H12.5" />
    <path d="M13.6 5.6 L15.6 8.2" />
  </svg>
);

/**
 * ApproachDotsIcon — 对向双球(候选65号, 备用未接线)
 * 取形: 淡蓝基准线 + 蓝/橙双球相向相碰后弹回(PRIMARY/WAIT_ACTION 两色)
 * 动画: animating=true 挂 dots-meetA/B(dots-meeta/b 2s translateX 往返), false 不挂类即静止;
 *   节奏唯一真源 index.css, 组件无自身计时器
 * 状态: 备用候选(与其余4图标同接口 {size, animating}), 换用时只改 ReasoningIcon 别名取值 — 小欧-2026-10-07
 */
export const ApproachDotsIcon: React.FC<{
  size?: number;
  animating?: boolean;
}> = ({ size = Icon.BOX, animating = false }) => (
  <svg
    viewBox="2.5 15.5 31 9"
    width={size}
    height={size}
    fill="none"
    strokeWidth={Icon.STROKE}
    style={{ flexShrink: 0 }}
    aria-hidden="true"
  >
    <path d="M4 20 H32" stroke={Colors.PRIMARY} opacity={0.3} />
    <circle
      className={animating ? 'dots-meetA' : undefined}
      cx="7"
      cy="20"
      r="3.5"
      fill={Colors.PRIMARY}
    />
    <circle
      className={animating ? 'dots-meetB' : undefined}
      cx="29"
      cy="20"
      r="3.5"
      fill={Colors.WAIT_ACTION}
    />
  </svg>
);

/**
 * SpinSquareIcon — 方框旋转(候选13号)
 * 取形: 圆角方框单描边(PRIMARY 色), 整体旋转 1s
 * 动画: animating=true 挂 .icon-spin1 旋转, false 不挂类即静止; 节奏唯一真源 index.css @keyframes icon-spin
 *   animating 由调用方 ThinkingStream 按 text 自判传入, 组件本身不感知 SSE — 小欧-2026-10-07
 * 对齐(北京老陈 2026-10-07 "图标要好看中心对齐, 不许犬牙交错"): viewBox 取描边外缘正好=盒子边界,
 *   图形填满 Icon.BOX 不留内缩空白, 与 GearIcon(同样填满)左边缘/视觉宽度/中心线一致 — 小欧-2026-10-07
 */
export const SpinSquareIcon: React.FC<{
  size?: number;
  animating?: boolean;
}> = ({ size = Icon.BOX, animating = false }) => (
  <svg
    viewBox="0 0 18 18"
    width={size}
    height={size}
    fill="none"
    stroke={Colors.PRIMARY}
    strokeWidth={Icon.STROKE}
    strokeLinecap="round"
    className={animating ? 'icon-spin1' : undefined}
    style={{ flexShrink: 0 }} // 2026-10-07 小欧 - 与 DropletIcon 一致防 flex 压扁 — 小欧-2026-10-07
    aria-hidden="true"
  >
    <rect x="1" y="1" width="16" height="16" rx="2" />
  </svg>
);
/**
 * ReasoningIcon = SpinSquareIcon — 推理折叠行前置图标(实体取候选13号方框旋转, 北京老陈 2026-10-07 选定)
 * 取值赋值非包装: 两者指向同一函数对象, 渲染结果与组件类型完全一致(不触发重挂载), 仅多一个模块级绑定
 * 编辑历史: 2026-10-07 小欧 - 取值由 EyeIcon 改为 SpinSquareIcon; 旧实体转备用名 EyeIcon — 小欧-2026-10-07
 */
export const ReasoningIcon = SpinSquareIcon;
