// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 附件多模态预留区, 上传随E1携带(暂缓)(4.6.2)
// 编辑历史: 2026-08-28 小欧 - ①D/d2: 暂缓期隐藏不占位, 启用加 Tooltip 说明
// 编辑历史: 2026-10-06 小欧 - 北京老陈指令: 暂缓期不再隐藏, 改为显示+置灰(disabled)。
// 编辑历史: 2026-11-06 小欧 - 重写为纯文件选择器(建会话/上传/入队/提示全部下沉 uploadAttachments 唯一
//   实现, 本组件只交文件); 加同机「从本机导入」入口(据后端 local-capability 结果显隐, 不做安全判定) — 小欧-2026-11-06
/**
 * AttachmentArea - 附件按钮（按钮行左侧「📎 附件」）
 *
 * 职责只有三件：渲染按钮、限制单批数量、把选中的文件交给 uploadAttachments。
 * 不建会话、不上传、不渲染 chip、不产生注入正文 —— 这些各有唯一归属（D1 / 附件域 / 引用区 / 后端 resolver）。
 * 同机时追加「从本机导入」入口：调 GET /attachments/local-capability 探测，仅同机显示。
 */
import React, { useMemo, useRef, useState } from 'react';
import { Button, Tooltip, Upload, Modal, List } from 'antd';
import type { UploadProps } from 'antd';
import { PaperClipOutlined } from '@ant-design/icons';

import { MAX_BATCH, uploadAttachments } from '@/features/refs/uploadAttachment';
import { getLocalCapability, importLocal } from '@/features/refs/localImport';
import { showMessage, ErrorType } from '@/services/error/handler';
import { fileApi, type FileNode } from '@/services/api/file.api';

interface AttachmentAreaProps {
  visible?: boolean;
  disabled?: boolean;
  /** 当前会话 ID；为空表示新会话（D1：选中文件后才建会话） */
  sessionId?: string | null;
  /** D1 唯一实现：无会话时创建并回填，返回新 sessionId；失败返回 null */
  ensureSession?: () => Promise<string | null>;
}

const AttachmentArea: React.FC<AttachmentAreaProps> = ({
  visible = false,
  disabled = false,
  sessionId,
  ensureSession,
}) => {
  const [busy, setBusy] = useState(0);
  const [canLocalImport, setCanLocalImport] = useState(false);
  const blocked = disabled || busy > 0;

  // 同机能力探测——前端只据后端结果显隐, 不做安全判定(薄前端)
  React.useEffect(() => {
    if (!visible || disabled) return;
    void getLocalCapability().then(setCanLocalImport);
  }, [visible, disabled]);

  // 同机本地导入选择器：只列后端返回的目录树（复用 /files/tree），不做类型/路径判定
  const [pickOpen, setPickOpen] = useState(false);
  const [pickPath, setPickPath] = useState('');
  const [pickNodes, setPickNodes] = useState<FileNode[]>([]);
  const [pickLoading, setPickLoading] = useState(false);

  /** posix 路径取父目录（空串 = 项目根） */
  const parentOf = (p: string): string => {
    const i = p.lastIndexOf('/');
    return i <= 0 ? '' : p.slice(0, i);
  };

  /** 列一层目录（后端已有能力，不新建文件树） */
  const loadDir = async (path: string) => {
    setPickLoading(true);
    try {
      const res = await fileApi.fetchTree(path, { maxDepth: 1 });
      setPickPath(path);
      setPickNodes(res.nodes);
    } catch {
      showMessage(ErrorType.UNKNOWN, '目录读取失败');
    } finally {
      setPickLoading(false);
    }
  };

  const openPicker = async () => {
    setPickOpen(true);
    await loadDir('');
  };

  /** 选中文件 → import-local（后端读盘）；路径只是读源，落盘目标由后端计算（TR-3） */
  const doImport = async (path: string) => {
    const sid = sessionId || (await ensureSession?.());
    if (!sid) {
      showMessage(ErrorType.UNKNOWN, '会话创建失败，附件未导入');
      return;
    }
    if (await importLocal(sid, path)) setPickOpen(false);
  };

  const tip = useMemo(() => {
    if (disabled) return '附件上传暂未启用';
    if (busy > 0) return `正在上传（${busy} 个）…`;
    return '支持图片、文本、PDF、Word、Excel、PowerPoint、视频（单批 ≤10，图片 ≤10MB，其他 ≤20MB）';
  }, [disabled, busy]);

  /** 批量索引是"本次选择的完整列表", 用它判第 10 个之后直接忽略(不维护批次计数器)。
   *  大小与类型判定统一在 uploadAttachments/后端, 此处不重复一份。
   *  beforeUpload 返回 false 阻止 antd 自动上传(防 multiple 并发 customRequest),
   *    收集所有文件后统一交给 uploadAttachments(串行, D1 建会话只调一次)。 */
  const pendingFiles = useRef<File[]>([]);
  const beforeUpload: NonNullable<UploadProps['beforeUpload']> = (
    file,
    batch
  ) => {
    if (batch.indexOf(file) >= MAX_BATCH) {
      showMessage(ErrorType.WARNING, `一次最多选择 ${MAX_BATCH} 个文件`);
      return Upload.LIST_IGNORE;
    }
    pendingFiles.current.push(file);
    // 最后一个文件触发上传: antd batch 是本次选择的完整列表
    if (pendingFiles.current.length === batch.length) {
      const files = pendingFiles.current;
      pendingFiles.current = [];
      setBusy((n) => n + files.length); // 上传期间按钮 loading/禁用
      void uploadAttachments(files, { sessionId, ensureSession }).then((r) => {
        setBusy((n) => Math.max(0, n - files.length + r.ok));
      });
    }
    return false; // 阻止 antd 自动调 customRequest
  };

  if (!visible) return null;
  return (
    <Tooltip title={tip}>
      <Upload
        multiple
        showUploadList={false}
        disabled={blocked}
        beforeUpload={beforeUpload}
      >
        <Button
          size="small"
          icon={<PaperClipOutlined />}
          loading={busy > 0}
          disabled={blocked}
        >
          附件
        </Button>
      </Upload>
      {canLocalImport && (
        <Button
          size="small"
          disabled={blocked}
          onClick={() => void openPicker()}
        >
          从本机导入
        </Button>
      )}
      <Modal
        open={pickOpen}
        title="从本机选择文件（同机：后端读盘，不上传内容）"
        footer={null}
        width={520}
        onCancel={() => setPickOpen(false)}
      >
        <div style={{ marginBottom: 8 }}>
          <Button
            size="small"
            disabled={!pickPath || pickLoading}
            onClick={() => void loadDir(parentOf(pickPath))}
          >
            ↑ 上级
          </Button>
          <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>
            {pickPath || '项目根'}
          </span>
        </div>
        <List
          size="small"
          loading={pickLoading}
          dataSource={pickNodes}
          style={{ maxHeight: 360, overflow: 'auto' }}
          renderItem={(n) => (
            <List.Item
              style={{ cursor: 'pointer' }}
              onClick={() =>
                n.type === 'dir' ? void loadDir(n.key) : void doImport(n.key)
              }
            >
              {n.type === 'dir' ? '📁 ' : '📄 '}
              {n.name}
            </List.Item>
          )}
        />
      </Modal>
    </Tooltip>
  );
};

export { AttachmentArea };
