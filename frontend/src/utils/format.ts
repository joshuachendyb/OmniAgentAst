// 前端通用格式化函数(公用函数库)
// 编辑历史: 2026-10-14 小欧 - 新建（北京老陈裁定：结果视图的 formatBytes 提为公用函数）。
//   本仓前端此前**没有通用工具文件** —— src/utils/ 下 14 个文件全按领域划分,
//   src/lib/ 仅 antd/bridge.ts, 故在此开此文件。
//   收录标准: 纯函数 + 零依赖 + 跨领域复用; 单领域专用的仍留各自领域文件。

/**
 * 人类可读体积(B/KB/MB/GB/TB)。
 *
 * 2026-10-14 小欧 - 北京老陈裁定提为公用函数。原先有两份私有实现:
 *   ① `features/settings2/components/AboutFiles.tsx` 的 `formatSize` —— 只到 MB;
 *   ② `features/chat/components/pipeline/ResultSpecialViews.tsx` 的 `formatBytes` —— 支持 GB/TB
 *      (起因: 工具 `tree` 的 `statistics.total_size` 实测最大 **6.6 GB**,
 *       用只到 MB 的版本会显示成 `6617050546.0 MB` 这种没法读的数字)。
 * 现统一到本文件, 两处调用方共用。
 *
 * 精度约定: `< 10` 时保留 1 位小数, `>= 10` 时取整(避免 `1234.5 MB` 这类冗余小数)。
 * 非法值(非 number / NaN / Infinity)统一返回 `—`, 避免输出 `NaN B`。
 */
export const formatBytes = (bytes: unknown): string => {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes)) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
};
