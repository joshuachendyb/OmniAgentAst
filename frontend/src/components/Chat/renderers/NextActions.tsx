/**
 * 推荐操作按钮组件（第13章设计方案）
 * 显示工具推荐的下一步操作按钮
 * 使用系统样式常量
 */
import React from 'react';
import { Button, Space } from 'antd';
import { Spacing, Colors, FontSize, Radius } from '@/utils/stepStyles';

interface NextActionsProps {
  actions?: string[];
  onActionClick?: (action: string) => void;
}

export const NextActions: React.FC<NextActionsProps> = ({
  actions,
  onActionClick,
}) => {
  if (!actions || actions.length === 0) return null;

  return (
    <div style={{ marginTop: Spacing.SM }}>
      <Space size={Spacing.XS} wrap>
        {actions.map((action, idx) => (
          <Button
            key={idx}
            size="small"
            type="text"
            onClick={() => onActionClick?.(action)}
            style={{
              fontSize: FontSize.XS,
              color: Colors.PRIMARY,
              borderRadius: Radius.SM,
              padding: `${Spacing.XXS}px ${Spacing.XS}px`,
            }}
          >
            {action}
          </Button>
        ))}
      </Space>
    </div>
  );
};

export default NextActions;
