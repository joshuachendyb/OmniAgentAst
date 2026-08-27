// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 新建安全时间戳格式化(复用优先)
// 2026-08-27 小欧 三堂会审: 容错解析任意输入, 非法值返回占位符, 杜绝new Date(非法串)抛错致组件崩溃
export function formatSafeTimestamp(s?: string | number | Date): string {
  try {
    const d = s == null ? new Date() : new Date(s);
    return isNaN(d.getTime()) ? '—' : d.toLocaleString('zh-CN');
  } catch {
    return '—';
  }
}
