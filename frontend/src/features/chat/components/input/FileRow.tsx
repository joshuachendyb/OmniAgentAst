// 编辑历史: 2026-11-02 小欧 - 尺寸令牌: Spacing.XXL=20/Radius.CONTAINER=12/Size.HEADER_HEIGHT=43(Layout壳/NavContent/LayoutSkeleton跨文件同值收口, 零视觉差) — 小欧-2026-11-02
// 编辑历史: 2026-11-07 小欧 - Colors.BG 新增 SELECTED=#e6f4ff(antd blue-1): 文件抽屉列表行「已加入」底与左栏导航选中底共用(收口两处硬编码) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 附件列表行统一组件(勾位/类型图标/文件名/次行/☆ 收藏/⋯ 更多),
//   供「最近用过/本会话/已收藏/任务产物/合集」复用; 键盘焦点态由 active 传入; 点文件名回调预览 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 色值令牌化 —— 选中底改 Colors.BG.SELECTED, 收藏星改 Colors.WARNING(与全站警告色同源),
//   消两处硬编码 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 注释清理: 去除文档号/修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
// 编辑历史: 2026-11-11 小欧 - iconOf(kind,mime) 按类型图标 + 行内 CapabilityBadge(state/contentKind) — 小欧-2026-11-11
/**
 * FileRow —— 文件抽屉的列表行（唯一实现）
 *
 * 布局：
 *   [✓/○] [类型图标] 文件名                  [☆] [⋯]
 *                    类型 · 大小 · 来源 · 相对时间
 *
 * 交互约定：整行 = 加入/移出本轮；文件名 = 预览；☆ = 收藏；⋯ = 低频操作。
 * 行内不设复选框 —— 整行就是开关，少一次"先勾选再点按钮"的往返。
 */
import React from 'react';
import { Button, Dropdown, Tooltip } from 'antd';
import type { MenuProps } from 'antd';
import {
  CheckOutlined,
  CustomerServiceOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  MoreOutlined,
  StarFilled,
  StarOutlined,
  VideoCameraOutlined,
  WarningOutlined,
} from '@ant-design/icons';

import { Colors, FontSize } from '@/utils/stepStyles';
import { CapabilityBadge, type CapabilityState } from './CapabilityBadge';

/** 按 kind 取类型图标（record.kind 权威，mime 仅兜底；线性图标，无 emoji） */
function iconOf(kind: string | undefined, mime: string): React.ReactNode {
  const k = kind || (mime.startsWith('image/') ? 'image' : mime === 'application/pdf' ? 'richdoc' : '');
  if (k === 'image') return <FileImageOutlined />;
  if (k === 'video') return <VideoCameraOutlined />;
  if (k === 'audio') return <CustomerServiceOutlined />;
  if (k === 'richdoc' || k === 'text') return <FileTextOutlined />;
  if (mime === 'application/pdf') return <FilePdfOutlined />;
  return <FileOutlined />;
}

export interface FileRowProps {
  name: string;
  /** 次行说明：类型 · 大小 · 来源 · 相对时间 */
  meta: string;
  mime?: string;
  /** 附件权威类型(七类), mime 仅兜底 — 小欧-2026-11-11 */
  kind?: string;
  /** 当前模型对该内容类型的能力状态(ref_capability_map 只读索引) — 小欧-2026-11-11 */
  capState?: CapabilityState;
  /** 已加入本轮 */
  added?: boolean;
  /** 已收藏（同 sha 存在全局行） */
  favorited?: boolean;
  /** 失效：磁盘文件已不存在 */
  invalid?: boolean;
  /** 键盘高亮行 */
  active?: boolean;
  /** 收藏按钮是否可点（失效/无会话时置灰） */
  starDisabled?: boolean;
  onToggle: () => void;
  onPreview?: () => void;
  onStar?: () => void;
  moreItems?: MenuProps['items'];
  onMoreClick?: (key: string) => void;
  rowRef?: (el: HTMLDivElement | null) => void;
}

const metaStyle: React.CSSProperties = {
  fontSize: FontSize.SECONDARY,
  color: Colors.TEXT.SECONDARY,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const FileRow: React.FC<FileRowProps> = ({
  name,
  meta,
  mime = '',
  kind,
  capState,
  added = false,
  favorited = false,
  invalid = false,
  active = false,
  starDisabled = false,
  onToggle,
  onPreview,
  onStar,
  moreItems,
  onMoreClick,
  rowRef,
}) => (
  <div
    ref={rowRef}
    role="button"
    tabIndex={-1}
    onClick={onToggle}
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 8px',
      borderRadius: 6,
      cursor: 'pointer',
      opacity: invalid ? 0.6 : 1,
      background: added
        ? Colors.BG.SELECTED
        : active
          ? Colors.BG.HOVER
          : 'transparent',
      borderLeft: added
        ? `2px solid ${Colors.PRIMARY}`
        : '2px solid transparent',
      outline: active ? `1px solid ${Colors.PRIMARY}` : 'none',
    }}
  >
    <span
      style={{
        width: 16,
        flexShrink: 0,
        textAlign: 'center',
        color: added ? Colors.PRIMARY : Colors.TEXT.SECONDARY,
        fontSize: FontSize.SECONDARY,
      }}
    >
      {added ? <CheckOutlined /> : '○'}
    </span>
    <span style={{ color: Colors.TEXT.SECONDARY, flexShrink: 0 }}>
      {invalid ? (
        <WarningOutlined style={{ color: Colors.ERROR_TEXT }} />
      ) : (
        iconOf(kind, mime)
      )}
    </span>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div
        onClick={(e) => {
          if (!onPreview) return;
          e.stopPropagation();
          onPreview();
        }}
        title={onPreview ? '预览' : undefined}
        style={{
          fontSize: FontSize.PRIMARY,
          color: Colors.TEXT.STRONG,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          cursor: onPreview ? 'pointer' : 'inherit',
        }}
      >
        {name}
      </div>
      <div style={metaStyle}>
        {invalid ? (
          <span style={{ color: Colors.ERROR_TEXT }}>源文件已不存在</span>
        ) : (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            {meta}
            {added ? ' · 已加入' : ''}
            {capState && <CapabilityBadge state={capState} contentKind={kind} />}
          </span>
        )}
      </div>
    </div>
    <Tooltip title={favorited ? '取消收藏' : '收藏（1 击，跨会话可用）'}>
      <Button
        type="text"
        size="small"
        disabled={starDisabled || invalid}
        aria-label={favorited ? '取消收藏' : '收藏'}
        icon={
          favorited ? (
            <StarFilled style={{ color: Colors.WARNING }} />
          ) : (
            <StarOutlined style={{ color: Colors.TEXT.SECONDARY }} />
          )
        }
        onClick={(e) => {
          e.stopPropagation();
          onStar?.();
        }}
      />
    </Tooltip>
    {moreItems && moreItems.length > 0 && (
      <Dropdown
        trigger={['click']}
        menu={{
          items: moreItems,
          onClick: ({ key, domEvent }) => {
            domEvent.stopPropagation();
            onMoreClick?.(key);
          },
        }}
      >
        <Button
          type="text"
          size="small"
          aria-label="更多操作"
          icon={<MoreOutlined />}
          onClick={(e) => e.stopPropagation()}
        />
      </Dropdown>
    )}
  </div>
);

export { FileRow };
