/**
 * 工具信息组件（第13章设计方案）
 * 合并显示 tool_name + tool_params
 * 使用系统样式常量，禁止硬编码
 */
import React from 'react';
import { Typography, Tag } from 'antd';
import { Spacing, Colors, FontSize, FontWeight } from '@/utils/stepStyles';

const { Text } = Typography;

interface ToolInfoProps {
  toolName?: string;
  toolParams?: Record<string, unknown>;
  compact?: boolean;
}

const formatParamValue = (value: unknown): string => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') {
    return value.length > 30 ? `${value.substring(0, 30)}...` : value;
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
};

export const ToolInfo: React.FC<ToolInfoProps> = ({
  toolName,
  toolParams,
  compact = false,
}) => {
  if (!toolName) return null;

  const params = toolParams || {};
  const paramEntries = Object.entries(params).slice(0, compact ? 2 : 5);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: Spacing.XS,
        flexWrap: 'wrap',
      }}
    >
      <Text
        strong
        style={{
          fontSize: FontSize.SECONDARY,
          fontWeight: FontWeight.MEDIUM,
          color: Colors.TEXT.PRIMARY,
        }}
      >
        {toolName}
      </Text>
      {paramEntries.length > 0 && (
        <>
          <Text style={{ color: Colors.TEXT.SECONDARY, fontSize: FontSize.TERTIARY }}>
            (
          </Text>
          {paramEntries.map(([key, value], idx) => (
            <React.Fragment key={key}>
              <Text
                style={{ color: Colors.TEXT.SECONDARY, fontSize: FontSize.TERTIARY }}
              >
                {key}=
              </Text>
              <Tag
                style={{
                  margin: 0,
                  padding: '0 4px',
                  fontSize: FontSize.TERTIARY,
                  lineHeight: '18px',
                  background: Colors.BG.LIGHT,
                  border: 'none',
                }}
              >
                {formatParamValue(value)}
              </Tag>
              {idx < paramEntries.length - 1 && (
                <Text
                  style={{
                    color: Colors.TEXT.SECONDARY,
                    fontSize: FontSize.TERTIARY,
                  }}
                >
                  ,{' '}
                </Text>
              )}
            </React.Fragment>
          ))}
          <Text style={{ color: Colors.TEXT.SECONDARY, fontSize: FontSize.TERTIARY }}>
            )
          </Text>
        </>
      )}
    </div>
  );
};

export default ToolInfo;
