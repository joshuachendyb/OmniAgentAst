// 编辑历史: 2026-10-13 13:45 小欧 - 新建: 历史输入面板(草稿区+最近提交区, 同一入口); 触发按钮与 Popover 封装在
//   本组件内(ChatInput 只传数据); 文案用「最近提交」不用「发送成功」(onSend 乐观提交, resolve 不代表任务成功);
//   /history 指令已被 ShortcutPanel 占用(查看会话历史), 本功能叫「历史输入」不占该名
// 编辑历史: 2026-10-13 14:35 小欧 - 三堂会审整改: 条目圆角由魔法数字 4 改走 Radius.SM 令牌(同值但绕过
//   仓库令牌化约定); PANEL_W/PANEL_MAX_H 补来源注释, 避免下一个人以为是随手写的数字
// 2026-11-13 商量 - 间距归一: 标题与条目、分组之间的距离改由父容器 gap 承担(删标题 marginBottom),
//   条目行高补足改走全站控件刻度 CONTROL_HEIGHT_SM — 商量-2026-11-13
import React, { useEffect, useState } from 'react';
import { Button, Empty, Popover, Space } from 'antd';
import { HistoryOutlined } from '@ant-design/icons';
import {
  Colors,
  FontFamily,
  FontSize,
  Radius,
  Spacing,
} from '@/utils/stepStyles';
import type { RecentInput } from '../../utils/recentInputs';
import { Gap } from '@/theme/spacing';
import { CONTROL_HEIGHT_SM } from '@/theme/controlScale';

interface InputHistoryPanelProps {
  draft: string;
  recents: RecentInput[];
  onDiscardDraft: () => void;
  onPick: (text: string) => void;
  onClear: () => void;
}

// 面板宽 360px: 容纳最长常用的单行命令且不撑破窄屏; 高 360px: 约 8 条, 再多交给内部滚动
const PANEL_W = 360;
const PANEL_MAX_H = 360;

const sectionHead: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: Gap.INLINE,
  fontSize: FontSize.CAPTION,
  color: Colors.TEXT.SECONDARY,
};

/** 分组容器: 标题与条目之间的距离由**父容器 gap** 唯一承担(标题自身不再带 marginBottom) */
const sectionStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: Gap.ROW,
};

const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: Gap.INLINE,
  // 铁律二: padding 只做"内容与容器边"的留白, 条目之间的间距由父容器 gap 承担
  padding: `0 ${Spacing.SM}px`,
  minHeight: CONTROL_HEIGHT_SM,
  borderRadius: Radius.SM, // 2026-10-13 14:35 小欧: 原为魔法数字 4, 与 Radius.SM 同值但绕过令牌, 违反仓库令牌化约定
  cursor: 'pointer',
  fontFamily: FontFamily.MONO,
  fontSize: FontSize.CODE,
  color: Colors.TEXT.PRIMARY,
};

const InputHistoryPanel: React.FC<InputHistoryPanelProps> = ({
  draft,
  recents,
  onDiscardDraft,
  onPick,
  onClear,
}) => {
  const [open, setOpen] = useState(false);
  // 清空二次确认(内联两步, 不引 Modal.confirm 新范式)
  const [confirmClear, setConfirmClear] = useState(false);
  useEffect(() => {
    if (!open) setConfirmClear(false);
  }, [open]);

  const pick = (text: string) => {
    onPick(text);
    setOpen(false);
  };

  const content = (
    <div
      style={{
        width: PANEL_W,
        maxHeight: PANEL_MAX_H,
        overflowY: 'auto',
        // 两个分组(草稿/最近提交)之间的距离由父容器 gap 唯一承担
        display: 'flex',
        flexDirection: 'column',
        gap: Gap.STACK,
      }}
    >
      {/* 区 1: 草稿(未提交) —— 有内容才显示 */}
      {draft.trim() !== '' && (
        <div style={sectionStyle}>
          <div style={sectionHead}>
            <span>草稿 · 未提交</span>
            <Button type="link" size="small" onClick={onDiscardDraft}>
              丢弃
            </Button>
          </div>
          <div
            style={itemStyle}
            onClick={() => pick(draft)}
            title={draft}
            data-testid="draft-item"
          >
            <span style={{ flex: 1, minWidth: 0, wordBreak: 'break-word' }}>
              {draft}
            </span>
          </div>
        </div>
      )}

      {/* 区 2: 最近提交(本机) */}
      <div style={sectionStyle}>
        <div style={sectionHead}>
          <span>最近提交 · 本机</span>
          {confirmClear ? (
            <Space size={4}>
              <Button
                size="small"
                type="text"
                danger
                onClick={() => {
                  onClear();
                  setConfirmClear(false);
                }}
              >
                确认清空
              </Button>
              <Button
                size="small"
                type="text"
                onClick={() => setConfirmClear(false)}
              >
                取消
              </Button>
            </Space>
          ) : (
            <Button
              size="small"
              type="link"
              disabled={recents.length === 0}
              onClick={() => setConfirmClear(true)}
            >
              清空
            </Button>
          )}
        </div>
        {recents.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史" />
        ) : (
          recents.map((r, i) => (
            <div
              key={`${r.ts}-${i}`}
              style={itemStyle}
              onClick={() => pick(r.text)}
              title={r.text}
              data-testid="recent-item"
            >
              <HistoryOutlined
                style={{
                  color: Colors.TEXT.TERTIARY,
                  fontSize: FontSize.CAPTION,
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {r.text}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );

  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      trigger="click"
      placement="topLeft"
      content={content}
    >
      <Button size="small" icon={<HistoryOutlined />}>
        历史输入
      </Button>
    </Popover>
  );
};

export { InputHistoryPanel };
