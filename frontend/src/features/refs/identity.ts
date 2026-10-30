// 编辑历史: 2026-10-30 小欧 - 新建：引用身份函数(自 store.ts 抽出, 供台账/chip/同 path 共用)
//   —— 只搬不改逻辑(复制实现 + 改导入路径), 避免二次改写引入行为差异 — 小欧-2026-10-30
// 编辑历史: 2026-10-30 小欧 批3: 增 labelOf(展示名, 兼容 `\`) 与 toWireRef(wire 投影, 自
//   chatStreamTransport 迁入, 纯投影不依赖 transport) — 小欧-2026-10-30
import type { ChatRefPayload } from '../../types/chat'; // wire 投影入参类型(与 store 同源)
/**
 * identity —— 引用身份归一(唯一实现)
 *
 * 为何独立(4.2.1)：refKeyOf 只服务入队去重(store.ts)，台账/chip/同 path 合并没有共用身份
 *   函数 → B1(同一文件整份+选区并存, token 翻倍)。抽到本模块后各处共用同一 identity。
 * 归一规则(4.5)：盘符统一小写 + 统一 `/`(Windows 大小写不敏感, 防 D:\a.md 与 d:\a.md
 *   同时两个 chip)。本文件不持状态、不发请求。
 */
export const normalizePath = (p: string): string =>
  p
    .replace(/\\/g, '/')
    .replace(/^([A-Za-z]):/, (_, d: string) => `${d.toLowerCase()}:`);

/** 引用展示名：路径末段（`/` 与 `\` 都认），空路径回退自身 — 唯一实现(2026-10-30 小欧)
 *
 * 为什么收口: 前端 4 处各自写 `path.split('/').pop() ?? path`，其中 2 处只认 `/`，
 *   Windows 反斜杠路径会整条当名字显示(实测足迹面板出现 `D:\a\b.md` 这种 chip 标题)。 */
export const labelOf = (path: string): string =>
  path.split(/[\\/]/).pop() || path;

/** wire 投影(F6): 契约字段白名单, 只留 kind/label/path/lineRange/size——
 *  content(正文由后端读, I1)、mtime(前端本地比对态, R2)、pending/invalid(内存态)均不进 wire。
 *  2026-10-30 小欧: 自 chatStreamTransport 迁入(纯投影函数, 归 refs 域), 入参/返回值同 wire 形态,
 *    transport 上行与 store 发送台账两处共用本实现。 */
export const toWireRef = (r: ChatRefPayload) => ({
  kind: r.kind,
  label: r.label,
  path: r.path,
  lineRange: r.lineRange ?? null,
  size: r.size,
});

interface RefIdentity {
  path?: string | null;
  lineRange?: { start: number; end: number } | null;
}

/** 同一文件 + 同一行区间视为同一引用(整文件 lineRange 为空)。 */
export const refKeyOf = (r: RefIdentity): string =>
  `${normalizePath(r.path ?? '')}|${
    r.lineRange ? `${r.lineRange.start}-${r.lineRange.end}` : ''
  }`;

/** 合并引用：同 key 原位替换(后一次内容覆盖前一次)，新 key 追加。 */
export const mergeRefs = <T extends RefIdentity>(
  prev: T[],
  incoming: T[]
): T[] => {
  const out = prev.slice();
  for (const ref of incoming) {
    const k = refKeyOf(ref);
    const i = out.findIndex((r) => refKeyOf(r) === k);
    if (i >= 0) out[i] = ref;
    else out.push(ref);
  }
  return out;
};
