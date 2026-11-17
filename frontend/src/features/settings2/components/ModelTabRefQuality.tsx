// 编辑历史: 2026-11-11 小欧 新建: 模型页附件引用能力矩阵面板(P5),
//   数据 = ModelEntry.ref_quality_map(后端 contract.ref_quality_map 生成, 只读不推导) — 小欧-2026-11-14
// 编辑历史: 2026-11-11 小欧 增运行指标条(P5): 拉取 GET /attachments/metrics 只读聚合,
//   展示近1天三比率(降级占比/原生失败率/抽取失败率) + fetch_fail 计数, 失败可定位到 source/kind — 小欧-2026-11-11
// 编辑历史: 2026-11-12 小欧 按[28]方案落地: 表标题「模型多态内容处理模式推测分析表」+行列简注
//   (引用=指针/附件=实体/外链=只注入链接地址); 行头「内容类型」→「内容形态」, 列头
//   「文件引用/附件/链接」→「引用/附件/外链」; tooltip 缩写串改常驻图例(按档位三组,
//   动作词复用 CapabilityBadge 的 ACTION/STATE_META 同一映射, 不另建副本); map 为空显示
//   空态文案; 指标条加标题「运行指标(近1天实测)」+列头(%) + 越低越好说明 — 小欧-2026-11-12
// 编辑历史: 2026-11-14 小欧 状态模型正交化: 数据源改 ref_quality_map(quality 四值), 图例与徽标
//   统一按 QUALITY_META 单表出文案, 删除 ACTION/STATE_META 与 url 列 opaque 特判 — 小欧-2026-11-14

/**
 * ModelTabRefQuality —— 当前模型的附件引用质量矩阵。
 *
 * 行 = content_kind(七类), 列 = source_kind(file/attachment/url),
 * 单元格 = 契约四值质量徽标, 缺格显示「—」; 底部运行指标条(近1天实测)。
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag } from 'antd';
import { FontSize, FontWeight } from '@/utils/stepStyles';

import { QualityBadge, QUALITY_META } from '@/features/chat/components/input/QualityBadge';
import type { RefQuality } from '@/services/api/model.api';
import { attachmentApi, type AttachmentMetrics } from '@/services/api/attachment.api';

const CONTENT_KINDS = ['text', 'image', 'video', 'audio', 'richdoc', 'binary', 'unknown'];
const SOURCE_KINDS = ['file', 'attachment', 'url'] as const;

const KIND_LABEL: Record<string, string> = {
  text: '文本', image: '图片', video: '视频', audio: '音频',
  richdoc: '富文档', binary: '二进制', unknown: '未知/无后缀',
};
const SOURCE_LABEL: Record<string, string> = {
  file: '引用', attachment: '附件', url: '外链',
};

type RefQualityMap = Record<string, Record<string, RefQuality>>;
const QUALITY_ORDER: RefQuality[] = ['native', 'text_full', 'meta_only', 'link_only'];

/** 常驻图例: 按四值单表出「图标+档位名+白话」, 与徽标同一真源 */
const Legend: React.FC = () => (
  <div style={{ marginTop: 4, fontSize: FontSize.SECONDARY }}>
    {QUALITY_ORDER.map((q) => (
      <div key={q} style={{ opacity: 0.85 }}>
        <Tag color={QUALITY_META[q].color} style={{ marginInlineEnd: 4 }}>
          {QUALITY_META[q].icon} {QUALITY_META[q].label}
        </Tag>
        {QUALITY_META[q].tip}
      </div>
    ))}
  </div>
);

export const ModelTabRefQuality: React.FC<{ map?: RefQualityMap }> = ({ map }) => {
  const hasData = map && SOURCE_KINDS.some((sk) => map[sk] && Object.keys(map[sk]).length);
  if (!hasData) {
    return (
      <div style={{ marginTop: 12, opacity: 0.6, fontSize: FontSize.SECONDARY }}>当前模型未提供质量数据</div>
    );
  }
  const dataSource = CONTENT_KINDS.map((ck) => ({
    key: ck,
    kind: KIND_LABEL[ck] ?? ck,
    ...Object.fromEntries(
      SOURCE_KINDS.map((sk) => [sk, map?.[sk]?.[ck] as RefQuality | undefined])
    ),
  }));
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: FontWeight.BOLD, marginBottom: 2 }}>模型多态内容处理模式推测分析表</div>
      <div style={{ fontSize: FontSize.SECONDARY, opacity: 0.7, marginBottom: 4 }}>
        行 = 内容形态（送进来的东西按后缀/MIME 分七类）；列 = 引用通道：
        <b>引用</b>（工作区文件路径，只记路径不复制，发送时现场读取）／
        <b>附件</b>（上传复制进附件目录的文件实体）／
        <b>外链</b>（URL，只注入链接地址，不抓取网页正文）
      </div>
      <Table
        size="small"
        pagination={false}
        dataSource={dataSource}
        rowKey="key"
        columns={[
          { title: '内容形态', dataIndex: 'kind', width: 96 },
          ...SOURCE_KINDS.map((sk) => ({
            title: SOURCE_LABEL[sk],
            dataIndex: sk,
            width: 110,
            render: (v: RefQuality | undefined) =>
              v ? <QualityBadge quality={v} /> : <span style={{ opacity: 0.4 }}>—</span>,
          })),
        ]}
      />
      <Legend />
      <MetricsStrip />
    </div>
  );
};

/** 运行指标条(P5): 近1天三比率 + fetch_fail 计数, 只读日志聚合(后端 /attachments/metrics);
 *  无数据不渲染(条件渲染, 近1天没跑过附件/引用处理属正常) */
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
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: FontWeight.BOLD, marginBottom: 2 }}>运行指标（近 1 天实测）</div>
      <Table
        size="small"
        pagination={false}
        rowKey="key"
        columns={[
          { title: '指标项', dataIndex: 'key', width: 140 },
          { title: '降级占比 (%)', dataIndex: 'degrade', width: 100 },
          { title: '原生失败率 (%)', dataIndex: 'native_fail', width: 110 },
          { title: '抽取失败率 (%)', dataIndex: 'extract_fail', width: 110 },
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
      <div style={{ fontSize: FontSize.SECONDARY, opacity: 0.7 }}>指标越低越好；下载失败次数为近 1 天累计</div>
    </div>
  );
};
