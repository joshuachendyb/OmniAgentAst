// 编辑历史: 2026-10-13 13:45 小欧 - 新建: 最近提交输入的本机历史(跨会话)
// 存储 localStorage 而非 sessionStorage: 后者按标签页隔离, 做不到"换会话也能翻历史"
//   ⚠️ 权宜方案: 后端 chat_user_message.content 已存全部用户提问(且 GET /sessions/{id}/user_messages 端点已存在),
//      本模块是影子副本, 存在"本机清了服务端还在"的漂移。二期应迁后端(需新增全局最近提问端点)。
//   2026-10-13 13:45 小欧 - 语义订正: 面板文案用「最近提交」而非「发送成功」—— onSend 是乐观提交,
//      await resolve 后流式中途报错不会 reject, 写进历史的可能实际失败, 不能承诺"成功"
export interface RecentInput {
  text: string;
  ts: number;
}

/** 上限 20 条(布局常量, 不用魔法数字) */
export const RECENT_INPUT_MAX = 20;

const KEY = 'omniagent_recent_inputs_v1';

/**
 * 快捷指令白名单(与 ShortcutPanel 硬编码的 4 条一致): 这些是控制指令不是提问, 不入历史。
 * 刻意不用"以 / 开头就排除" —— 用户可能真要发以 / 开头的路径。
 */
const COMMAND_LIKE = /^\/(clear|help|history|settings2)$/;

const isRecentInput = (v: unknown): v is RecentInput =>
  typeof v === 'object' &&
  v !== null &&
  typeof (v as RecentInput).text === 'string' &&
  (v as RecentInput).text.trim() !== '' &&
  typeof (v as RecentInput).ts === 'number';

/** 读历史(容错: 缺失/损坏/结构不符一律按无历史, 绝不抛异常阻断输入) */
export const loadRecentInputs = (): RecentInput[] => {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRecentInput).slice(0, RECENT_INPUT_MAX);
  } catch (e) {
    console.warn('[recentInputs] 读取失败, 按无历史处理:', e);
    return [];
  }
};

/**
 * 追加一条(在提交成功之后调用, 不能在点击发送时调用 —— 发送可能失败, 写早了会混进没发成功的输入)。
 * 去重: 与最新一条文本相同则只更新时间戳, 不新增条目(连发同一条命令是高频场景)。
 */
export const addRecentInput = (text: string): void => {
  const t = text.trim();
  if (!t || COMMAND_LIKE.test(t)) return;
  try {
    const list = loadRecentInputs();
    const rest = list[0]?.text === t ? list.slice(1) : list;
    const next: RecentInput[] = [{ text: t, ts: Date.now() }, ...rest].slice(
      0,
      RECENT_INPUT_MAX
    );
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch (e) {
    // 隐私模式 / 配额满: 静默降级, 绝不阻断输入
    console.warn('[recentInputs] 保存失败, 本次不记录:', e);
  }
};

/** 清空(面板「清空」入口必须有 —— 否则用户输入过 token 类内容后无法删除) */
export const clearRecentInputs = (): void => {
  try {
    window.localStorage.removeItem(KEY);
  } catch (e) {
    console.warn('[recentInputs] 清空失败:', e);
  }
};
