// 编辑历史: 2026-08-26 小欧 - 8.1 实施: 会话工具栏精简仅新建会话(4.3.1)
// 编辑历史: 2026-08-28 小欧 - ②B/b1: 去Space冗余+删zIndex100残留, gap统一
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
import { Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

interface ChatToolbarProps {
  onNewSession: () => void;
}

const ChatToolbar: React.FC<ChatToolbarProps> = ({ onNewSession }) => {
  return (
    <Button
      icon={<PlusOutlined />}
      onClick={onNewSession}
      size="small"
      type="primary"
    >
      新建会话
    </Button>
  );
};

ChatToolbar.displayName = 'ChatToolbar';

export default ChatToolbar;
