/**
 * ChatToolbar 组件 - 会话工具栏（topbar slot）
 *
 * 【小欧 2026-08-26 8.1】按 4.3.1 定案精简：仅保留「新建会话」。
 * 流式开关/显示过程/清空对话移除——始终流式；清空对话功能随面板化迁出顶栏。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Button, Space } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

interface ChatToolbarProps {
  onNewSession: () => void;
}

const ChatToolbar: React.FC<ChatToolbarProps> = ({ onNewSession }) => {
  return (
    <Space>
      <Button
        icon={<PlusOutlined />}
        onClick={onNewSession}
        size="small"
        type="primary"
        style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
      >
        新建会话
      </Button>
    </Space>
  );
};

ChatToolbar.displayName = 'ChatToolbar';

export default ChatToolbar;
