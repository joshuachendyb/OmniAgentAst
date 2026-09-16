// HITLModalShell.tsx — 统一Modal壳: border/radius/shadow/footer一致
// 编辑历史: 2026-09-16 老杨 - 统一Modal壳: 消除两Modal视觉不一致 - 老杨-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 修复: motion={false}非antd ModalProps(tsc TS2322), 改rc-dialog transitionName/maskTransitionName空串禁入场动画, 意图不变 - 小欧-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 修复: role/aria-modal非antd ModalProps(tsc TS2322), 运行时探测antd默认即渲染role=dialog+aria-modal=true, 删除零退化 - 小欧-2026-09-16

import React from 'react';
import { Modal } from 'antd';

// 设计令牌(解决魔法数字散布)
export const HITL_TOKENS = {
  MODAL_WIDTH: 480,
  ICON_SIZE: 32,
  BODY_PADDING: 24,
  BORDER_RADIUS: 8,
  BORDER_WIDTH: 1.5,
  PROGRESS_SIZE: 60,
} as const;

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
    transitionName=""
    maskTransitionName=""
    title={null}
    footer={null}
    closable={false}
    maskClosable={false}
    keyboard={false}
    width={HITL_TOKENS.MODAL_WIDTH}
    style={{
      border: isBypass
        ? `${HITL_TOKENS.BORDER_WIDTH}px dashed #1677ff`
        : `${HITL_TOKENS.BORDER_WIDTH}px solid #faad14`,
      borderRadius: `${HITL_TOKENS.BORDER_RADIUS}px`,
      overflow: 'hidden',
      boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
    }}
    styles={{ body: { padding: `${HITL_TOKENS.BODY_PADDING}px` } }}
  >
    {children}
  </Modal>
);

export default HITLModalShell;
