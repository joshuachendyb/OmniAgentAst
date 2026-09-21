// 编辑历史: 2026-09-21 小强 - 新建：剪贴板工具（复制成功才返回 ok，失败可感知——供只读复制按钮用，防"未写出即弹成功"）
/**
 * 复制文本到剪贴板
 *
 * 返回 { ok: true } 或 { ok: false }，调用方据结果提示（剪贴板权限被拒/非 HTTPS 环境时不再假成功）。
 *
 * @param text - 要复制的文本
 * @returns Promise<{ ok: true } | { ok: false }>
 */
export async function copyTextToClipboard(
  text: string
): Promise<{ ok: true } | { ok: false }> {
  try {
    await navigator.clipboard.writeText(text);
    return { ok: true };
  } catch {
    return { ok: false };
  }
}
