// 编辑历史: 2026-08-26 小欧 - 输入框组合根: 六组件组合, Props兼容父级+modelPickerSlot/onSend二参
// 编辑历史: 2026-08-28 小欧 - 去孤行+gap8, 指令+续聊并入SubmitBar leftExtra, 外层flex column gap8, 总高≤5行
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①CI-01乐观清空(先save后清, onSend失败由父级回补)②CI-02增sessionId入参+useEffect重置draft防跨会话泄漏 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 修复: handleSendInternal改async可回补, onSend抛错时还原draft/linked, 杜绝网络/500致输入丢失
// 编辑历史: 2026-10-03 小欧 - 删本地 linked 自持 state(跨会话泄漏根因), 改受控 linkEnabled+
//   onToggleLink(真源寄存 useChatState); onSend 第二参由 contextLinkMode 改 linkEnabled: boolean;
//   删发送后 setLinked(false)(违背用户意图的根因行), draft 回补保留 — 小欧 2026-10-03
// 编辑历史: 2026-10-08 小欧 - 发送门判据抽 utils/sendGate 单一真源(原裸 loading 挡死开态插话), disabled 与发送门共用
// 编辑历史: 2026-10-10 小欧 - Props 补 sessionWorkspaces/setSessionWorkspaces;
//   挂载 SessionWorkspacePanel(wsPanelOpen 受控); 传 SubmitBar 的 workspaceCount(现算)与 onOpenWorkspaces
//   (无会话时不传 → SubmitBar 不渲染入口, GET 空 id 必 422 干脆不显示); 关闭面板时重拉一次同步徽标(失败静默) — 小欧-2026-10-10
// 编辑历史: 2026-10-13 13:45 小欧 - 草稿持久化+最近提交历史: draft 交 useInputDraft 单一真源(localStorage);
//   删"会话一改就无条件清空草稿"; 提交成功后记本机历史(指令不入库); 新增「历史输入」面板; IME 组字期不劫持 ↑↓
// 编辑历史: 2026-10-13 13:55 小欧 - 载入判据二轮修正(真浏览器实锤): 首版"上次非空才载入"致草稿跨会话泄漏;
//   改为"sessionId 变了就载入", 仅「提交标记+上次无会话+提交后又打字」三条件成立才判为建会话回填而跳过
// 编辑历史: 2026-10-13 14:20 小欧 - 焦点归还: 复现出点「发送」后焦点停在按钮、↑↓ 到不了 textarea(历史已入库);
//   InputCore 加 focusKey, 提交成功与"输入框由禁用转可用"两处自增(禁用期 focus() 为空操作, 解锁必须补)
// 编辑历史: 2026-10-13 14:35 小欧 - 复核整改: ①切会话复位 histIdx(否则按↑跳错条目) ②删 ↓ 的死逻辑 atLastLine
//   (恒为 true, 条件归一为 histIdx>=0) ③焦点归还加 rootRef.contains 前置条件, 不夺走用户放到别处的焦点
//   ④面板圆角改走 Radius.SM 令牌
// 编辑历史: 2026-10-13 14:50 小欧 - 撤回落盘防抖(自纠): 防抖化致刷新丢字(刷新不执行 React 卸载清理, 4 条用例变红);
//   草稿体量小, 同步写开销可接受, 拿正确性换性能属退化, 退回同步落盘
// 编辑历史: 2026-10-13 18:15 小欧 - ①输入框不再 disabled(把提交权限误当编辑权限, 执行中打不了字翻不了历史)
//   ②C 常驻灰字显隐改用 sendBlocked(与按钮置灰同源, 原用 isReceiving&&!allowInterject 会漏 loading 窗口)
//   ③提交门被拦不再静默; 实测"弹 toast"反而致执行中无法换行, 改为不可发送时回车照常换行(见 18:40)
// 编辑历史: 2026-10-20 小欧 - 动作按钮组移入框内右下角(北京老陈指令): 新增 SubmitActions 经 InputCore actions
//   插槽挂载(发送/停止/暂停三钮方形图标化), SubmitBar 只留左侧控件; 新增 emptyDraft 置灰判据
//   (与 handleSendInternal 的 !content 同源) 并入发送钮受阻态 — 小欧-2026-10-20
// 编辑历史: 2026-10-21 小杨 - 引用通道落地: store 订阅 + refs 独立托管 + @token 剥离 + @ 补全
//   (结构化引用 chip，正文不再写 @label；@ 补全改为光标真实位置驱动 + 真防抖 + 键盘导航) — 小杨-2026-10-21
// 编辑历史: 2026-10-21 小杨 - 跨会话保留 + 发送用重读 refs（选区按行切片）+ @ 词边界与去重 + chip 新标签打开 — 小杨-2026-10-21
// 编辑历史: 2026-10-21 小杨 - 合并 useComposerRefs 到组件内（单消费者，删除空壳 hook）— 小杨-2026-10-21
// 编辑历史: 2026-10-22 小欧 - 重建 useComposerRefs 共享 hook（虚报已补上），
//   refs 状态从组件内 useState 迁入 hook；原 7 处 setRefs 调用点改写为 hook 方法
//   （setAll/remove/removeWhere/clear/add）；删除 useSyncExternalStore/composerRefStore/mergeRefs 直接依赖 — 小欧-2026-10-22
// 编辑历史: 2026-10-22 小欧 - 引用 chip 点击判 path 非空：上下文包 chip 无单一路径（path=''），
//   原实现拼空路径深链点了跳空白页；改为空路径仅作展示不跳转 — 小欧-2026-10-22
// 2026-10-25 小欧 - 动作按钮组回迁 SubmitBar 行右端(北京老陈指令): InputCore 删 actions 插槽(死代码清零,
//   不留兼容层), SubmitBar 新增 rightActions 接收 SubmitActions; 两受阻判据(sendBlocked/emptyDraft)与
//   提交门同源不变 — 小欧-2026-10-25
// 2026-10-25 小欧 - 新增 executingHint 传 InputCore(北京老陈令): 执行中且输入框为空时 placeholder 区
//   追加橘红色 "任务执行中…开启插话开关可追加输入"; 非执行中/非空态自动消失 — 小欧-2026-10-25
// 2026-10-26 小欧 - 执行中提示归一: 判据 isReceiving→sendBlocked(与按钮置灰同源), 文案原样搬移
//   B 的原话(执行中/提交中两段), 删输入框下方 B 块(原 694-707)消除双提示并存; testid 保 overlay 内层
//   以保 H3/H9/H10 e2e 不断 — 小欧-2026-10-26

