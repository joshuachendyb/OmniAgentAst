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
// 编辑历史: 2026-10-13 13:45 小欧 - 草稿持久化+最近提交历史: draft 交 useInputDraft 单一真源(localStorage);
//   删"会话一改就无条件清空草稿"; 提交成功后记本机历史(指令不入库); 新增「历史输入」面板; IME 组字期不劫持 ↑↓
// 编辑历史: 2026-10-13 13:55 小欧 - 载入判据二轮修正(真浏览器实锤): 首版"上次非空才载入"致草稿跨会话泄漏;
//   改为"sessionId 变了就载入", 仅「提交标记+上次无会话+提交后又打字」三条件成立才判为建会话回填而跳过
// 编辑历史: 2026-10-13 14:20 小欧 - 焦点归还: 复现出点「发送」后焦点停在按钮、↑↓ 到不了 textarea(历史已入库);
//   InputCore 加 focusKey, 提交成功与"输入框由禁用转可用"两处自增(禁用期 focus() 为空操作, 解锁必须补)
// 编辑历史: 2026-10-13 14:35 小欧 - 三堂会审整改: ①切会话复位 histIdx(否则按↑跳错条目) ②删 ↓ 的死逻辑 atLastLine
//   (恒为 true, 条件归一为 histIdx>=0) ③焦点归还加 rootRef.contains 前置条件, 不夺走用户放到别处的焦点
//   ④面板圆角改走 Radius.SM 令牌
// 编辑历史: 2026-10-13 14:50 小欧 - 撤回落盘防抖(自纠): 防抖化致刷新丢字(刷新不执行 React 卸载清理, 4 条用例变红);
//   草稿体量小, 同步写开销可接受, 拿正确性换性能属退化, 退回同步落盘
// 编辑历史: 2026-10-13 18:15 小欧 - 文档[30] §2.5 B+C: ①输入框不再 disabled(把提交权限误当编辑权限, 执行中打不了字翻不了历史)
//   ②C 常驻灰字显隐改用 sendBlocked(与按钮置灰同源, 原用 isReceiving&&!allowInterject 会漏 loading 窗口)
//   ③提交门被拦不再静默; 实测"弹 toast"反而致执行中无法换行, 改为不可发送时回车照常换行(见 18:40)
// 编辑历史: 2026-10-20 小欧 - 动作按钮组移入框内右下角(北京老陈指令): 新增 SubmitActions 经 InputCore actions
//   插槽挂载(发送/停止/暂停三钮方形图标化), SubmitBar 只留左侧控件; 新增 emptyDraft 置灰判据
//   (与 handleSendInternal 的 !content 同源) 并入发送钮受阻态 — 小欧-2026-10-20
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

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Space } from 'antd';
import { InputCore } from './input/InputCore';
import { TaskTypeToggle } from './input/TaskTypeToggle';
import { CommandPanel } from './input/CommandPanel';
import { SubmitBar } from './input/SubmitBar';
import { SubmitActions } from './input/SubmitActions'; // 2026-10-20 小欧 - 框内右下角动作按钮组(自 SubmitBar 拆出)
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
import { Colors, FontSize } from '@/utils/stepStyles';

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
  const { draft, setDraft, markSubmitted, cancelSubmitted } =
    useInputDraft(sessionId);
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

  // 2026-10-08 小欧 - 文档[11] 3.5.2: 发送门单一真源(2026-10-13 18:15 起只管"提交", 不再兼管输入框禁用)
  const sendBlocked = isSendBlocked(loading, isReceiving, allowInterject);
  // 2026-10-20 小欧 - 空草稿置灰判据, 与 handleSendInternal 的 !content 同判据(单空格也算空, 两处 trim 同步)
  const emptyDraft = draft.trim() === '';

  // 2026-10-13 14:20 小欧 - 焦点归还: 实测"点发送 → 按↑ 翻不出历史"病根是焦点停在按钮上,
  //   ↑↓ 事件到不了 textarea。两处触发: ①提交成功立即自增; ②输入框由"发送受阻"转"可发送"
  //   (模型跑完那一刻)再自增一次 —— 用户点完发送到可发之间有窗口, 补这一次才能接上焦点。
  // 2026-10-13 14:35 小欧 - 反骚扰: ②不能无条件抢焦点, 否则用户已点到别处(侧栏/设置弹窗/别的输入框)
  //   会被突然夺走, 后续打字落错控件。加前置条件: 仅当焦点已丢失(停在 body)或仍停在本组件内才归还。
  //   发送中「发送」按钮被 disabled 不卸载, 故 activeElement 仍在组件内 → 正常归还, 两者不冲突。
  const [focusKey, setFocusKey] = useState(0);
  const wasBlockedRef = useRef(sendBlocked);
  const rootRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const was = wasBlockedRef.current;
    wasBlockedRef.current = sendBlocked;
    if (!was || sendBlocked) return;
    const active = document.activeElement;
    if (
      active !== null &&
      active !== document.body &&
      !rootRef.current?.contains(active)
    ) {
      return; // 用户已把焦点放到本组件之外, 不抢
    }
    setFocusKey((k) => k + 1);
  }, [sendBlocked]);

  /**
   * 2026-10-13 18:40 小欧 - 文档[30] §2.5: 回车语义按「能否发送」分流。
   *   能发送 → preventDefault 并提交; 不能发送(执行中且未开插话) → 不拦截, 回车照常换行,
   *   否则用户打不了多行消息。
   *   刻意不用 useCallback: handleSendInternal 每次渲染重建, 收进依赖数组等于白包一层;
   *   InputCore 也未 memo, 包装无收益(以 lint 零告警的直线写法替代)。
   */
  const handlePressEnter = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.shiftKey || e.nativeEvent.isComposing) return;
    if (sendBlocked) return; // 放行 → textarea 默认行为即换行
    e.preventDefault();
    void handleSendInternal();
  };

  /** 退出历史翻动态(手动打字 / 面板选中 / 切会话 后都要复位, 否则 ↑↓ 基准错乱) */
  const exitHistory = useCallback(() => {
    setHistIdx(-1);
    setHistBackup(null);
  }, []);

  // 2026-10-13 14:35 小欧 - 切会话必须复位翻动游标。
  //   实测缺陷: A 会话里 ↑ 翻到 idx=2, 切到 B 会话后按一次 ↑ 给出 recents[3] 而非 recents[0]
  //   —— histIdx 是组件级 state, 不随会话走, 游标基准串到了别的会话。
  useEffect(() => {
    exitHistory();
  }, [sessionId, exitHistory]);

  // 2026-10-13 18:15 小欧 - 文档[30] §2.5: 提交门被拦时**不做静默**。
  //   注: 最初做成「弹 toast 提示」, 真浏览器实测发现副作用更大 —— 执行中按回车被 preventDefault
  //   拦住, 既不换行也不发送, 用户打不了多行消息(功能退化)。现改为**不可发送时回车照常换行**,
  //   「为什么不能发」由 B(按钮置灰+Tooltip) 与 C(常驻灰字) 表达, 无需回车再弹一次。
  //   发送按钮 disabled 时浏览器本就不派发 click, 故不存在「点了没反应」的死角。

  // 2026-09-03 小欧 修复: 乐观清空改可回补 — 备份draft, onSend失败时回填防输入永久丢失 - 小欧-2026-09-03
  // linked 不再复位(违背用户粘性意图), 开关真源在 useChatState.linkEnabled
  const handleSendInternal = async () => {
    const content = draft.trim();
    if (!content || sendBlocked) return;
    const backup = draft;
    exitHistory();
    setDraft('');
    // 2026-10-13 小欧: 标记提交中, 使 hook 能区分「建会话回填」与「用户真切会话」
    markSubmitted();
    try {
      await onSend(content, { linkEnabled, allowInterject }); // 对象参数, 见 3.5.4
      // 2026-10-13 13:45 小欧: **提交成功后**才记历史(onSend 抛错 = 提交失败, 不能记; 流式中途报错不 reject,
      //   故面板文案用「最近提交」而非「发送成功」)
      addRecentInput(content);
      setRecents(loadRecentInputs());
      setFocusKey((k) => k + 1); // 焦点还给输入框, 否则 ↑↓ 翻历史事件到不了 textarea
    } catch {
      setDraft(backup);
      cancelSubmitted();
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
      // 2026-10-13 14:35 小欧 - 收敛为"是否已在翻动"单一判据。
      //   旧写法在 ↑ 用 atFirstLine、在 ↓ 用 (atLastLine || histIdx>0), 两者自相矛盾:
      //   histIdx===0 认光标位置、histIdx>0 又无条件劫持; 且翻动后 caret 已由 rAF 置于末尾,
      //   atLastLine 恒为 true —— 整个表达式恒等于 histIdx>=0, 是纯死逻辑。
      //   归一后: 未翻动时严格要求首行行首才启动(保护多行光标编辑); 一旦进入翻动, ↑↓ 一律续翻。
      const browsing = histIdx >= 0;
      const atFirstLine = el.selectionStart === 0;

      // 2026-10-13 13:55 小欧 - 修正: 条件放宽为 histIdx>=0 || 光标在首行行首。
      //   原写法只看 atFirstLine, 但翻出一条后光标已被置于末尾, 第二次 ↑ 因 selectionStart!==0
      //   而不劫持 → 无法连续往更旧翻(与 bash 习惯不符)。已在翻动态时无条件续翻;
      //   未进入翻动态时仍严格要求首行行首, 绝不影响多行光标移动。
      if (
        e.key === 'ArrowUp' &&
        recents.length > 0 &&
        (browsing || atFirstLine)
      ) {
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

      if (e.key === 'ArrowDown' && browsing) {
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
    <div
      ref={rootRef}
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <InputCore
        value={draft}
        onChange={handleInputChange}
        onPressEnter={handlePressEnter}
        onKeyDown={handleInputKeyDown}
        focusKey={focusKey}
        /*
         * 2026-10-13 18:15 小欧 - 文档[30] §2.5: 不再 disabled。
         *   病根: 输入框曾与提交门共用 sendBlocked, 把「提交权限」误当「编辑权限」, 导致执行中
         *   连打字/翻历史/存草稿都做不到。执行中不可发是**提交**问题, 由发送按钮置灰(B)与
         *   常驻提示(C)表达, 不该由禁用来表达。
         */
        actions={
          // 2026-10-20 小欧 - 框内右下角动作按钮组: 两受阻判据均与提交门/提交处理同源, 见 SubmitActions 头注
          <SubmitActions
            loading={loading}
            isReceiving={isReceiving}
            isPaused={isPaused}
            sendBlocked={sendBlocked}
            emptyDraft={emptyDraft}
            onSend={handleSendInternal}
            onCancel={onCancel}
            onTogglePause={onTogglePause}
          />
        }
      />
      {/*
        2026-10-13 18:40 小欧 - 文档[30] §2.5 C: 「不可发送」的常驻说明。
          ⚠️ 显隐判据必须用 sendBlocked(与发送按钮置灰同源), 早前写成 `isReceiving && !allowInterject`
          导致 loading=true 而 isReceiving=false 的窗口里按钮灰着却无任何说明, 判据两套互相打架。
          文案按 isReceiving 区分「执行中」与「发送中」两种受阻原因。
      */}
      {sendBlocked && (
        <div
          data-testid="receiving-hint"
          style={{
            fontSize: FontSize.CAPTION,
            color: Colors.TEXT.SECONDARY,
            marginTop: -2,
          }}
        >
          {isReceiving
            ? '任务执行中，可开启「插话开关」后追加输入，或等待完成后发送'
            : '正在提交，请稍候'}
        </div>
      )}
      <SubmitBar
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
                setFocusKey((k) => k + 1); // 选完历史直接接着打字
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
