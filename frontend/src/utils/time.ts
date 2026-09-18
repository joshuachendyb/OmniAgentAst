// 编辑历史: 2026-08-28 小欧 - 合并 timestamp/timeFormatters/formatSafeTimestamp+组件内formatTime为单一源
// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复toLocaleTimeString对象字面量多行→单行(行长度超80字符), 防止格式再次出错
// 编辑历史: 2026-09-18 小欧 - 北京老陈定案"formatTimeHMS/formatDurationHMS/formatDebugTime 各自重写 padStart 管道, 太奇怪":
//   抽模块私有 pad2 统一拼 HH:MM:SS, 三者共用, 语义各留各的不合并 — 小欧-2026-09-18
// 合并来源: timestamp.ts(80行) + timeFormatters.ts(43行) + formatSafeTimestamp.ts(10行) + TaskListPanel.tsx:30 + History/index.tsx:285

/** 两位补零辅助(模块私有, 避免三处重复 padStart 管道) — 小欧-2026-09-18 */
const pad2 = (n: number): string => String(n).padStart(2, '0');

export const parseTimeSafe = (input: Date | string | number): Date | null => {
  try {
    const d = input instanceof Date ? input : new Date(input);
    return isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
};

// 编辑历史: 2026-08-28 小欧 - 回退formatTimestamp契约: 非法日期返回''(权威契约见utils-pure-bugs B10), 与formatTime(返原串)刻意不同 - 小欧-2026-08-28
export const formatTimestamp = (ts: number | string | undefined): string => {
  if (ts === undefined || ts === null || ts === '') return '';
  const d = parseTimeSafe(ts as string | number | Date);
  if (!d) return '';
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}.${String(d.getMilliseconds()).padStart(3, '0')}`;
};

// 编辑历史: 2026-08-28 小欧 - 修复formatTime契约回归(合并timeUtils时行为漂移): 空值返回'-',非法串返回原串,有效串含月/日 时:分 - 小欧-2026-08-28
export const formatTime = (date: Date | string | number): string => {
  if (date === undefined || date === null || date === '') return '-';
  const d = parseTimeSafe(date);
  if (!d) return String(date);
  const md = `${d.getMonth() + 1}/${d.getDate()}`;
  const hm = d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
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

// 编辑历史: 2026-09-08 小欧 - 六章6.5(P2-13/3.6): 新增 formatTimeHMS(固定 HH:MM:SS, 时间轴左列用),
//   复用 parseTimeSafe, 不覆盖 formatTime(既有契约"月/日 时:分") — 小欧-2026-09-08
export const formatTimeHMS = (date: Date | string | number): string => {
  const d = parseTimeSafe(date);
  if (!d) return '-';
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
};

// 编辑历史: 2026-09-18 小欧 - 新增 formatDurationHMS(耗时秒 → 固定 HH:MM:SS, TaskInfoBar 耗时显示用,
//   北京老陈令"秒值改时分秒结构显示 00:04:32") — 小欧-2026-09-18
export const formatDurationHMS = (sec: number): string => {
  const total = Math.max(0, Math.floor(sec || 0));
  return `${pad2(Math.floor(total / 3600))}:${pad2(Math.floor((total % 3600) / 60))}:${pad2(total % 60)}`;
};

// 小欧 2026-09-14 DRY: console.log调试时间戳 [HH:MM:SS.mmm] — 小欧-2026-09-14
export const formatDebugTime = (): string => {
  const d = new Date();
  return `[${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}]`;
};
