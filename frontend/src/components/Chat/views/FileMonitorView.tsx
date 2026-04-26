/**
 * FileMonitorView - file_monitor 工具结果渲染组件
 *
 * 显示文件监控结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { EyeOutlined, FileAddOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { List, Tag } from "antd";

interface FileEvent {
  path?: string;
  event_type?: string;
  timestamp?: number;
  size?: number;
}

interface FileMonitorViewProps {
  data: {
    directory?: string;
    events?: FileEvent[];
    event_count?: number;
  };
}

/**
 * FileMonitorView 主组件
 */
const FileMonitorView: React.FC<FileMonitorViewProps> = ({ data }) => {
  const {
    directory = "",
    events = [],
    event_count = 0,
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || (!directory && events.length === 0);
  }, [data, directory, events.length]);

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: "linear-gradient(135deg, #e6f7ff 0%, #f5f5f5 100%)",
    border: "1px solid #91d5ff",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), []);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: "#1890ff",
  }), []);

  // 事件类型标签颜色
  const getEventColor = (eventType: string): string => {
    switch (eventType) {
      case "created": return "#52c41a";
      case "modified": return "#1890ff";
      case "deleted": return "#ff4d4f";
      case "renamed": return "#722ed1";
      default: return "#8c8c8c";
    }
  };

  // 事件类型图标
  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case "created": return <FileAddOutlined />;
      case "modified": return <EditOutlined />;
      case "deleted": return <DeleteOutlined />;
      case "renamed": return <EyeOutlined />;
      default: return null;
    }
  };

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 监控数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <EyeOutlined style={{ marginRight: 8 }} />
        👁️ 文件监控
      </div>

      {/* 监控目录 */}
      <div style={{ marginBottom: 12, fontSize: 12, color: "#8c8c8c" }}>
        📁 {directory}
      </div>

      {/* 事件统计 */}
      <div style={{ marginBottom: 12 }}>
        <Tag color="blue">共 {event_count || events.length} 个事件</Tag>
      </div>

      {/* 事件列表 */}
      {events && events.length > 0 && (
        <List
          size="small"
          dataSource={events.slice(0, 10)}
          renderItem={(item: FileEvent) => (
            <List.Item style={{ padding: "4px 8px" }}>
              <div style={{ display: "flex", alignItems: "center", width: "100%" }}>
                {getEventIcon(item.event_type || "")}
                <Tag color={getEventColor(item.event_type || "")} style={{ marginLeft: 8 }}>
                  {item.event_type}
                </Tag>
                <span style={{ marginLeft: 8, fontSize: 12, flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item.path}
                </span>
              </div>
            </List.Item>
          )}
        />
      )}

      {events && events.length > 10 && (
        <div style={{ textAlign: "center", color: "#8c8c8c", marginTop: 8 }}>
          ... 还有 {events.length - 10} 个事件
        </div>
      )}
    </div>
  );
};

export default React.memo(FileMonitorView);