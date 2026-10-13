// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 输入框组合根, 六组件组合, Props兼容父级+modelPickerSlot/onSend二参(8.14 E1)
// 编辑历史: 2026-08-28 小欧 - ①A/a1: 去孤行+gap8, 指令+续聊并入SubmitBar leftExtra, 外层flex column gap8, 总高≤5行
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①CI-01乐观清空(先save后清, onSend失败由父级回补)②CI-02增sessionId入参+useEffect重置draft防跨会话泄漏 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 修复: handleSendInternal改async可回补, onSend抛错时还原draft/linked, 杜绝网络/500致输入丢失
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.8: 删本地 linked 自持 state(跨会话泄漏根因), 改受控 linkEnabled+
//   onToggleLink(真源寄存 useChatState); onSend 第二参由 contextLinkMode 改 linkEnabled: boolean;
//   删发送后 setLinked(false)(违背用户意图的根因行), draft 回补保留 — 小欧 2026-10-03
// 编辑历史: 2026-10-08 小欧 - 文档[11] 3.5.2: 发送门判据抽 utils/sendGate 单一真源(原裸 loading 挡死开态插话), disabled 与发送门共用
// 编辑历史: 2026-10-10 小欧 - 文档[16] §3.6.5/§3.6.6: Props 补 sessionWorkspaces/setSessionWorkspaces;
//   挂载 SessionWorkspacePanel(wsPanelOpen 受控); 传 SubmitBar 的 workspaceCount(现算)与 onOpenWorkspaces
//   (无会话时不传 → SubmitBar 不渲染入口, GET 空 id 必 422 干脆不显示); 关闭面板时重拉一次同步徽标(失败静默) — 小欧-2026-10-10
// 编辑历史: 2026-10-13 13:45 小欧 - 草稿持久化 + 最近提交历史(输入历史):
//   ①草稿改由 useInputDraft 单一真源托管(内存 + sessionStorage 持久化, 复用既有 saveDraft/loadDraft);
//     删掉原先"会话一改就无条件清空草稿"的副作用式清空 —— 现由 hook 内部按
//     「首次挂载 + 上次非空且真切换」载入目标会话草稿, 既防跨会话串草稿, 又防建会话回填窗口吞掉用户连打的字
//   ②提交成功后 addRecentInput(content) 记入本机历史(localStorage, 跨会话); /clear /help /history /settings2 不入历史;
//     提交失败(throw)不记; 重复文本只更新 ts 不新增条目
//   ③提交栏新增「历史输入」面板(草稿区可丢弃 + 最近提交区可清空二次确认)
//   ④InputCore 上抛 onKeyDown: 光标在首行行首按 ↑ / 末行行尾按 ↓ 翻历史(中间位置不劫持, 保护多行光标编辑);
//     IME 组字期间(e.nativeEvent.isComposing)一律不劫持 —— 拼音输入法下 ↑↓ 是切换候选词, 全仓无先例故必须自己判
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

