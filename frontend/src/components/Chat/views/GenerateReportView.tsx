/**
 * GenerateReportView - generate_report 工具结果渲染组件
 *
 * 显示报告生成结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-24
 */

import React from "react";
import { Card, Tag } from "antd";
import { FileTextOutlined, CheckCircleOutlined } from "@ant-design/icons";

interface GenerateReportViewProps {
  data: {
    reports?: Record<string, string>;
  };
  isExpanded?: boolean;
  onToggle?: () => void;
}

/**
 * 统一的步骤样式函数 - 与MessageItem.tsx中的getStepStyle保持一致
 */
const getStepStyle = (stepType: string) => {
  const baseStyle = {
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: 13,
    lineHeight: 1.8,
  };

  const colorSchemes: Record<string, { bg1: string; bg2: string; border: string; text: string }> = {
    thought: { bg1: "#fff7e6", bg2: "#fffbe6", border: "#ffd591", text: "#d46b08" },
    start: { bg1: "#e6f7ff", bg2: "#f0f8ff", border: "#91d5ff", text: "#1890ff" },
    final: { bg1: "#f6ffed", bg2: "#f5f5f5", border: "#b7eb8f", text: "#52c41a" },
    error: { bg1: "#fff1f0", bg2: "#fff", border: "#ffa39e", text: "#cf1322" },
    interrupted: { bg1: "#fff7e6", bg2: "#fff", border: "#ffd591", text: "#d46b08" },
    paused: { bg1: "#fffbe6", bg2: "#fff", border: "#ffe58f", text: "#d46b08" },
    resumed: { bg1: "#f6ffed", bg2: "#f5f5f5", border: "#b7eb8f", text: "#52c41a" },
    retrying: { bg1: "#e6f7ff", bg2: "#f0f8ff", border: "#91d5ff", text: "#1890ff" },
    observation: { bg1: "#f6ffed", bg2: "#f5f5f5", border: "#b7eb8f", text: "#52c41a" },
    action_tool: { bg1: "#e6f7ff", bg2: "#f0f8ff", border: "#91d5ff", text: "#1890ff" },
    report: { bg1: "#f6ffed", bg2: "#f5f5f5", border: "#b7eb8f", text: "#52c41a" },
  };

  const scheme = colorSchemes[stepType] || colorSchemes.final;
  
  return {
    ...baseStyle,
    background: `linear-gradient(135deg, ${scheme.bg1} 0%, ${scheme.bg2} 100%)`,
    border: `1px solid ${scheme.border}`,
    color: scheme.text,
  };
};

/**
 * GenerateReportView 主组件
 * 【小强修改 2026-03-24】添加 isExpanded 和 onToggle 支持折叠功能
 * 【小强修改 2026-03-24】使用统一的getStepStyle函数，保持视觉风格一致
 */
const GenerateReportView: React.FC<GenerateReportViewProps> = ({ data, isExpanded = true, onToggle }) => {
  const { reports = {} } = data;

  const reportEntries = Object.entries(reports);

  if (reportEntries.length === 0) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        📊 无报告数据
      </div>
    );
  }

  // 使用统一的样式函数，与气泡内其他元素保持视觉一致
  const cardStyle = getStepStyle("report");

  // 【小强修改 2026-03-24】标题行：始终显示报告数量和折叠按钮
  const reportHeader = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        cursor: "pointer",
      }}
      onClick={onToggle}
    >
      <div>
        <CheckCircleOutlined style={{ color: "#52c41a", fontSize: 18, marginRight: 8 }} />
        <span style={{ color: "#52c41a", fontWeight: 600 }}>报告生成完成</span>
        <Tag color="green" style={{ marginLeft: 8 }}>{reportEntries.length} 个报告</Tag>
      </div>
      <span style={{ color: "#1890ff", fontWeight: 500 }}>
        {isExpanded ? "▼ 收起" : "▶ 展开"}
      </span>
    </div>
  );

  return (
    <div>
      {/* 标题行 - 始终显示 */}
      {reportHeader}

      {/* 报告列表 - 仅在展开时显示 */}
      {isExpanded && (
        <>
          {reportEntries.map(([key, report]) => (
            <Card
              key={key}
              size="small"
              style={cardStyle}
              title={
                <div style={{ display: "flex", alignItems: "center" }}>
                  <FileTextOutlined
                    style={{ color: "#1890ff", marginRight: 8 }}
                  />
                  <span style={{ fontWeight: 500 }}>{key}</span>
                </div>
              }
            >
              {/* 文件路径 - 现在 report 就是字符串路径 */}
              {report && (
                <div style={{ marginTop: 6, fontSize: 12, color: "#666" }}>
                  <span>📝 保存路径：</span>
                  <code
                    style={{
                      background: "#f5f5f5",
                      padding: "2px 6px",
                      borderRadius: 4,
                      fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                      fontSize: 12,
                    }}
                  >
                    {report}
                  </code>
                </div>
              )}
            </Card>
          ))}
        </>
      )}
    </div>
  );
};

export default GenerateReportView;
