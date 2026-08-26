/**
 * SubmitBar - 底部功能行：模型按钮(ModelPicker) + 附件 + 发送/停止 + 暂停·继续
 *
 * 【小欧 2026-08-26 8.12】4.3.6 底部一行；与附件按钮同一行，位于输入区底部。
 * ModelPicker 为既有组件（7.13 L2 落库已实施），此处原位引用。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Button, Space } from 'antd';
import {
  PauseOutlined,
  PlayCircleOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { AttachmentArea } from './AttachmentArea';

interface SubmitBarProps {
  loading: boolean;
  isReceiving: boolean;
  isPaused: boolean;
  modelPickerSlot: React.ReactNode; // 既有 ModelPicker 实例
  onSend: () => void;
  onCancel: () => void;
  onTogglePause: () => void;
}

const SubmitBar: React.FC<SubmitBarProps> = ({
  loading,
  isReceiving,
  isPaused,
  modelPickerSlot,
  onSend,
  onCancel,
  onTogglePause,
}) => (
  <Space
    style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}
  >
    <Space>
      {modelPickerSlot}
      <AttachmentArea />
    </Space>
    <Space>
      {loading || isReceiving ? (
        <>
          <Button
            size="small"
            danger
            icon={<StopOutlined />}
            onClick={onCancel}
          >
            停止
          </Button>
          <Button
            size="small"
            icon={isPaused ? <PlayCircleOutlined /> : <PauseOutlined />}
            onClick={onTogglePause}
          >
            {isPaused ? '继续' : '暂停'}
          </Button>
        </>
      ) : (
        <Button
          size="small"
          type="primary"
          icon={<SendOutlined />}
          onClick={onSend}
        >
          发送
        </Button>
      )}
    </Space>
  </Space>
);

export { SubmitBar };
