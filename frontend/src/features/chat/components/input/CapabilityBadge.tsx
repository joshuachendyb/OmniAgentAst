// 编辑历史: 2026-11-11 小欧 新建: 附件/引用能力状态徽标(纯展示, 零状态判定) — 小欧-2026-11-11
// 编辑历史: 2026-11-12 小欧 动作词单源收口: 徽标文案由三态评价词改六动作名(全文注入/原生直传/
//   抽取注入/媒体元数据注入/文件元数据注入/链接地址注入), 动作名=纯展示词汇, 档位仍唯一状态真源;
//   tooltip 全量覆盖(按 content_kind×档位给出动作名+白话解释, 缺键兜底); 增档位图标双重编码
//   (色盲友好); 导出 ACTION/STATE_META 供矩阵图例复用(同一映射, 不另建副本) — 小欧-2026-11-12

// 编辑历史: 2026-11-12 小欧 三堂会审整改: 补 text:opaque/unknown:opaque 两键(路由
//   native_modality=None+link, 实为链接地址注入, 原兜底错显元信息注入); degraded 档位名
//   「转化注入」改「降级注入」(以偏概全, 与指标条降级占比口径一致; 档下已按内容形态
//   自然细分动作词, 不再细分档位) — 小欧-2026-11-12
import { Tag, Tooltip } from 'antd';

/** 状态徽标: 纯展示组件 —— state 必填由调用方给出, 组件不查表、不推导、不发请求。
 *  附件/文件 chip 取 modelEntry.ref_capability_map[source][content];
 *  URL chip 取 [23] preflight items[].state; 两者计算函数同源 state_of(C9)。 */
export type CapabilityState = 'native' | 'degraded' | 'opaque' | 'unknown';

/** 档位元数据: 颜色/图标/档位名, 动作词与白话解释的唯一展示真源(矩阵图例复用) */
export const STATE_META: Record<CapabilityState, { color: string; icon: string; label: string }> = {
  native: { color: 'green', icon: '✓', label: '原生理解' },
  degraded: { color: 'blue', icon: '≈', label: '降级注入' },
  opaque: { color: 'default', icon: '—', label: '元信息注入' },
  unknown: { color: 'default', icon: '?', label: '未知' },      // 缺键兜底, 不崩(守门测试断言)
};

/** 动作词: (content_kind, 档位) → 实际处理动作名; 纯展示映射, 不含状态判定(矩阵图例复用) */
export const ACTION: Record<string, string> = {
  'text:native': '原始文本注入',
  'image:native': '原图直接注入', 'video:native': '视频直接注入',
  'audio:native': '音频直接注入', 'richdoc:native': '文档直接注入',
  'richdoc:degraded': '文档抽取信息注入',
  'video:degraded': '媒体元数据注入', 'audio:degraded': '媒体元数据注入',
  'image:degraded': '降级转化注入',                                    // base64 转化注入(本系统原生走 image part, 兜底)
  'image:opaque': '文件元数据注入', 'binary:opaque': '文件元数据注入',
  'url:opaque': '链接地址注入',
  'text:opaque': '链接地址注入', 'unknown:opaque': '链接地址注入',   // text/unknown 路由 native_modality=None+link → 链接地址注入
};

/** tooltip 白话解释: (content_kind, 档位) → 文案; 全量覆盖 + 缺键兜底 */
const TIP: Record<string, string> = {
  'text:native': '原文完整塞进请求体，无损失',
  'image:native': '图片按原生形态直接给模型',
  'video:native': '视频按原生形态直接给模型',
  'audio:native': '音频按原生形态直接给模型',
  'richdoc:native': '文档按原生形态直接给模型',
  'image:degraded': '图片被转化后注入，形态已转',
  'video:degraded': '只能读到时长/编码等元数据，看不到画面',
  'audio:degraded': '只能读到时长/编码等元数据，听不到声音',
  'richdoc:degraded': '将收到抽取后的文本，丢失版式/图表',
  'image:opaque': '当前模型只能看到文件名/大小，看不到图片内容',
  'binary:opaque': '当前模型只能看到文件名/大小，看不到文件内容',
  'url:opaque': '只收到链接字符串，未获取网页内容',
  'text:opaque': '只收到链接字符串，未获取网页内容',
  'unknown:opaque': '无法识别内容形态，只注入链接地址',
};

export function CapabilityBadge(props: { state?: CapabilityState; contentKind?: string }) {
  const state = props.state ?? 'unknown';
  const meta = STATE_META[state];
  const key = `${props.contentKind ?? ''}:${state}`;
  const action = ACTION[key];
  const tip = props.contentKind ? (TIP[key] ?? `该模型对此类内容无原生理解通道（${meta.label}）`) : undefined;
  const text = action ? `${meta.icon} ${action}` : `${meta.icon} ${meta.label}`;
  const tag = <Tag color={meta.color} style={{ marginInlineEnd: 0 }}>{text}</Tag>;
  return tip ? <Tooltip title={tip}>{tag}</Tooltip> : tag;
}
