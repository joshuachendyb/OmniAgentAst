// 编辑历史: 2026-09-21 小强 - 新建：剪贴板工具（复制成功才返回 ok，失败可感知——供只读复制按钮用，防"未写出即弹成功"）
// 编辑历史: 2026-11-20 小欧 - 加 execCommand 降级: 嵌入式浏览器/权限被拒/文档未聚焦时 clipboard API 抛 NotAllowedError,
//   原样失败会让所有复制按钮报"复制失败"; 降级用隐藏 textarea + execCommand('copy'), 两法都失败才返回 ok:false — 小欧-2026-11-20
/**
 * 复制文本到剪贴板。
 *
 * 主路径用 Clipboard API；被拒（权限/非安全上下文/文档未聚焦）时降级 execCommand。
 * 返回 { ok: true } 或 { ok: false }，调用方据结果提示（两法都失败才不假成功）。
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
    // Clipboard API 不可用/被拒时降级: 隐藏 textarea + execCommand（旧浏览器/嵌入 webview 仍可用）
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.style.top = '0';
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, ta.value.length);
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok ? { ok: true } : { ok: false };
    } catch {
      return { ok: false };
    }
  }
}
