// 编辑历史: 2026-10-30 小欧 - 新建：SSE refs_notice → chip 状态唯一映射 — 小欧-2026-10-30
// 编辑历史: 2026-10-30 小欧 批3: 增 chipToneOf(5 态→3 色系的唯一映射), 组件只查表不写嵌套三元 — 小欧-2026-10-30
// 编辑历史: 2026-10-30 小欧 R9: chipStateText 接收整条回执 —— degraded 拼 detail(省略行数/字符数),
//   dropped 拼中文 reason; 新增 noticeOf/noticeDetailText 供组件标题与文案共用 — 小欧-2026-10-30
/**
 * notice —— 引用回执 → chip 状态机(5 态)唯一映射
 *
 * 为何独立(4.2.1)：回执原先没有落点，chip 只能内联 pending/invalid 两态。
 *   本模块把内存态(pending/invalid)与回执态(notice)统一映射到 5 态。
 * 状态机(4.9)：
 *   idle      刚入队                常规 chip
 *   checking  发送前 probe 中       载入态(禁发)
 *   degraded  收到 info/warn 回执   黄标 + "已省略"
 *   dropped   收到 error 回执       红标 + "已丢弃"
 *   invalid   probe 失败           红标 + "已失效"
 *
 * 消费链(5.4.9 接线): SSE refs_notice → noticeMapByPath(items) → refNoticeStore(公域外部 store)
 *   → useComposerRefs 经 useSyncExternalStore 取 map → chipStateOf(r, notices)。
 *   按 path 键控而非 per-ref 字段: chips 列表归 useComposerRefs(ChatInput 本地态),
 *   store 直改 per-ref 字段够不到; map 归 refNoticeStore 公域。
 */
import type { ComposerRef } from './store';
import { normalizePath } from './identity';

export type ChipState =
  | 'idle'
  | 'checking'
  | 'degraded'
  | 'dropped'
  | 'invalid';

/** 回执条目(wire refs_notice.items 元素, level 已由后端 build_notice 补齐)。 */
export interface NoticeItem {
  level: string;
  reason: string;
  detail?: string;
  path?: string;
}

/** 归一 path → 回执条目(refNoticeStore 快照形状)。 */
export type NoticeMap = Map<string, NoticeItem>;

/** 回执态叠加规则: error→dropped, warn/info→degraded, 无有效级别→空。 */
export const noticeStateOf = (notice: {
  level: string;
}): 'dropped' | 'degraded' | null => {
  if (notice.level === 'error') return 'dropped';
  if (notice.level === 'warn' || notice.level === 'info') return 'degraded';
  return null;
};

/**
 * chip 状态唯一入口: invalid > 回执 dropped/degraded > checking > idle。
 * notices 传 refNoticeStore 快照; 不传只看内存态。
 */
export const chipStateOf = (r: ComposerRef, notices?: NoticeMap): ChipState => {
  if (r.invalid) return 'invalid';
  const hit = noticeOf(r, notices);
  if (hit) {
    const rc = noticeStateOf(hit);
    if (rc) return rc; // 回执态优先于 checking(回执是已定结论)
  }
  if (r.pending) return 'checking';
  return 'idle';
};

/** 取一条引用的回执(按归一 path) — 2026-10-30 小欧 R9: chip 文案/标题与状态判定共用同一查表 */
export const noticeOf = (
  r: ComposerRef,
  notices?: NoticeMap
): NoticeItem | undefined => notices?.get(normalizePath(r.path ?? ''));

/** 后端 dropped reason → 中文原因(4.9「红标 + 原因」的渲染落点) — 小欧-2026-10-30 */
const DROP_REASON_TEXT: Record<string, string> = {
  missing: '文件不存在',
  unsupported: '不支持的文件类型',
  out_of_root: '路径超出允许范围',
  range_out: '选区超出文件范围',
  timeout: '读取超时',
  no_path: '缺少文件路径',
  rejected: '整批被拒（超出预算）',
};

/**
 * 回执 → 人类可读结论(唯一实现) — 2026-10-30 小欧 R9
 *
 * 为何需要: 后端为每条回执算好了 detail("已省略 1234 行")与 reason(missing/range_out/
 *   rejected…), 原实现只按 5 态给固定四字文案, 这些信息全链无渲染落点 —— 用户分不清
 *   "文件不存在""选区越界"还是"整批被拒", 也不知道省略了多少。
 */
export const noticeDetailText = (notice?: NoticeItem): string => {
  if (!notice) return '';
  if (notice.reason === 'truncated') return notice.detail || '内容超长已省略';
  if (notice.reason === 'compressed') return notice.detail || '已压缩'; // detail="已省略 N 行"
  if (notice.reason === 'range_clipped') return '选区超出文件尾';
  const known = DROP_REASON_TEXT[notice.reason];
  if (known) return known;
  return notice.detail || notice.reason;
};

/**
 * chip 状态 → 文案(5 态, 4.9)。
 * 2026-10-30 小欧 R9: degraded 拼 detail(省略行数/字符数), dropped 拼中文原因;
 *   无回执信息时回退原固定文案(内存态 checking/invalid 不涉及回执)。
 */
export const chipStateText = (
  state: ChipState,
  notice?: NoticeItem
): string => {
  if (state === 'checking') return '（载入中…）';
  if (state === 'invalid') return '（已失效）';
  if (state === 'dropped') {
    const t = noticeDetailText(notice);
    return t ? `（已丢弃：${t}）` : '（已丢弃）';
  }
  if (state === 'degraded') {
    const t = noticeDetailText(notice);
    return t ? `（${t}）` : '（已省略）';
  }
  return '';
};

/** chip 色调(状态的视觉投影): 5 态 → 3 色系 — 2026-10-30 小欧
 *
 * 为何放这里: 状态判定归本模块; 配色若在组件里按 state 现算, 背景与边框就要各写一遍三层
 * 嵌套三元(实测 6 处分支), 改一档颜色要同时对两处。具体色值仍归组件(本模块不依赖主题 token)。 */
export type ChipTone = 'danger' | 'warn' | 'normal';

export const chipToneOf = (state: ChipState): ChipTone => {
  if (state === 'invalid' || state === 'dropped') return 'danger';
  if (state === 'degraded') return 'warn';
  return 'normal';
};

/** refs_notice items → 归一 path 键控的回执表(chatStreamStore/transport 写入 refNoticeStore)。 */
export const noticeMapByPath = (items: NoticeItem[]): NoticeMap => {
  const m: NoticeMap = new Map();
  for (const it of items) if (it.path) m.set(normalizePath(it.path), it);
  return m;
};
