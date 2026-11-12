// 编辑历史: 2026-11-11 小欧 新建: 附件/引用能力状态徽标(纯展示, 零状态判定) — 小欧-2026-11-11
import { Tag, Tooltip } from 'antd';

/** 状态徽标: 纯展示组件 —— state 必填由调用方给出, 组件不查表、不推导、不发请求。
 *  附件/文件 chip 取 modelEntry.ref_capability_map[source][content];
 *  URL chip 取 [23] preflight items[].state; 两者计算函数同源 state_of(C9)。 */
export type CapabilityState = 'native' | 'degraded' | 'opaque' | 'unknown';

const BADGE: Record<CapabilityState, { color: string; text: string }> = {
  native: { color: 'green', text: '原生理解' },
  degraded: { color: 'blue', text: '降级' },
  opaque: { color: 'default', text: '仅档案' },
  unknown: { color: 'default', text: '未知' },      // 缺键兜底, 不崩(守门测试断言)
};

/** tooltip 文案: (content_kind, state) → i18n 文案键, 纯文案映射不含任何状态判定 */
const TIP: Record<string, string> = {
  'image:opaque': '当前模型只能拿到文件名，看不到图片内容',
  'video:degraded': '当前模型只能读到时长/编码等元数据',
  'audio:degraded': '当前模型只能读到时长/编码等元数据',
  'richdoc:degraded': '当前模型将收到抽取后的文本',
  'url:opaque': '当前模型只收到链接文本，未获取内容',
};

export function CapabilityBadge(props: { state?: CapabilityState; contentKind?: string }) {
  const state = props.state ?? 'unknown';
  const cfg = BADGE[state];
  const tip = props.contentKind ? TIP[`${props.contentKind}:${state}`] : undefined;
  const tag = <Tag color={cfg.color} style={{ marginInlineEnd: 0 }}>{cfg.text}</Tag>;
  return tip ? <Tooltip title={tip}>{tag}</Tooltip> : tag;
}
