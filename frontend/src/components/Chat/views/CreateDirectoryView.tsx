/**
 * CreateDirectoryView - create_directory 工具结果渲染组件
 *
 * 显示目录创建结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined, FolderOutlined, CopyOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";

interface CreateDirectoryViewProps {
  data: {
    directory_path?: string;
    success?: boolean;
    permissions?: string;
    created_at?: string;
    error_message?: string;
  };
}

const INFO_ITEM_STYLE: React.CSSProperties = { display: "flex", alignItems: "center", marginBottom: 8, fontSize: 13, color: "#595959" };
const LABEL_STYLE: React.CSSProperties = { minWidth: 80, color: "#8c8c8c", marginRight: 8 };

const CreateDirectoryView: React.FC<CreateDirectoryViewProps> = ({ data }) => {
  const { 
    directory_path = "", 
    success = true, 
    permissions = "755",
    created_at,
    error_message 
  } = data;

  const containerStyle: React.CSSProperties = {
    background: success ? "#e6f7ff" : "#fff2f0",
    border: success ? "1px solid #91d5ff" : "1px solid #ffa39e",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  };

  const titleStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: success ? "#1890ff" : "#ff4d4f",
  };

  const handleCopyPath = (path: string) => {
    navigator.clipboard.writeText(path);
  };

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        {success ? (
          <>
            <CheckCircleOutlined style={{ marginRight: 8 }} />
            目录创建成功
          </>
        ) : (
          <>
            <CloseCircleOutlined style={{ marginRight: 8 }} />
            目录创建失败
          </>
        )}
      </div>

      {/* 目录路径 */}
      <div style={INFO_ITEM_STYLE}>
        <span style={LABEL_STYLE}>目录路径：</span>
        <div style={{ flex: 1, display: "flex", alignItems: "center" }}>
          <FolderOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
          <span style={{ flex: 1, fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
            {directory_path}
          </span>
          <Tooltip title="复制路径">
            <Button 
              type="text" 
              size="small" 
              onClick={() => handleCopyPath(directory_path)}
              icon={<CopyOutlined />}
              style={{ padding: "0 4px", minWidth: "auto" }}
            />
          </Tooltip>
        </div>
      </div>

      {/* 权限 */}
      <div style={INFO_ITEM_STYLE}>
        <span style={LABEL_STYLE}>权限：</span>
        <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace" }}>{permissions}</span>
      </div>

      {/* 创建时间 */}
      {created_at && (
        <div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}>创建时间：</span>
          <span>{created_at}</span>
        </div>
      )}

      {/* 错误信��� */}
      {!success && error_message && (
        <div style={{
          marginTop: 12,
          padding: "8px 12px",
          background: "#fff2f0",
          border: "1px solid #ffccc7",
          borderRadius: 4,
          color: "#ff4d4f",
          fontSize: 12,
        }}>
          <strong>错误信息：</strong> {error_message}
        </div>
      )}
    </div>
  );
};

export default React.memo(CreateDirectoryView);