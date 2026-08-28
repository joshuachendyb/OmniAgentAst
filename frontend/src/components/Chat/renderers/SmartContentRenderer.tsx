/**
 * 智能内容渲染组件（第13章设计方案）
 * 根据内容类型自动选择合适的渲染方式
 * - 字符串：直接显示
 * - 对象/数组：JSON格式化显示
 * - 代码：代码块显示
 */
import React from 'react';
import { Typography } from 'antd';
import { Spacing, Colors, FontSize, BorderWidth } from '@/utils/stepStyles';

const { Text, Paragraph } = Typography;

// 2026-08-27 小欧 三堂会审C13: 行高常量化
const LINE_HEIGHT_PX = 20;

interface SmartContentRendererProps {
  content?: unknown;
  maxLines?: number;
}

// 2026-08-27 小欧 修复chat-D: 移除裸花括号作为代码特征, 避免"请设置参数 {timeout:30}"等含花括号普通文本误判为代码块
const isCode = (str: string): boolean => {
  const codeIndicators = [
    'function',
    'class',
    'import',
    'export',
    'const',
    'let',
    'var',
  ];
  const matchCount = codeIndicators.filter((indicator) =>
    str.includes(indicator)
  ).length;
  return matchCount >= 2;
};

const renderString = (str: string, maxLines?: number): React.ReactNode => {
  if (isCode(str)) {
    return (
      <pre
        style={{
          margin: 0,
          padding: Spacing.SM,
          background: 'transparent',
          borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
          borderRadius: 0,
          fontSize: FontSize.TERTIARY,
          overflow: 'auto',
          maxHeight: maxLines ? `${maxLines * LINE_HEIGHT_PX}px` : undefined,
        }}
      >
        {str}
      </pre>
    );
  }

  return (
    <Paragraph
      style={{
        margin: 0,
        fontSize: FontSize.SECONDARY,
        color: Colors.TEXT.PRIMARY,
      }}
      ellipsis={maxLines ? { rows: maxLines, expandable: true } : false}
    >
      {str}
    </Paragraph>
  );
};

const renderObject = (obj: unknown): React.ReactNode => {
  try {
    const json = JSON.stringify(obj, null, 2);
    return (
      <pre
        style={{
          margin: 0,
          padding: Spacing.SM,
          background: 'transparent',
          borderLeft: `2px solid ${Colors.BORDER.VERTICAL}`,
          borderRadius: 0,
          fontSize: FontSize.TERTIARY,
          overflow: 'auto',
          maxHeight: '300px',
        }}
      >
        {json}
      </pre>
    );
  } catch {
    return <Text type="secondary">[无法序列化]</Text>;
  }
};

export const SmartContentRenderer: React.FC<SmartContentRendererProps> = ({
  content,
  maxLines,
}) => {
  if (content === null || content === undefined) {
    return <Text type="secondary">-</Text>;
  }

  if (typeof content === 'string') {
    return renderString(content, maxLines);
  }

  if (typeof content === 'number' || typeof content === 'boolean') {
    return <Text>{String(content)}</Text>;
  }

  if (typeof content === 'object') {
    return renderObject(content);
  }

  return <Text>{String(content)}</Text>;
};

export default SmartContentRenderer;
