/**
 * 智能内容渲染组件（第13章设计方案）
 * 根据内容类型自动选择合适的渲染方式
 * - 字符串：直接显示
 * - 对象/数组：JSON格式化显示
 * - 代码：代码块显示
 */
import React from 'react';
import { Typography } from 'antd';
import { Spacing, Colors, FontSize, Radius } from '@/utils/stepStyles';

const { Text, Paragraph } = Typography;

interface SmartContentRendererProps {
  content?: unknown;
  maxLines?: number;
}

const isCode = (str: string): boolean => {
  const codeIndicators = [
    '{',
    '}',
    'function',
    'class',
    'import',
    'export',
    'const',
    'let',
    'var',
  ];
  return codeIndicators.some((indicator) => str.includes(indicator));
};

const renderString = (str: string, maxLines?: number): React.ReactNode => {
  if (isCode(str)) {
    return (
      <pre
        style={{
          margin: 0,
          padding: Spacing.SM,
          background: Colors.BG.LIGHT,
          borderRadius: Radius.SM,
          fontSize: FontSize.XS,
          overflow: 'auto',
          maxHeight: maxLines ? `${maxLines * 20}px` : undefined,
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
        fontSize: FontSize.SM,
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
          background: Colors.BG.LIGHT,
          borderRadius: Radius.SM,
          fontSize: FontSize.XS,
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
