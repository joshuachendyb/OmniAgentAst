// 编辑历史: 2026-11-07 小欧 - [13] P4 新建: 附件预览抽屉(图片/PDF 走带 token 的 blob,
//   文本走 /text 前 200 行, 其他给元数据卡), 底部 [加入本轮] + [删除] — 小欧-2026-11-07
/**
 * PreviewDrawer —— 单附件预览（文档[13] 9.2）
 *
 * 渲染矩阵：image/* → <img>（最高 60vh）；pdf → <iframe>（不支持则元数据卡）；
 *   text/* 与 json → 等宽字体前 200 行；其他 → 元数据卡（名称/类型/大小/SHA/来源/时间）。
 * 二进制一律经 attachmentApi.loadRawBlob 带 token 取回 —— 裸 src 带不了 header 必 401。
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Button, Drawer, Empty, Skeleton, Typography } from 'antd';

import {
  attachmentApi,
  type AttachmentRecord,
} from '@/services/api/attachment.api';
import { formatBytes } from '@/utils/format';
import { formatRelativeTime } from '@/utils/time';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

const PREVIEW_LINES = 200;

interface PreviewDrawerProps {
  record: AttachmentRecord | null;
  sessionId?: string | null;
  added?: boolean;
  onClose: () => void;
  onAdd: (rec: AttachmentRecord) => void;
  onDelete: (rec: AttachmentRecord) => void;
}

const metaRow = (label: string, value: string): React.ReactNode => (
  <div
    key={label}
    style={{
      display: 'flex',
      gap: Spacing.SM,
      padding: '4px 0',
      borderBottom: `1px solid ${Colors.BORDER.LIGHT}`,
    }}
  >
    <span style={{ width: 72, flexShrink: 0, color: Colors.TEXT.SECONDARY }}>
      {label}
    </span>
    <span style={{ color: Colors.TEXT.STRONG, wordBreak: 'break-all' }}>
      {value}
    </span>
  </div>
);

const PreviewDrawer: React.FC<PreviewDrawerProps> = ({
  record,
  sessionId,
  added = false,
  onClose,
  onAdd,
  onDelete,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [text, setText] = useState('');
  const [blobUrl, setBlobUrl] = useState('');
  const mime = record?.mime ?? '';
  const isImage = mime.startsWith('image/');
  const isPdf = mime === 'application/pdf';
  const isText =
    mime.startsWith('text/') ||
    mime === 'application/json' ||
    mime.includes('json');

  useEffect(() => {
    setText('');
    setError('');
    setBlobUrl('');
    if (!record || !sessionId) return;
    let alive = true;
    let url = '';
    setLoading(true);
    if (isText && record.kind === 'text') {
      attachmentApi
        .text(record.id, sessionId)
        .then((r) => {
          if (alive) setText(r.text);
        })
        .catch(() => {
          if (alive) setError('文本读取失败，文件可能已被移动');
        })
        .finally(() => {
          if (alive) setLoading(false);
        });
    } else if (isImage || isPdf) {
      attachmentApi
        .loadRawBlob(record.id, sessionId)
        .then((b) => {
          if (!alive) return;
          url = URL.createObjectURL(b);
          setBlobUrl(url);
        })
        .catch(() => {
          if (alive) setError('预览加载失败，文件可能已被移动');
        })
        .finally(() => {
          if (alive) setLoading(false);
        });
    } else {
      setLoading(false);
    }
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [record, sessionId, isText, isImage, isPdf]);

  const body = useMemo((): React.ReactNode => {
    if (!record) return null;
    if (loading) {
      return (
        <div style={{ marginTop: Spacing.MD }}>
          <Skeleton active paragraph={{ rows: 4 }} />
        </div>
      );
    }
    if (error) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span style={{ color: Colors.ERROR_TEXT }}>{error}</span>
          }
        />
      );
    }
    if (isImage) {
      return blobUrl ? (
        <img
          src={blobUrl}
          alt={record.original_name}
          style={{
            maxWidth: '100%',
            maxHeight: '60vh',
            display: 'block',
            margin: '0 auto',
          }}
        />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="没有可预览的内容"
        />
      );
    }
    if (isPdf) {
      return blobUrl ? (
        <iframe
          title={record.original_name}
          src={blobUrl}
          style={{ width: '100%', height: '60vh', border: 'none' }}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="预览不可用" />
      );
    }
    if (isText && text) {
      const lines = text.split('\n');
      const head = lines.slice(0, PREVIEW_LINES).join('\n');
      return (
        <>
          <pre
            style={{
              margin: 0,
              padding: Spacing.SM,
              background: Colors.BG.SECONDARY,
              borderRadius: 6,
              fontSize: FontSize.SECONDARY,
              fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              maxHeight: '60vh',
              overflow: 'auto',
            }}
          >
            {head}
          </pre>
          {lines.length > PREVIEW_LINES && (
            <Typography.Text
              style={{
                fontSize: FontSize.SECONDARY,
                color: Colors.TEXT.SECONDARY,
              }}
            >
              仅预览前 {PREVIEW_LINES} 行（共 {lines.length}{' '}
              行），完整内容将在引用时注入
            </Typography.Text>
          )}
        </>
      );
    }
    // 其他类型：元数据卡
    return (
      <div style={{ fontSize: FontSize.PRIMARY }}>
        {metaRow('名称', record.original_name)}
        {metaRow('类型', record.mime || '未知')}
        {metaRow('大小', formatBytes(record.size))}
        {metaRow('SHA256', record.sha256.slice(0, 16))}
        {metaRow('来源会话', record.session_id ?? '全局资产')}
        {metaRow('上传时间', record.created_at.slice(0, 16).replace('T', ' '))}
        {metaRow(
          '最近使用',
          record.last_used_at
            ? `${formatRelativeTime(record.last_used_at)}（${record.use_count} 次）`
            : '未使用过'
        )}
        <Typography.Text
          style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}
        >
          该类型不支持内联预览，加入本轮后由后端按类型生成注入文本。
        </Typography.Text>
      </div>
    );
  }, [record, loading, error, isImage, isPdf, isText, blobUrl, text]);

  return (
    <Drawer
      open={!!record}
      onClose={onClose}
      width={560}
      title={record?.original_name ?? '预览'}
      footer={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button
            type="primary"
            disabled={!record || added}
            onClick={() => record && onAdd(record)}
          >
            {added ? '已在本轮' : '加入本轮'}
          </Button>
          <Button
            danger
            type="text"
            style={{ marginLeft: 'auto' }}
            onClick={() => record && onDelete(record)}
          >
            删除
          </Button>
        </div>
      }
    >
      {body}
    </Drawer>
  );
};

export { PreviewDrawer };
