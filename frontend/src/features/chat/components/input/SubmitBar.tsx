// 编辑历史: 2026-08-26 小欧: 底部功能行 模型按钮+附件+发送/停止+暂停继续
// 编辑历史: 2026-08-27 小欧: modelPickerSlot 改为可选属性(调用方可不传)
// 编辑历史: 2026-08-28 小欧: 新增leftExtra插槽(指令+续聊), 左侧序leftExtra/modelPicker/附件, 去marginTop4, gap8节奏
// 编辑历史: 2026-10-06 小欧 - 北京老陈指令: 附件区调用点补 visible(不再隐藏) + disabled(置灰占位)，
//   上传功能仍暂缓（AttachmentArea 内 beforeUpload 照旧拦），此处仅改渲染参数不改左插槽顺序 — 小欧-2026-10-06
// 编辑历史: 2026-10-10 小欧: Props 补 workspaceCount/onOpenWorkspaces; 插话开关之后、发送按钮之前加「会话事务
//   空间」入口, antd Badge count 现算(0 自动隐藏) — 小欧-2026-10-10
// 编辑历史: 2026-10-13 18:05 小欧: 执行中也保留发送按钮(原为消失), 置灰 + Tooltip 说明不可发送;
//   置灰判据 sendBlocked 由 ChatInput 传入并与提交门同源, 避免按钮态与实际可发能力矛盾 — 小欧-2026-10-13
// 编辑历史: 2026-10-20 小欧 - 右侧动作按钮组(发送/停止/暂停)拆出为 SubmitActions 并移入输入框内右下角(北京老陈
//   指令), 本组件只留左侧控件; loading/isReceiving/isPaused/sendBlocked/onSend/onCancel/onTogglePause 七项
//   props 随迁(唯一调用方 ChatInput 同步, 不留兼容层) — 小欧-2026-10-20
// 2026-10-25 小欧 - 动作按钮组回迁至本行右端(北京老陈指令): 新增 rightActions 插槽, 布局由 Space 改 flex
//   容器, 左控件靠左、动作组 marginLeft:auto 贴右; SubmitActions 由 ChatInput 直接构造传入(纯 ReactNode,
//   本组件零业务) — 小欧-2026-10-25

// 编辑历史: 2026-11-06 小欧 - 新增 attachment 插槽(附件按钮)与 rightExtra 插槽(素材包面板), 均由
//   ChatInput 构造传入(本组件零业务, 只排布) — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧: 入口合门 —— 删 rightExtra 插槽(素材包并入文件抽屉, 右端只留动作按钮组);
//   内层 Space 加 wrap —— 原单行 flex 无 wrap 时子项被压到文字竖排 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 注释清理: 去除文档号/决策号/修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
// 2026-11-13 商量 - 新增 middleExtra 插槽(左控件组与动作组之间的弹性中段, 右对齐): 承载低强调说明
//   (输入微图例), 使说明与按钮共用同一行高度, 输入区不再为说明单开一行; 空间不足时插槽收缩,
//   内容自行省略(由插槽内容负责 minWidth:0/ellipsis) — 商量-2026-11-13
// 2026-11-13 商量 - 间距归一: gap 改走全站间距语义档 Gap.INLINE(含 antd Space 的 size), 不再写裸 8 — 商量-2026-11-13

/**
 * SubmitBar - 底部功能行：左侧控件(历史/指令/类型/模型/附件/插话/会话事务空间) + 右端动作按钮组
 *
 * 底部一行；与附件按钮同一行，位于输入区底部。
 * ModelPicker 为既有组件，此处原位引用。
 *
 * @author 小欧
 * @date 2026-08-26
 */
import React from 'react';
import { Button, Space, Checkbox, Badge } from 'antd'; // 2026-10-07 小欧: 插话开关 Checkbox 合并为同行 import; 2026-10-10 小欧: 加 Badge 徽标
import { Gap } from '@/theme/spacing';

