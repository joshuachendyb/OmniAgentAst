// HITLModalShell.tsx — 统一Modal壳: border/radius/shadow/footer一致
// 编辑历史: 2026-09-16 老杨 - 统一Modal壳: 消除两Modal视觉不一致 - 老杨-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 修复: motion={false}非antd ModalProps(tsc TS2322), 改rc-dialog transitionName/maskTransitionName空串禁入场动画, 意图不变 - 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 修复: role/aria-modal非antd ModalProps(tsc TS2322), 运行时探测antd默认即渲染role=dialog+aria-modal=true, 删除零退化 - 小欧-2026-09-16
// 编辑历史: 2026-09-18 小欧 - 审核整改: MODAL_WIDTH 480→520 加宽(内容/路径2行截断从容, 弹窗仍紧凑) - 小欧-2026-09-18
// 编辑历史: 2026-11-18 商量 - 去 antd Modal 的缺省派生 + 裸色值归位:
//   ① 壳的边框/圆角/投影/内距从外层 .ant-modal 挪进 styles.content 一处承担 —— 原写法边框画在外层壳,
//      而用户看到的表面是库自带的 .ant-modal-content(它自己还带 20/24 缺省内距与阴影圆角), 等于两层壳各算一遍;
//   ② 内距去掉「库缺省 20/24 + 我们 24」的叠加(实测左右累计 48px, 弹窗内容被挤掉两成宽),
//      统一由 body 内距一处给出, 取值回到刻度 Spacing.XXL;
//   ③ 显式 centered —— 不写则由库缺省的 top:100px 决定落点(属库缺省值, 违 theme/controlScale.ts 铁律);
//   ④ BORDER_WIDTH 1.5 是半像素(不在刻度上, 跨 DPR 渲染还不稳) → BorderWidth.THIN;
//      BORDER_RADIUS → Radius.LG; 删 PROGRESS_SIZE(倒计时环改自绘后已无引用);
//   ⑤ 裸色 #1677ff → Colors.PRIMARY, #faad14 → Colors.WAIT_ACTION(与弹窗正文同一套琥珀警示色) — 商量-2026-11-18

import React from 'react';
import { Modal } from 'antd';

import { BorderWidth, Colors, Radius, Spacing } from '@/utils/stepStyles';

/**
 * 弹窗自身几何 —— 只留两项无全局刻度对应的值:
 *   宽度是产品决策(520 是长路径折行两行可容的实测宽度); 图标字号是弹窗标题行的视觉锚点。
 * 其余几何(边框/圆角/内距/颜色)一律引用全局令牌, 不再在本文件另立。
 */
export const HITL_TOKENS = {
  MODAL_WIDTH: 520,
  ICON_SIZE: 32,
} as const;

/**
 * 弹窗投影 —— 比浮层卡片重一档: 弹窗盖在半透明遮罩之上, 用卡片同档投影会"浮不起来"。
 * 两级投影(近处接地 + 远处扩散), 与 PanelCard 的 RAISED_SHADOW 同一手法。
 */
const MODAL_SHADOW = '0 8px 24px rgba(0, 0, 0, 0.12)';

interface HITLModalShellProps {
  open: boolean;
  isBypass?: boolean;
  children: React.ReactNode;
}

const HITLModalShell: React.FC<HITLModalShellProps> = ({
  open,
  isBypass = false,
  children,
}) => (
  <Modal
    open={open}
    centered
    transitionName=""
    maskTransitionName=""
    title={null}
    footer={null}
    closable={false}
    maskClosable={false}
    keyboard={false}
    width={HITL_TOKENS.MODAL_WIDTH}
    styles={{
      content: {
        // 可见表面就是这一层: 边框/圆角/投影/内距全部在此一处声明, 不再对外层壳叠第二套
        padding: 0,
        border: `${BorderWidth.THIN}px ${isBypass ? 'dashed' : 'solid'} ${
          isBypass ? Colors.PRIMARY : Colors.WAIT_ACTION
        }`,
        borderRadius: Radius.LG,
        boxShadow: MODAL_SHADOW,
        overflow: 'hidden',
      },
      body: { padding: Spacing.XXL },
    }}
  >
    {children}
  </Modal>
);

export default HITLModalShell;
