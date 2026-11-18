// CountdownRing — 倒计时环(自绘 SVG, 每秒重渲染隔离在环内)
// 编辑历史: 2026-09-16 老杨 - 拆分CountdownRing子组件,React.memo隔离重渲染 - 老杨-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 修复: React.FC+memo内联解构致react/prop-types误报2error, 对齐ErrorDetail.tsx惯例文件级disable - 小欧-2026-09-16
// 编辑历史: 2026-09-18 小欧 - 恢复圆圈倒计时(北京老陈令): 回退a59aaff8e的扁平纯文本, 恢复Progress circle饼环+双层格式化div嵌套, 恢复confirmTimeout prop - 小欧-2026-09-18
// 编辑历史: 2026-10-11 00:55:20 小欧 - 直径可调(北京老陈「计时钟不能删除但可以改变位置」配套): 新增 size prop(默认 60), 数字随环缩放, 供标题行右侧 44px 调用(见 index.tsx 同批) — 小欧-2026-10-11
// 编辑历史: 2026-11-13 商量 - 字重与字号归位: fontWeight 600 → FontWeight.BOLD, 字号 11 → FontSize.SMALL, import 同步补 FontWeight — 商量-2026-11-13
// 编辑历史: 2026-11-18 商量 - 去 antd Progress, 环改自绘 SVG:
//   ① 原实现把环的直径/环宽/中心内容全交给库的 size/strokeWidth/format 三件套, 而这三处都是库缺省派生的口径
//      (见 theme/controlScale.ts 铁律「不许拿 UI 库默认值当标准」); 现改 <circle> + strokeDasharray 直接算弧长,
//      直径/环宽/字色/字重一律取本项目令牌, 库不再参与任何规格;
//   ② 顺带去掉了外层 marginBottom: 4 的假留白 —— 那是为了抵掉库组件的基线下沉, 盒子尺寸本该就是直径本身,
//      调用方(问询浮层)此前要用负 margin 再抵回来, 一处距离两处补偿(违 theme/spacing.ts 铁律一);
//   ③ 共用关系不变: 本组件同时供 HITL 危险确认弹窗(size 44)与 question 问询浮层(size 40)使用,
//      两者只在直径上分叉, 环的形状/配色/到点脉冲只有这一份实现 — 商量-2026-11-18
// 编辑历史: 2026-11-18 商量 - 目录/导出归位: 原在 components/AuthorizationModal/ 且 default export, 两处共用后迁 components/CountdownRing/ 改具名导出 — 商量-2026-11-18

// props 一律由 TS 接口 CountdownRingProps 约束, propTypes 在 TSX 里无意义;
// react/prop-types 对"memo 包裹的函数组件解构入参"只会误报, 故本文件沿用 ErrorDetail.tsx 的文件级 disable。
/* eslint-disable react/prop-types */

import React from 'react';

import { Colors, FontSize, FontWeight } from '@/utils/stepStyles';

export interface CountdownRingProps {
  countdown: number;
  confirmTimeout: number;
  /**
   * 2026-10-11 00:20 小欧 - 直径可调（北京老陈："弹框中的计时钟不能删除，但是可以改变位置"）。
   * 原为写死 60px 独占一整行居中，倒计时这个**辅助信息**占了确认弹框最大的视觉权重——
   * 用户该先看"要我确认什么"，其次才是"还有多久自动放行"。改为可传入更小直径，
   * 挪到标题行右侧（视线终点）后缩到 44，与次级信息同一量级。
   */
  size?: number;
}

/**
 * 环宽(px) —— 与大直径配套加粗一档, 否则 60px 的环看着像根细线;
 * 两档都刻意小于半径的 1/4, 保证环内足够写数字(44px 环内可写 16px 数字)。
 */
const ringStroke = (size: number) => (size > 50 ? 5 : 4);

/**
 * 环色三档 —— 走既有语义色, 不新开色值:
 *   充裕 = 主色; 将到点(≤5s) = 等待/警示橙; 临近到点(≤3s) = 确认超时红(ORANGE_RED 的既有语义正是"确认超时提示")。
 * 数字与环同色, 到点档另加脉冲 —— 颜色与动效同源, 不会出现"环红了字还是灰的"。
 */
const ringColor = (countdown: number) =>
  countdown <= 3
    ? Colors.ORANGE_RED
    : countdown <= 5
      ? Colors.WAIT_ACTION
      : Colors.PRIMARY;

export const CountdownRing: React.FC<CountdownRingProps> = React.memo(
  function CountdownRing({ countdown, confirmTimeout, size = 60 }) {
    const center = size / 2;
    const stroke = ringStroke(size);
    const radius = center - stroke / 2;
    const circumference = 2 * Math.PI * radius;
    // 剩余比例: confirmTimeout=0 语义为"无到点可言", 环按空处理(与不渲染环的调用方口径一致)
    const ratio =
      confirmTimeout > 0
        ? Math.min(1, Math.max(0, countdown / confirmTimeout))
        : 0;
    const color = ringColor(countdown);
    // 数字随环一起缩，避免 60→44 后数字撑破圆环
    const numFont = Math.round(size * 0.36);

    return (
      <div
        role="timer"
        aria-label={`剩余 ${countdown} 秒`}
        data-testid="countdown-ring"
        style={{
          position: 'relative',
          width: size,
          height: size,
          flexShrink: 0,
        }}
      >
        {/* 环: 起点在 12 点(整体旋转 -90°), 剩余弧长由 dashoffset 表达 */}
        <svg
          width={size}
          height={size}
          aria-hidden="true"
          style={{ display: 'block', transform: 'rotate(-90deg)' }}
        >
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={Colors.BG.HOVER}
            strokeWidth={stroke}
          />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - ratio)}
            style={{ transition: 'stroke-dashoffset 0.3s linear' }}
          />
        </svg>
        {/* 中心内容: 绝对定位压在环心, 不参与环的尺寸计算 */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <span
            style={{
              fontSize: numFont,
              lineHeight: 1,
              fontWeight: FontWeight.BOLD,
              color: countdown <= 3 ? Colors.ORANGE_RED : Colors.TEXT.STRONG,
              animation:
                countdown <= 3 ? 'pulse 0.8s ease-in-out infinite' : 'none',
            }}
          >
            {countdown}
          </span>
          <span
            style={{
              fontSize: FontSize.SMALL,
              lineHeight: 1,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            秒
          </span>
        </div>
      </div>
    );
  }
);

CountdownRing.displayName = 'CountdownRing';
