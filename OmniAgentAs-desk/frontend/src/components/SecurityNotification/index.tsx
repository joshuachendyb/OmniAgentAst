/**
 * 安全通知组件 - SecurityNotification
 * 
 * 功能：4-6分中等风险操作的顶部通知（执行并提示）
 * 样式：黄色Notification、3秒后自动消失
 * 
 * @author 小新
 * @version 2.0.0
 * @since 2026-02-19
 * @update 升级到v2.0 API（score+message）
 */

import React from 'react';
import { notification, Typography, Tag } from 'antd';
import { WarningOutlined } from '@ant-design/icons';

const { Text } = Typography;

/**
 * 显示安全通知
 * 
 * 设计规范（来自设计文档第3.2.2节）：
 * - 使用 Ant Design Notification 组件
 * - type: "warning"
 * - duration: 3秒
 * - placement: "top"
 * 
 * @param command 操作命令
 * @param score 风险分数（4-6分）
 * @param message 提示信息
 * @author 小新
 */
export const showSecurityNotification = (
  command: string,
  score: number,
  message: string
): void => {
  notification.warning({
    message: (
      <div>
        <Text strong style={{ fontSize: 16 }}>
          <WarningOutlined style={{ color: '#faad14', marginRight: 8 }} />
          正在执行敏感操作
        </Text>
        <Tag color="orange" style={{ marginLeft: 8 }}>
          {score}分
        </Tag>
      </div>
    ),
    description: (
      <div style={{ marginTop: 8 }}>
        <Text style={{ display: 'block', marginBottom: 8 }}>
          {message}
        </Text>
        <Text code style={{ 
          display: 'block',
          fontSize: 12,
          wordBreak: 'break-all'
        }}>
          {command}
        </Text>
      </div>
    ),
    placement: 'top',
    duration: 3,
    style: {
      backgroundColor: '#fffbe6',
      border: '1px solid #ffe58f'
    }
  });
};

/**
 * 安全通知组件（简单版）
 * 用于在组件内直接调用
 * 
 * @param props 组件属性
 * @author 小新
 */
interface SecurityNotificationProps {
  command: string;
  score: number;
  message: string;
}

export const SecurityNotification: React.FC<SecurityNotificationProps> = ({
  command,
  score,
  message
}) => {
  // 组件挂载时自动显示通知
  React.useEffect(() => {
    showSecurityNotification(command, score, message);
  }, [command, score, message]);

  return null;
};

export default SecurityNotification;
