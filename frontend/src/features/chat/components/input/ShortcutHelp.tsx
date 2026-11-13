// 编辑历史: 2026-11-13 商量 - 新建: 输入框帮助信息分层归属。输入框内只保留核心 placeholder[1],
//   原常驻编号清单([2]~[6])迁入「输入技巧」浮层(按 输入/文件与引用/图片 三组归类, 可无限扩展);
//   拖拽提示不常驻(由 ChatInput 拖拽态虚线框承担), 图片/附件等能力发现走本浮层 — 商量-2026-11-13
// 2026-11-13 商量 - 归位到按钮行: 微图例不再自占一行, 改为 SubmitBar 中段插槽(<ShortcutHelp/>),
//   与动作按钮同高 → 输入区零额外高度; 组内仅 XS 间距, 无上下外边距; 空间不足时图例文本省略,
//   「输入技巧」入口恒可见可点(不被压缩) — 商量-2026-11-13
// 2026-11-13 商量 - 微图例并入 placeholder 尾段(@ 引用 · 拖入文件 · 粘贴图片, 见 InputCore 的
//   PLACEHOLDER_HINTS): 空态自带说明且 minRows=2 已预留两行, 不额外占高; 本组件随之只留
//   「输入技巧」浮层入口(单一职责), 常驻入口承担打字后/受阻态的持续可发现性 — 商量-2026-11-13
// 2026-11-13 商量 - 间距归一: 分组/条目间距改由父容器 gap 承担(删 marginBottom 与条目 padding 叠加),
//   行高改走全站标准 LineHeight.DENSE, 内距改走 controlScale 的 CONTROL_PADDING — 商量-2026-11-13
import React, { useState } from 'react';
import type { CSSProperties } from 'react';
import { Popover } from 'antd';
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontSize,
  Radius,
} from '@/utils/stepStyles';
import { Gap, LineHeight } from '@/theme/spacing';
import { CONTROL_PADDING } from '@/theme/controlScale';

interface ShortcutItem {
  /** 键位/触发物徽标; 无固定键位的能力(如拖拽)填动作名 */
  key: string;
  text: string;
}

interface ShortcutGroup {
  title: string;
  items: ShortcutItem[];
}

/**
 * 输入方式帮助的唯一真源: 新增/调整输入方式只改本数组, 浮层按分组自动渲染。
 * 与输入框 placeholder(核心提交语义)分工: 高频键位不再重复灌入 placeholder。
 */
export const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: '输入',
    items: [
      { key: 'Enter', text: '提交消息' },
      { key: 'Shift + Enter', text: '换行' },
      { key: '↑ / ↓', text: '在光标位于首/末行时翻历史消息' },
    ],
  },
  {
    title: '文件与引用',
    items: [
      { key: '@', text: '引用项目文件，选中后显示在输入框上方的引用区' },
      { key: '附件', text: '点「附件」选择文件（项目 / 后端电脑 / 上传等）' },
      { key: '拖拽', text: '从本机文件管理器拖文件进输入区' },
    ],
  },
  {
    title: '图片',
    items: [
      { key: '粘贴', text: '粘贴截图或图片文件' },
      { key: 'URL', text: '输入公网图片链接（https://…/pic.png）' },
    ],
  },
];

// 面板宽/限高: 与历史输入面板同规格(360), 组多时内部滚动, 浮层不撑破窄屏
const PANEL_W = 360;
const PANEL_MAX_H = 360;

const kbdStyle: CSSProperties = {
  flexShrink: 0,
  minWidth: 44,
  padding: `0 ${CONTROL_PADDING.CHIP_X}px`,
  fontFamily: FontFamily.MONO,
  fontSize: FontSize.SMALL,
  lineHeight: LineHeight.DENSE,
  textAlign: 'center',
  color: Colors.TEXT.PRIMARY,
  background: Colors.BG.SECONDARY,
  border: `${BorderWidth.THIN}px solid ${Colors.BORDER.DEFAULT}`,
  borderRadius: Radius.SM,
};

const ShortcutHelp: React.FC = () => {
  const [open, setOpen] = useState(false);

  const content = (
    <div
      style={{
        width: PANEL_W,
        maxHeight: PANEL_MAX_H,
        overflowY: 'auto',
        // 分组之间的距离由父容器 gap 唯一承担
        display: 'flex',
        flexDirection: 'column',
        gap: Gap.SECTION,
      }}
    >
      {SHORTCUT_GROUPS.map((group) => (
        <div
          key={group.title}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: Gap.ROW,
          }}
        >
          <div
            style={{
              fontSize: FontSize.SMALL,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            {group.title}
          </div>
          {group.items.map((item) => (
            <div
              key={item.key}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: Gap.INLINE,
              }}
            >
              <span style={kbdStyle}>{item.key}</span>
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  fontSize: FontSize.SECONDARY,
                  lineHeight: LineHeight.DENSE,
                  color: Colors.TEXT.PRIMARY,
                }}
              >
                {item.text}
              </span>
            </div>
          ))}
        </div>
      ))}
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
      <button
        type="button"
        aria-label="查看输入技巧"
        style={{
          flexShrink: 0, // 中段收缩时入口不被压缩, 恒可点
          // 铁律三例外①: 负 margin 与自身内距等量抵消, 使入口文字视觉贴右缘, 不是元素间距
          margin: `-${CONTROL_PADDING.CHIP_Y}px -${CONTROL_PADDING.CHIP_X}px`,
          // 按钮内距(内容离按钮边), 非元素间距
          padding: `${CONTROL_PADDING.CHIP_Y}px ${CONTROL_PADDING.CHIP_X}px`,
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          fontSize: FontSize.SECONDARY,
          lineHeight: LineHeight.DENSE,
          color: Colors.PRIMARY,
        }}
      >
        输入技巧
      </button>
    </Popover>
  );
};

export { ShortcutHelp };
