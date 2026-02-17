/**
 * DangerConfirmModal组件 - 危险操作确认弹窗
 * 
 * 功能：检测危险命令时显示确认弹窗，防止误操作
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-18
 */

import React from 'react';
import {
  Modal,
  Card,
  Alert,
  Space,
  Typography,
  Button,
  Tag,
} from 'antd';
import {
  ExclamationCircleOutlined,
  WarningOutlined,
  SafetyOutlined,
  CodeOutlined,
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

interface DangerConfirmModalProps {
  /** 是否显示 */
  visible: boolean;
  /** 命令内容 */
  command: string;
  /** 风险描述 */
  risk: string;
  /** 建议 */
  suggestion?: string;
  /** 确认回调 */
  onConfirm: () => void;
  /** 取消回调 */
  onCancel: () => void;
  /** 加载状态 */
  loading?: boolean;
}

/**
 * 危险操作确认弹窗
 * 
 * 设计要点：
 * - 醒目的红色警告图标
 * - 清晰的命令展示
 * - 明确的风险说明
 * - 需要用户明确确认
 * 
 * @param visible - 是否显示弹窗
 * @param command - 检测到的命令
 * @param risk - 风险描述
 * @param suggestion - 安全建议
 * @param onConfirm - 确认执行回调
 * @param onCancel - 取消回调
 * @param loading - 加载状态
 */
const DangerConfirmModal: React.FC<DangerConfirmModalProps> = ({
  visible,
  command,
  risk,
  suggestion = '该操作可能对系统造成不可逆损害，请确认您知道自己在做什么。',
  onConfirm,
  onCancel,
  loading = false,
}) => {
  /**
   * 高亮显示危险命令中的关键词
   */
  const highlightDangerousParts = (cmd: string): React.ReactNode => {
    const dangerousPatterns = [
      { pattern: /rm\s+-[rf]+/gi, label: '强制删除' },
      { pattern: /mkfs/gi, label: '格式化' },
      { pattern: /dd\s+if=/gi, label: '磁盘写入' },
      { pattern: />\s*\/dev\/null/gi, label: '重定向到空设备' },
      { pattern: /sudo/gi, label: '提权操作' },
      { pattern: /chmod\s+777/gi, label: '全开权限' },
    ];

    let highlighted = cmd;
    dangerousPatterns.forEach(({ pattern, label }) => {
      highlighted = highlighted.replace(pattern, (match) => 
        `{{DANGER:${match}:${label}}}`
      );
    });

    // 解析并渲染
    const parts = highlighted.split(/\{\{DANGER:([^:]+):([^\}]+)\}\}/);
    return (
      <>
        {parts.map((part, index) => {
          if (index % 3 === 1) {
            // 这是危险命令部分
            const command = parts[index];
            const label = parts[index + 1];
            return (
              <span key={index}>
                <Tag color="red" style={{ fontFamily: 'monospace', fontSize: 14 }}>
                  {command}
                </Tag>
                <Text type="danger" style={{ fontSize: 12, marginLeft: 4 }}>
                  ({label})
                </Text>
              </span>
            );
          } else if (index % 3 === 0) {
            // 普通文本
            return <span key={index} style={{ fontFamily: 'monospace', fontSize: 14 }}>{part}</span>;
          }
          return null;
        })}
      </>
    );
  };

  return (
    <Modal
      open={visible}
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#ff4d4f', fontSize: 24 }} />
          <Title level={4} style={{ margin: 0, color: '#ff4d4f' }}>
            危险操作确认
          </Title>
        </Space>
      }
      onOk={onConfirm}
      onCancel={onCancel}
      okText={
        <Space>
          <WarningOutlined />
          确认执行
        </Space>
      }
      cancelText="取消操作"
      okButtonProps={{ 
        danger: true, 
        loading,
        size: 'large',
      }}
      cancelButtonProps={{
        size: 'large',
      }}
      width={600}
      centered
      maskClosable={false}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* 风险警告 */}
        <Alert
          type="error"
          message={
            <Space>
              <WarningOutlined />
              <Text strong>系统检测到危险命令</Text>
            </Space>
          }
          description={risk}
          showIcon={false}
          style={{ 
            background: '#fff1f0', 
            border: '1px solid #ffccc7',
            borderRadius: 8,
          }}
        />

        {/* 命令展示 */}
        <Card
          size="small"
          title={
            <Space>
              <CodeOutlined />
              <Text strong>命令内容</Text>
            </Space>
          }
          style={{ 
            background: '#fff',
            border: '1px solid #ffccc7',
          }}
          headStyle={{ 
            background: '#fff1f0',
            borderBottom: '1px solid #ffccc7',
          }}
        >
          <div style={{ 
            padding: 12, 
            background: '#fff1f0', 
            borderRadius: 4,
            overflowX: 'auto',
          }}>
            <Text code style={{ fontSize: 14, whiteSpace: 'pre-wrap' }}>
              {highlightDangerousParts(command)}
            </Text>
          </div>
        </Card>

        {/* 风险说明 */}
        <Alert
          type="warning"
          message={
            <Space>
              <SafetyOutlined />
              <Text strong>风险提示</Text>
            </Space>
          }
          description={
            <Paragraph>
              {suggestion}
              <br /><br />
              <Text type="warning">
                ⚠️ 如果这不是您期望的操作，请点击"取消操作"。
              </Text>
            </Paragraph>
          }
          showIcon={false}
          style={{ 
            background: '#fffbe6', 
            border: '1px solid #ffe58f',
            borderRadius: 8,
          }}
        />

        {/* 确认提示 */}
        <div style={{ textAlign: 'center', padding: '12px 0' }}>
          <Text type="danger" strong style={{ fontSize: 16 }}>
            您确定要执行这个危险操作吗？
          </Text>
        </div>
      </Space>
    </Modal>
  );
};

export default DangerConfirmModal;
