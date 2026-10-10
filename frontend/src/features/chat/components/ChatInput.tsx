// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 输入框组合根, 六组件组合, Props兼容父级+modelPickerSlot/onSend二参(8.14 E1)
// 编辑历史: 2026-08-28 小欧 - ①A/a1: 去孤行+gap8, 指令+续聊并入SubmitBar leftExtra, 外层flex column gap8, 总高≤5行
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①CI-01乐观清空(先save后清, onSend失败由父级回补)②CI-02增sessionId入参+useEffect重置draft防跨会话泄漏 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 修复: handleSendInternal改async可回补, onSend抛错时还原draft/linked, 杜绝网络/500致输入丢失
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.8: 删本地 linked 自持 state(跨会话泄漏根因), 改受控 linkEnabled+
//   onToggleLink(真源寄存 useChatState); onSend 第二参由 contextLinkMode 改 linkEnabled: boolean;
//   删发送后 setLinked(false)(违背用户意图的根因行), draft 回补保留 — 小欧 2026-10-03
// 编辑历史: 2026-10-08 小欧 - 文档[11] 3.5.2: 发送门判据抽 utils/sendGate 单一真源(原裸 loading 挡死开态插话), disabled 与发送门共用
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
import SessionWorkspacePanel from './input/SessionWorkspacePanel'; // 2026-10-10 小欧 - 文档[16] §3.6.6 面板挂载(默认导出)
import type { SendOpts, WorkspaceEntry } from '../../../types/chat'; // 2026-10-07 小欧 - 文档[11] 3.5.4(决策 14 对象参数)
import { sessionApi } from '../../../services/api/session.api'; // 2026-10-10 小欧 - 文档[16]: 关闭面板时重拉徽标数
import { isSendBlocked } from '../utils/sendGate'; // 2026-10-08 小欧 - 文档[11] 3.5.2: 发送门单一真源

interface ChatInputProps {
  loading: boolean;
  isReceiving: boolean;
  isPaused: boolean;
  onSend: (content: string, opts: SendOpts) => void | Promise<void>;
  onCancel: () => void;
  onTogglePause: () => void;
  modelPickerSlot?: React.ReactNode;
  sessionId?: string | null;
  linkEnabled: boolean;
  onToggleLink: (enabled: boolean) => void;
  allowInterject: boolean; // 2026-10-07 小欧 - 文档[11] 3.5.2
  onToggleInterject: (enabled: boolean) => void;
  // 2026-10-10 小欧 - 文档[16] §3.6.5: 会话使用的目录（徽标数 + 面板回写）
  sessionWorkspaces: WorkspaceEntry[];
  setSessionWorkspaces: React.Dispatch<React.SetStateAction<WorkspaceEntry[]>>;
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
  allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.2
  onToggleInterject,
  sessionWorkspaces, // 2026-10-10 小欧 - 文档[16]
  setSessionWorkspaces,
}) => {
  const [draft, setDraft] = useState('');
  // 2026-10-10 小欧 - 文档[16] §3.6.6: 面板挂载点
  const [wsPanelOpen, setWsPanelOpen] = useState(false);
  // 2026-10-10 小欧: 面板关闭时重拉一次徽标数（后端 reconcile/禁区清理可能改行，
  //   前端只在 sessionId 变化时刷新，此处补齐漂移；失败静默（具名 noop 过 no-empty-function 门禁），会话本身可用）
  const noop = () => undefined;
  const handleWsClose = () => {
    setWsPanelOpen(false);
    if (sessionId) {
      sessionApi
        .getWorkspaces(sessionId)
        .then((r) => setSessionWorkspaces(r.workspaces))
        .catch(noop);
    }
  };
  useEffect(() => {
    setDraft('');
  }, [sessionId]);

  // 2026-10-08 小欧 - 文档[11] 3.5.2: 发送门与输入框禁用共用此一处
  const sendBlocked = isSendBlocked(loading, isReceiving, allowInterject);

  // 2026-09-03 小欧 修复: 乐观清空改可回补 — 备份draft, onSend失败时回填防输入永久丢失 - 小欧-2026-09-03
  // linked 不再复位(违背用户粘性意图), 开关真源在 useChatState.linkEnabled
  const handleSendInternal = async () => {
    const content = draft.trim();
    if (!content || sendBlocked) return;
    const backup = draft;
    setDraft('');
    try {
      await onSend(content, { linkEnabled, allowInterject }); // 对象参数, 见 3.5.4
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
        disabled={sendBlocked}
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
        allowInterject={allowInterject} // 2026-10-07 小欧 - 文档[11] 3.5.3: 下传给 SubmitBar(开关落在附件之后)
        onToggleInterject={onToggleInterject}
        // 2026-10-10 小欧 - 文档[16] §3.6.5: 徽标现算(决策72 已作废, 无 dirty 角标)
        // 无会话时不传 onOpenWorkspaces → SubmitBar 不渲染入口（GET 空 id 必 422，不如不显示）
        workspaceCount={sessionWorkspaces.length}
        onOpenWorkspaces={sessionId ? () => setWsPanelOpen(true) : undefined}
        onSend={handleSendInternal}
        onCancel={onCancel}
        onTogglePause={onTogglePause}
      />
      {/* 2026-10-10 小欧 - 文档[16] §3.6.6: 会话使用目录面板(决策70 入口在此打开) */}
      <SessionWorkspacePanel
        sessionId={sessionId ?? ''}
        open={wsPanelOpen}
        onClose={handleWsClose}
        onSaved={setSessionWorkspaces}
      />
    </div>
  );
};

export { ChatInput };
