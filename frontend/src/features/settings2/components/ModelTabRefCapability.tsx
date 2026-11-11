// 编辑历史: 2026-11-11 小欧 新建: 模型页附件引用能力矩阵面板(P5),
//   数据 = ModelEntry.ref_capability_map(后端 contract.ref_capability_map 生成, 只读不推导) — 小欧-2026-11-11

/**
 * ModelTabRefCapability —— 当前模型的附件引用能力矩阵。
 *
 * 行 = content_kind(七类), 列 = source_kind(file/attachment/url),
 * 单元格 = 契约三态徽标(native/degraded/opaque), 缺格显示「—」。
 */
import React from 'react';
import { Table, Tooltip } from 'antd';

import { CapabilityBadge, type CapabilityState } from '@/features/chat/components/input/CapabilityBadge';

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
    </div>
  );
};
