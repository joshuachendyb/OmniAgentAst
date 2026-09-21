// 编辑历史: 2026-09-21 小强 - 新建：关于区文件查看（配置文件全文 / version 文件全文，Modal 只读展示）
// 2026-09-21 小强 - 视觉对齐项目 tokens（FontSize/Colors/Spacing/settingsRadius），全 antd SVG 图标，
//   代码区等宽 CODE 字号 + VERTICAL 边框 + TERTIARY 底，不硬编码色值/字号（stepStyles 铁律）。
// 2026-09-21 小欧 - P2-8：关于区按钮由横排改竖排+靠左对齐（[58] P2-8）
// 2026-09-21 小欧 - P2-9：文件查看 Modal 作品级 UI——Header/元信息条/行号正文/加载错误态/footer（[58] P2-9）
import React, { useCallback, useMemo, useState } from 'react';
import { Button, Modal, Spin } from 'antd';
import {
  FileDoneOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { configApi } from '@/services/api/config.api';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsRadius } from '@/theme/settingsTokens';
import { showSuccess } from '@/services/error/handler';
import { CopyIcon } from './icons';

type FileKind = 'config' | 'version';

const CODE_FONT = 'Consolas, Menlo, monospace';

const stripBom = (s: string): string => s.replace(/^\uFEFF/, '');

const actionStyle: React.CSSProperties = {
  fontSize: FontSize.PRIMARY,
  fontWeight: FontWeight.REGULAR,
};

interface FileMeta {
  path: string;
  size: number;
  lines: number;
  mtime: number;
}

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatTime = (ts: number): string => {
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return String(ts);
  }
};

export const AboutFiles: React.FC = () => {
  const [open, setOpen] = useState<FileKind | null>(null);
  const [content, setContent] = useState('');
  const [meta, setMeta] = useState<FileMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openFile = useCallback(async (kind: FileKind) => {
    setLoading(true);
    setOpen(kind);
    setError(null);
    setContent('');
    setMeta(null);
    try {
      if (kind === 'config') {
        const res = await configApi.readConfigFile();
        setContent(stripBom(res.config_content));
        setMeta({ path: res.path, size: res.size, lines: res.lines, mtime: res.mtime });
      } else {
        const res = await configApi.readVersionFile();
        setContent(stripBom(res.version_content));
        setMeta({ path: res.path, size: res.size, lines: res.lines, mtime: res.mtime });
      }
    } catch {
      setError('读取' + (kind === 'config' ? '配置文件' : '版本文件') + '全文失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const close = useCallback(() => {
    setOpen(null);
    setContent('');
    setMeta(null);
    setError(null);
  }, []);

  const copyAll = useCallback(() => {
    void navigator.clipboard.writeText(content);
    showSuccess('已复制全文');
  }, [content]);

  const lines = useMemo(() => content.split('\n'), [content]);
  const title = open === 'config' ? '配置文件全文' : 'version 文件全文';

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: Spacing.XS, margin: `${Spacing.XS}px 0 ${Spacing.MD}px` }}>
        <Button
          icon={<FileTextOutlined />}
          style={actionStyle}
          loading={loading && open === 'config'}
          onClick={() => openFile('config')}
        >
          查看配置文件全文
        </Button>
        <Button
          icon={<FileDoneOutlined />}
          style={actionStyle}
          loading={loading && open === 'version'}
          onClick={() => openFile('version')}
        >
          查看 version 文件全文
        </Button>
      </div>
      <Modal
        open={open !== null}
        width={800}
        onCancel={close}
        footer={[
          <Button key="copy" icon={<CopyIcon />} onClick={copyAll} disabled={!content}>
            复制全文
          </Button>,
          <Button key="close" type="primary" onClick={close}>
            关闭
          </Button>,
        ]}
        title={
          <div>
            <div style={{ fontWeight: FontWeight.BOLD, fontSize: FontSize.PRIMARY }}>
              <FileTextOutlined style={{ marginRight: 8 }} />
              {title}
            </div>
            {meta && (
              <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.REGULAR }}>
                {meta.path}
              </div>
            )}
          </div>
        }
      >
        {meta && (
          <div style={{
            display: 'flex', gap: Spacing.LG, alignItems: 'center',
            padding: `${Spacing.SM}px ${Spacing.MD}px`,
            background: Colors.BG.TERTIARY,
            borderRadius: settingsRadius.DEFAULT,
            marginBottom: Spacing.MD,
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
          }}>
            <span>{meta.lines} 行</span>
            <span>·</span>
            <span>{formatSize(meta.size)}</span>
            <span>·</span>
            <span>更新 {formatTime(meta.mtime)}</span>
            <span style={{
              marginLeft: 'auto',
              padding: '0 6px',
              borderRadius: 4,
              background: Colors.BG.SECONDARY,
              fontSize: FontSize.SECONDARY,
            }}>只读</span>
          </div>
        )}
        {loading && (
          <div style={{ textAlign: 'center', padding: Spacing.XL * 2 }}>
            <Spin tip="正在读取文件…" />
          </div>
        )}
        {error && (
          <div style={{
            padding: Spacing.MD,
            background: Colors.BG.TERTIARY,
            borderRadius: settingsRadius.DEFAULT,
            color: Colors.TEXT.SECONDARY,
            marginBottom: Spacing.MD,
          }}>
            {error}
          </div>
        )}
        {!loading && !error && content && (
          <div style={{ display: 'flex', maxHeight: '60vh', overflow: 'auto', border: `1px solid ${Colors.BORDER.VERTICAL}`, borderRadius: settingsRadius.LG }}>
            <pre style={{
              margin: 0,
              padding: `${Spacing.LG}px ${Spacing.MD}px`,
              background: Colors.BG.TERTIARY,
              color: Colors.TEXT.SECONDARY,
              textAlign: 'right',
              userSelect: 'none',
              fontSize: FontSize.CODE,
              lineHeight: 1.7,
              fontFamily: CODE_FONT,
              minWidth: 48,
              borderRight: `1px solid ${Colors.BORDER.VERTICAL}`,
            }}>
              {lines.map((_, i) => i + 1).join('\n')}
            </pre>
            <pre style={{
              margin: 0,
              padding: `${Spacing.LG}px ${Spacing.XL}px`,
              background: Colors.BG.PRIMARY,
              fontSize: FontSize.CODE,
              lineHeight: 1.7,
              fontFamily: CODE_FONT,
              whiteSpace: 'pre',
              wordBreak: 'normal',
              color: Colors.TEXT.PRIMARY,
              flex: 1,
              overflow: 'auto',
            }}>
              {content}
            </pre>
          </div>
        )}
      </Modal>
    </>
  );
};