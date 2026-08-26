/**
 * CommandPanel - 快捷指令面板（复用既有 ShortcutPanel 逻辑）
 * 【小欧 2026-08-26 8.12】可注册更多指令，不侵入 InputCore（4.6.2）。
 * 【R1 二轮 A5 修正】对齐 ShortcutPanel 真实接口 {visible, onClose, onExecute}
 * （components/ShortcutPanel/index.tsx:15-19，三者全必填），本组件自持 visible 状态。
 * @author 小欧 @date 2026-08-26
 */
import React, { useState } from 'react';
import { Button } from 'antd';
import { AppstoreOutlined } from '@ant-design/icons';
import ShortcutPanel from '../../ShortcutPanel';

interface CommandPanelProps {
  onPick: (command: string) => void;
}

const CommandPanel: React.FC<CommandPanelProps> = ({ onPick }) => {
  const [visible, setVisible] = useState(false);
  return (
    <>
      <Button
        icon={<AppstoreOutlined />}
        size="small"
        onClick={() => setVisible(true)}
      >
        指令
      </Button>
      <ShortcutPanel
        visible={visible}
        onClose={() => setVisible(false)}
        onExecute={(command) => {
          onPick(command);
          setVisible(false);
        }}
      />
    </>
  );
};

export { CommandPanel };
