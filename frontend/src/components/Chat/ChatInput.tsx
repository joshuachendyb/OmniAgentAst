// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 输入框组合根, 六组件组合, Props兼容父级+modelPickerSlot/onSend二参(8.14 E1)
/**
 * ChatInput - 输入框组合根（8.12 六组件组合）
 *
 * 【小欧 2026-08-26 8.12】单体拆分为 InputCore/TaskTypeToggle/CommandPanel/
 * AttachmentArea/SubmitBar 组合；对外 Props 保持 loading/isReceiving/isPaused/
 * onCancel/onTogglePause 兼容父级，新增 modelPickerSlot 与 onSend 第二参
 * contextLinkMode（8.14 E1）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useState } from 'react';
import { InputCore } from './input/InputCore';
import { TaskTypeToggle } from './input/TaskTypeToggle';
import { CommandPanel } from './input/CommandPanel';
import { SubmitBar } from './input/SubmitBar';

interface ChatInputProps {
  loading: boolean;
  isReceiving: boolean;
  isPaused: boolean;
  onSend: (content: string, contextLinkMode?: 'linked' | 'independent') => void;
  onCancel: () => void;
  onTogglePause: () => void;
  modelPickerSlot?: React.ReactNode;
}

const ChatInput: React.FC<ChatInputProps> = ({
  loading,
  isReceiving,
  isPaused,
  onSend,
  onCancel,
  onTogglePause,
  modelPickerSlot,
}) => {
  const [draft, setDraft] = useState('');
  const [linked, setLinked] = useState(false); // 默认新任务 independent

  const handleSendInternal = () => {
    const content = draft.trim();
    if (!content || loading || isReceiving) return;
    onSend(content, linked ? 'linked' : 'independent'); // context_link_mode 随 E1（8.14）
    setDraft('');
    setLinked(false); // 发送后复位为新任务（4.6.1）
  };

  return (
    <div style={{ padding: '4px 0' }}>
      <CommandPanel onPick={(c) => setDraft((d) => (d ? `${d}\n${c}` : c))} />
      <InputCore
        value={draft}
        onChange={setDraft}
        onPressEnter={handleSendInternal}
        disabled={loading}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <TaskTypeToggle checked={linked} onChange={setLinked} />
        <span style={{ flex: 1 }} />
      </div>
      <SubmitBar
        loading={loading}
        isReceiving={isReceiving}
        isPaused={isPaused}
        modelPickerSlot={modelPickerSlot ?? null}
        onSend={handleSendInternal}
        onCancel={onCancel}
        onTogglePause={onTogglePause}
      />
    </div>
  );
};

export { ChatInput };
