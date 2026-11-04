// 编辑历史: 2026-10-21 小杨 - 新建：引用体量阈值与估算（纯告知不阻断） — 小杨-2026-10-21
/**
 * 引用体量提示
 *
 * 纯告知、**不阻断、不降级**（引用多少发多少）；只让用户在发送前知情。
 * 唯一真源：阈值与估算都在本文件。
 */

/** 粗估 token：中文语境 1 字符 ≈ 0.8~1.2 token，保守取 1.0；仅展示，不做阻断 */
export const estimateTokens = (chars: number): number =>
  Math.max(0, Math.ceil(chars));

/** 橙色警示阈值（≈2 万 token 级，超出系统提示基底两个数量级） */
export const REF_COST_WARN = 20_000;

/** 引导选区引用阈值 */
export const REF_COST_SUGGEST = 200_000;

export type RefCostLevel = 'ok' | 'warn' | 'suggest';

export interface RefCost {
  level: RefCostLevel;
  tokens: number;
  chars: number;
}

/** 体量分级：ok 常态 / warn 超 2 万（按钮转橙 + 警示） / suggest 超 20 万（引导只引行号） */
export const refCost = (chars: number): RefCost => {
  const tokens = estimateTokens(chars);
  return {
    level:
      tokens > REF_COST_SUGGEST
        ? 'suggest'
        : tokens > REF_COST_WARN
          ? 'warn'
          : 'ok',
    tokens,
    chars,
  };
};
