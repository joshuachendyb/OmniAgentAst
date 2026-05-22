/**
 * 警告框组件（第13章设计方案）
 * 禁止到处框框色块：警告框无背景，仅1px左边框
 * 使用系统样式常量
 */
import React from 'react';
import { Typography } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import { Spacing, Colors, FontSize, BorderWidth } from '@/utils/stepStyles';

const { Text } = Typography;

interface WarningBoxProps {
  warning?: string;
}

export const WarningBox: React.FC<WarningBoxProps> = ({ warning }) => {
  if (!warning) return null;

  return (
    <div
      style={{
        paddingLeft: Spacing.SM,
        marginLeft: Spacing.XS,
        borderLeft: `${BorderWidth.THIN}px solid ${Colors.WARNING}`,
        display: 'flex',
        alignItems: 'flex-start',
        gap: Spacing.XS,
      }}
    >
      <WarningOutlined
        style={{ color: Colors.WARNING, fontSize: FontSize.SM, marginTop: 2 }}
      />
      <Text
        style={{ color: Colors.TEXT.SECONDARY, fontSize: FontSize.SM, flex: 1 }}
      >
        {warning}
      </Text>
    </div>
  );
};

export default WarningBox;
