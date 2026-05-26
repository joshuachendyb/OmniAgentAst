/**
 * FileOperationView - 通用文件操作结果渲染组件
 *
 * 用于 edit_text_file/rename_file/get_directory_tree/list_allowed_directories
 * read_media_file/read_batch_file/precise_replace_in_file/get_file_hash/extract_archive
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-05-10
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface FileOperationViewProps {
  message?: string;
  success?: boolean;
}

const FileOperationView: React.FC<FileOperationViewProps> = ({ message = "", success = true }) => {
  const containerStyle: React.CSSProperties = {
    background: success ? "#f6ffed" : "#fff2f0",
    border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
    fontSize: 13,
    lineHeight: 1.8,
  };

  return (
    <div style={containerStyle}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: message ? 8 : 0 }}>
        {success ? (
          <CheckCircleOutlined style={{ color: "#52c41a", marginRight: 8 }} />
        ) : (
          <CloseCircleOutlined style={{ color: "#ff4d4f", marginRight: 8 }} />
        )}
        <span style={{ fontWeight: 500, color: success ? "#52c41a" : "#ff4d4f" }}>
          {success ? "操作成功" : "操作失败"}
        </span>
      </div>
      {message && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap" }}>
          {message}
        </div>
      )}
    </div>
  );
};

export default React.memo(FileOperationView);
