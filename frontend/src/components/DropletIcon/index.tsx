// 编辑历史: 2026-09-15 老杨 - 新建水滴图标控件: 替代✔/✖字符符号，用于工具执行结果状态展示 — 老杨-2026-09-15
import React from 'react';
import { Colors } from '@/utils/stepStyles';

/**
 * DropletIcon - 水滴图标控件
 *
 * 用途：工具执行结果状态展示（成功/失败/警告）
 * 替代原来的✔/✖字符符号，更规整好看
 *
 * @author 老杨
 * @date 2026-09-15
 */

export type DropletStatus = 'success' | 'error' | 'warning';

const colorMap: Record<DropletStatus, string> = {
  success: Colors.SUCCESS,
  error: Colors.ERROR,
  warning: Colors.WARNING,
};

interface DropletIconProps {
  status: DropletStatus;
  size?: number;
}

export const DropletIcon: React.FC<DropletIconProps> = ({ status, size = 10 }) => (
  <svg
    width={size}
    height={Math.round(size * 1.2)}
    viewBox="0 0 10 12"
    style={{ flexShrink: 0 }}
  >
    <path
      d="M5 0 L9.5 5.5 Q9.5 11 5 11 Q0.5 11 0.5 5.5 Z"
      fill={colorMap[status]}
    />
  </svg>
);
