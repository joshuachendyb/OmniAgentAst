/**
 * AvatarDisplay组件 - 头像显示
 * 
 * 根据角色显示不同的头像图标
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

/* eslint-disable react/prop-types */
import React, { memo } from "react";
import { Avatar } from "antd";
import {
  UserOutlined,
  RobotOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";

interface AvatarDisplayProps {
  role: "user" | "assistant" | "system" | string;
}

/**
 * AvatarDisplay组件
 * 根据role显示对应的头像
 */
const AvatarDisplay: React.FC<AvatarDisplayProps> = memo(({ role }) => {
  switch (role) {
    case "user":
      return (
        <Avatar
          size={32}
          icon={<UserOutlined />}
          style={{
            background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
          }}
        />
      );
    case "assistant":
      return (
        <Avatar
          size={32}
          icon={<RobotOutlined />}
          style={{
            background: "linear-gradient(135deg, #52c41a 0%, #389e0d 100%)",
          }}
        />
      );
    case "system":
      return (
        <Avatar
          size={32}
          icon={<InfoCircleOutlined />}
          style={{ background: "#faad14" }}
        />
      );
    default:
      return null;
  }
});

AvatarDisplay.displayName = "AvatarDisplay";

export default AvatarDisplay;
