// 编辑历史: 2026-09-15 老杨 - 新建水滴图标控件: 替代✔/✖字符符号，用于工具执行结果状态展示 — 老杨-2026-09-15
// 编辑历史: 2026-10-07 小欧 - 图标列中心对齐(北京老陈: 图标要好看中心对齐, 不许犬牙交错, 不要缩进):
//   size 默认 10 → Icon.BOX(16px, 与标题行方框/齿轮同盒); 高度去掉 *1.2 改正方盒(10:12 竖长比
//   会让盒子比同列图标高 3px, 视觉不齐), 竖长由 viewBox 0 0 10 12 + preserveAspectRatio 居中留边承担 — 小欧-2026-10-07
import React from 'react';
import { Colors, Icon } from '@/utils/stepStyles';

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

export const DropletIcon: React.FC<DropletIconProps> = ({
  status,
  size = Icon.BOX,
}) => (
  <svg width={size} height={size} viewBox="0 0 10 12" style={{ flexShrink: 0 }}>
    <path
      d="M5 0 L9.5 5.5 Q9.5 11 5 11 Q0.5 11 0.5 5.5 Z"
      fill={colorMap[status]}
    />
  </svg>
);
