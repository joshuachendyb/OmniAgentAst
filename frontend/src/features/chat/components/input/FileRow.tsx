// 编辑历史: 2026-11-07 小欧 - [13] P3/P4 新建: 附件列表行统一组件(勾位/类型图标/文件名/次行/
//   ☆ 收藏/⋯ 更多), 供「最近用过/本会话/已收藏/AI 生成/合集」复用; 键盘焦点态由 active 传入,
//   点文件名回调预览(不触发加入), 其余区域点整行 = 加入/移出本轮 — 小欧-2026-11-07
/**
 * FileRow —— 文件抽屉的列表行（唯一实现）
 *
 * 布局（文档[13] 6.4）：
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
  FileImageOutlined,
  FileOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  MoreOutlined,
  StarFilled,
  StarOutlined,
  WarningOutlined,
} from '@ant-design/icons';

import { Colors, FontSize } from '@/utils/stepStyles';

/** 按 mime 取类型图标（线性图标，无 emoji） */
function iconOf(mime: string): React.ReactNode {
  if (mime.startsWith('image/')) return <FileImageOutlined />;
  if (mime === 'application/pdf') return <FilePdfOutlined />;
  if (mime.startsWith('text/') || mime.includes('json'))
    return <FileTextOutlined />;
  return <FileOutlined />;
}

export interface FileRowProps {
  name: string;
  /** 次行说明：类型 · 大小 · 来源 · 相对时间 */
  meta: string;
  mime?: string;
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
      background: added ? '#e6f4ff' : active ? Colors.BG.HOVER : 'transparent',
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
        iconOf(mime)
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
          <>
            {meta}
            {added ? ' · 已加入' : ''}
          </>
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
            <StarFilled style={{ color: '#faad14' }} />
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
