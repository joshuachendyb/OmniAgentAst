// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段B —— 发送前提示行(输入区容器引用行下, 不新增页面):
//   worst_quality 降级提示 + 推荐切换/超限/非法链接三类提示;
//   mode 优先(超限/非法链接/推荐切换互斥), 无 mode 才看 worst_quality, 互不串扰 — 小欧-2026-11-16

// 2026-11-16 小欧 修正: 删除未使用的 switch 场景(模型切换建议由 RecommendationBar 承载)


/**
 * HintLine —— 发送前提示行（所有输入项发送前可见处理方式）
 *
 * 数据源: worst_quality 与三类 mode 均为后端 preflight/上限真源的直读投影, 本组件零判定逻辑,
 * 只做"mode 优先于 worst"的展示优先级(同一行不叠两条提示)。
 */
import React from 'react';
import { Colors } from '@/utils/stepStyles';
import { chatTokens } from '@/theme/tokens';

export type HintMode = 'over-limit' | 'invalid-url';

/** 两类提示文案(键即场景, 互不串扰的唯一来源; 模型切换建议由 RecommendationBar 承载) */
const MODE_TEXT: Record<HintMode, string> = {
  'over-limit': '引用数量超限，请先移除部分条目再发送',
  'invalid-url': '存在无法使用的链接，已拒绝加入本轮引用',
};

interface HintLineProps {
  /** preflight worst_quality 聚合结果(任一非 native 即 degraded) */
  worstQuality?: 'native' | 'degraded';
  /** 场景提示(优先于 worst_quality 展示) */
  mode?: HintMode;
}

export function HintLine({ worstQuality, mode }: HintLineProps) {
  const text = mode
    ? MODE_TEXT[mode]
    : worstQuality === 'degraded'
      ? '部分引用将被降级处理，发送前请确认各项处理方式'
      : null;
  if (!text) return null;
  return (
    <div
      role="note"
      style={{ color: Colors.TEXT.SECONDARY, fontSize: chatTokens.fontSM }}
    >
      {text}
    </div>
  );
}
