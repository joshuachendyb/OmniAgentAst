// 编辑历史: 2026-09-21 小强 - 新建：关于区文件查看（配置文件全文 / version 文件全文，Modal 只读展示）
// 2026-09-21 小强 - 视觉对齐项目 tokens（FontSize/Colors/Spacing/settingsRadius），全 antd SVG 图标，
//   代码区等宽 CODE 字号 + VERTICAL 边框 + TERTIARY 底，不硬编码色值/字号（stepStyles 铁律）。
// 2026-09-21 小欧 - P2-8：关于区按钮由横排改竖排+靠左对齐（[58] P2-8）
// 2026-09-21 小欧 - P2-9：文件查看 Modal 作品级 UI——Header/元信息条/行号正文/加载错误态/footer（[58] P2-9）
// 2026-09-21 小欧 - 全文逐章核查(P2-9第4条)：错误横幅改 Colors.ERROR 系（ERROR_BG/ERROR_BORDER/ERROR），与文档"Colors.ERROR 系"一致（[58] v1.12）
// 2026-09-21 小欧 - 全文逐章核查：展示弹窗宽散落 800 → settingsModalWidth.display 令牌收口（[58] v1.12 第六章 6.1 规范一）
// 2026-09-21 小欧 - 全文逐章核查：标题图标 marginRight:8、只读 badge padding:6/borderRadius:4 → Spacing.MD/SM、Radius.SM 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小欧 - 关于区排版修复：按钮从独立竖排块改为嵌入对应信息行右侧（排版修复）
// 2026-09-21 小强 - 按钮改名：查看配置文件/查看版本文件（去"全文"，北京老陈定）
// 2026-09-21 小强 - 弹框优化：标题与按钮统一去"全文"（单源 docName 派生，删 title/btnLabel/报错三处双写）；行号栏 sticky；复制失败走框内错误条；空文件占位；Modal 加 destroyOnHidden（北京老陈定）
// 2026-09-22 小欧 - DRY+魔数收口：lineHeight:1.7 两处重复 → CODE_LINE_HEIGHT 常量；行号栏 minWidth:48 → LINE_NO_MIN_WIDTH 命名常量 - 小欧-2026-09-22
import React, { useCallback, useMemo, useState } from 'react';
import { Button, Modal, Spin } from 'antd';
import { FileDoneOutlined, FileTextOutlined } from '@ant-design/icons';
import { configApi } from '@/services/api/config.api';
import {
  Colors,
  FontSize,
  FontWeight,
  Spacing,
  Radius as Radius_SM,
} from '@/utils/stepStyles';
import { settingsRadius, settingsModalWidth } from '@/theme/settingsTokens';
import { showSuccess } from '@/services/error/handler';
import { CopyIcon } from './icons';

type FileKind = 'config' | 'version';

const CODE_FONT = 'Consolas, Menlo, monospace';
// 2026-09-22 小欧 - DRY 收口：行号栏/正文两处 lineHeight:1.7 → 单常量（杜绝改一处漏一处）
const CODE_LINE_HEIGHT = 1.7;
// 2026-09-22 小欧 - 魔数收口：行号栏固定最小宽 48 提取命名常量（代码区等宽布局固有值）
const LINE_NO_MIN_WIDTH = 48;

const stripBom = (s: string): string => s.replace(/^\uFEFF/, '');

const btnStyle: React.CSSProperties = {
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
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(ts);
  }
};

interface AboutFilesProps {
  kind: FileKind;
}

