// 编辑历史: 2026-10-22 小欧 - 新建：引用入口唯一实现（读盘 + 组装 + 入队）— 小欧-2026-10-22

// 编辑历史: 2026-10-29 小欧 - 读取权收归后端: quoteFile/quoteSelection 改调 probeRef(轻量探
//   size/mtime, 不再读正文), 删 opts.content 参数与正文组装; 删 quotePack(无调用方死代码);
//   清未用 import — 小欧-2026-10-29

/**
 * quote —— 「把文件送进对话」的唯一入口
 *
 * 为什么收口（DRY）：重构前有 3 份近似实现（文件页 / 足迹面板 / 任务卡），
 *   各自读盘、各自组装 ref、各自提示错误 —— 加一个入口就多一份分叉。
 *   本文件是唯一实现，新增入口（产出物可点、上下文包）只调这里。
 *
 * 语义约定：
 * - 就地收集：只入队不导航（用户在文件页读/挑多个文件时不该被反复踢走）；
 *   需要跳回对话页时由调用方决定（文件页有「去对话」按钮）。
 * - 正文不在前端：只入队标识（路径 / 行区间 / 大小），正文由后端按标识读取，前端不留副本。
 * - 读失败不静默：只返回 reason，不弹提示——成功与失败文案都归调用方。
 *   2026-10-30 小欧 A12 更正: 原写"正文当轮即弃(content 只存在队列里)"——正文已不由前端读,
 *   队列里只有标识(路径/行区间/size/mtime), 不存在 content 副本。
 */
import { composerRefStore, newRefId } from './store';
import { probeRef } from './probe'; // 探测唯一入口(stat, 5.4.1)

export interface QuoteResult {
  ok: boolean;
  /** 失败原因（ok=false 时给出，供调用方分支选择提示文案） */
  reason?: string;
}

/** 引用整个文件（正文由后端读，前端只入队标识；probe 轻量探 size/mtime） */
export const quoteFile = async (
  path: string,
  opts?: { label?: string; size?: number }
): Promise<QuoteResult> => {
  const label = opts?.label ?? path.split('/').pop() ?? path;
  // 2026-10-30 小欧(D3): 删死 try/catch——probeRef 内部自捕错(失败返 {ok:false} 不 throw),
  //   push 返回布尔不 throw, 原 try/catch 是死分支(YAGNI, 设计 5.4.4 裁定)。
  //   2026-10-29 小欧: 入队只存标识, 不再读正文(正文由后端读, 读取权收归后端)。
  //   probe 轻量探(取 size/mtime), 失败仍允许入队(chip 标"未校验", 4.11)。
  const probe = await probeRef(path);
  return composerRefStore.push({
    id: newRefId(),
    kind: 'file',
    label,
    path,
    size: opts?.size ?? probe.size,
    mtime: probe.mtime,
    lineRange: null,
  })
    ? { ok: true }
    : { ok: false, reason: 'too_many' };
};

/** 引用一段行区间（选区引用）；正文由后端读，前端只入队标识 */
export const quoteSelection = async (
  path: string,
  range: { start: number; end: number },
  opts?: { label?: string; size?: number }
): Promise<QuoteResult> => {
  const label = opts?.label ?? path.split('/').pop() ?? path;
  // 2026-10-30 小欧(D3): 同 quoteFile——删死 try/catch(YAGNI)。
  const probe = await probeRef(path);
  return composerRefStore.push({
    id: newRefId(),
    kind: 'selection',
    label,
    path,
    size: opts?.size ?? probe.size,
    mtime: probe.mtime,
    lineRange: range,
  })
    ? { ok: true }
    : { ok: false, reason: 'too_many' };
};

// 2026-10-29 小欧: quotePack 整段删除(D6, YAGNI) — 全仓无调用方(grep 确认), 入队 path=''
//   造伪引用, refreshRefs 首行 `if (!r.path) return r` 永不重读、永不判失效(refresh.ts:33 已删)。
//   删除后不再造 path='' 条目(读取权收归后端, 正文不再由前端拼包)。
