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
import { getStepStyle, type StepType } from "../../../utils/stepStyles";

interface GenerateReportViewProps {
  data: {
    reports?: Record<string, string>;
  };
  isExpanded?: boolean;
  onToggle?: () => void;
}



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
  const cardStyle = getStepStyle("report" as StepType);

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