export const AboutFiles: React.FC<AboutFilesProps> = ({ kind }) => {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState('');
  const [meta, setMeta] = useState<FileMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 2026-09-21 小强 - 单源 docName：标题/按钮/报错/toast/复制按钮全由它派生，删 title/btnLabel/报错三处双写（DRY）
  const docName = kind === 'config' ? '配置文件' : '版本文件';

  const openFile = useCallback(async () => {
    setLoading(true);
    setOpen(true);
    setError(null);
    setContent('');
    setMeta(null);
    try {
      if (kind === 'config') {
        const res = await configApi.readConfigFile();
        setContent(stripBom(res.config_content));
        setMeta({
          path: res.path,
          size: res.size,
          lines: res.lines,
          mtime: res.mtime,
        });
      } else {
        const res = await configApi.readVersionFile();
        setContent(stripBom(res.version_content));
        setMeta({
          path: res.path,
          size: res.size,
          lines: res.lines,
          mtime: res.mtime,
        });
      }
    } catch {
      setError('读取' + docName + '失败');
    } finally {
      setLoading(false);
    }
  }, [kind, docName]);

  const close = useCallback(() => {
    setOpen(false);
    setContent('');
    setMeta(null);
    setError(null);
  }, []);

  const copyAll = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content);
      showSuccess(`已复制${docName}`);
    } catch {
      setError('复制失败，请手动选择复制');
    }
  }, [content, docName]);

  const lines = useMemo(() => content.split('\n'), [content]);
  const icon = kind === 'config' ? <FileTextOutlined /> : <FileDoneOutlined />;

  return (
    <>
      <Button icon={icon} style={btnStyle} loading={loading} onClick={openFile}>
        查看{docName}
      </Button>
      <Modal
        open={open}
        width={settingsModalWidth.display}
        destroyOnHidden
        onCancel={close}
        footer={[
          <Button
            key="copy"
            icon={<CopyIcon />}
            onClick={copyAll}
            disabled={!content}
          >
            复制{docName}
          </Button>,
          <Button key="close" type="primary" onClick={close}>
            关闭
          </Button>,
        ]}
        title={
          <div>
            <div
              style={{
                fontWeight: FontWeight.BOLD,
                fontSize: FontSize.PRIMARY,
              }}
            >
              <span style={{ marginRight: Spacing.MD }}>{icon}</span>
              {docName}
            </div>
            {meta && (
              <div
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.SECONDARY,
                  fontWeight: FontWeight.REGULAR,
                }}
              >
                {meta.path}
              </div>
            )}
          </div>
        }
      >
        {meta && (
          <div
            style={{
              display: 'flex',
              gap: Spacing.LG,
              alignItems: 'center',
              padding: `${Spacing.SM}px ${Spacing.MD}px`,
              background: Colors.BG.TERTIARY,
              borderRadius: settingsRadius.DEFAULT,
              marginBottom: Spacing.MD,
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            <span>{meta.lines} 行</span>
            <span>·</span>
            <span>{formatSize(meta.size)}</span>
            <span>·</span>
            <span>更新 {formatTime(meta.mtime)}</span>
            <span
              style={{
                marginLeft: 'auto',
                padding: `0 ${Spacing.SM}px`,
                borderRadius: Radius_SM.SM,
                background: Colors.BG.SECONDARY,
                fontSize: FontSize.SECONDARY,
              }}
            >
              只读
            </span>
          </div>
        )}
        {loading && (
          <div style={{ textAlign: 'center', padding: Spacing.XL * 2 }}>
            <Spin tip="正在读取文件…" />
          </div>
        )}
        {error && (
          <div
            style={{
              padding: Spacing.MD,
              background: Colors.ERROR_BG,
              border: `1px solid ${Colors.ERROR_BORDER}`,
              borderRadius: settingsRadius.DEFAULT,
              color: Colors.ERROR,
              marginBottom: Spacing.MD,
            }}
          >
            {error}
          </div>
        )}
        {!loading && !error && content && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr',
              maxHeight: '60vh',
              overflow: 'auto',
              border: `1px solid ${Colors.BORDER.VERTICAL}`,
              borderRadius: settingsRadius.LG,
            }}
          >
            <pre
              style={{
                margin: 0,
                padding: `${Spacing.LG}px ${Spacing.MD}px`,
                background: Colors.BG.TERTIARY,
                color: Colors.TEXT.SECONDARY,
                textAlign: 'right',
                userSelect: 'none',
                fontSize: FontSize.CODE,
                lineHeight: CODE_LINE_HEIGHT,
                fontFamily: CODE_FONT,
                minWidth: LINE_NO_MIN_WIDTH,
                whiteSpace: 'pre',
                borderRight: `1px solid ${Colors.BORDER.VERTICAL}`,
                flexShrink: 0,
              }}
            >
              {lines.map((_, i) => i + 1).join('\n')}
            </pre>
            <pre
              style={{
                margin: 0,
                padding: `${Spacing.LG}px ${Spacing.XL}px`,
                background: Colors.BG.PRIMARY,
                fontSize: FontSize.CODE,
                lineHeight: CODE_LINE_HEIGHT,
                fontFamily: CODE_FONT,
                whiteSpace: 'pre-wrap',
                wordBreak: 'normal',
                color: Colors.TEXT.PRIMARY,
                flex: 1,
              }}
            >
              {content}
            </pre>
          </div>
        )}
        {!loading && !error && !content && (
          <div
            style={{
              textAlign: 'center',
              padding: Spacing.XL * 2,
              color: Colors.TEXT.SECONDARY,
              fontSize: FontSize.SECONDARY,
            }}
          >
            文件为空
          </div>
        )}
      </Modal>
    </>
  );
};
