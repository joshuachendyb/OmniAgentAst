// 编辑历史: 2026-11-07 小欧 - 新建: 统一文件抽屉 —— 唯一「附件」入口的面板, 收纳 MaterialPackPanel(合集)
//   与 LocalImportButton(同机导入)两项能力; 左栏选来源、右栏点行即加入本轮; 附件 enqueue / 文件 quoteFile /
//   同机 importLocal 三条入队路径各自唯一 — 小欧-2026-11-07
/**
 * FileDrawer —— 「附件」唯一面板（一个动作：把文件放进本轮；一个仓库：合集）
 *
 * 左栏来源：
 * - 本会话：本会话已上传的附件（attachments 会话级）
 * - 项目文件：项目根文件树（/files/tree）
 * - 我的电脑：同机 import-local（只传路径，后端读盘，0 传输）；跨机退化为上传
 * - 合集：只存清单、不复制文件（material_packs）
 *
 * 交互：点整行 = 加入本轮（无复选框、无批量确认），关掉抽屉即完成。
 * 入队唯一实现：附件 enqueue / 文件 quoteFile / 同机 importLocal（内部 enqueue）。
 */
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Button,
  Drawer,
  Dropdown,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Spin,
  Typography,
  Upload,
} from 'antd';
import type { UploadProps } from 'antd';
import {
  FileOutlined,
  FolderOpenOutlined,
  MoreOutlined,
  UploadOutlined,
} from '@ant-design/icons';

import {
  attachmentApi,
  type AttachmentRecord,
} from '@/services/api/attachment.api';
import {
  materialPackApi,
  type MaterialPack,
} from '@/services/api/materialPack.api';
import { fileApi, type FileNode } from '@/services/api/file.api';
import {
  enqueue,
  uploadAttachments,
  MAX_BATCH,
} from '@/features/refs/uploadAttachment';
import { quoteFile } from '@/features/refs/quote';
import { getLocalCapability, importLocal } from '@/features/refs/localImport';
import { refLimitText, type ComposerRef } from '@/features/refs/store';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import { formatBytes } from '@/utils/format';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import { MaterialPackSaveForm } from './MaterialPackSaveForm';

type SourceKey = 'session' | 'project' | 'local' | 'pack';

const NAV: Array<{ key: SourceKey; label: string }> = [
  { key: 'session', label: '本会话' },
  { key: 'project', label: '项目文件' },
  { key: 'local', label: '我的电脑' },
];

/** 项目根文件树拍平为文件列表（目录只用于展开，不占行） */
function flattenFiles(nodes: FileNode[], out: FileNode[] = []): FileNode[] {
  for (const n of nodes) {
    if (n.type === 'file') out.push(n);
    else if (n.children) flattenFiles(n.children, out);
  }
  return out;
}

const metaStyle: React.CSSProperties = {
  fontSize: FontSize.CAPTION,
  color: Colors.TEXT.SECONDARY,
};

interface FileDrawerProps {
  open: boolean;
  onClose: () => void;
  /** 当前会话 ID；为空表示新会话（选中文件后才建会话） */
  sessionId?: string | null;
  /** D1 唯一实现：无会话时创建并回填，返回新 sessionId；失败返回 null */
  ensureSession?: () => Promise<string | null>;
  /** 本轮文件（「已加入」判定 + 底部计数） */
  refs: ComposerRef[];
  disabled?: boolean;
}