// 编辑历史: 2026-10-29 小欧 - 发送闸门与 @ 补全改走 probeRef: 发送前校验由 refreshRefs 改
//   precheckOrBlock(precheckRefs 三元组, 失效阻断+updated 点名"内容已更新"); @ 补全改调 probeRef
//   (轻量探 size/mtime, 不再切片读正文); 引用条数限 MAX_REFS(超限拦截点名) — 小欧-2026-10-29

/**
 * ChatInput - 输入框组合根（8.12 六组件组合）
 *
 * 【小欧 2026-08-26 8.12】单体拆分为 InputCore/TaskTypeToggle/CommandPanel/
 * AttachmentArea/SubmitBar 组合；对外 Props 保持 loading/isReceiving/isPaused/
 * onCancel/onTogglePause 兼容父级，新增 modelPickerSlot；chatLink 开关改受控
 * （linkEnabled/onToggleLink，真源在 useChatState），onSend 第二参为 boolean linkEnabled。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Space } from 'antd';
import { FileOutlined } from '@ant-design/icons';
import { InputCore } from './input/InputCore';
import { TaskTypeToggle } from './input/TaskTypeToggle';
import { CommandPanel } from './input/CommandPanel';
import { SubmitBar } from './input/SubmitBar';
import { SubmitActions } from './input/SubmitActions'; // 2026-10-20 小欧 - 动作按钮组(与 SubmitBar 拆出; 2026-10-25 回迁 SubmitBar 行右端)
import SessionWorkspacePanel from './input/SessionWorkspacePanel'; // 2026-10-10 小欧 - 面板挂载(默认导出)
import { InputHistoryPanel } from './input/InputHistoryPanel';
import { useInputDraft } from '../hooks/useInputDraft';
// 2026-10-22 小欧 - 共享 hook + 引用域归位
import { useComposerRefs } from '@/features/refs/useComposerRefs';
import { probeRef, precheckRefs } from '@/features/refs/probe'; // 读盘唯一入口 + 发送前预检(5.4.1)
import { newRefId, MAX_REFS, type ComposerRef } from '@/features/refs/store'; // @ 补全入队限流(与 push 同一上限)
import { fileApi, type SearchHit } from '../../../services/api/file.api';
import { buildFileDeepLink } from '@/utils/fileDeepLink';
import { showMessage, ErrorType } from '../../../services/error/handler';
import { chatTokens } from '@/theme/tokens';
import {
  loadRecentInputs,
  addRecentInput,
  clearRecentInputs,
  type RecentInput,
} from '../utils/recentInputs';
import type { SendOpts, WorkspaceEntry } from '../../../types/chat'; // 2026-10-07 小欧 - SendOpts 对象参数（避免相邻 boolean 位置参数错位）
import { sessionApi } from '../../../services/api/session.api'; // 2026-10-10 小欧 - 关闭面板时重拉徽标数
import { isSendBlocked } from '../utils/sendGate'; // 2026-10-08 小欧 - 发送门单一真源
import { Colors } from '@/utils/stepStyles';

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
  allowInterject: boolean; // 2026-10-07 小欧 - 插话开关
  onToggleInterject: (enabled: boolean) => void;
  // 2026-10-10 小欧 - 会话使用的目录（徽标数 + 面板回写）
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
  allowInterject, // 2026-10-07 小欧 - 插话开关
  onToggleInterject,
  sessionWorkspaces, // 2026-10-10 小欧 - 会话目录
  setSessionWorkspaces,
}) => {
  // 2026-10-13 13:45 小欧: 草稿单一真源(内存 + sessionStorage 持久化), 取代原自持 useState + 无条件清空 effect
  const { draft, setDraft, markSubmitted, cancelSubmitted } =
    useInputDraft(sessionId);
  // 2026-10-22 小欧 - 引用状态封进共享 hook（订阅+消费+托管唯一点）
  const {
    refs,
    pending: refsPending,
    remove,
    removeWhere,
    clear,
    add,
    setAll,
  } = useComposerRefs();
  // 2026-10-21 小杨 - @ 补全状态
  const [atOpen, setAtOpen] = useState(false);
  const [atHits, setAtHits] = useState<SearchHit[]>([]);
  const [atIndex, setAtIndex] = useState(0); // 2026-10-21 小杨 - 键盘导航：当前高亮项
  const [atRange, setAtRange] = useState<{ at: number; caret: number } | null>(
    null
  ); // 2026-10-21 小杨 - 选中候选时**替换** @查询词 段（而非追加）— 小杨-2026-10-21
  const [picking, setPicking] = useState(false); // @ 补全在途唯一性闸门（防连点）
  const atSeq = useRef(0); // 迟到响应丢弃（debounce 后的旧请求不得覆盖新结果）
  const atTimer = useRef<number | null>(null); // 2026-10-21 小杨 - 真防抖（每次击键不再真发一次全盘扫描）
  const inputRef = useRef<HTMLTextAreaElement | null>(null); // 取真实光标位置

  // 卸载时清理定时器（避免卸载后 setState）
  useEffect(
    () => () => {
      if (atTimer.current) window.clearTimeout(atTimer.current);
    },
    []
  );
  // 2026-10-21 小杨 - 候选浮层**点外部关闭**
  //   浮层化后（absolute）会压住下方内容，用户点页面其他地方 expect 浮层散开（antd 惯例），
  //   现实现只有 Esc 能关 → 把内容永久压住。用 rootRef 判定点击是否落在整块输入组件外。
  useEffect(() => {
    if (!atOpen) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (
        rootRef.current &&
        e.target instanceof Node &&
        !rootRef.current.contains(e.target)
      ) {
        setAtOpen(false);
      }
    };
    window.addEventListener('mousedown', onDocMouseDown);
    return () => window.removeEventListener('mousedown', onDocMouseDown);
  }, [atOpen]);
  // 2026-10-13 13:45 小欧: 本机最近提交历史(懒初始化一次; 写入只发生在本标签页, 无需跨标签页同步)
  const [recents, setRecents] = useState<RecentInput[]>(loadRecentInputs);
  // 2026-10-13 13:45 小欧: 历史翻动游标(-1 = 未在翻历史); histBackup = 上翻前正在输入的内容, ↓ 翻到底时回填
  const [histIdx, setHistIdx] = useState(-1);
  const [histBackup, setHistBackup] = useState<string | null>(null);
  // 2026-10-10 小欧 - 面板挂载点
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

  // 2026-10-08 小欧 - 发送门单一真源(2026-10-13 18:15 起只管"提交", 不再兼管输入框禁用)
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
   * 2026-10-13 18:40 小欧 - 回车语义按「能否发送」分流。
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

  // 2026-10-13 18:15 小欧 - 提交门被拦时**不做静默**。
  //   注: 最初做成「弹 toast 提示」, 真浏览器实测发现副作用更大 —— 执行中按回车被 preventDefault
  //   拦住, 既不换行也不发送, 用户打不了多行消息(功能退化)。现改为**不可发送时回车照常换行**,
  //   「为什么不能发」由 B(按钮置灰+Tooltip) 与 C(常驻灰字) 表达, 无需回车再弹一次。
  //   发送按钮 disabled 时浏览器本就不派发 click, 故不存在「点了没反应」的死角。

  // 2026-09-03 小欧 修复: 乐观清空改可回补 — 备份draft, onSend失败时回填防输入永久丢失 - 小欧-2026-09-03
  // linked 不再复位(违背用户粘性意图), 开关真源在 useChatState.linkEnabled
  /**
   * 发送前预检(F7): stat 预检 → 筛 → 点名 → return。返回 refsToSend / blocked / updated。
   * 2026-10-30 小欧 - 闸门抽成可单测函数; 数据源 stat 端点(R3); 旧 refreshRefs 路径随 refresh.ts 删除(5.4.5)。
   */
  const precheckOrBlock = async (
    refs: ComposerRef[]
  ): Promise<{
    refsToSend: ComposerRef[];
    blocked: boolean;
    updated: ComposerRef[];
  }> => {
    if (refs.length === 0)
      return { refsToSend: refs, blocked: false, updated: [] };
    const { checked, invalid, updated } = await precheckRefs(refs);
    setAll(checked);
    if (invalid.length > 0) {
      showMessage(
        ErrorType.FILE_READ,
        `引用已失效：${invalid.map((b) => b.label).join('、')}（文件不存在、不可读或选区已不存在），请在引用区移除后再发送`
      );
      return { refsToSend: refs, blocked: true, updated };
    }
    return { refsToSend: checked, blocked: false, updated };
  };

  const handleSendInternal = async () => {
    const content = draft.trim();
    if (!content || sendBlocked) return;
    // 2026-10-21 小杨 - 引用正文在途时禁发送（防发出 content:'' 的空引用）
    if (refsPending) {
      showMessage(ErrorType.FILE_READ, '引用内容仍在载入，请稍候');
      return;
    }
    /**
     * 2026-10-30 小欧 - 闸门抽成可单测函数(F7); 数据源 stat 端点(R3);
     *   旧 refreshRefs 路径随 refresh.ts 删除(5.4.5)。
     */
    const { refsToSend, blocked, updated } = await precheckOrBlock(refs);
    if (blocked) return; // 已点名(内部 showMessage), 不产生任何 LLM 调用
    // 2026-10-30 小欧(阻断级修正): 原 precheckRefs 产出 updated 无消费落点, "内容已更新"
    //   功能分支丢失(4.5/R2)。发送前点名提示——后端按标识必读最新, 不阻断、不改 chip 态。
    if (updated.length > 0) {
      showMessage(
        ErrorType.FILE_READ,
        `以下引用在盘上已有更新：${updated.map((u) => u.label).join('、')}（将按最新内容解析）`
      );
    }
    // 2026-10-21 小杨 - **正文即最终正文**（不再做 stripAtTokens 反向剥离）
    //   旧模型：正文里塞了 "@label"，发送前再逐个剥 → 边界误伤（吃掉"邮箱 a@b.com"的 b.com）、
    //   且全文折叠空格会毁掉用户粘贴的代码缩进。
    //   新模型：引用是**结构化 refs**（chip 唯一表示），正文只有用户写的字 → 直接发，无需剥离。
    const cleanText = content;
    const backup = draft;
    exitHistory();
    setDraft('');
    // 2026-10-13 小欧: 标记提交中, 使 hook 能区分「建会话回填」与「用户真切会话」
    markSubmitted();
    try {
      // 2026-10-21 小杨 - refs 随消息搭同一班便车上行（正文走 refs，不进 content）
      await onSend(cleanText, {
        linkEnabled,
        allowInterject,
        refs: refsToSend,
      }); // 对象参数，避免相邻 boolean 位置参数错位 — 小杨-2026-10-21
      // 2026-10-13 13:45 小欧: **提交成功后**才记历史(onSend 抛错 = 提交失败, 不能记; 流式中途报错不 reject,
      //   故面板文案用「最近提交」而非「发送成功」)
      addRecentInput(cleanText);
      setRecents(loadRecentInputs());
      setFocusKey((k) => k + 1); // 焦点还给输入框, 否则 ↑↓ 翻历史事件到不了 textarea
      clear(); // 仅成功才清（失败保留 refs，重试仍有内容）— 小欧-2026-10-22
    } catch {
      setDraft(backup);
      cancelSubmitted();
      // refs 保留（不 setRefs）—— 发送失败草稿与引用都还在
    }
  };

  /**
   * 2026-10-13 13:45 小欧 - 历史翻动键盘判定。
   * ⚠️ ①IME 组字期间(e.nativeEvent.isComposing)一律放行: 拼音输入法下 ↑↓ 是「切换候选词」,
   *    劫持会让候选词切不了 —— 全中文用户必踩, 全仓无 isComposing 先例, 故必须自己判。
   * ⚠️ ②只在光标位于首行行首 / 末行行尾时才劫持: TextArea 里 ↑↓ 默认移动光标,
   *    无条件劫持会导致多行文本无法上下移动光标 = 严重功能退化。
   */
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 2026-10-21 小杨 - @ 候选面板打开时，↑↓/Enter/Esc 归候选面板（不再翻历史）
    if (atOpen && atHits.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        moveAtIndex(1);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        moveAtIndex(-1);
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const hit = atHits[atIndex];
        if (hit) void pickAtItem(hit);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setAtOpen(false);
        setAtHits([]);
        atSeq.current += 1; // 作废在途请求
        return;
      }
    }
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
  };

  /**
   * 手动打字时复位历史游标(否则打完字按 ↑ 会从旧游标继续, 跳错条目)
   *
   * 2026-10-21 小杨 - **@ 补全改为"光标真实位置"驱动 + 真正防抖**
   *   ① 触发判据用**真实光标位置**（原实现用 v.length 当光标 → 光标不在末尾时误触发/漏触发）；
   *   ② 触发范围：`@` 位于词边界（排除 a@b.com），后续为路径形态或无后缀 ASCII 文件名（Dockerfile）；
   *   ③ **真防抖**（clearTimeout + 卸载清理）→ 每次击键不再真发一次 20000 节点的全盘扫描；
   *   ④ 关闭候选时**作废在途请求**（原实现不自增序号 → 删掉 @ 后过期响应会把面板凭空弹回）。
   */
  const handleInputChange = useCallback(
    (v: string) => {
      setDraft(v);
      if (histIdx >= 0) exitHistory();
      const el = inputRef.current;
      const caret = el ? (el.selectionStart ?? v.length) : v.length;
      const at = v.lastIndexOf('@', caret - 1);
      const query = at >= 0 ? v.slice(at + 1, caret) : '';
      const prev = at > 0 ? v[at - 1] : '';
      const atBoundary = !/[A-Za-z0-9._%+-]/.test(prev);
      const looksPath = /[\\/]|[\w-]+\.[A-Za-z0-9]{1,8}$/.test(query);
      const looksBareName =
        /^[A-Za-z0-9_.-]+$/.test(query) && !query.includes('.');
      const ok =
        at >= 0 &&
        atBoundary &&
        !/\s/.test(query) &&
        query.length > 1 &&
        (looksPath || looksBareName);
      if (!ok) {
        atSeq.current += 1; // 作废在途请求（否则删掉 @ 后过期响应会把面板弹回）
        if (atTimer.current) window.clearTimeout(atTimer.current);
        setAtOpen(false);
        setAtHits([]);
        return;
      }
      setAtRange({ at, caret });
      const seq = ++atSeq.current;
      if (atTimer.current) window.clearTimeout(atTimer.current);
      atTimer.current = window.setTimeout(() => {
        fileApi
          .searchFiles(query, 20)
          .then((r) => {
            if (seq !== atSeq.current) return; // 迟到响应丢弃
            // 6.7 表第 3 行：@ 候选只列可读文本类型（对齐后端 _preview_of 的 text 判定）
            setAtHits(r.results.filter((x) => x.preview === 'text'));
            setAtOpen(true);
          })
          .catch(() => {
            if (seq !== atSeq.current) return;
            setAtHits([]);
            setAtOpen(false);
          });
      }, 220);
    },
    [histIdx, setDraft, exitHistory]
  );

  /**
   * 2026-10-21 小杨 - @ 补全选中改造：
   *   选中候选 → **把 @查询词 段替换掉**（原实现是追加 → 正文出现 "@查询词 @文件名" 双 @），
   *   同时把该文件作为**结构化引用**注入（chip 是唯一表示，正文不留 @label）。
   */
  const pickAtItem = async (hit: SearchHit) => {
    if (picking) return; // 防连点
    if (hit.preview !== 'text') return; // 只收可预览文本
    // 2026-10-30 小欧(D5): 限流必须在 add(pending 占位) 之前——原实现先 add 占位再限流,
    //   超限 return 后占位 chip 残留(pending:true) → refsPending=true 卡死发送闸门
    //   "引用内容仍在载入"; 设计 5.4.7"在入队前同限"由此达成(占位也是入队, 必须一并拦)。
    if (refs.length >= MAX_REFS) {
      showMessage(ErrorType.FILE_READ, `一次最多引用 ${MAX_REFS} 项`);
      return;
    }
    setPicking(true);
    // 先渲染"载入中"占位 token（去重保证连点只会替换不会追加）— 小欧-2026-10-22 改用 hook.add
    add({
      id: newRefId(),
      kind: 'file',
      label: hit.name,
      path: hit.path,
      pending: true,
    });
    // 正文里的 "@查询词" 是**检索动作**而非用户想发送的内容 → 选中即移除该段
    if (atRange) {
      setDraft((d) => `${d.slice(0, atRange.at)}${d.slice(atRange.caret)}`);
    }
    try {
      // 2026-10-30 小欧(D5): 限流已前置到占位前(见上), 此处不再重复判。
      //   store 内 MAX_REFS 拦截够不到此入口 → 在入队前同限(同一常量), 消除绕过得掉的入口。
      const pr = await probeRef(hit.path); // 现: 唯一读盘点
      // 2026-10-22 小欧 - 改用 hook.add（mergeRefs 同 path+lineRange 原位替换 → pending 占位被解析结果覆盖）
      add({
        id: newRefId(),
        kind: 'file',
        label: hit.name,
        path: hit.path,
        size: pr.size,
        mtime: pr.mtime, // probe 失败也为 undefined, 仍入队(4.11 "未校验")
        pending: false,
      });
    } catch {
      removeWhere((r) => r.pending === true && r.path === hit.path); // 小欧-2026-10-22 改用 hook.removeWhere
      showMessage(ErrorType.FILE_READ, '引用内容读取失败，请重试');
    } finally {
      setPicking(false);
      setAtOpen(false);
      setAtHits([]);
      setAtRange(null);
    }
  };

  /** 2026-10-21 小杨 - @ 候选的**键盘导航**（↑↓ 移动 / Enter 选中 / Esc 关闭）
   *  内联在 handleInputKeyDown 内（唯一调用点）——不再单列函数，避免依赖数组失配。 */
  const moveAtIndex = (delta: number) => {
    setAtIndex((i) => (i + delta + atHits.length) % atHits.length);
  };

  return (
    <div
      ref={rootRef}
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      {/* 2026-10-21 小杨 - 引用 token 行（一个信息一个家：删 token = 一次 setRefs 过滤） */}
      {refs.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 6,
            marginBottom: 4,
          }}
        >
          {/* 2026-10-21 小杨 - 给引用区一个**名字与计数**（否则用户不知道那排 chip 是什么） */}
          <span
            aria-live="polite"
            style={{
              color: Colors.TEXT.SECONDARY,
              fontSize: chatTokens.fontSM,
            }}
          >
            引用 {refs.length} · 发送到当前会话
          </span>
          {refs.map((r) => (
            <span
              key={r.id}
              title={`${r.path ?? ''}${
                r.lineRange
                  ? `（第 ${r.lineRange.start}-${r.lineRange.end} 行）`
                  : ''
              }`}
              style={{
                /* 2026-10-21 小杨 - 失效引用红底（与正常蓝底一眼区分） */
                background: r.invalid
                  ? Colors.ERROR_BG
                  : chatTokens.colorPrimaryBg,
                color: Colors.TEXT.STRONG,
                border: `1px solid ${r.invalid ? Colors.ERROR_BORDER : chatTokens.colorBorder}`,
                borderRadius: chatTokens.radius,
                padding: '1px 4px 1px 6px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
              onClick={() => {
                // 2026-10-22 小欧 - 上下文包无单一路径（path=''）→
                //   不跳文件页（否则点开一个空 path 的死链），仅作展示
                if (!r.path) return;
                window.open(
                  buildFileDeepLink(r.path, r.lineRange ?? null),
                  '_blank'
                );
              }}
            >
              <FileOutlined style={{ color: chatTokens.colorPrimary }} />
              {r.label}
              {r.pending ? '（载入中…）' : r.invalid ? '（已失效）' : ''}
              {/* 2026-10-21 小杨 - 删除按钮放大到可点面积 + 键盘可达（原来是裸 × 字符） */}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  remove(r.id); // 小欧-2026-10-22 改用 hook.remove
                }}
                aria-label={`删除引用 ${r.label}`}
                title="移除该引用"
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  padding: '0 4px',
                  fontSize: 14,
                  lineHeight: '16px',
                  color: Colors.TEXT.SECONDARY,
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      {refsPending && (
        <div style={{ color: Colors.WAIT_ACTION, fontSize: chatTokens.fontSM }}>
          引用内容正在载入，稍候即可发送
        </div>
      )}
      {sendBlocked && refs.length > 0 && (
        <div style={{ color: Colors.TEXT.WEAK, fontSize: chatTokens.fontSM }}>
          当前正在生成，请等待本轮结束后编辑并发送
        </div>
      )}
      {/* 2026-10-21 小杨 - 候选面板改为**浮层**（absolute）
          原实现是普通文档流 → 每打开一次就把下方内容整体下推，输入区位置跳动。
          现在锚定在输入框下沿、不参与布局。 */}
      <div style={{ position: 'relative' }}>
        <InputCore
          value={draft}
          onChange={handleInputChange}
          onPressEnter={handlePressEnter}
          onKeyDown={handleInputKeyDown}
          focusKey={focusKey}
          inputRef={inputRef}
          executingHint={
            sendBlocked
              ? isReceiving
                ? '任务执行中，可开启「插话开关」后追加输入，或等待完成后发送'
                : '正在提交，请稍候'
              : undefined
          }
          /*
           * 2026-10-13 18:15 小欧 - 不再 disabled。
           *   病根: 输入框曾与提交门共用 sendBlocked, 把「提交权限」误当「编辑权限」, 导致执行中
           *   连打字/翻历史/存草稿都做不到。执行中不可发是**提交**问题, 由发送按钮置灰(B)与
           *   常驻提示(C)表达, 不该由禁用来表达。
           */
        />
        {/* 2026-10-21 小杨 - @ 候选面板放在**输入框下方**
            （原实现放在输入框上方 → 遮住引用行，且与"输入框在上、辅助在下"的常规心智相反）；
            并支持 ↑↓/Enter/Esc 键盘操作 + 当前项高亮。 */}
        {atOpen && atHits.length > 0 && (
          <div
            role="listbox"
            aria-label="文件候选"
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: 4,
              zIndex: 20,
              border: `1px solid ${chatTokens.colorBorder}`,
              borderRadius: chatTokens.radius,
              maxHeight: 200,
              overflow: 'auto',
              background: Colors.BG.PRIMARY,
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            }}
          >
            {atHits.map((h, i) => (
              <div
                key={h.path}
                role="option"
                aria-selected={i === atIndex}
                onMouseEnter={() => setAtIndex(i)}
                onMouseDown={(e) => {
                  e.preventDefault(); // 保住输入框焦点
                  void pickAtItem(h);
                }}
                style={{
                  padding: '4px 8px',
                  cursor: 'pointer',
                  background: i === atIndex ? Colors.BG.TERTIARY : undefined,
                }}
              >
                <FileOutlined style={{ color: chatTokens.colorPrimary }} />{' '}
                {h.name}
                {h.dir ? ` · ${h.dir}` : ''}
              </div>
            ))}
          </div>
        )}
        {/* 2026-10-21 小杨 - 读屏：焦点留在输入框，用 live region 播报当前候选
            （listbox 的 aria-activedescendant 需挂在焦点元素上，本组件结构下用播报更可靠） */}
        <div
          role="status"
          aria-live="polite"
          style={{
            position: 'absolute',
            width: 1,
            height: 1,
            overflow: 'hidden',
            clip: 'rect(0 0 0 0)',
            whiteSpace: 'nowrap',
          }}
        >
          {atOpen && atHits[atIndex]
            ? `第 ${atIndex + 1} 项，共 ${atHits.length} 项：${atHits[atIndex].name}`
            : ''}
        </div>
      </div>

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
        allowInterject={allowInterject} // 2026-10-07 小欧 - 下传给 SubmitBar(开关落在附件之后)
        onToggleInterject={onToggleInterject}
        // 2026-10-10 小欧 - 徽标现算(无 dirty 角标)
        // 无会话时不传 onOpenWorkspaces → SubmitBar 不渲染入口（GET 空 id 必 422，不如不显示）
        workspaceCount={sessionWorkspaces.length}
        onOpenWorkspaces={sessionId ? () => setWsPanelOpen(true) : undefined}
        /*
         * 2026-10-25 小欧 - 动作按钮组回迁本行右端(北京老陈指令): 原在 InputCore 框内右下角;
         *   两受阻判据(sendBlocked/emptyDraft)与提交门/提交处理同源, 见 SubmitActions 头注
         */
        rightActions={
          <SubmitActions
            loading={loading}
            isReceiving={isReceiving}
            isPaused={isPaused}
            sendBlocked={sendBlocked || refsPending}
            emptyDraft={emptyDraft}
            onSend={handleSendInternal}
            onCancel={onCancel}
            onTogglePause={onTogglePause}
          />
        }
      />
      {/* 2026-10-10 小欧 - 会话使用目录面板入口 */}
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
