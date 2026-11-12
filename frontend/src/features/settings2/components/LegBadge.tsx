// 编辑历史: 2026-11-09 小欧 - 新建：腿徽标与结论徽标（页面内 4 处重复的 ✓/✗/? 图标与配色三元收口到一处）— 小欧-2026-11-09
// 2026-11-11 小欧 - BadgeRow 改 forwardRef + 透传 props：antd <Tooltip> 向直接子元素 cloneElement 注入
//   onMouseEnter/onMouseLeave/ref，原非 forwardRef 函数组件接收不到也不转发到真实 DOM，导致悬停徽标不弹 tip。
//   输入图片/视频/音频行 + 生成能力行共用本 BadgeRow，单点修复一并覆盖四条验证行。— 小欧-2026-11-11
import React from 'react';
import {
  CheckOutlined,
  CloseOutlined,
  QuestionOutlined,
} from '@ant-design/icons';
import { FontSize, Spacing } from '@/utils/stepStyles';
import { legColor, type LegState } from '../utils/probeView';

const StateIcon: React.FC<{ st: LegState }> = ({ st }) => {
  if (st === 'pass')
    return <CheckOutlined style={{ fontSize: FontSize.SECONDARY }} />;
  if (st === 'fail')
    return <CloseOutlined style={{ fontSize: FontSize.SECONDARY }} />;
  if (st === 'warn')
    return <QuestionOutlined style={{ fontSize: FontSize.SECONDARY }} />;
  // skipped 独立「未执行」符号：既不算通过也不算失败，与未测灰字区分
  if (st === 'skip')
    return <span style={{ fontSize: FontSize.SECONDARY }}>—</span>;
  return null;
};

/** 单腿徽标：通道名 + 符号（灰=未测/不适用，绿✓通过，红✗失败，黄?已请求未取证） */
export const LegBadge: React.FC<{ label: string; state: LegState }> = ({
  label,
  state,
}) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 2,
      fontSize: FontSize.PRIMARY,
      color: legColor(state),
    }}
  >
    {label}
    <StateIcon st={state} />
  </span>
);

/** 结论徽标：「能力名 + 结论词 + 符号」，与腿徽标同语法 */
export const VerdictBadge: React.FC<{
  caption: string;
  word: string;
  state: LegState;
}> = ({ caption, word, state }) => (
  <span
    style={{ display: 'inline-flex', alignItems: 'baseline', gap: Spacing.XS }}
  >
    <span style={{ fontSize: FontSize.PRIMARY }}>{caption}</span>
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 2,
        fontSize: FontSize.PRIMARY,
        color: legColor(state),
      }}
    >
      {word}
      <StateIcon st={state} />
    </span>
  </span>
);

/** 徽标组容器：minWidth 锚定，结论文案长短不推按钮搬家。」
 *  2026-11-11 小欧 - forwardRef + 透传 props：antd <Tooltip> 通过 cloneElement 向直接子元素注入
 *  onMouseEnter/onMouseLeave/ref 等，原 React.FC 非 forwardRef 组件的这些 props 会丢到真实 DOM 上，
 *  导致悬停徽标不弹 tip（输入图片/视频/音频行 + 生成能力行共用本组件，一并修复）。— 小欧-2026-11-11
 */
export const BadgeRow = React.forwardRef<
  HTMLSpanElement,
  React.HTMLAttributes<HTMLSpanElement>
>(({ children, ...rest }, ref) => (
  <span
    ref={ref}
    {...rest}
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: Spacing.SM,
      cursor: 'help',
      whiteSpace: 'nowrap',
      minWidth: 240,
    }}
  >
    {children}
  </span>
));
BadgeRow.displayName = 'BadgeRow';
