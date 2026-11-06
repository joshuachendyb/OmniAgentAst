// 编辑历史: 2026-11-06 小欧 - 三堂会审(SRP): 自 AttachmentArea 抽出 —— 同机导入选择器独立成组件,
//   AttachmentArea 回归「渲染按钮/限制数量/交文件」三职责(设计 §5.6.2) — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧 - F-04: 增"输入绝对路径"入口 —— 原 fileApi.fetchTree 只列项目根目录树,
//   用户无法导入项目根外的本地文件; 输入框直调 importLocal, 后端 _import_roots 校验边界 — 小欧-2026-11-07
/**
 * LocalImportButton - 同机「从本机导入」入口(仅同机显示)
 *
 * 独立组件(SRP): 负责同机目录树选择 + import-local 调用 + Modal/List 渲染。
 * 不做安全判定(薄前端), 探测与导入走 localImport。
 */
import React, { useState } from 'react';
import { Button, Modal, List, Input } from 'antd';
import { showMessage, ErrorType } from '@/services/error/handler';
import { fileApi, type FileNode } from '@/services/api/file.api';
import { importLocal } from '@/features/refs/localImport';

interface LocalImportButtonProps {
  /** 当前会话 ID；为空表示新会话（选中文件后才建会话） */
  sessionId?: string | null;
  /** D1 唯一实现：无会话时创建并回填，返回新 sessionId；失败返回 null */
  ensureSession?: () => Promise<string | null>;
  /** 上传/导入进行中置灰 */
  disabled?: boolean;
}

const LocalImportButton: React.FC<LocalImportButtonProps> = ({
  sessionId,
  ensureSession,
  disabled = false,
}) => {
  const [pickOpen, setPickOpen] = useState(false);
  const [pickPath, setPickPath] = useState('');
  const [pickNodes, setPickNodes] = useState<FileNode[]>([]);
  const [pickLoading, setPickLoading] = useState(false);
  // F-04: 手动输入绝对路径(绕过目录树只列项目根的限制), 后端 _import_roots 校验边界
  const [typedPath, setTypedPath] = useState('');

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

  return (
    <>
      <Button size="small" disabled={disabled} onClick={() => void openPicker()}>
        从本机导入
      </Button>
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
        {/* F-04: 手动输入绝对路径, 绕过目录树只列项目根的限制 */}
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <Input
            size="small"
            placeholder="输入绝对路径，如 D:\数据\report.xlsx"
            value={typedPath}
            onChange={(e) => setTypedPath(e.target.value)}
            onPressEnter={() => void doImport(typedPath.trim())}
            style={{ flex: 1 }}
          />
          <Button
            size="small"
            type="primary"
            disabled={!typedPath.trim()}
            onClick={() => void doImport(typedPath.trim())}
          >
            导入
          </Button>
        </div>
      </Modal>
    </>
  );
};

export { LocalImportButton };
