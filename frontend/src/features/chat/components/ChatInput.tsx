// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 输入框组合根, 六组件组合, Props兼容父级+modelPickerSlot/onSend二参(8.14 E1)
// 编辑历史: 2026-08-28 小欧 - ①A/a1: 去孤行+gap8, 指令+续聊并入SubmitBar leftExtra, 外层flex column gap8, 总高≤5行
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①CI-01乐观清空(先save后清, onSend失败由父级回补)②CI-02增sessionId入参+useEffect重置draft防跨会话泄漏 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 修复: handleSendInternal改async可回补, onSend抛错时还原draft/linked, 杜绝网络/500致输入丢失
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.8: 删本地 linked 自持 state(跨会话泄漏根因), 改受控 linkEnabled+
//   onToggleLink(真源寄存 useChatState); onSend 第二参由 contextLinkMode 改 linkEnabled: boolean;
//   删发送后 setLinked(false)(违背用户意图的根因行), draft 回补保留 — 小欧 2026-10-03
/**
 * ChatInput - 输入框组合根（8.12 六组件组合）
 *
 * 【小欧 2026-08-26 8.12】单体拆分为 InputCore/TaskTypeToggle/CommandPanel/
 * AttachmentArea/SubmitBar 组合；对外 Props 保持 loading/isReceiving/isPaused/
 * onCancel/onTogglePause 兼容父级，新增 modelPickerSlot；chatLink 开关改受控
 * （linkEnabled/onToggleLink，真源在 useChatState；文档[4] 5.8），onSend 第二参为 boolean linkEnabled。
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
  onSend: (content: string, linkEnabled: boolean) => void | Promise<void>;
  onCancel: () => void;
  onTogglePause: () => void;
  modelPickerSlot?: React.ReactNode;
  sessionId?: string | null;
  linkEnabled: boolean;
  onToggleLink: (enabled: boolean) => void;
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
  linkEnabled,
  onToggleLink,
}) => {
  const [draft, setDraft] = useState('');
  useEffect(() => {
    setDraft('');
  }, [sessionId]);

  // 2026-09-03 小欧 修复: 乐观清空改可回补 — 备份draft, onSend失败时回填防输入永久丢失 - 小欧-2026-09-03
  // linked 不再复位(违背用户粘性意图), 开关真源在 useChatState.linkEnabled
  const handleSendInternal = async () => {
    const content = draft.trim();
    if (!content || loading || isReceiving) return;
    const backup = draft;
    setDraft('');
    try {
      await onSend(content, linkEnabled);
    } catch {
      setDraft(backup);
    }
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
            <TaskTypeToggle checked={linkEnabled} onChange={onToggleLink} />
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
