/**
 * StepRow组件 - 步骤行主组件（容器）
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React, { useState, useMemo, useCallback } from "react";
import type { ExecutionStep } from "../../../utils/sse";
import { STEP_LABEL_MAP, STEP_ICON_MAP } from "../constants/stepConstants";
import {
  getStepBadgeStyle,
  getStepLabelStyle,
  getTimestampStyle,
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

const StepRow: React.FC<StepRowProps> = ({ step, taskId: _taskId, stepIndex = 0, expandedSteps, toggleExpand }) => {
  const [_isLoadingMore, _setIsLoadingMore] = useState(false);
  const [_showAllData, setShowAllData] = useState(false);

  const isExpanded = expandedSteps.get(stepIndex) ?? true;
  const effectiveType = step.type === 'incident' ? (step as any).incident_value || 'incident' : step.type;
  const label = STEP_LABEL_MAP[effectiveType] || STEP_LABEL_MAP[step.type] || "步骤";
  const icon = STEP_ICON_MAP[effectiveType] || STEP_ICON_MAP[step.type] || "";
  const executionResult = step.execution_result;

  const badgeStyle = useMemo(() => getStepBadgeStyle(effectiveType as StepType), [effectiveType]);
  const labelStyle = useMemo(() => getStepLabelStyle(effectiveType as StepType), [effectiveType]);

  const contentStyle = useMemo((): React.CSSProperties => ({
    color: "#333",
    wordBreak: "break-word",
    fontSize: 13,
    lineHeight: 1.8,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif",
  }), []);

  const handleMouseEnter = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.background = "rgba(0,0,0,0.04)";
    e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
  }, []);

  const handleMouseLeave = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.background = "rgba(0,0,0,0.02)";
    e.currentTarget.style.boxShadow = "none";
  }, []);

  const handleLinkMouseEnter = useCallback((e: React.MouseEvent<HTMLSpanElement>) => {
    e.currentTarget.style.color = "#096dd9";
  }, []);

  const handleLinkMouseLeave = useCallback((e: React.MouseEvent<HTMLSpanElement>) => {
    e.currentTarget.style.color = "#1890ff";
  }, []);

  const handleLoadMore = useCallback(() => {
    setShowAllData(true);
  }, []);

  const getPageData = () => {
    const rawData = executionResult as any;
    const allData = rawData?.matches || rawData?.entries || rawData?.results || [];
    const FRONTEND_PAGE_SIZE = 100;
    
    if (_showAllData) {
      return { displayData: allData, hasMore: false };
    }
    
    if (allData.length > FRONTEND_PAGE_SIZE) {
      return { displayData: allData.slice(0, FRONTEND_PAGE_SIZE), hasMore: true };
    }
    
    return { displayData: allData, hasMore: false };
  };

  const { hasMore } = getPageData();

  return (
    <div style={{ 
      marginBottom: 8, 
      marginRight: 30,
      padding: "8px 12px",
      borderRadius: 8,
      background: "rgba(0,0,0,0.02)",
      transition: "all 0.2s ease",
    }}
    onMouseEnter={handleMouseEnter}
    onMouseLeave={handleMouseLeave}
    >
      <StepHeader 
        step={step}
        badgeStyle={badgeStyle}
        labelStyle={labelStyle}
        label={label}
        icon={icon}
      />
      
      <StepContent
        step={step}
        stepIndex={stepIndex}
        expandedSteps={expandedSteps}
        toggleExpand={toggleExpand}
        contentStyle={contentStyle}
        handleLoadMore={handleLoadMore}
        handleLinkMouseEnter={handleLinkMouseEnter}
        handleLinkMouseLeave={handleLinkMouseLeave}
      />
      
      <StepFooter
        step={step}
        hasMore={hasMore}
        onLoadMore={handleLoadMore}
        onLinkMouseEnter={handleLinkMouseEnter}
        onLinkMouseLeave={handleLinkMouseLeave}
      />
    </div>
  );
};

export default React.memo(StepRow);
