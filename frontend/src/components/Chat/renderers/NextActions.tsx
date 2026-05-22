/**
 * 推荐操作按钮组件（第13章设计方案）
 * 显示工具推荐的下一步操作按钮
 * 使用系统样式常量
 */
import React from 'react';
import { Button, Space, Tooltip } from 'antd';
import { Spacing, Colors, FontSize, Radius } from '@/utils/stepStyles';

interface NextAction {
  tool: string;
  description: string;
  when?: string;
  params?: Record<string, unknown>;
}

interface NextActionsProps {
  actions?: NextAction[];
  onActionClick?: (action: NextAction) => void;
}

export const NextActions: React.FC<NextActionsProps> = ({
  actions,
  onActionClick,
}) => {
  if (!actions || actions.length === 0) return null;

  return (
    <div style={{ marginTop: Spacing.SM }}>
      <div
        style={{
          fontSize: FontSize.XS,
          color: Colors.TEXT.TERTIARY,
          marginBottom: Spacing.XS,
        }}
      >
        💡 推荐下一步：
      </div>
      <Space size={Spacing.XS} wrap>
        {actions.map((action, idx) => (
          <Tooltip
            key={idx}
            title={
              <div>
                <div>{action.description}</div>
                {action.when && (
                  <div
                    style={{
                      color: Colors.TEXT.TERTIARY,
                      fontSize: FontSize.XS,
                    }}
                  >
                    适用：{action.when}
                  </div>
                )}
              </div>
            }
          >
            <Button
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
              {action.tool}
            </Button>
          </Tooltip>
        ))}
      </Space>
    </div>
  );
};

export default NextActions;
