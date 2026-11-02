// 2026-11-02 小欧 - 顶栏胶囊语义色单一来源: 严重度 ok(绿)→warn(黄)→alert(橘红)→error(红), neutral=无状态灰 — 小欧-2026-11-02
import { Colors } from './stepStyles';

export type Tone = 'ok' | 'warn' | 'alert' | 'error' | 'neutral';

export const TONE_COLOR: Record<Tone, string> = {
  ok: Colors.SUCCESS,
  warn: Colors.WARNING,
  alert: Colors.ORANGE_RED,
  error: Colors.ERROR,
  neutral: Colors.TEXT.SECONDARY,
};
