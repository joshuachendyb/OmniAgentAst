// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 底部功能行 模型按钮+附件+发送/停止+暂停继续(4.3.6)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: modelPickerSlot改为可选属性(调用方可不传)
// 编辑历史: 2026-08-28 小欧 - ①A/a2: 新增leftExtra插槽(指令+续聊), 左侧序leftExtra/modelPicker/附件, 去marginTop4, gap8节奏
// 编辑历史: 2026-10-06 小欧 - 北京老陈指令: 附件区调用点补 visible(不再隐藏) + disabled(置灰占位)，
//   上传功能仍暂缓（AttachmentArea 内 beforeUpload 照旧拦），此处仅改渲染参数不改左插槽顺序 — 小欧-2026-10-06
// 编辑历史: 2026-10-10 小欧 - 文档[16] §3.6.5: Props 补 workspaceCount/onOpenWorkspaces;
//   插话开关之后、发送按钮之前(决策70)加「会话事务空间」入口, antd Badge count 现算(0 自动隐藏) — 小欧-2026-10-10
// 编辑历史: 2026-10-13 18:05 小欧 - 文档[30] §2.5 B: 执行中也保留发送按钮(原为消失), 置灰 + Tooltip 说明不可发送;
//   置灰判据 sendBlocked 由 ChatInput 传入并与提交门同源, 避免按钮态与实际可发能力矛盾
/**
 * SubmitBar - 底部功能行：模型按钮(ModelPicker) + 附件 + 发送/停止 + 暂停·继续
 *
 * 【小欧 2026-08-26 8.12】4.3.6 底部一行；与附件按钮同一行，位于输入区底部。
 * ModelPicker 为既有组件（7.13 L2 落库已实施），此处原位引用。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Button, Space, Checkbox, Badge, Tooltip } from 'antd'; // 2026-10-07 小欧 三堂会审补 - 文档[11] 3.5.3(插话开关 Checkbox, 合并为同行 import); 2026-10-10 小欧 - 文档[16] §3.6.5(加 Badge 徽标)
import {
  PauseOutlined,
  PlayCircleOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { AttachmentArea } from './AttachmentArea';

interface SubmitBarProps {
  loading: boolean;
  isReceiving: boolean;
  isPaused: boolean;
  modelPickerSlot?: React.ReactNode; // 既有 ModelPicker 实例（可选）
  leftExtra?: React.ReactNode; // 2026-08-28 小欧 ①A: 指令+续聊插槽，置最左（工具>模型>附件）
  allowInterject?: boolean; // 2026-10-07 小欧 - 文档[11] 3.5.3: 插话开关值(可选, 缺省不渲染)
  onToggleInterject?: (v: boolean) => void;
  // 2026-10-10 小欧 - 文档[16] §3.6.5: 会话事务空间入口(决策70: 插话开关之后、发送按钮之前)
  workspaceCount?: number;
  onOpenWorkspaces?: () => void;
  // 2026-10-13 18:05 小欧 - 文档[30] §2.5 B: 发送按钮置灰判据, 由 ChatInput 用 isSendBlocked 算好后传入(与提交门同源)
  sendBlocked?: boolean;
  onSend: () => void;
  onCancel: () => void;
  onTogglePause: () => void;
}

const SubmitBar: React.FC<SubmitBarProps> = ({
  loading,
  isReceiving,
  isPaused,
  modelPickerSlot,
  leftExtra,
  allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.3
  onToggleInterject,
  workspaceCount, // 2026-10-10 小欧 - 文档[16] §3.6.5
  onOpenWorkspaces,
  sendBlocked,
  onSend,
  onCancel,
  onTogglePause,
}) => (
  <Space style={{ display: 'flex', justifyContent: 'space-between' }}>
    <Space size={8} style={{ display: 'inline-flex', alignItems: 'center' }}>
      {leftExtra}
      {modelPickerSlot}
      {/* 2026-10-06 小欧 - 北京老陈指令: 附件按钮不再隐藏, 显示+置灰占位（上传仍暂缓） */}
      <AttachmentArea visible disabled />
      {/* 插话开关: 附件之后(2026-10-06 北京老陈定); 复用 TaskTypeToggle 邻位 Checkbox 样式不新造组件 */}
      {onToggleInterject && (
        <Checkbox
          checked={!!allowInterject}
          onChange={(e) => onToggleInterject(e.target.checked)}
        >
          插话开关
        </Checkbox>
      )}
      {/* 2026-10-10 小欧 - 文档[16] §3.6.5: 会话事务空间入口(决策70 位置) */}
      {onOpenWorkspaces && (
        <Badge count={workspaceCount ?? 0} size="small">
          <Button size="small" onClick={onOpenWorkspaces}>
            会话事务空间
          </Button>
        </Badge>
      )}
    </Space>
    <Space>
      {loading || isReceiving ? (
        <>
          <Button
            size="small"
            danger
            icon={<StopOutlined />}
            onClick={onCancel}
          >
            停止
          </Button>
          <Button
            size="small"
            icon={isPaused ? <PlayCircleOutlined /> : <PauseOutlined />}
            onClick={onTogglePause}
          >
            {isPaused ? '继续' : '暂停'}
          </Button>
        </>
      ) : null}
      {/*
        2026-10-13 18:05 小欧 - 文档[30] §2.5 B: 执行中也保留发送按钮, 但置灰。
        原为二选一(执行中按钮消失), 用户只知道"发不了"不知"为什么"; 现改为置灰 + Tooltip。
        ⚠️ disabled 判据必须与 ChatInput 的提交门同源 isSendBlocked —— 否则会出现
          「按钮亮着但发不了」或「按钮灰着而回车能发」的新矛盾; 故由 ChatInput 算好后传入 sendBlocked。
      */}
      {sendBlocked ? (
        <Tooltip title="任务执行中，暂不可发送">
          <span>
            <Button
              size="small"
              type="primary"
              icon={<SendOutlined />}
              disabled
            >
              发送
            </Button>
          </span>
        </Tooltip>
      ) : (
        <Button
          size="small"
          type="primary"
          icon={<SendOutlined />}
          onClick={onSend}
        >
          发送
        </Button>
      )}
    </Space>
  </Space>
);

export { SubmitBar };
