// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D D12 —— Composer 级输入预检重算 hook。
//   取代"仅 URL 采集时预检": 引用条增删(签名变化)防抖后整体重算, 一次响应同时供
//   worst_quality 聚合、逐项 quality 回写、routing_advice 展示;
//   seq 递增丢弃迟到响应(防慢的旧请求覆盖新的) — 小欧-2026-11-16

// 2026-11-16 小欧 修正: 无生效模型时不发预检(画像无从判定, 避免误报降级); 去掉无用 sessionId 入参;
//   modelKey 无 provider 时不再拼前导斜杠

import { useEffect, useRef, useState } from 'react';
import { preflightInput } from '@/services/api/inputs.api';
import type { RoutingAdvice } from '@/types/chat';
import type { ComposerRef } from '../../refs/store';
import {
  refsSignature,
  refsToPreflightItems,
} from '../../refs/preflightItems';

export type { RoutingAdvice };

export interface InputPreflightState {
  /** 后端聚合 worst_quality(无引用/未返回时为 native) */
  worstQuality: 'native' | 'degraded';
  /** 能力路由建议(keep 归一为 null, 不展示) */
  routingAdvice: RoutingAdvice | null;
  /** 逐项 quality, 按 preflightItemKey 键控(供 chip 徽标回写) */
  qualityByKey: Record<string, string>;
}

export interface UseInputPreflightOpts {
  refs: ComposerRef[];
  modelId?: string;
  modelProvider?: string;
  routingMode?: 'suggest' | 'auto' | 'strict';
  /** 防抖窗口(ms), 仅在签名变化后触发 */
  delayMs?: number;
}

const EMPTY: InputPreflightState = {
  worstQuality: 'native',
  routingAdvice: null,
  qualityByKey: {},
};

export function useInputPreflight({
  refs,
  modelId,
  modelProvider,
  routingMode = 'suggest',
  delayMs = 150,
}: UseInputPreflightOpts): InputPreflightState {
  const [state, setState] = useState<InputPreflightState>(EMPTY);
  const seqRef = useRef(0);
  const refsRef = useRef(refs);
  refsRef.current = refs;

  const sig = refsSignature(refs);
  const modelKey = modelId
    ? (modelProvider ? `${modelProvider}/${modelId}` : modelId)
    : '';

  useEffect(() => {
    if (!sig || !modelKey) {
      setState(EMPTY);
      return;
    }
    const seq = ++seqRef.current;
    const timer = window.setTimeout(() => {
      void preflightInput({
        model_id: modelKey,
        text: '',
        items: refsToPreflightItems(refsRef.current),
        mode: routingMode,
      })
        .then((res) => {
          if (seq !== seqRef.current) return;
          const qualityByKey: Record<string, string> = {};
          for (const it of res.items) qualityByKey[it.key] = it.quality;
          setState({
            worstQuality: res.worst_quality,
            routingAdvice:
              res.routing_advice.action === 'keep'
                ? null
                : res.routing_advice,
            qualityByKey,
          });
        })
        .catch(() => {
          // 预检失败不改状态: 建议性预览, 不阻断、不误标
        });
    }, delayMs);
    return () => window.clearTimeout(timer);
  }, [sig, modelKey, routingMode, delayMs]);

  return state;
}
