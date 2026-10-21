// 编辑历史: 2026-10-20 小欧 - 新建: 发送/停止/暂停按钮组自 SubmitBar 拆出并移入输入框内右下角(北京老陈指令);
//   三钮统一方形图标样式(↑/⏹/⏸/▶), 配色走主题令牌 Colors/Radius/Spacing(禁魔法数字); 空输入发送钮置灰 — 小欧-2026-10-20
/**
 * SubmitActions - 输入框内右下角动作按钮组: 发送(常驻) + 停止/暂停·继续(执行中渲染)
 *
 * 纯展示组件不接业务: 置灰判据由 ChatInput 算好传入, 两判据均与提交门同源 —
 *   sendBlocked = isSendBlocked(执行中), emptyDraft = draft.trim()===''(与 handleSendInternal
 *   的 !content 同判据), 保证按钮态与实际可发能力一致, 无「灰着却能回车发」矛盾。
 *
 * @author 小欧
 * @date 2026-10-20
 */
import React from 'react';
import { Button, Space } from 'antd';
import {
  ArrowUpOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { Colors, Icon, Radius, Spacing } from '@/utils/stepStyles';

interface SubmitActionsProps {
  loading: boolean;
  isReceiving: boolean;
  isPaused: boolean;
  /** 执行中不可发送(ChatInput 用 isSendBlocked 算好, 与提交门同源) */
  sendBlocked: boolean;
  /** 空草稿不可发送(与 handleSendInternal 的 !content 判据同源) */
  emptyDraft: boolean;
  onSend: () => void;
  onCancel: () => void;
  onTogglePause: () => void;
}

// 方形动作钮统一规格: 34 见方贴图样式(图标 16 = Icon.BOX 行首图标同规格); InputCore 的按钮区
//   预留高度 ACTION_RESERVE 随本值联动, 改钮规格须两处同步
const BTN = 34;
const square: React.CSSProperties = {
  width: BTN,
  height: BTN,
  padding: 0,
  borderRadius: Radius.LG,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
};

const SubmitActions: React.FC<SubmitActionsProps> = ({
  loading,
  isReceiving,
  isPaused,
  sendBlocked,
  emptyDraft,
  onSend,
  onCancel,
  onTogglePause,
}) => {
  const blocked = sendBlocked || emptyDraft;
  // 图标内联 fontSize 走 Icon.BOX; 颜色不设 — icon 继承 Button currentColor(发送正态白/停止红由按钮与图标各管)
  const iconSize = { fontSize: Icon.BOX };

  return (
    <Space size={Spacing.SM}>
      {loading || isReceiving ? (
        <>
          <Button
            aria-label="停止"
            icon={<StopOutlined style={{ ...iconSize, color: Colors.ERROR }} />}
            style={{ ...square, borderColor: Colors.BORDER.DEFAULT }}
            onClick={onCancel}
          />
          <Button
            aria-label={isPaused ? '继续' : '暂停'}
            icon={
              isPaused ? (
                <PlayCircleOutlined style={iconSize} />
              ) : (
                <PauseOutlined style={iconSize} />
              )
            }
            style={{ ...square, borderColor: Colors.BORDER.DEFAULT }}
            onClick={onTogglePause}
          />
        </>
      ) : null}
      {/*
        2026-10-20 小欧 - 受阻态: 置灰走中性灰(BG.TERTIARY)而非 antd primary 默认的半透明蓝,
          贴图灰态; Tooltip 文案按受阻原因分流(与框外常驻提示各司其职: 常驻提示管执行中, 这里管 hover)
      */}
      {/*
        2026-10-21 小杨 - 双 tooltip 收敛（北京老陈拍板）：受阻态的原生 title 已有
          框外常驻提示（同信息一处即可），antd 浮泡层剥掉 —— 外层 span 承接 hover 失效，
          disabled Button 直接渲染（提示文案由 aria-label / 常驻提示承载）。
      */}
      {blocked ? null : (
        <Button
          type="primary"
          aria-label="发送"
          icon={<ArrowUpOutlined style={iconSize} />}
          style={square}
          onClick={onSend}
        />
      )}
    </Space>
  );
};

export { SubmitActions };
