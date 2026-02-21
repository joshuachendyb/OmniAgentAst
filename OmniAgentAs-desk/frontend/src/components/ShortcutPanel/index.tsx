/**
 * ShortcutPanel组件 - 快捷指令面板
 * 
 * 功能：提供常用快捷指令的快速访问
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-21
 */

import React from 'react';
import { Modal, List, Tag, Button } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';

interface ShortcutPanelProps {
  visible: boolean;
  onClose: () => void;
  onExecute: (command: string) => void;
}

interface Shortcut {
  command: string;
  description: string;
  category: string;
}

const shortcuts: Shortcut[] = [
  { command: '/clear', description: '清空当前对话', category: '对话' },
  { command: '/help', description: '显示帮助信息', category: '帮助' },
  { command: '/history', description: '查看历史记录', category: '会话' },
  { command: '/settings', description: '打开设置页面', category: '系统' },
];

const ShortcutPanel: React.FC<ShortcutPanelProps> = ({ 
  visible, onClose, onExecute 
}) => {
  return (
    <Modal
      title={<><ThunderboltOutlined /> 快捷指令</>}
      open={visible}
      onCancel={onClose}
      footer={null}
      width={600}
    >
      <List
        dataSource={shortcuts}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button 
                type="primary" 
                size="small"
                onClick={() => {
                  onExecute(item.command);
                  onClose();
                }}
              >
                执行
              </Button>
            ]}
          >
            <List.Item.Meta
              avatar={<Tag color="blue">{item.category}</Tag>}
              title={<code>{item.command}</code>}
              description={item.description}
            />
          </List.Item>
        )}
      />
    </Modal>
  );
};

export default ShortcutPanel;