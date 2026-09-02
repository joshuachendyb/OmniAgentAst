// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 输入框组合根, 六组件组合, Props兼容父级+modelPickerSlot/onSend二参(8.14 E1)
// 编辑历史: 2026-08-28 小欧 - ①A/a1: 去孤行+gap8, 指令+续聊并入SubmitBar leftExtra, 外层flex column gap8, 总高≤5行
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①CI-01乐观清空(先save后清, onSend失败由父级回补)②CI-02增sessionId入参+useEffect重置draft防跨会话泄漏 — 小欧-2026-09-02
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

import React, { useEffect, useState } from 'react';
import { Space } from 'antd';
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
  sessionId?: string | null;
}

const ChatInput: React.FC<ChatInputProps> = ({
  loading,
  isReceiving,
  isPaused,
  onSend,
  onCancel,
  onTogglePause,
  modelPickerSlot,
  sessionId,
}) => {
  const [draft, setDraft] = useState('');
  const [linked, setLinked] = useState(false); // 默认新任务 independent
  useEffect(() => {
    setDraft('');
  }, [sessionId]);

  const handleSendInternal = () => {
    const content = draft.trim();
    if (!content || loading || isReceiving) return;
    setDraft('');
    setLinked(false); // 发送后复位为新任务（4.6.1）
    onSend(content, linked ? 'linked' : 'independent'); // context_link_mode 随 E1（8.14）
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <InputCore
        value={draft}
        onChange={setDraft}
        onPressEnter={handleSendInternal}
        disabled={loading}
      />
      <SubmitBar
        loading={loading}
        isReceiving={isReceiving}
        isPaused={isPaused}
        modelPickerSlot={modelPickerSlot ?? null}
        leftExtra={
          <Space
            size={8}
            style={{ display: 'inline-flex', alignItems: 'center' }}
          >
            <CommandPanel
              onPick={(c) => setDraft((d) => (d ? `${d}\n${c}` : c))}
            />
            <TaskTypeToggle checked={linked} onChange={setLinked} />
          </Space>
        }
        onSend={handleSendInternal}
        onCancel={onCancel}
        onTogglePause={onTogglePause}
      />
    </div>
  );
};

export { ChatInput };
