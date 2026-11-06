// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 附件多模态预留区, 上传随E1携带(暂缓)(4.6.2)
// 编辑历史: 2026-08-28 小欧 - ①D/d2: 暂缓期隐藏不占位, 启用加 Tooltip 说明
// 编辑历史: 2026-10-06 小欧 - 北京老陈指令: 暂缓期不再隐藏, 改为显示+置灰(disabled)。
// 编辑历史: 2026-11-06 小欧 - 重写为纯文件选择器(建会话/上传/入队/提示全部下沉 uploadAttachments 唯一
//   实现, 本组件只交文件); 加同机「从本机导入」入口(据后端 local-capability 结果显隐, 不做安全判定) — 小欧-2026-11-06
// 编辑历史: 2026-11-06 小欧 - 三堂会审: ①busy 计算修正(原 n-files.length+r.ok 部分失败残留→按钮永久 loading);
//   ②抽 collectAndUpload(beforeUpload 只留 antd 拦截, SLAP); ③batch.length 判超限(等价 indexOf, 更直接) — 小欧-2026-11-06
/**
 * AttachmentArea - 附件按钮（按钮行左侧「📎 附件」）
 *
 * 职责只有三件：渲染按钮、限制单批数量、把选中的文件交给 uploadAttachments。
 * 不建会话、不上传、不渲染 chip、不产生注入正文 —— 这些各有唯一归属（D1 / 附件域 / 引用区 / 后端 resolver）。
 * 同机时追加「从本机导入」入口：调 GET /attachments/local-capability 探测，仅同机显示。
 */
import React, { useMemo, useRef, useState } from 'react';
import { Button, Tooltip, Upload } from 'antd';
import type { UploadProps } from 'antd';
import { PaperClipOutlined } from '@ant-design/icons';

import { MAX_BATCH, MAX_IMAGE_MB, MAX_FILE_MB, uploadAttachments } from '@/features/refs/uploadAttachment';
import { getLocalCapability } from '@/features/refs/localImport';
import { showMessage, ErrorType } from '@/services/error/handler';
// 2026-11-06 小欧 三堂会审(SRP): 同机导入选择器独立成组件, 本组件只留探测显隐 — 小欧-2026-11-06
import { LocalImportButton } from './LocalImportButton';

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

  const tip = useMemo(() => {
    if (disabled) return '附件上传暂未启用';
    if (busy > 0) return `正在上传（${busy} 个）…`;
    return `支持图片、文本、PDF、Word、Excel、PowerPoint、视频（单批 ≤${MAX_BATCH}，图片 ≤${MAX_IMAGE_MB}MB，其他 ≤${MAX_FILE_MB}MB）`;
  }, [disabled, busy]);

  /** 批量索引是"本次选择的完整列表", 用它判第 10 个之后直接忽略(不维护批次计数器)。
   *  大小与类型判定统一在 uploadAttachments/后端, 此处不重复一份。
   *  beforeUpload 返回 false 阻止 antd 自动上传(防 multiple 并发 customRequest),
   *    收集所有文件后统一交给 uploadAttachments(串行, D1 建会话只调一次)。 */
  const pendingFiles = useRef<File[]>([]);
  /** 收集满一批后统一交给 uploadAttachments（串行, D1 建会话只调一次）。
   *  2026-11-06 小欧 三堂会审(SLAP): 从 beforeUpload 抽出 —— beforeUpload 只留 antd 拦截语义,
   *  本函数专职业务编排(收集→触发上传→busy 管理), 不再混搭抽象层。 */
  const collectAndUpload = (batch: File[]): void => {
    const files = pendingFiles.current;
    pendingFiles.current = [];
    setBusy((n) => n + files.length); // 上传期间按钮 loading/禁用
    void uploadAttachments(files, { sessionId, ensureSession }).then(() => {
      // 2026-11-06 小欧 三堂会审(KISS/bug): 上传完成无论成败都减 files.length;
      //   原 n - files.length + r.ok 在部分失败/全成功时残留 busy(只减成功数), 按钮永久 loading — 小欧-2026-11-06
      setBusy((n) => Math.max(0, n - files.length));
    });
  };

  const beforeUpload: NonNullable<UploadProps['beforeUpload']> = (
    file,
    batch
  ) => {
    // 2026-11-06 小欧 三堂会审(DRY/简化): batch.length 判超限(等价 indexOf, 更直接);
    //   数量上限唯一真源是 uploadAttachment.rejectReason, 此处仅 antd UI 层拦截 — 小欧-2026-11-06
    if (batch.length > MAX_BATCH) {
      showMessage(ErrorType.WARNING, `一次最多选择 ${MAX_BATCH} 个文件`);
      return Upload.LIST_IGNORE;
    }
    pendingFiles.current.push(file);
    // 最后一个文件触发上传: antd batch 是本次选择的完整列表
    if (pendingFiles.current.length === batch.length) {
      collectAndUpload(batch);
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
      {/* 2026-11-06 小欧 三堂会审(SRP): 同机导入选择器独立成组件, 本组件只留探测显隐 */}
      {canLocalImport && (
        <LocalImportButton
          sessionId={sessionId}
          ensureSession={ensureSession}
          disabled={blocked}
        />
      )}
    </Tooltip>
  );
};

export { AttachmentArea };
