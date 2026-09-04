/**
 * 状态图标组件（第13章设计方案）
 * 根据状态码显示对应图标和颜色
 * 使用系统颜色常量，禁止硬编码
 */
import React from 'react';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { Colors } from '@/utils/stepStyles';

export type StatusCode = 'SUCCESS' | 'ERROR' | 'WARNING' | 'INFO';

interface StatusIconProps {
  code?: StatusCode | string;
  size?: number;
}

const getStatusConfig = (
  code?: string
): { icon: React.ReactNode; color: string } => {
  switch (code) {
    case 'SUCCESS':
      return { icon: <CheckCircleOutlined />, color: Colors.SUCCESS };
    case 'ERROR':
      return { icon: <CloseCircleOutlined />, color: Colors.ERROR };
    case 'WARNING':
      return { icon: <WarningOutlined />, color: Colors.WARNING };
    case 'INFO':
    default:
      return { icon: <InfoCircleOutlined />, color: Colors.TEXT.SECONDARY };
  }
};

export const StatusIcon: React.FC<StatusIconProps> = ({ code, size = 16 }) => {
  const { icon, color } = getStatusConfig(code);
  return React.cloneElement(icon as React.ReactElement, {
    style: { color, fontSize: size },
  });
};

export default StatusIcon;
