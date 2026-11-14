// 编辑历史: 2026-08-26 小欧: 附件多模态预留区实施, 上传随消息携带(暂缓)
// 编辑历史: 2026-08-28 小欧: 暂缓期隐藏不占位, 启用加 Tooltip 说明
// 编辑历史: 2026-10-06 小欧 - 北京老陈指令: 暂缓期不再隐藏, 改为显示+置灰(disabled)。
// 编辑历史: 2026-11-06 小欧 - 重写为纯文件选择器(建会话/上传/入队/提示全部下沉 uploadAttachments 唯一
//   实现, 本组件只交文件); 加同机「从本机导入」入口(据后端 local-capability 结果显隐, 不做安全判定) — 小欧-2026-11-06
// 编辑历史: 2026-11-06 小欧: busy 计算修正(部分失败残留→按钮永久 loading); 抽 collectAndUpload(SLAP);
//   batch.length 判超限(等价 indexOf, 更直接) — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧: 删 collectAndUpload 死参数 batch(数据源是 pendingFiles, 死参数误导阅读);
//   busyRef 守卫 beforeUpload(setBusy 到 re-render 有间隙, ref 即时生效防混入) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 入口合门 —— 只留唯一「附件」按钮打开文件抽屉(FileDrawer);
//   上传收集/同机导入/合集全部迁入抽屉, 本组件不再持有 Upload 与 pendingFiles(职责只剩按钮+抽屉宿主) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 - Tooltip 入口清单同步抽屉标签定名(后端电脑/任务产物) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 注释清理: 去除文档号/修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
// 编辑历史: 2026-11-10 小欧 - 抽屉标题加帮助图标(Tooltip 展示附件规则), 按钮 Tooltip 补规则行, 消抽屉内常驻文字的视觉噪音 — 小欧-2026-11-10
// 编辑历史: 2026-11-14 小欧 - 附件规则文案改由 attachmentRules(后端 limits) 派生: 上限不写死、补「音频」 — 小欧-2026-11-14
/**
 * AttachmentArea - 附件唯一入口（按钮行左侧「附件」）
 *
 * 职责两件：渲染按钮、打开文件抽屉。
 * 上传、同机导入、项目文件、合集都在 FileDrawer 内 —— 本组件不建会话、不上传、不入队。
 */
import React, { useEffect, useState } from 'react';
import { Button, Tooltip } from 'antd';
import { PaperClipOutlined } from '@ant-design/icons';

import { attachmentRules } from '@/features/refs/uploadAttachment';
import { loadCapabilities } from '@/services/api/attachment.api';
import { setAttachmentByteLimits, type ComposerRef } from '@/features/refs/store';
import { FileDrawer } from './FileDrawer';

interface AttachmentAreaProps {
  visible?: boolean;
  disabled?: boolean;
  /** 当前会话 ID；为空表示新会话（D1：选中文件后才建会话） */
  sessionId?: string | null;
  /** D1 唯一实现：无会话时创建并回填，返回新 sessionId；失败返回 null */
  ensureSession?: () => Promise<string | null>;
  /** 本轮文件（抽屉内「已加入」判定 + 底部计数） */
  refs: ComposerRef[];
  /** 按 chip id 移出本轮（抽屉内点已加入行 = 取消加入） */
  onRemoveRef?: (refId: string) => void;
}

const AttachmentArea: React.FC<AttachmentAreaProps> = ({
  visible = false,
  disabled = false,
  sessionId,
  ensureSession,
  refs,
  onRemoveRef,
}) => {
  const [open, setOpen] = useState(false);
  /** 上限加载后自增一次, 触发规则文案重渲(上限数值存 store 单真源) */
  const [, bumpLimits] = useState(0);

  useEffect(() => {
    if (!visible) return;
    let alive = true;
    void loadCapabilities()
      .then((c) => {
        if (!alive) return;
        setAttachmentByteLimits(c.limits.max_image_bytes, c.limits.max_file_bytes);
        bumpLimits((n) => n + 1);
      })
      .catch(() => void 0);
    return () => {
      alive = false;
    };
  }, [visible]);

  if (!visible) return null;
  return (
    <>
      <Tooltip
        title={
          <div style={{ maxWidth: 280 }}>
            <div>添加文件到本轮（本会话附件 / 本会话产物 / 他会话附件 / 项目文件 / 后端电脑 / 收藏）</div>
            <div style={{ marginTop: 4, opacity: 0.85 }}>{attachmentRules()}</div>
          </div>
        }
      >
        <Button
          size="small"
          icon={<PaperClipOutlined />}
          disabled={disabled}
          onClick={() => setOpen(true)}
        >
          附件
        </Button>
      </Tooltip>
      <FileDrawer
        open={open}
        onClose={() => setOpen(false)}
        sessionId={sessionId}
        ensureSession={ensureSession}
        refs={refs}
        onRemoveRef={onRemoveRef}
        disabled={disabled}
      />
    </>
  );
};

export { AttachmentArea };
