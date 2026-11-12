// 编辑历史: 2026-11-11 小欧 新建: 模型页附件引用能力矩阵面板(P5),
//   数据 = ModelEntry.ref_capability_map(后端 contract.ref_capability_map 生成, 只读不推导) — 小欧-2026-11-11
// 编辑历史: 2026-11-11 小欧 增运行指标条(P5): 拉取 GET /attachments/metrics 只读聚合,
//   展示近1天三比率(降级占比/原生失败率/抽取失败率) + fetch_fail 计数, 失败可定位到 source/kind — 小欧-2026-11-11

/**
 * ModelTabRefCapability —— 当前模型的附件引用能力矩阵。
 *
 * 行 = content_kind(七类), 列 = source_kind(file/attachment/url),
 * 单元格 = 契约三态徽标(native/degraded/opaque), 缺格显示「—」。
 */
import React, { useEffect, useState } from 'react';
import { Table, Tooltip } from 'antd';

import { CapabilityBadge, type CapabilityState } from '@/features/chat/components/input/CapabilityBadge';
import { attachmentApi, type AttachmentMetrics } from '@/services/api/attachment.api';

const CONTENT_KINDS = ['text', 'image', 'video', 'audio', 'richdoc', 'binary', 'unknown'];
const SOURCE_KINDS = ['file', 'attachment', 'url'] as const;

const KIND_LABEL: Record<string, string> = {
  text: '文本', image: '图片', video: '视频', audio: '音频',
  richdoc: '富文档', binary: '二进制', unknown: '未知/无后缀',
};
const SOURCE_LABEL: Record<string, string> = {
  file: '文件引用', attachment: '附件', url: '链接',
};

type RefCapabilityMap = Record<string, Record<string, 'native' | 'degraded' | 'opaque'>>;

export const ModelTabRefCapability: React.FC<{ map?: RefCapabilityMap }> = ({ map }) => {
  const dataSource = CONTENT_KINDS.map((ck) => ({
    key: ck,
    kind: KIND_LABEL[ck] ?? ck,
    ...Object.fromEntries(
      SOURCE_KINDS.map((sk) => [sk, map?.[sk]?.[ck] as CapabilityState | undefined])
    ),
  }));
  return (
    <div style={{ marginTop: 12 }}>
      <Table
        size="small"
        pagination={false}
        dataSource={dataSource}
        rowKey="key"
        columns={[
          { title: '内容类型', dataIndex: 'kind', width: 96 },
          ...SOURCE_KINDS.map((sk) => ({
            title: SOURCE_LABEL[sk],
            dataIndex: sk,
            width: 110,
            render: (v: CapabilityState | undefined) =>
              v ? <CapabilityBadge state={v} /> : <span style={{ opacity: 0.4 }}>—</span>,
          })),
        ]}
      />
      <div style={{ marginTop: 4, opacity: 0.7, fontSize: 12 }}>
        <Tooltip title="native=原生模态直传 / degraded=降级注入(文本出口) / opaque=仅链接文本">
          <span>native=原生直传 · degraded=降级注入 · opaque=仅链接文本</span>
        </Tooltip>
      </div>
      <MetricsStrip />
    </div>
  );
};

/** 运行指标条(P5): 近1天三比率 + fetch_fail 计数, 只读日志聚合(后端 /attachments/metrics) */
const MetricsStrip: React.FC = () => {
  const [m, setM] = useState<AttachmentMetrics | null>(null);
  useEffect(() => {
    let alive = true;
    attachmentApi.metrics(1).then((r) => alive && setM(r)).catch(() => {/* 指标拉取失败静默, 面板不受影响 */});
    return () => { alive = false; };
  }, []);
  if (!m) return null;
  const keys = Array.from(new Set([
    ...Object.keys(m.rates.degrade), ...Object.keys(m.rates.native_fail),
    ...Object.keys(m.rates.extract_fail), ...Object.keys(m.counts.fetch_fail ?? {}),
  ]));
  if (!keys.length) return null;
  const pct = (v: number | undefined) => (v === undefined ? '—' : `${(v * 100).toFixed(1)}%`);
  return (
    <Table
      size="small"
      pagination={false}
      style={{ marginTop: 8 }}
      rowKey="key"
      columns={[
        { title: '运行指标(近1天)', dataIndex: 'key', width: 140 },
        { title: '降级占比', dataIndex: 'degrade', width: 90 },
        { title: '原生失败率', dataIndex: 'native_fail', width: 100 },
        { title: '抽取失败率', dataIndex: 'extract_fail', width: 100 },
        { title: '下载失败次数', dataIndex: 'fetch_fail', width: 110 },
      ]}
      dataSource={keys.map((k) => ({
        key: k,
        degrade: pct(m.rates.degrade[k]),
        native_fail: pct(m.rates.native_fail[k]),
        extract_fail: pct(m.rates.extract_fail[k]),
        fetch_fail: m.counts.fetch_fail?.[k] ?? '—',
      }))}
    />
  );
};
