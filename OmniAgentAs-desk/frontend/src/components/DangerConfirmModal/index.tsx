/**
 * 危险操作确认弹窗 - DangerConfirmModal
 * 
 * 功能：7-8分高风险操作的确认弹窗（基于设计文档第3.2.2节）
 * 样式：橙色边框、警告图标、确认/取消按钮
 * 
 * @author 小新
 * @version 2.0.0
 * @since 2026-02-19
 * @update 升级到v2.0 API（score+message）
 */

import React from 'react';
import { Modal, Button, Space, Typography, Tag } from 'antd';
import { WarningOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

/**
 * 组件属性
 */
interface DangerConfirmModalProps {
  /** 是否可见 */
  visible: boolean;
  /** 操作命令 */
  command: string;
  /** 风险分数（7-8分） */
  score: number;
  /** 提示信息 */
  message: string;
  /** 确认回调 */
  onConfirm: () => void;
  /** 取消回调 */
  onCancel: () => void;
  /** 加载状态 */
  loading?: boolean;
}

/**
 * 危险操作确认弹窗组件
 * 
 * 设计规范（来自设计文档第3.2.2节）：
 * - 宽度: 480px
 * - 边框: 2px solid #faad14 (橙色)
 * - 图标: WarningOutlined (橙色)
 * - 按钮: "确认执行"（橙色）、"取消"（灰色）
 * 
 * @param props 组件属性
 * @returns React组件
 * @author 小新
 */
export const DangerConfirmModal: React.FC<DangerConfirmModalProps> = ({
  visible,
  command,
  score,
  message,
  onConfirm,
  onCancel,
  loading = false
}) => {
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
        overflow: 'hidden'
      }}
      bodyStyle={{
        padding: '24px'
      }}
    >
      <div style={{ textAlign: 'center' }}>
        {/* 警告图标 */}
        <WarningOutlined 
          style={{ 
            fontSize: 48, 
            color: '#faad14',
            marginBottom: 16 
          }} 
        />
        
        {/* 标题 */}
        <Title level={4} style={{ marginBottom: 8 }}>
          危险操作确认
        </Title>
        
        {/* 风险等级标签 */}
        <Tag color="orange" style={{ marginBottom: 16, fontSize: 14 }}>
          风险等级: {score}分 (7-8分)
        </Tag>
        
        {/* 提示信息 */}
        <Text style={{ 
          display: 'block', 
          marginBottom: 12,
          fontSize: 16 
        }}>
          {message}
        </Text>
        
        {/* 显示具体操作 */}
        <div style={{
          backgroundColor: '#fff7e6',
          border: '1px solid #ffd591',
          borderRadius: 4,
          padding: 12,
          marginBottom: 24,
          textAlign: 'left'
        }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            操作命令：
          </Text>
          <br />
          <Text code style={{ 
            display: 'block',
            marginTop: 4,
            fontSize: 14,
            wordBreak: 'break-all'
          }}>
            {command}
          </Text>
        </div>
        
        {/* 风险等级提示 */}
        <Text type="warning" style={{ 
          display: 'block', 
          marginBottom: 24,
          fontSize: 14 
        }}>
          ⚠️ 此操作可能对项目文件造成影响，请确认是否继续？
        </Text>
        
        {/* 按钮组 */}
        <Space size="middle">
          <Button 
            onClick={onCancel}
            size="large"
            disabled={loading}
          >
            取消
          </Button>
          <Button 
            type="primary"
            onClick={onConfirm}
            size="large"
            loading={loading}
            style={{
              backgroundColor: '#faad14',
              borderColor: '#faad14',
              color: '#fff'
            }}
          >
            确认执行
          </Button>
        </Space>
      </div>
    </Modal>
  );
};

export default DangerConfirmModal;
