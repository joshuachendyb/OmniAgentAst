// 2026-11-02 小欧 - 流状态浮层数据行唯一实现: 顶栏流状态灯与服务胶囊共用, 免两处各写一套口径 — 小欧-2026-11-02
import type { StreamPulseView } from '../../features/chat/hooks/useStreamPulse';
import type { PillTipRow } from './PillTip';

export const ageText = (sec: number | null): string =>
  sec === null ? '未收到' : `${sec} 秒前`;

/** 业务帧/心跳/最后字节三行: 判据各自独立, 颜色只标异常项 — 2026-11-02 小欧 */
export const streamDataRows = (
  view: StreamPulseView,
  group?: string
): PillTipRow[] => [
  {
    label: '业务帧',
    value: ageText(view.bizAgeSec),
    tone: view.bizStale ? 'warn' : undefined,
    ...(group ? { group } : {}),
  },
  { label: '心跳', value: ageText(view.heartbeatAgeSec) },
  {
    label: '最后字节',
    value: ageText(view.dataAgeSec),
    // dataStale 即"流静默"档的判据, 行色对齐该档橘红, 与迟滞的黄区分 —— 2026-11-02 小欧
    tone: view.dataStale ? 'alert' : undefined,
  },
];
