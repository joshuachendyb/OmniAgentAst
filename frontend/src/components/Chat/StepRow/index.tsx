/**
 * StepRow组件 - 步骤行主组件（容器）
 * 
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 * @update 2026-04-28 小强 - 第一步：容器三区域背景色设计（Header浅灰/Content白/Footer极浅灰）
 */

import React, { useState, useMemo, useCallback } from "react";
import type { ExecutionStep } from "../../../utils/sse";
import { STEP_LABEL_MAP, STEP_ICON_MAP } from "../constants/stepConstants";
import {
  getStepBadgeStyle,
  getStepLabelStyle,
  isDarkMode,
  darkModeColors,
  type StepType
} from "../../../utils/stepStyles";
import StepHeader from "./StepHeader";
import StepContent from "./StepContent";
import StepFooter from "./StepFooter";

interface StepRowProps {
  step: ExecutionStep;
  taskId?: string;
  stepIndex?: number;
  expandedSteps: Map<number, boolean>;
  toggleExpand: (index: number) => void;
}

/**
 * 容器样式 - 浅色模式静态定义（已废弃，使用dynamicContainerStyle）
 * 第七步：深色模式使用useMemo动态生成，不再使用静态定义
 */
const containerStyle: React.CSSProperties = {
  marginBottom: 12,
  borderRadius: 12,
  background: "#fff",
  border: "1px solid #e8e8e8",
  boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
  overflow: "hidden",
  transition: "all 0.25s ease",
};

/**
 * Header头部样式 - 浅色模式（已废弃，使用dynamicHeaderStyle）
 */
const headerStyle: React.CSSProperties = {
  background: "#f5f5f5",
  padding: "10px 16px",
  borderBottom: "1px solid #eee",
};

/**
 * Content中部样式 - 浅色模式（已废弃，使用dynamicContentStyle）
 */
const contentStyle: React.CSSProperties = {
  background: "#ffffff",
  padding: "16px",
};

/**
 * Footer底部样式 - 浅色模式（已废弃，使用dynamicFooterStyle）
 */
const footerStyle: React.CSSProperties = {
  background: "#fafafa",
  padding: "8px 16px",
  borderTop: "1px solid #eee",
};

const StepRow: React.FC<StepRowProps> = ({ step, taskId: _taskId, stepIndex = 0, expandedSteps, toggleExpand }) => {
  const [_isLoadingMore, _setIsLoadingMore] = useState(false);
  const [_showAllData, _setShowAllData] = useState(false);

  const _isExpanded = expandedSteps.get(stepIndex) ?? true;
  const effectiveType = step.type === 'incident' ? (step as ExecutionStep).incident_value || 'incident' : step.type;
  const label = STEP_LABEL_MAP[effectiveType] || STEP_LABEL_MAP[step.type] || "步骤";
  const icon = STEP_ICON_MAP[effectiveType] || STEP_ICON_MAP[step.type] || "";
  const _executionResult = step.execution_result;

  const badgeStyle = useMemo(() => getStepBadgeStyle(effectiveType as StepType), [effectiveType]);
  const labelStyle = useMemo(() => getStepLabelStyle(effectiveType as StepType), [effectiveType]);

  // 第七步：深色模式动态样式
  const dark = isDarkMode();
  
  const dynamicContainerStyle = useMemo((): React.CSSProperties => ({
    marginBottom: 12,
    borderRadius: 12,
    background: dark ? darkModeColors.container : "#fff",
    border: `1px solid ${dark ? darkModeColors.border : "#e8e8e8"}`,
    boxShadow: dark ? "0 2px 8px rgba(0,0,0,0.3)" : "0 2px 8px rgba(0,0,0,0.06)",
    overflow: "hidden",
    transition: "all 0.25s ease",
  }), [dark]);

  const dynamicHeaderStyle = useMemo((): React.CSSProperties => ({
    background: dark ? darkModeColors.headerBg : "#f5f5f5",
    padding: "10px 16px",
    borderBottom: `1px solid ${dark ? darkModeColors.border : "#eee"}`,
  }), [dark]);

  const dynamicContentStyle = useMemo((): React.CSSProperties => ({
    background: dark ? darkModeColors.contentBg : "#ffffff",
    padding: "16px",
  }), [dark]);

  const dynamicFooterStyle = useMemo((): React.CSSProperties => ({
    background: dark ? darkModeColors.footerBg : "#fafafa",
    padding: "8px 16px",
    borderTop: `1px solid ${dark ? darkModeColors.border : "#eee"}`,
  }), [dark]);

  const textStyle = useMemo((): React.CSSProperties => ({
    color: dark ? darkModeColors.text : "#333",
    wordBreak: "break-word",
    fontSize: 13,
    lineHeight: 1.8,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif",
  }), [dark]);

  // 第七步：深色模式hover效果
  const handleMouseEnter = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.boxShadow = dark ? "0 4px 16px rgba(0,0,0,0.4)" : "0 4px 16px rgba(0,0,0,0.1)";
    e.currentTarget.style.borderColor = dark ? darkModeColors.hoverBorder : "#d9d9d9";
  }, [dark]);

  const handleMouseLeave = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.boxShadow = dark ? "0 2px 8px rgba(0,0,0,0.3)" : "0 2px 8px rgba(0,0,0,0.06)";
    e.currentTarget.style.borderColor = dark ? darkModeColors.border : "#e8e8e8";
  }, [dark]);

  // 第六步P2：焦点样式
  const handleFocus = useCallback((e: React.FocusEvent<HTMLDivElement>) => {
    e.currentTarget.style.outline = "2px solid #1890ff";
    e.currentTarget.style.outlineOffset = "2px";
  }, []);

  const handleBlur = useCallback((e: React.FocusEvent<HTMLDivElement>) => {
    e.currentTarget.style.outline = "none";
  }, []);

  const [hasMore, setHasMore] = useState(false);

  // 2026-04-28 小强修改：第六步添加无障碍ARIA标签
  const effectiveLabel = STEP_LABEL_MAP[effectiveType] || STEP_LABEL_MAP[step.type] || "步骤";

  return (
    // 第六步无障碍优化：添加role和aria-label，添加焦点样式
    // 第七步深色模式：使用动态样式
    <div 
      style={dynamicContainerStyle} 
      onMouseEnter={handleMouseEnter} 
      onMouseLeave={handleMouseLeave}
      onFocus={handleFocus}
      onBlur={handleBlur}
      role="group"
      aria-label={`执行步骤 ${step.step || ''} ${effectiveLabel}`}
      tabIndex={0}
    >
      
      {/* Header头部 - 浅灰色背景 */}
      <div style={dynamicHeaderStyle} aria-label="步骤头部区域">
        <StepHeader 
          step={step}
          badgeStyle={badgeStyle}
          labelStyle={labelStyle}
          label={label}
          icon={icon}
        />
      </div>
      
      {/* Content中部 - 白色背景 */}
      <div style={dynamicContentStyle} aria-label="步骤内容区域">
        <StepContent
          step={step}
          stepIndex={stepIndex}
          expandedSteps={expandedSteps}
          toggleExpand={toggleExpand}
          contentStyle={textStyle}
        />
      </div>
      
      {/* Footer底部 - 极浅灰色背景 */}
      <div style={dynamicFooterStyle} aria-label="步骤底部区域">
        <StepFooter
          step={step}
          hasMore={hasMore}
          onLoadMore={() => setHasMore(false)}
        />
      </div>
    </div>
  );
};

export default React.memo(StepRow);
