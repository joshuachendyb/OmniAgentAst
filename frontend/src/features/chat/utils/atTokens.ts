// 编辑历史: 2026-10-21 小杨 - 文档[28]§9.7.4(O6) 新建：@token 扫描式剥离（覆盖 label 含 @） — 小杨-2026-10-21
/**
 * stripAtTokens —— 把正文里的 `@<引用label>` 精确剥掉（O6 最终版）
 *
 * 为什么不用 split/join（4.4.6 旧版）：
 * - 旧版对 label 含 `@` 的文件名（如 `a@b.md`）会半截误剥（`@a` 被吃掉，剩下 `b.md`）
 * - 旧版按 label 逐个 replace，长短顺序也可能吞掉前缀（`@a.md` 命中 `@a-depth.md` 的前缀）
 *
 * O6 做法：**扫描式** —— 从左到右扫正文，遇到 `@` 就尝试匹配候选 label，
 *   命中则整段跳过（不误伤），未命中则把 `@` 当普通字符继续。
 *   故 label 含 `@`、label 互为前缀都能正确处理。
 *
 * 语义约束：
 * - 无 refs 时调用方**不得调**（原样发送，M27：`@2024 年的计划` 不受影响）
 * - 只剥"完整匹配"的 token（label 边界须为非标签字符或文本边界）
 */
export const stripAtTokens = (text: string, labels: string[]): string => {
  if (!labels.length) return text;
  // 长 label 优先（`a-depth.md` 先于 `a.md`），避免短 label 先命中导致长 label 残留
  const ordered = [...labels]
    .filter((l) => !!l)
    .sort((a, b) => b.length - a.length);
  let out = '';
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (ch === '@') {
      const hit = ordered.find((l) => text.startsWith(l, i + 1));
      if (hit) {
        i += 1 + hit.length; // 整段跳过（不产出）
        continue;
      }
    }
    out += ch;
    i += 1;
  }
  return out.replace(/[ \t]{2,}/g, ' ').trim();
};
