/**
 * CompareFilesView - compare_files 工具结果渲染组件
 *
 * 显示两个文件的比较结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";
import { CheckCircleOutlined, MinusCircleOutlined, FileOutlined, SwapOutlined } from "@ant-design/icons";

interface CompareFilesViewProps {
  data: {
    file_a?: string;
    file_b?: string;
    file_a_size?: number;
    file_b_size?: number;
    size_diff?: number;
    modified_time_diff?: string;
    content_diff_count?: number;
    success?: boolean;
    error_message?: string;
  };
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
  if (bytes < 0) bytes = Math.abs(bytes);
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

/**
 * CompareFilesView 主组件
 */
const CompareFilesView: React.FC<CompareFilesViewProps> = ({ data }) => {
  const { 
    file_a = "",
    file_b = "",
    file_a_size,
    file_b_size,
    size_diff,
    modified_time_diff,
    content_diff_count,
    success = true,
    error_message 
  } = data;

  // 错误状态
  const hasError = !success || (error_message !== undefined && error_message !== "");

  // 容器样式 - 与系统设计风格一致
  const containerStyle = {
    background: hasError 
      ? "linear-gradient(135deg, #fff2f0 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #e6f7ff 0%, #f5f5f5 100%)",
    border: hasError 
      ? "1px solid #ffa39e"
      : "1px solid #91d5ff",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  };

  // 标题样式
  const titleStyle = {
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: hasError ? "#ff4d4f" : "#1890ff",
  };

  // 对比面板样式
  const comparePanelStyle = {
    display: "grid",
    gridTemplateColumns: "1fr auto 1fr",
    gap: 16,
    alignItems: "center",
    marginBottom: 12,
  };

  // 文件卡片样式
  const fileCardStyle = {
    background: "#fafafa",
    border: "1px solid #d9d9d9",
    borderRadius: 6,
    padding: "10px 12px",
    fontSize: 12,
  };

  // 信息项样式
  const infoItemStyle = {
    display: "flex",
    alignItems: "center",
    marginBottom: 8,
    fontSize: 13,
    color: "#595959",
  };

  // 标签样式
  const labelStyle = {
    minWidth: 100,
    color: "#8c8c8c",
    marginRight: 8,
  };

  // 处理文件大小
  const sizeA = file_a_size !== undefined ? formatFileSize(file_a_size) : null;
  const sizeB = file_b_size !== undefined ? formatFileSize(file_b_size) : null;
  const sizeDiff = size_diff !== undefined ? formatFileSize(size_diff) : null;

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        {hasError ? (
          <>
            <MinusCircleOutlined style={{ marginRight: 8 }} />
            ❌ 文件比较失败
          </>
        ) : (
          <>
            <SwapOutlined style={{ marginRight: 8 }} />
            🔍 文件比较结果
          </>
        )}
      </div>

      {/* 对比面板 */}
      {!hasError && file_a && file_b && (
        <div style={comparePanelStyle}>
          {/* 文件A */}
          <div style={fileCardStyle}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: 6 }}>
              <FileOutlined style={{ marginRight: 6, color: "#1890ff" }} />
              <span style={{ fontWeight: 500 }}>文件A</span>
            </div>
            <div style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", wordBreak: "break-all" }}>
              {file_a}
            </div>
            {sizeA && (
              <div style={{ marginTop: 4, color: "#8c8c8c", fontSize: 11 }}>
                📊 {sizeA}
              </div>
            )}
          </div>

          {/* 比较箭头 */}
          <SwapOutlined style={{ fontSize: 20, color: "#8c8c8c" }} />

          {/* 文件B */}
          <div style={fileCardStyle}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: 6 }}>
              <FileOutlined style={{ marginRight: 6, color: "#52c41a" }} />
              <span style={{ fontWeight: 500 }}>文件B</span>
            </div>
            <div style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", wordBreak: "break-all" }}>
              {file_b}
            </div>
            {sizeB && (
              <div style={{ marginTop: 4, color: "#8c8c8c", fontSize: 11 }}>
                📊 {sizeB}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 差异信息 */}
      {!hasError && (
        <>
          {/* 大小差异 */}
          {sizeDiff && size_diff !== undefined && (
            <div style={infoItemStyle}>
              <span style={labelStyle}>📊 大小差异：</span>
              <span style={{ 
                color: size_diff > 0 ? "#52c41a" : (size_diff < 0 ? "#ff4d4f" : "#595959"),
                fontWeight: 500 
              }}>
                {size_diff > 0 ? "+" : ""}{sizeDiff}
              </span>
            </div>
          )}

          {/* 修改时间差异 */}
          {modified_time_diff && (
            <div style={infoItemStyle}>
              <span style={labelStyle}>📅 修改时间差异：</span>
              <span>{modified_time_diff}</span>
            </div>
          )}

          {/* 内容差异数量 */}
          {content_diff_count !== undefined && (
            <div style={infoItemStyle}>
              <span style={labelStyle}>📝 内容差异：</span>
              <span style={{ fontWeight: 500 }}>
                {content_diff_count}处不同
              </span>
            </div>
          )}

          {/* 无差异提示 */}
          {content_diff_count === 0 && (
            <div style={{ 
              ...infoItemStyle, 
              color: "#52c41a",
              fontWeight: 500 
            }}>
              <CheckCircleOutlined style={{ marginRight: 6 }} />
              文件内容完全相同
            </div>
          )}
        </>
      )}

      {/* 错误信息 */}
      {hasError && error_message && (
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

export default React.memo(CompareFilesView);