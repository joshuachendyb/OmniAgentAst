// 编辑历史: 2026-09-21 小强 - 新建：关于区文件查看（配置文件全文 / version 文件全文，Modal 只读展示）
// 2026-09-21 小强 - 视觉对齐项目 tokens（FontSize/Colors/Spacing/settingsRadius），全 antd SVG 图标，
//   代码区等宽 CODE 字号 + VERTICAL 边框 + TERTIARY 底，不硬编码色值/字号（stepStyles 铁律）。
import React, { useCallback, useState } from 'react';
import { Button, Modal } from 'antd';
import {
  FileDoneOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { configApi } from '@/services/api/config.api';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsRadius } from '@/theme/settingsTokens';
import { showSuccess, showMessage, ErrorType } from '@/services/error/handler';
import { CopyIcon } from './icons';

type FileKind = 'config' | 'version';

const CODE_FONT = 'Consolas, Menlo, monospace';

const stripBom = (s: string): string => s.replace(/^\uFEFF/, '');

const actionStyle: React.CSSProperties = {
  fontSize: FontSize.PRIMARY,
  fontWeight: FontWeight.REGULAR,
};

const metaStyle: React.CSSProperties = {
  fontSize: FontSize.SECONDARY,
  color: Colors.TEXT.SECONDARY,
  marginBottom: Spacing.MD,
};

const preStyle: React.CSSProperties = {
  maxHeight: '60vh',
  overflow: 'auto',
  margin: 0,
  padding: `${Spacing.LG}px ${Spacing.XL}px`,
  background: Colors.BG.TERTIARY,
  border: `1px solid ${Colors.BORDER.VERTICAL}`,
  borderRadius: settingsRadius.LG,
  fontSize: FontSize.CODE,
  lineHeight: 1.7,
  fontFamily: CODE_FONT,
  whiteSpace: 'pre',
  wordBreak: 'normal',
  color: Colors.TEXT.PRIMARY,
};

export const AboutFiles: React.FC = () => {
  const [open, setOpen] = useState<FileKind | null>(null);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);

  const openFile = useCallback(async (kind: FileKind) => {
    setLoading(true);
    setOpen(kind);
    try {
      if (kind === 'config') {
        const { config_content } = await configApi.readConfigFile();
        setContent(stripBom(config_content));
      } else {
        const { version_content } = await configApi.readVersionFile();
        setContent(stripBom(version_content));
      }
    } catch {
      setOpen(null);
      showMessage(
        ErrorType.LOAD_CONFIG_FAILED,
        '读取' + (kind === 'config' ? '配置文件' : '版本文件') + '全文失败'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const copyAll = useCallback(() => {
    void navigator.clipboard.writeText(content);
    showSuccess('已复制全文');
  }, [content]);

  const title = open === 'config' ? '配置文件全文' : 'version 文件全文';
  return (
    <>
      <div style={{ display: 'flex', gap: Spacing.MD, margin: `${Spacing.XS}px 0 ${Spacing.MD}px` }}>
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
        title={title}
        width={800}
        onCancel={() => setOpen(null)}
        footer={[
          <Button key="copy" icon={<CopyIcon />} onClick={copyAll} disabled={!content}>
            复制全文
          </Button>,
          <Button key="close" type="primary" onClick={() => setOpen(null)}>
            关闭
          </Button>,
        ]}
      >
        <div style={metaStyle}>
          文件全文只读展示（需要改动请使用上方设置项保存后此处同步刷新）
        </div>
        <pre style={preStyle}>{content}</pre>
      </Modal>
    </>
  );
};