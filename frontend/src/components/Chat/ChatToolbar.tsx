/**
 * ChatToolbar 组件 - 会话工具栏按钮组
 * 
 * 功能：
 * - 新建会话按钮
 * - 流式模式开关
 * - 显示过程开关（仅流式模式下显示）
 * - 清空对话按钮
 * 
 * @author 小沈
 * @date 2026-04-21
 */

import React from 'react';
import { Button, Tag, Space } from 'antd';
import { PlusOutlined, ThunderboltOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons';

interface ChatToolbarProps {
  // 状态
  useStream: boolean;
  showExecution: boolean;
  
  // 回调
  onNewSession: () => void;
  onClear: () => void;
  onToggleStream: (checked: boolean) => void;
  onToggleExecution: () => void;
}

/**
 * ChatToolbar - 会话工具栏组件
 */
const ChatToolbar: React.FC<ChatToolbarProps> = ({
  useStream,
  showExecution,
  onNewSession,
  onClear,
  onToggleStream,
  onToggleExecution,
}) => {
  return (
    <Space>
      {/* 新建会话按钮 */}
      <Button
        icon={<PlusOutlined />}
        onClick={onNewSession}
        size="small"
        type="primary"
        style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
      >
        新建会话
      </Button>

      {/* 流式开关（同时控制显示过程） */}
      <Tag.CheckableTag
        checked={useStream}
        onChange={(checked) => {
          onToggleStream(checked);
        }}
        style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
      >
        <ThunderboltOutlined /> {useStream ? "流式关闭" : "流式开启"}
      </Tag.CheckableTag>

      {/* 执行过程显示开关（仅在流式模式下显示） */}
      {useStream && (
        <Button
          size="small"
          icon={showExecution ? <EyeOutlined /> : <EyeInvisibleOutlined />}
          onClick={onToggleExecution}
          style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
        >
          {showExecution ? "隐藏过程" : "显示过程"}
        </Button>
      )}

      {/* 清空对话按钮 */}
      <Button 
        onClick={onClear}
        size="small"
        style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
      >
        清空对话
      </Button>
    </Space>
  );
};

ChatToolbar.displayName = 'ChatToolbar';

export default ChatToolbar;