import React, { useCallback, useState } from 'react';
import { Space } from 'antd';
import { InputCore } from './input/InputCore';
import { TaskTypeToggle } from './input/TaskTypeToggle';
import { CommandPanel } from './input/CommandPanel';
import { SubmitBar } from './input/SubmitBar';
import SessionWorkspacePanel from './input/SessionWorkspacePanel'; // 2026-10-10 小欧 - 文档[16] §3.6.6 面板挂载(默认导出)
import { InputHistoryPanel } from './input/InputHistoryPanel';
import { useInputDraft } from '../hooks/useInputDraft';
import {
  loadRecentInputs,
  addRecentInput,
  clearRecentInputs,
  type RecentInput,
} from '../utils/recentInputs';
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
  // 2026-10-13 13:45 小欧: 草稿单一真源(内存 + sessionStorage 持久化), 取代原自持 useState + 无条件清空 effect
  const { draft, setDraft } = useInputDraft(sessionId);
  // 2026-10-13 13:45 小欧: 本机最近提交历史(懒初始化一次; 写入只发生在本标签页, 无需跨标签页同步)
  const [recents, setRecents] = useState<RecentInput[]>(loadRecentInputs);
  // 2026-10-13 13:45 小欧: 历史翻动游标(-1 = 未在翻历史); histBackup = 上翻前正在输入的内容, ↓ 翻到底时回填
  const [histIdx, setHistIdx] = useState(-1);
  const [histBackup, setHistBackup] = useState<string | null>(null);
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

  // 2026-10-08 小欧 - 文档[11] 3.5.2: 发送门与输入框禁用共用此一处
  const sendBlocked = isSendBlocked(loading, isReceiving, allowInterject);

  /** 退出历史翻动态(手动打字 / 面板选中后都要复位, 否则 ↑↓ 基准错乱) */
  const exitHistory = useCallback(() => {
    setHistIdx(-1);
    setHistBackup(null);
  }, []);

  // 2026-09-03 小欧 修复: 乐观清空改可回补 — 备份draft, onSend失败时回填防输入永久丢失 - 小欧-2026-09-03
  // linked 不再复位(违背用户粘性意图), 开关真源在 useChatState.linkEnabled
  const handleSendInternal = async () => {
    const content = draft.trim();
    if (!content || sendBlocked) return;
    const backup = draft;
    exitHistory();
    setDraft('');
    try {
      await onSend(content, { linkEnabled, allowInterject }); // 对象参数, 见 3.5.4
      // 2026-10-13 13:45 小欧: **提交成功后**才记历史(onSend 抛错 = 提交失败, 不能记; 流式中途报错不 reject,
      //   故面板文案用「最近提交」而非「发送成功」)
      addRecentInput(content);
      setRecents(loadRecentInputs());
    } catch {
      setDraft(backup);
    }
  };

  /**
   * 2026-10-13 13:45 小欧 - 历史翻动键盘判定。
   * ⚠️ ①IME 组字期间(e.nativeEvent.isComposing)一律放行: 拼音输入法下 ↑↓ 是「切换候选词」,
   *    劫持会让候选词切不了 —— 全中文用户必踩, 全仓无 isComposing 先例, 故必须自己判。
   * ⚠️ ②只在光标位于首行行首 / 末行行尾时才劫持: TextArea 里 ↑↓ 默认移动光标,
   *    无条件劫持会导致多行文本无法上下移动光标 = 严重功能退化。
   */
  const handleInputKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.nativeEvent.isComposing) return;
      const el = e.currentTarget;
      const atFirstLine = el.selectionStart === 0;
      const atLastLine = el.selectionEnd === el.value.length;

      if (e.key === 'ArrowUp' && recents.length > 0 && atFirstLine) {
        const next = histIdx + 1;
        if (next >= recents.length) return;
        e.preventDefault();
        if (histIdx < 0) setHistBackup(draft);
        setHistIdx(next);
        setDraft(recents[next].text);
        requestAnimationFrame(() =>
          el.setSelectionRange(el.value.length, el.value.length)
        );
        return;
      }

      if (e.key === 'ArrowDown' && histIdx >= 0 && atLastLine) {
        e.preventDefault();
        const next = histIdx - 1;
        if (next < 0) {
          setHistIdx(-1);
          setDraft(histBackup ?? '');
          setHistBackup(null);
        } else {
          setHistIdx(next);
          setDraft(recents[next].text);
        }
        requestAnimationFrame(() =>
          el.setSelectionRange(el.value.length, el.value.length)
        );
        return;
      }

      if (e.key === 'Escape' && histIdx >= 0) {
        e.preventDefault();
        setHistIdx(-1);
        setDraft(histBackup ?? '');
        setHistBackup(null);
      }
    },
    [recents, histIdx, histBackup, draft, setDraft]
  );

  /** 手动打字时复位历史游标(否则打完字按 ↑ 会从旧游标继续, 跳错条目) */
  const handleInputChange = useCallback(
    (v: string) => {
      setDraft(v);
      if (histIdx >= 0) exitHistory();
    },
    [histIdx, setDraft, exitHistory]
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <InputCore
        value={draft}
        onChange={handleInputChange}
        onPressEnter={handleSendInternal}
        onKeyDown={handleInputKeyDown}
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
            {/* 2026-10-13 13:45 小欧 - 历史输入面板(草稿区 + 最近提交区) */}
            <InputHistoryPanel
              draft={draft}
              recents={recents}
              onDiscardDraft={() => {
                exitHistory();
                setDraft('');
              }}
              onPick={(t) => {
                exitHistory();
                setDraft(t);
              }}
              onClear={() => {
                clearRecentInputs();
                setRecents([]);
              }}
            />
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
