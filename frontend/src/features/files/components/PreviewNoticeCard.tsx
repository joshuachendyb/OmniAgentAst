// 编辑历史: 2026-10-23 小欧 - 新建：文件页深链未命中右侧预览区提示卡 — 小欧-2026-10-23
// 2026-10-23 小欧 - 三堂会审：补文件头；路径块 padding 硬码 10px 换 Spacing.LG 令牌；
//   复制路径按钮保留（用户令），setTimeout 改 useEffect 清理防悬挂 — 小欧-2026-10-23
// 2026-10-23 小欧 - 改名为 PreviewNoticeCard（通用预览区整块提示卡，三堂会审消重）：
//   统一「未找到 / 加载失败 / 暂不支持预览」三类，仅 kind 驱动标题/图标/色/说明/按钮组。
//   文件改名 + 语义泛化，原 PathNotFoundPane 删除，避免同抽象两套实现（DRY）。— 小欧-2026-10-23
/**
 * PreviewNoticeCard —— 文件页右侧预览区「整块提示」统一卡片
 *
 * 触发：深链未命中 / 读取失败 / 不可预览（binary/none）—— 预览区整块被替换。
 * 布局：标题 + 路径块 + 说明 + 底部操作；路径在目录分隔符后可换行，文件名不硬切。
 * 操作：按 kind 提供（未找到=知道了 / 失败=重试+复制 / 不支持=复制路径）。
 * 退出：点关闭按钮或重新选中文件即回到正常预览。
 */
import React, { Fragment, useEffect, useMemo, useState } from 'react';
import { Button } from 'antd';
import {
  CheckOutlined,
  CopyOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { copyTextToClipboard } from '@/utils/clipboard';
import {
  Colors,
  FontFamily,
  FontWeight,
  Radius,
  Spacing,
} from '@/utils/stepStyles';
import { chatTokens } from '@/theme/tokens';
import { ErrorType, showMessage } from '@/services/error/handler';

export type PreviewNoticeKind = 'notfound' | 'failed' | 'unsupported';

interface PreviewNoticeCardProps {
  kind: PreviewNoticeKind;
  path: string;
  /** 说明文案（加载失败时为后端错误原文；其他为固定文案） */
  description?: string;
  /** 关闭按钮（未找到场景） */
  onDismiss?: () => void;
  /** 重试/刷新按钮（加载失败场景） */
  onRetry?: () => void;
}

const kindMeta: Record<
  PreviewNoticeKind,
  {
    title: string;
    icon: React.ComponentType<{ style?: React.CSSProperties }>;
    color: string;
    hint: string;
    actions: ReadonlyArray<'dismiss' | 'retry' | 'copy'>;
  }
> = {
  notfound: {
    title: '未找到该路径',
    icon: WarningOutlined,
    color: Colors.WARNING,
    hint: '请检查路径是否正确，或从左侧文件树中选择。',
    actions: ['dismiss'],
  },
  failed: {
    title: '加载失败',
    icon: ExclamationCircleOutlined,
    color: Colors.ERROR,
    hint: '请检查文件是否仍可读，或稍后重试。',
    actions: ['retry', 'copy'],
  },
  unsupported: {
    title: '暂不支持预览',
    icon: ExclamationCircleOutlined,
    color: Colors.WARNING,
    hint: '该文件不是可预览的文本或图片（可能是二进制或无法读取）。你可以复制路径，或引用到对话中再处理。',
    actions: ['copy'],
  },
};

/** 长路径在目录分隔符后允许换行，避免把文件名劈成两行 — 小欧-2026-10-23 */
const pathBreakNodes = (path: string) =>
  path.split(/([\\/])/).map((seg, i) => (
    <Fragment key={i}>
      {seg}
      {/[\\/]/.test(seg) ? <wbr /> : null}
    </Fragment>
  ));

export const PreviewNoticeCard: React.FC<PreviewNoticeCardProps> = ({
  kind,
  path,
  description,
  onDismiss,
  onRetry,
}) => {
  const meta = kindMeta[kind];
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const { ok } = await copyTextToClipboard(path);
    if (!ok) {
      showMessage(ErrorType.WARNING, '复制路径失败');
      return;
    }
    setCopied(true);
  };

  // 复制成功 1.2s 后复位按钮文案；组件卸载时清理，避免对已卸载组件 setState — 小欧-2026-10-23
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1200);
    return () => clearTimeout(t);
  }, [copied]);

  const nodes = useMemo(() => pathBreakNodes(path), [path]);
  const Icon = meta.icon;

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        padding: Spacing.XL,
        overflow: 'auto',
        boxSizing: 'border-box',
      }}
    >
      <div
        role="alert"
        style={{
          width: '100%',
          maxWidth: 560,
          display: 'flex',
          flexDirection: 'column',
          gap: Spacing.MD,
          padding: Spacing.XL,
          background: Colors.BG.PRIMARY,
          border: `1px solid ${Colors.BORDER.LIGHT}`,
          borderLeft: `3px solid ${meta.color}`,
          borderRadius: Radius.LG,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: Spacing.SM,
            color: Colors.TEXT.STRONG,
            fontSize: chatTokens.fontMD,
            fontWeight: FontWeight.BOLD,
          }}
        >
          <Icon style={{ color: meta.color }} />
          {meta.title}
        </div>

        <div
          style={{
            background: Colors.BG.SECONDARY,
            border: `1px solid ${Colors.BORDER.LIGHT}`,
            borderRadius: Radius.SM,
            padding: `${Spacing.MD}px ${Spacing.LG}px`,
            fontFamily: FontFamily.MONO,
            fontSize: chatTokens.fontSM,
            lineHeight: 1.6,
            color: Colors.TEXT.PRIMARY,
            wordBreak: 'normal',
            overflowWrap: 'anywhere',
          }}
        >
          {nodes}
        </div>

        <div
          style={{
            color: Colors.TEXT.SECONDARY,
            fontSize: chatTokens.fontSM,
            lineHeight: 1.5,
          }}
        >
          {description || meta.hint}
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: Spacing.SM,
            marginTop: Spacing.XS,
          }}
        >
          {meta.actions.includes('copy') && (
            <Button
              size="small"
              icon={copied ? <CheckOutlined /> : <CopyOutlined />}
              onClick={() => void handleCopy()}
            >
              {copied ? '已复制' : '复制路径'}
            </Button>
          )}
          {meta.actions.includes('retry') && onRetry && (
            <Button size="small" onClick={onRetry}>
              {kind === 'failed' ? '重试' : '刷新'}
            </Button>
          )}
          {meta.actions.includes('dismiss') && onDismiss && (
            <Button size="small" type="primary" onClick={onDismiss}>
              知道了
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
