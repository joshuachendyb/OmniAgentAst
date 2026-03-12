/**
 * 危险警告组件 - SecurityAlert
 *
 * 功能：9-10分极高风险操作的警告提示（直接拒绝执行）
 * 样式：红色Alert、禁止图标、不可关闭
 *
 * @author 小新
 * @version 2.0.0
 * @since 2026-02-19
 * @update 升级到v2.0 API（score+message）
 */

import React from 'react';
import { Alert, Space, Typography, Tag } from 'antd';
import { StopOutlined, WarningOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

/**
 * 组件属性
 */
interface SecurityAlertProps {
  /** 操作命令 */
  command: string;
  /** 风险分数（9-10分） */
  score: number;
  /** 提示信息 */
  message: string;
}

/**
 * 危险警告组件
 *
 * 设计规范（来自设计文档第3.2.2节）：
 * - 使用 Ant Design Alert 组件
 * - type: "error"
 * - message: "危险操作已被系统拦截"
 * - description: 显示具体操作和风险信息
 * - closable: false
 *
 * @param props 组件属性
 * @returns React组件
 * @author 小新
 */
export const SecurityAlert: React.FC<SecurityAlertProps> = ({
  command,
  score,
  message,
}) => {
  return (
    <Alert
      type="error"
      showIcon={false}
      closable={false}
      style={{
        marginBottom: 16,
        border: '2px solid #ff4d4f',
        borderRadius: 8,
        backgroundColor: '#fff1f0',
      }}
      message={
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* 头部：图标 + 标题 */}
          <Space align="center">
            <StopOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
            <Title level={4} style={{ margin: 0, color: '#cf1322' }}>
              危险操作已被拦截
            </Title>
          </Space>

          {/* 风险等级标签 */}
          <Tag color="red" style={{ fontSize: 14, alignSelf: 'flex-start' }}>
            <WarningOutlined /> 风险等级: {score}分 (9-10分/致命)
          </Tag>

          {/* 提示信息 */}
          <Text style={{ fontSize: 16, color: '#cf1322' }}>{message}</Text>

          {/* 显示被拦截的命令 */}
          <div
            style={{
              backgroundColor: '#ffccc7',
              border: '1px solid #ff4d4f',
              borderRadius: 4,
              padding: 12,
            }}
          >
            <Text type="secondary" style={{ fontSize: 12 }}>
              被拦截的命令：
            </Text>
            <br />
            <Text
              code
              style={{
                display: 'block',
                marginTop: 4,
                fontSize: 14,
                wordBreak: 'break-all',
                color: '#cf1322',
              }}
            >
              {command}
            </Text>
          </div>

          {/* 说明文字 */}
          <Text type="secondary" style={{ fontSize: 12 }}>
            💡 系统已自动阻止此危险操作，如需执行请联系管理员。
          </Text>
        </Space>
      }
    />
  );
};

export default SecurityAlert;
