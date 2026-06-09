/**
 * AuthorizationModal - HITL人工确认弹窗
 *
 * 功能：显示工具执行授权请求，用户可选择允许/拒绝/本会话信任
 *
 * 设计规范（参考DangerConfirmModal）：
 * - 宽度: 480px
 * - 边框: 2px solid #faad14 (橙色)
 * - 图标: WarningOutlined (橙色, 48px)
 * - 按钮: "允许执行"（橙色）、"拒绝执行"（灰色）
 * - 居中对齐
 *
 * 【v3.4实施 2026-06-09 小沈】
 * - SRP: 只负责显示授权弹窗和回传用户选择
 * - KISS: 简单Modal + 3个按钮，不搞复杂状态
 * - DRY: 复用Ant Design Modal组件
 */

import React from 'react';
import { Modal, Button, Space, Typography, Tag, Checkbox } from 'antd';
import { WarningOutlined, ExclamationCircleOutlined, StopOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

export interface AuthorizationRequest {
  toolName: string;
  params: Record<string, unknown>;
  safetyLevel: string;
}

interface AuthorizationModalProps {
  visible: boolean;
  request: AuthorizationRequest | null;
  onConfirm: (confirmed: boolean, trustSession: boolean) => void;
}

const SAFETY_LEVEL_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  read_only: { color: 'green', label: '只读', icon: null },
  safe: { color: 'blue', label: '安全', icon: null },
  destructive: { color: 'orange', label: '破坏性', icon: <WarningOutlined /> },
  dangerous_sandbox: { color: 'volcano', label: '沙箱危险', icon: <ExclamationCircleOutlined /> },
  dangerous: { color: 'red', label: '系统危险', icon: <StopOutlined /> },
};

const AuthorizationModal: React.FC<AuthorizationModalProps> = ({
  visible,
  request,
  onConfirm,
}) => {
  const [trustSession, setTrustSession] = React.useState(false);

  if (!request) {
    return null;
  }

  const safetyConfig = SAFETY_LEVEL_CONFIG[request.safetyLevel] || {
    color: 'default',
    label: request.safetyLevel,
    icon: null,
  };

  const handleConfirm = (confirmed: boolean) => {
    onConfirm(confirmed, trustSession);
    setTrustSession(false);
  };

  return (
    <Modal
      open={visible}
      title={null}
      footer={null}
      closable={false}
      width={480}
      style={{
        border: '2px solid #faad14',
        borderRadius: '8px',
        overflow: 'hidden',
      }}
      styles={{
        body: {
          padding: '24px',
        },
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <WarningOutlined
          style={{
            fontSize: 48,
            color: '#faad14',
            marginBottom: 16,
          }}
        />

        <Title level={4} style={{ marginBottom: 8 }}>
          安全确认请求
        </Title>

        <Tag color={safetyConfig.color} style={{ marginBottom: 16, fontSize: 14 }}>
          {safetyConfig.label}
        </Tag>

        <div
          style={{
            backgroundColor: '#fff7e6',
            border: '1px solid #ffd591',
            borderRadius: 4,
            padding: 12,
            marginBottom: 16,
            textAlign: 'left',
          }}
        >
          <Text type="secondary" style={{ fontSize: 12 }}>
            工具名称：
          </Text>
          <br />
          <Text strong style={{ display: 'block', marginTop: 4, fontSize: 14 }}>
            {request.toolName}
          </Text>
        </div>

        <div
          style={{
            backgroundColor: '#f5f5f5',
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            padding: 12,
            marginBottom: 16,
            textAlign: 'left',
            maxHeight: 200,
            overflow: 'auto',
          }}
        >
          <Text type="secondary" style={{ fontSize: 12 }}>
            执行参数：
          </Text>
          <br />
          <Text
            code
            style={{
              display: 'block',
              marginTop: 4,
              fontSize: 12,
              wordBreak: 'break-all',
            }}
          >
            {JSON.stringify(request.params, null, 2)}
          </Text>
        </div>

        <div style={{ marginBottom: 24 }}>
          <Checkbox
            checked={trustSession}
            onChange={(e) => setTrustSession(e.target.checked)}
          >
            本次会话信任此操作
          </Checkbox>
        </div>

        <Space size="middle">
          <Button
            onClick={() => handleConfirm(false)}
            size="large"
          >
            拒绝执行
          </Button>
          <Button
            type="primary"
            onClick={() => handleConfirm(true)}
            size="large"
            style={{
              backgroundColor: '#faad14',
              borderColor: '#faad14',
              color: '#fff',
            }}
          >
            允许执行
          </Button>
        </Space>
      </div>
    </Modal>
  );
};

export default AuthorizationModal;