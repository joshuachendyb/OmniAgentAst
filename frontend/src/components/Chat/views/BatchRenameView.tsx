/**
 * BatchRenameView - batch_rename 工具结果渲染组件
 *
 * 显示批量重命名结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React, { useState } from "react";
import { CheckCircleOutlined, CloseCircleOutlined, WarningOutlined, SyncOutlined, DownOutlined, RightOutlined } from "@ant-design/icons";
import { Collapse, Tag } from "antd";

interface BatchRenameViewProps {
  data: {
    total_count?: number;
    success_count?: number;
    skip_count?: number;
    failed_count?: number;
    rename_list?: Array<{
      old_name: string;
      new_name: string;
      success: boolean;
      error_message?: string;
    }>;
    success?: boolean;
    error_message?: string;
  };
}

/**
 * BatchRenameView 主组件
 */
const BatchRenameView: React.FC<BatchRenameViewProps> = ({ data }) => {
  const { 
    total_count = 0,
    success_count = 0,
    skip_count = 0,
    failed_count = 0,
    rename_list = [],
    error_message 
  } = data;

  const [expanded, setExpanded] = useState(false);
  const hasList = rename_list && rename_list.length > 0;

  // 错误状态
  const hasError = error_message !== undefined && error_message !== "";

  // 容器样式 - 与系统设计风格一致
  const containerStyle = {
    background: hasError 
      ? "linear-gradient(135deg, #fff2f0 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)",
    border: hasError 
      ? "1px solid #ffa39e"
      : "1px solid #b7eb8f",
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
    color: hasError ? "#ff4d4f" : "#52c41a",
  };

  // 统计数字样式
  const statsStyle = {
    display: "flex",
    gap: 16,
    marginBottom: 12,
    paddingBottom: 12,
    borderBottom: "1px solid #f0f0f0",
  };

  // 统计项样式
  const statItemStyle = {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 13,
  };

  // 重命名列表项样式
  const listItemStyle = {
    display: "flex",
    alignItems: "center",
    padding: "6px 0",
    fontSize: 12,
    fontFamily: "Consolas, Monaco, 'Courier New', monospace",
    borderBottom: "1px solid #f5f5f5",
  };

  const panelStyle = {
    background: "#fafafa",
    border: "1px solid #d9d9d9",
    borderRadius: 6,
    marginTop: 8,
  };

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        {hasError ? (
          <>
            <CloseCircleOutlined style={{ marginRight: 8 }} />
            ❌ 批量重命名失败
          </>
        ) : (
          <>
            <SyncOutlined style={{ marginRight: 8 }} />
            🔄 批量重命名完成
          </>
        )}
      </div>

      {/* 统计信息 */}
      {!hasError && (
        <>
          <div style={statsStyle}>
            <div style={statItemStyle}>
              <span style={{ color: "#8c8c8c" }}>📊 处理文件：</span>
              <strong>{total_count}个</strong>
            </div>
            
            <div style={statItemStyle}>
              <CheckCircleOutlined style={{ color: "#52c41a" }} />
              <span style={{ color: "#52c41a" }}>成功：</span>
              <strong>{success_count}个</strong>
            </div>
            
            {skip_count > 0 && (
              <div style={statItemStyle}>
                <WarningOutlined style={{ color: "#faad14" }} />
                <span style={{ color: "#faad14" }}>跳过：</span>
                <strong>{skip_count}个</strong>
              </div>
            )}
            
            {failed_count > 0 && (
              <div style={statItemStyle}>
                <CloseCircleOutlined style={{ color: "#ff4d4f" }} />
                <span style={{ color: "#ff4d4f" }}>失败：</span>
                <strong>{failed_count}个</strong>
              </div>
            )}
          </div>

          {/* 重命名列表 */}
          {hasList && (
            <Collapse
              ghost
              style={panelStyle}
              items={[
                {
                  key: '1',
                  label: (
                    <span style={{ fontSize: 13, color: "#595959" }}>
                      📋 重命名列表（{rename_list.length}项）
                    </span>
                  ),
                  children: (
                    <div style={{ maxHeight: 200, overflowY: "auto" }}>
                      {rename_list.map((item, index) => (
                        <div 
                          key={index} 
                          style={{
                            ...listItemStyle,
                            opacity: item.success ? 1 : 0.5,
                            color: item.success ? "#595959" : "#ff4d4f",
                          }}
                        >
                          {item.success ? (
                            <CheckCircleOutlined style={{ color: "#52c41a", marginRight: 8 }} />
                          ) : (
                            <CloseCircleOutlined style={{ color: "#ff4d4f", marginRight: 8 }} />
                          )}
                          <span style={{ flex: 1 }}>{item.old_name}</span>
                          <RightOutlined style={{ margin: "0 8px", color: "#8c8c8c" }} />
                          <span style={{ flex: 1 }}>{item.new_name}</span>
                          {item.error_message && (
                            <Tag color="red" style={{ marginLeft: 8 }}>
                              {item.error_message}
                            </Tag>
                          )}
                        </div>
                      ))}
                    </div>
                  ),
                },
              ]}
            />
          )}
        </>
      )}

      {/* 错误信息 */}
      {hasError && (
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

export default React.memo(BatchRenameView);