interface SubmitBarProps {
  modelPickerSlot?: React.ReactNode; // 既有 ModelPicker 实例（可选）
  leftExtra?: React.ReactNode; // 2026-08-28 小欧: 指令+续聊插槽，置最左（工具>模型>附件）
  allowInterject?: boolean; // 2026-10-07 小欧: 插话开关值(可选, 缺省不渲染)
  onToggleInterject?: (v: boolean) => void;
  // 2026-10-10 小欧: 会话事务空间入口(插话开关之后、发送按钮之前)
  workspaceCount?: number;
  onOpenWorkspaces?: () => void;
  /** 2026-10-25 小欧 - 右端动作按钮组(发送/停止/暂停); 不传则不渲染, 整行仅左控件靠左 — 小欧-2026-10-25 */
  rightActions?: React.ReactNode;
  /** 2026-11-06 小欧 - 附件入口插槽(附件按钮), 由 ChatInput 构造 — 小欧-2026-11-06 */
  attachment?: React.ReactNode;
  /**
   * 2026-11-13 商量 - 弹性中段插槽(左控件组与动作组之间, 右对齐)。
   *   承载低强调说明类内容, 与按钮同处一行 → 不额外占用输入区高度;
   *   容器 flex:1 + minWidth:0, 空间不足时收缩, 省略策略由插槽内容自行负责 — 商量-2026-11-13
   */
  middleExtra?: React.ReactNode;
  // 2026-11-07 小欧: 合门删 rightExtra 插槽(素材包面板并入文件抽屉, 右端只留动作按钮组) — 小欧-2026-11-07
}

const SubmitBar: React.FC<SubmitBarProps> = ({
  modelPickerSlot,
  leftExtra,
  allowInterject, // 2026-10-07 小欧: 插话开关
  onToggleInterject,
  workspaceCount, // 2026-10-10 小欧: 会话事务空间入口
  onOpenWorkspaces,
  rightActions, // 2026-10-25 小欧 - 右端动作按钮组插槽
  attachment, // 2026-11-06 小欧 - 附件入口
  middleExtra, // 2026-11-13 商量 - 弹性中段插槽(说明类)
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: Gap.INLINE,
      // 2026-11-07 小欧 - 窄屏允许换行: 原单行 flex 无 wrap 导致按钮被挤成竖排 — 小欧-2026-11-07
      flexWrap: 'wrap',
      rowGap: Gap.INLINE,
    }}
  >
    <Space size={Gap.INLINE} wrap style={{ alignItems: 'center' }}>
      {leftExtra}
      {modelPickerSlot}
      {/* 2026-11-06 小欧 - 附件入口改插槽——本组件不再认识会话/上传，纯布局(SRP) */}
      {attachment}
      {/* 插话开关: 附件之后(2026-10-06 北京老陈定); 复用 TaskTypeToggle 邻位 Checkbox 样式不新造组件 */}
      {onToggleInterject && (
        <Checkbox
          checked={!!allowInterject}
          onChange={(e) => onToggleInterject(e.target.checked)}
        >
          插话开关
        </Checkbox>
      )}
      {/* 2026-10-10 小欧: 会话事务空间入口(插话开关之后、发送按钮之前) */}
      {onOpenWorkspaces && (
        <Badge count={workspaceCount ?? 0} size="small">
          <Button size="small" onClick={onOpenWorkspaces}>
            事项工作区
          </Button>
        </Badge>
      )}
    </Space>
    {/* 2026-11-13 商量 - 弹性中段: 说明类内容与按钮同行, 不占输入区高度; 收缩时由内容省略 */}
    {middleExtra && (
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
        }}
      >
        {middleExtra}
      </div>
    )}
    {/* 2026-10-25 小欧 - marginLeft:auto 贴最右: 左控件组与动作组分居两端 */}
    {/* 2026-11-07 小欧: 合门后右端只剩动作按钮组(素材包并入文件抽屉) */}
    {rightActions && (
      <div
        style={{
          marginLeft: 'auto',
          display: 'flex',
          alignItems: 'center',
          gap: Gap.INLINE,
        }}
      >
        {rightActions}
      </div>
    )}
  </div>
);

export { SubmitBar };
