// 编辑历史: 2026-09-08 小欧 - 六章6.5: 抽"省略 + Tooltip 全文"封装(DRY, G4 长错误/G5 收窄/G6 hover ≥4 处) — 小欧-2026-09-08
import React from 'react';
import { Tooltip } from 'antd';

export interface EllipsisTipProps {
  text: string;
  tooltip?: string;
  maxWidth: number;
  children?: React.ReactNode;
}

export const EllipsisTip: React.FC<EllipsisTipProps> = ({
  text,
  tooltip,
  maxWidth,
  children,
}) => {
  const inner = (
    <span
      style={{
        display: 'inline-block',
        maxWidth,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        verticalAlign: 'bottom',
      }}
    >
      {children ?? text}
    </span>
  );
  return tooltip ? <Tooltip title={tooltip}>{inner}</Tooltip> : inner;
};
