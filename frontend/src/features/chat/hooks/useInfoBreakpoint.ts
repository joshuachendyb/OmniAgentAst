// 编辑历史: 2026-09-09 小欧 - [16]3.9 断点矩阵基础设施(见设计文档 3.9 响应式缩略与浮层矩阵):
//   精确三档 1280/960/768 (antd Grid.useBreakpoint 无 mid=960 档, 文档所需尺寸精确对应;
//   复用优先: 全前端仅此一处需要三档, 无需建通用组件额外抽象)—— 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 三堂会审#2: resolve 修为 — matchMedia 全不命中(真实<768)原误回 wide,
//   断点矩阵完全失效; 改 innerWidth 兜底(jsdom 默认 1024→mid, 真实窄屏归 xsmall), 仅 SSR 回 wide — 小欧-2026-09-09
/**
 * TaskInfoBar 断点 hook（对应设计文档[16] 3.9 G1~G8 断点行为矩阵）
 *
 * 档位：wide(≥1280) / mid(1280~960) / narrow(960~768) / xsmall(<768)
 *
 * 判定：主判 window.matchMedia(min-width) 逐档命中，取最宽命中档；
 * 三档全不命中 → 以 window.innerWidth 兜底校准（真实窄屏 <768 归 xsmall，勿误回 wide）；
 * matchMedia 与 innerWidth 均不可得（SSR）→ 回 wide 完整展示（断点只负责"收窄"，
 * 宽度未知时信息带恒为最完整形态。信息安全，非功能回退）。
 *
 * @author 小欧
 * @date 2026-09-09
 */
import { useEffect, useState } from 'react';

export type InfoBreakpoint = 'wide' | 'mid' | 'narrow' | 'xsmall';

const BP_QUERIES: Array<{ bp: InfoBreakpoint; query: string }> = [
  { bp: 'wide', query: '(min-width: 1280px)' },
  { bp: 'mid', query: '(min-width: 960px)' },
  { bp: 'narrow', query: '(min-width: 768px)' },
];

// 三档全不命中 = 真实窄屏(<768) → xsmall；jsdom/setup mock 恒 false 时以 innerWidth 校准
const resolveXSmall = (): InfoBreakpoint => {
  if (typeof window === 'undefined') return 'wide';
  const w = window.innerWidth;
  if (typeof w !== 'number' || Number.isNaN(w)) return 'xsmall';
  if (w >= 1280) return 'wide';
  if (w >= 960) return 'mid';
  if (w >= 768) return 'narrow';
  return 'xsmall';
};

const resolve = (): InfoBreakpoint => {
  if (
    typeof window === 'undefined' ||
    typeof window.matchMedia !== 'function'
  ) {
    return 'wide'; // SSR 无宽度信号 → 完整展示
  }
  for (const { bp, query } of BP_QUERIES) {
    if (window.matchMedia(query).matches) return bp;
  }
  return resolveXSmall();
};

export const useInfoBreakpoint = (): InfoBreakpoint => {
  const [bp, setBp] = useState<InfoBreakpoint>(resolve);
  useEffect(() => {
    if (
      typeof window === 'undefined' ||
      typeof window.matchMedia !== 'function'
    ) {
      return;
    }
    const update = () => setBp(resolve());
    const mqls = BP_QUERIES.map(({ query }) => window.matchMedia(query));
    mqls.forEach((m) => m.addEventListener('change', update));
    return () => mqls.forEach((m) => m.removeEventListener('change', update));
  }, []);
  return bp;
};
