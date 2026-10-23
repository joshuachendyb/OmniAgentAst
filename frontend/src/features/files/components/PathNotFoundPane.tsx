// 编辑历史: 2026-10-23 小欧 - 新建：文件页深链未命中右侧预览区提示卡 — 小欧-2026-10-23
// 2026-10-23 小欧 - 三堂会审：补文件头；路径块 padding 硬码 10px 换 Spacing.LG 令牌；
//   复制路径按钮保留（用户令），setTimeout 改 useEffect 清理防悬挂 — 小欧-2026-10-23
/**
 * PathNotFoundPane —— 文件页「跳转路径未命中」右侧预览区提示卡
 *
 * 触发：深链（?path=）未命中（根外非法 / 根内归一失败 / 树中不存在）时，
 *   右侧预览区整块被本卡替换（此时预览区本空，正好补位）。
 * 布局：标题 + 路径块 + 说明 + 底部操作（复制路径 / 知道了）；
 *   路径在目录分隔符后可换行，文件名不硬切。
 * 退出：点「知道了」或重新选中文件即清 linkErr，回到正常预览。
 */
import React, { Fragment, useEffect, useMemo, useState } from 'react';
import { Button } from 'antd';
import {
  CheckOutlined,
  CopyOutlined,
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

interface PathNotFoundPaneProps {
  path: string;
  onDismiss: () => void;
}

/** 长路径在目录分隔符后允许换行，避免把文件名劈成两行 — 小欧-2026-10-23 */
const pathBreakNodes = (path: string) =>
  path.split(/([\\/])/).map((seg, i) => (
    <Fragment key={i}>
      {seg}
      {/[\\/]/.test(seg) ? <wbr /> : null}
    </Fragment>
  ));

export const PathNotFoundPane: React.FC<PathNotFoundPaneProps> = ({
  path,
  onDismiss,
}) => {
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
          borderLeft: `3px solid ${Colors.WARNING}`,
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
          <WarningOutlined style={{ color: Colors.WARNING }} />
          未找到该路径
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
          请检查路径是否正确，或从左侧文件树中选择。
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: Spacing.SM,
            marginTop: Spacing.XS,
          }}
        >
          <Button
            size="small"
            icon={copied ? <CheckOutlined /> : <CopyOutlined />}
            onClick={() => void handleCopy()}
          >
            {copied ? '已复制' : '复制路径'}
          </Button>
          <Button size="small" type="primary" onClick={onDismiss}>
            知道了
          </Button>
        </div>
      </div>
    </div>
  );
};
