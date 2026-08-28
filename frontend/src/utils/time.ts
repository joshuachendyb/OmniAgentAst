// 编辑历史: 2026-08-28 小欧 - 合并 timestamp/timeFormatters/formatSafeTimestamp+组件内formatTime为单一源
// 合并来源: timestamp.ts(80行) + timeFormatters.ts(43行) + formatSafeTimestamp.ts(10行) + TaskListPanel.tsx:30 + History/index.tsx:285

export const parseTimeSafe = (input: Date | string | number): Date | null => {
  try {
    const d = input instanceof Date ? input : new Date(input);
    return isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
};

// 编辑历史: 2026-08-28 小欧 - 修复formatTimestamp契约回归: 非法日期返回原串(与formatTime一致), 空值返回'' - 小欧-2026-08-28
export const formatTimestamp = (ts: number | string | undefined): string => {
  if (ts === undefined || ts === null || ts === '') return '';
  const d = parseTimeSafe(ts as string | number | Date);
  if (!d) return typeof ts === 'string' ? ts : '';
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}.${String(d.getMilliseconds()).padStart(3, '0')}`;
};

// 编辑历史: 2026-08-28 小欧 - 修复formatTime契约回归(合并timeUtils时行为漂移): 空值返回'-',非法串返回原串,有效串含月/日 时:分 - 小欧-2026-08-28
export const formatTime = (date: Date | string | number): string => {
  if (date === undefined || date === null || date === '') return '-';
  const d = parseTimeSafe(date);
  if (!d) return String(date);
  const md = `${d.getMonth() + 1}/${d.getDate()}`;
  const hm = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  return `${md} ${hm}`;
};

export const formatRelativeTime = (date: Date | string | number): string => {
  const d = parseTimeSafe(date);
  if (!d) return '';
  const diff = Date.now() - d.getTime();
  if (diff < 0) return d.toLocaleDateString('zh-CN');
  const m = Math.floor(diff / 60000);
  if (m < 1) return '刚刚';
  if (m < 60) return `${m}分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}小时前`;
  return d.toLocaleDateString('zh-CN');
};

export const formatSafeTimestamp = (s?: string | number | Date): string => {
  if (s == null) return '';
  const d = parseTimeSafe(s as string | number | Date);
  return d ? d.toLocaleString('zh-CN') : '';
};

export const formatDate = (s?: string | number | Date): string => {
  const d = s == null ? null : parseTimeSafe(s as string | number | Date);
  return d
    ? `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    : '-';
};
