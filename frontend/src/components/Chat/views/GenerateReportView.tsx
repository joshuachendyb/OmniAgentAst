/**
 * GenerateReportView - generate_report 工具结果渲染组件
 *
 * 显示报告生成结果
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-24
 */

import React from "react";
import { Tag } from "antd";
import { CheckCircleOutlined, FileTextOutlined } from "@ant-design/icons";
import { 
  getStepStyle, 
  getStepLabelStyle,
  getStepContentStyle,
  FontSize,
  FontWeight,
  Colors,
  type StepType 
} from "../../../utils/stepStyles";

interface GenerateReportViewProps {
  data: {
    reports?: Record<string, string>;
  };
  isExpanded?: boolean;
  onToggle?: () => void;
}

/**
 * GenerateReportView 主组件
 * 【小强修改 2026-03-24】使用inline布局，标签和路径一行显示
 */
const GenerateReportView: React.FC<GenerateReportViewProps> = ({ data, isExpanded = true, onToggle }) => {
  const { reports = {} } = data;

  const reportEntries = Object.entries(reports);

  if (reportEntries.length === 0) {
    return (
      <div style={{ 
        color: Colors.TEXT.TERTIARY, 
        fontStyle: "italic",
        fontSize: FontSize.TERTIARY,
      }}>
        📊 无报告数据
      </div>
    );
  }

  return (
    <div style={getStepStyle("report" as StepType)}>
      {/* 标题行：报告状态 - 始终显示，inline布局 */}
      <div style={{ 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "space-between",
        cursor: onToggle ? "pointer" : "default",
      }} onClick={onToggle}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <CheckCircleOutlined style={{ color: Colors.SUCCESS, fontSize: 16 }} />
          <span style={getStepContentStyle("report" as StepType, "primary")}>
            报告生成完成
          </span>
          <Tag color="green" style={{ margin: 0, fontSize: FontSize.SMALL }}>
            {reportEntries.length} 个报告
          </Tag>
        </div>
        {onToggle && (
          <span style={{ 
            color: Colors.INFO, 
            fontWeight: FontWeight.MEDIUM,
            fontSize: FontSize.TERTIARY,
          }}>
            {isExpanded ? "▼ 收起" : "▶ 展开"}
          </span>
        )}
      </div>

      {/* 报告列表 - 仅在展开时显示 */}
      {isExpanded && (
        <div style={{ marginTop: 8 }}>
          {reportEntries.map(([key, report]) => (
            <div 
              key={key}
              style={{ 
                display: "flex", 
                alignItems: "center", 
                gap: 8,
                padding: "4px 0",
                borderBottom: reportEntries.indexOf([key, report]) < reportEntries.length - 1 
                  ? `1px solid ${Colors.BORDER.LIGHT}` 
                  : "none",
              }}
            >
              {/* 报告类型标签 */}
              <span style={getStepLabelStyle("report" as StepType)}>
                <FileTextOutlined style={{ fontSize: 12 }} />
                {key}
              </span>
              
              {/* 文件路径 - 一行显示，不分行 */}
              {report && (
                <span style={{ 
                  ...getStepContentStyle("report" as StepType, "secondary"),
                  fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                  fontSize: FontSize.CODE,
                  wordBreak: "break-all",
                  flex: 1,
                }}>
                  {report}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default GenerateReportView;