const FileDrawer: React.FC<FileDrawerProps> = ({
  open,
  onClose,
  sessionId,
  ensureSession,
  refs,
  disabled = false,
}) => {
  const [source, setSource] = useState<SourceKey>('session');
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionFiles, setSessionFiles] = useState<AttachmentRecord[]>([]);
  const [projectFiles, setProjectFiles] = useState<FileNode[]>([]);
  const [packs, setPacks] = useState<MaterialPack[]>([]);
  const [activePack, setActivePack] = useState<MaterialPack | null>(null);
  const [canLocal, setCanLocal] = useState(false);
  const [typedPath, setTypedPath] = useState('');
  const [importing, setImporting] = useState(false);
  const [feedBusy, setFeedBusy] = useState(false);
  const [renaming, setRenaming] = useState<MaterialPack | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // 上传批量收集（与 AttachmentArea 原实现同口径：antd beforeUpload 逐文件回调 + 末个触发）
  const [busy, setBusy] = useState(0);
  const busyRef = useRef(0);
  const pendingFiles = useRef<File[]>([]);

  const reloadSession = useCallback(async (): Promise<void> => {
    if (!sessionId) {
      setSessionFiles([]);
      return;
    }
    setLoading(true);
    try {
      setSessionFiles(await attachmentApi.list(sessionId));
    } catch {
      /* 全局错误处理器已提示 */
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const reloadProject = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      const res = await fileApi.fetchTree('', { maxDepth: 2 });
      setProjectFiles(flattenFiles(res.nodes).slice(0, 300));
    } catch {
      setProjectFiles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const reloadPacks = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      setPacks(await materialPackApi.list());
    } catch {
      /* 全局错误处理器已提示 */
    } finally {
      setLoading(false);
    }
  }, []);

  // 打开才拉：抽屉外不做任何预取
  useEffect(() => {
    if (!open) return;
    void getLocalCapability().then(setCanLocal);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (source === 'session') void reloadSession();
    else if (source === 'project') void reloadProject();
    else if (source === 'pack') void reloadPacks();
  }, [open, source, reloadSession, reloadProject, reloadPacks]);

  const totalSize = useMemo(
    () => refs.reduce((sum, r) => sum + (r.size ?? 0), 0),
    [refs]
  );

  /** 加入本轮：附件走 enqueue（唯一入队口） */
  const addAttachment = (rec: AttachmentRecord): void => {
    if (refs.some((r) => r.attachment_id === rec.id)) return;
    if (!enqueue(rec)) showMessage(ErrorType.WARNING, refLimitText());
  };

  /** 加入本轮：普通文件走 quoteFile（唯一引用入口） */
  const addFile = async (path: string, label: string): Promise<void> => {
    if (refs.some((r) => r.path === path && r.kind !== 'attachment')) return;
    const r = await quoteFile(path, { label });
    if (!r.ok) showMessage(ErrorType.WARNING, refLimitText());
  };

  const collectAndUpload = (): void => {
    const files = pendingFiles.current;
    pendingFiles.current = [];
    busyRef.current += files.length;
    setBusy(busyRef.current);
    void uploadAttachments(files, { sessionId, ensureSession }).then(() => {
      busyRef.current = Math.max(0, busyRef.current - files.length);
      setBusy(busyRef.current);
      if (sessionId) void reloadSession();
    });
  };

  const beforeUpload: NonNullable<UploadProps['beforeUpload']> = (
    file,
    batch
  ) => {
    // busyRef 即时生效：setBusy 到 re-render 有间隙，间隙内再次选择会混入 pendingFiles
    if (busyRef.current > 0) return Upload.LIST_IGNORE;
    if (batch.length > MAX_BATCH) {
      showMessage(ErrorType.WARNING, `一次最多选择 ${MAX_BATCH} 个文件`);
      return Upload.LIST_IGNORE;
    }
    pendingFiles.current.push(file);
    if (pendingFiles.current.length === batch.length) collectAndUpload();
    return false; // 阻止 antd 自动上传（统一交 uploadAttachments）
  };

  /** 同机导入：只传路径，落盘目标由后端计算（TR-3） */
  const importByPath = async (): Promise<void> => {
    const path = typedPath.trim();
    if (!path) return;
    const sid = sessionId || (await ensureSession?.());
    if (!sid) {
      showMessage(ErrorType.UNKNOWN, '会话创建失败，附件未导入');
      return;
    }
    setImporting(true);
    try {
      if (await importLocal(sid, path)) setTypedPath('');
    } finally {
      setImporting(false);
    }
  };

  /** 整组加入本轮：按条目身份分流（附件按 id 恢复附件语义） */
  const feedPack = async (pack: MaterialPack): Promise<void> => {
    setFeedBusy(true);
    let failed = 0;
    try {
      for (const it of pack.items) {
        if (it.kind === 'attachment' && it.attachment_id) {
          try {
            const rec = await attachmentApi.get(
              it.attachment_id,
              sessionId ?? ''
            );
            if (!enqueue(rec)) failed += 1;
          } catch {
            failed += 1; // 跨会话附件尚未 promote，按失效计
          }
          continue;
        }
        const r = await quoteFile(it.path, { label: it.label });
        if (!r.ok) failed += 1;
      }
      if (failed === 0) {
        showSuccess(
          `已将「${pack.name}」的 ${pack.items.length} 个文件加入本轮`
        );
      } else {
        showMessage(
          ErrorType.WARNING,
          `「${pack.name}」有 ${failed} 个文件已失效，其余已加入本轮`
        );
      }
    } finally {
      setFeedBusy(false);
    }
  };

  const removePack = async (pack: MaterialPack): Promise<void> => {
    try {
      await materialPackApi.remove(pack.id);
      showSuccess(`已删除合集「${pack.name}」（磁盘文件不受影响）`);
      if (activePack?.id === pack.id) setActivePack(null);
      await reloadPacks();
    } catch {
      /* 全局错误处理器已提示 */
    }
  };

  const doRename = async (): Promise<void> => {
    if (!renaming) return;
    const name = renameValue.trim();
    if (!name) {
      showMessage(ErrorType.WARNING, '名称不能为空');
      return;
    }
    try {
      const updated = await materialPackApi.update(renaming.id, { name });
      showSuccess('已重命名合集');
      setRenaming(null);
      if (activePack?.id === updated.id) setActivePack(updated);
      await reloadPacks();
    } catch {
      /* 409 同名由全局处理器提示 */
    }
  };

  const kw = keyword.trim().toLowerCase();
  const match = (name: string): boolean =>
    !kw || name.toLowerCase().includes(kw);

  const sessionShown = sessionFiles.filter((f) => match(f.original_name));
  const projectShown = projectFiles.filter((f) => match(f.name));
  const packShown = (activePack?.items ?? []).filter((it) =>
    match(it.label || it.path)
  );

  const rowStyle = (added: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: Spacing.XS,
    padding: '6px 8px',
    borderRadius: 6,
    cursor: 'pointer',
    background: added ? '#e6f4ff' : 'transparent',
    borderLeft: added ? `2px solid ${Colors.PRIMARY}` : '2px solid transparent',
  });

  const navItemStyle = (active: boolean): React.CSSProperties => ({
    padding: '6px 10px',
    borderRadius: 6,
    cursor: 'pointer',
    background: active ? '#e6f4ff' : 'transparent',
    borderLeft: active
      ? `2px solid ${Colors.PRIMARY}`
      : '2px solid transparent',
    color: active ? Colors.PRIMARY : Colors.TEXT.PRIMARY,
    fontSize: FontSize.PRIMARY,
  });

  const renderRows = (): React.ReactNode => {
    if (source === 'local') {
      return (
        <div style={{ padding: Spacing.XS }}>
          <Typography.Text style={metaStyle}>
            {canLocal
              ? '同机模式：后端直接读取本机文件，不传输、不占额外空间'
              : '当前为远程访问，无法直接读取本机文件，请用上方「上传文件」'}
          </Typography.Text>
          <div style={{ display: 'flex', gap: 8, marginTop: Spacing.SM }}>
            <Input
              placeholder="输入绝对路径，如 D:\资料\报告.xlsx"
              value={typedPath}
              disabled={!canLocal}
              onChange={(e) => setTypedPath(e.target.value)}
              onPressEnter={() => void importByPath()}
            />
            <Button
              type="primary"
              disabled={!canLocal || !typedPath.trim()}
              loading={importing}
              onClick={() => void importByPath()}
            >
              导入
            </Button>
          </div>
        </div>
      );
    }

    if (loading) return <Spin style={{ marginTop: Spacing.MD }} />;

    if (source === 'session') {
      if (sessionShown.length === 0) {
        return (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              sessionId
                ? '本会话还没有附件'
                : '还没有会话，先上传或加入一个文件'
            }
          />
        );
      }
      return sessionShown.map((rec) => {
        const added = refs.some((r) => r.attachment_id === rec.id);
        return (
          <div
            key={rec.id}
            style={rowStyle(added)}
            onClick={() => addAttachment(rec)}
          >
            <FileOutlined style={{ color: Colors.TEXT.SECONDARY }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: FontSize.PRIMARY,
                  color: Colors.TEXT.STRONG,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {rec.original_name}
              </div>
              <div style={metaStyle}>
                {formatBytes(rec.size)} ·{' '}
                {rec.created_at.slice(0, 16).replace('T', ' ')}
                {added ? ' · 已加入' : ''}
              </div>
            </div>
            <Popconfirm
              title={`删除「${rec.original_name}」？`}
              description="只删记录，磁盘文件不受影响"
              onConfirm={() => {
                void attachmentApi
                  .remove(rec.id, sessionId ?? '')
                  .then(() => reloadSession());
              }}
            >
              <Button
                type="text"
                size="small"
                icon={<MoreOutlined />}
                onClick={(e) => e.stopPropagation()}
              />
            </Popconfirm>
          </div>
        );
      });
    }

    if (source === 'project') {
      if (projectShown.length === 0) {
        return (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="项目根没有可加入的文件"
          />
        );
      }
      return projectShown.map((node) => {
        const added = refs.some(
          (r) => r.path === node.key && r.kind !== 'attachment'
        );
        return (
          <div
            key={node.key}
            style={rowStyle(added)}
            onClick={() => void addFile(node.key, node.name)}
          >
            <FileOutlined style={{ color: Colors.TEXT.SECONDARY }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: FontSize.PRIMARY,
                  color: Colors.TEXT.STRONG,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {node.name}
              </div>
              <div style={metaStyle}>
                {node.key} · {formatBytes(node.size ?? 0)}
                {added ? ' · 已加入' : ''}
              </div>
            </div>
          </div>
        );
      });
    }

    // 合集：展开某组
    if (!activePack) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="左栏选择一个合集"
        />
      );
    }
    if (packShown.length === 0) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="该合集没有文件"
        />
      );
    }
    return packShown.map((it) => {
      const added =
        it.kind === 'attachment'
          ? refs.some((r) => r.attachment_id === it.attachment_id)
          : refs.some((r) => r.path === it.path && r.kind !== 'attachment');
      return (
        <div
          key={`${it.seq}-${it.path}`}
          style={rowStyle(added)}
          onClick={() => {
            if (it.kind === 'attachment' && it.attachment_id) {
              void attachmentApi
                .get(it.attachment_id, sessionId ?? '')
                .then((rec) => {
                  if (!enqueue(rec)) {
                    showMessage(ErrorType.WARNING, refLimitText());
                  }
                })
                .catch(() => {
                  showMessage(
                    ErrorType.WARNING,
                    `「${it.label}」已失效（跨会话附件暂不支持）`
                  );
                });
              return;
            }
            void addFile(it.path, it.label || it.path);
          }}
        >
          <FileOutlined style={{ color: Colors.TEXT.SECONDARY }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: FontSize.PRIMARY,
                color: Colors.TEXT.STRONG,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {it.label || it.path}
            </div>
            <div style={metaStyle}>
              {it.path}
              {added ? ' · 已加入' : ''}
            </div>
          </div>
        </div>
      );
    });
  };

  const paneTitle = (): string => {
    if (source === 'pack') return activePack ? activePack.name : '合集';
    return NAV.find((n) => n.key === source)?.label ?? '';
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={720}
      title="附件"
      footer={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={metaStyle}>
            已加入 {refs.length} 项 · 共 {formatBytes(totalSize)}
          </span>
          <div style={{ marginLeft: 'auto' }}>
            <Button type="primary" onClick={onClose}>
              完成
            </Button>
          </div>
        </div>
      }
    >
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: Spacing.SM }}
      >
        <div style={{ display: 'flex', gap: 8 }}>
          <Input
            allowClear
            placeholder="搜索文件名…"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <Upload
            multiple
            showUploadList={false}
            disabled={disabled || busy > 0}
            beforeUpload={beforeUpload}
          >
            <Button icon={<UploadOutlined />} loading={busy > 0}>
              上传文件
            </Button>
          </Upload>
        </div>

        <div style={{ display: 'flex', gap: Spacing.SM }}>
          {/* 左栏：来源 + 合集仓库 */}
          <div
            style={{
              width: 172,
              flexShrink: 0,
              borderRight: `1px solid ${Colors.BORDER.LIGHT}`,
              paddingRight: Spacing.XS,
            }}
          >
            {NAV.map((n) => (
              <div
                key={n.key}
                style={navItemStyle(source === n.key)}
                onClick={() => {
                  setSource(n.key);
                  setActivePack(null);
                }}
              >
                {n.label}
              </div>
            ))}
            <div
              style={{
                margin: `${Spacing.SM}px 0 ${Spacing.XS}px`,
                fontSize: FontSize.CAPTION,
                color: Colors.TEXT.SECONDARY,
              }}
            >
              合集
            </div>
            <div style={{ maxHeight: 260, overflowY: 'auto' }}>
              {packs.length === 0 ? (
                <div style={{ ...metaStyle, padding: '2px 10px' }}>
                  暂无合集
                </div>
              ) : (
                packs.map((p) => (
                  <div
                    key={p.id}
                    style={{
                      ...navItemStyle(
                        source === 'pack' && activePack?.id === p.id
                      ),
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                    onClick={() => {
                      setSource('pack');
                      setActivePack(p);
                    }}
                  >
                    <FolderOpenOutlined />
                    <span
                      style={{
                        flex: 1,
                        minWidth: 0,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {p.name}
                    </span>
                    <span style={metaStyle}>{p.items.length}</span>
                    <Dropdown
                      trigger={['click']}
                      menu={{
                        items: [
                          { key: 'rename', label: '重命名' },
                          { key: 'remove', label: '删除合集' },
                        ],
                        onClick: ({ key, domEvent }) => {
                          domEvent.stopPropagation();
                          if (key === 'rename') {
                            setRenaming(p);
                            setRenameValue(p.name);
                          } else {
                            void removePack(p);
                          }
                        },
                      }}
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<MoreOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Dropdown>
                  </div>
                ))
              )}
            </div>
            <div style={{ marginTop: Spacing.XS }}>
              <MaterialPackSaveForm refs={refs} onSaved={reloadPacks} />
            </div>
          </div>

          {/* 右栏：来源内容 */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: Spacing.XS,
                marginBottom: Spacing.XS,
              }}
            >
              {source === 'pack' && activePack && (
                <Button
                  size="small"
                  type="text"
                  onClick={() => setActivePack(null)}
                >
                  ← 返回
                </Button>
              )}
              <Typography.Text strong>{paneTitle()}</Typography.Text>
              {source === 'pack' && activePack && (
                <Button
                  size="small"
                  style={{ marginLeft: 'auto' }}
                  loading={feedBusy}
                  disabled={activePack.items.length === 0}
                  onClick={() => void feedPack(activePack)}
                >
                  全部加入本轮
                </Button>
              )}
            </div>
            <div style={{ maxHeight: 460, overflowY: 'auto' }}>
              {renderRows()}
            </div>
          </div>
        </div>
      </div>

      <Modal
        open={!!renaming}
        title="重命名合集"
        okText="保存"
        cancelText="取消"
        onOk={() => void doRename()}
        onCancel={() => setRenaming(null)}
      >
        <Input
          value={renameValue}
          autoFocus
          onChange={(e) => setRenameValue(e.target.value)}
          onPressEnter={() => void doRename()}
        />
      </Modal>
    </Drawer>
  );
};

export { FileDrawer };
