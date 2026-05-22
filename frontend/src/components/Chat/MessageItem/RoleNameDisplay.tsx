/**
 * RoleNameDisplay组件 - 角色名称显示
 * 
 * 根据角色和消息状态显示对应的名称
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

/* eslint-disable react/prop-types */
import React, { memo } from "react";

interface RoleNameDisplayProps {
  role: "user" | "assistant" | "system" | string;
  isStreaming?: boolean;
  isError?: boolean;
  sendStatus?: 'sending' | 'sent' | 'failed'; // 【小沈修复2026-04-23】P0-1: 用户消息发送状态
  display_name?: string;
  model?: string;
}

/**
 * RoleNameDisplay组件
 * 根据role和消息状态显示对应的名称
 */
const RoleNameDisplay: React.FC<RoleNameDisplayProps> = memo(({
  role,
  isStreaming = false,
  isError = false,
  sendStatus,
  display_name,
  model,
}) => {
  switch (role) {
    case "user": {
      // 【小沈修复2026-04-23】P0-1: 显示发送失败状态
      if (sendStatus === "failed") {
        return <span>❌ 我</span>;
      }
      if (sendStatus === "sending") {
        return <span>⏳ 我</span>;
      }
      return <span>我</span>;
    }
    case "assistant": {
      // 加载状态
      if (isStreaming) {
        let display_nameToShow = display_name;
        if (!display_nameToShow && model) {
          display_nameToShow = model;
        }
        
        const result = display_nameToShow
          ? `🤔 AI 助手【${display_nameToShow}】【加载中...】`
          : `🤔 AI 助手【加载中...】`;
        return <span>{result}</span>;
      }

      // 错误状态
      if (isError) {
        return display_name
          ? <span>⚠️ AI 助手【{display_name}】【错误】</span>
          : <span>⚠️ AI 助手【错误】</span>;
      }
      
      // 普通状态
      return display_name
        ? <span>AI 助手【{display_name}】</span>
        : <span>AI 助手</span>;
    }
    case "system":
      return <span>系统</span>;
    default:
      return <span></span>;
  }
});

RoleNameDisplay.displayName = "RoleNameDisplay";

export default RoleNameDisplay;
