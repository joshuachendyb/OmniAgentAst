/**
 * 通用结果数据渲染器（第13章设计方案）
 * 统一渲染工具返回的结构化数据
 * 使用9种浅色方案，禁止深色背景
 */
import React from 'react';
import { Typography, Descriptions, Tag, Image } from 'antd';
import {
  Spacing,
  Colors,
  FontSize,
  Radius,
  BorderWidth,
} from '@/utils/stepStyles';

const { Text, Paragraph } = Typography;

interface GenericResultRendererProps {
  data?: Record<string, unknown> | null;
  title?: string;
}

const colorSchemes = [
  { bg: Colors.BG.LIGHT, border: Colors.PRIMARY },
  { bg: '#E6F7FF', border: '#1890FF' },
  { bg: '#FFF7E6', border: '#FA8C16' },
  { bg: '#F6FFED', border: '#52C41A' },
  { bg: '#FFF1F0', border: '#FF4D4F' },
  { bg: '#F9F0FF', border: '#722ED1' },
  { bg: '#E6FFFB', border: '#13C2C2' },
  { bg: '#FFF0F6', border: '#EB2F96' },
  { bg: '#F0F5FF', border: '#2F54EB' },
];

const renderValue = (value: unknown, depth = 0): React.ReactNode => {
  if (value === null || value === undefined) {
    return <Text type="secondary">-</Text>;
  }

  if (typeof value === 'string') {
    if (
      value.startsWith('data:image') ||
      value.match(/\.(jpg|jpeg|png|gif|webp)$/i)
    ) {
      return (
        <Image src={value} width={100} style={{ borderRadius: Radius.SM }} />
      );
    }
    if (value.length > 100) {
      return (
        <Paragraph
          style={{ margin: 0, fontSize: FontSize.SM }}
          ellipsis={{ rows: 2, expandable: true }}
        >
          {value}
        </Paragraph>
      );
    }
    return <Text style={{ fontSize: FontSize.SM }}>{value}</Text>;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return <Text style={{ fontSize: FontSize.SM }}>{String(value)}</Text>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <Text type="secondary">[]</Text>;
    if (value.length <= 5 && value.every((v) => typeof v !== 'object')) {
      return (
        <div style={{ display: 'flex', gap: Spacing.XS, flexWrap: 'wrap' }}>
          {value.map((v, i) => (
            <Tag key={i} style={{ margin: 0, fontSize: FontSize.XS }}>
              {String(v)}
            </Tag>
          ))}
        </div>
      );
    }
    return (
      <div
        style={{
          padding: Spacing.XS,
          background: colorSchemes[depth % colorSchemes.length].bg,
          borderRadius: Radius.SM,
          borderLeft: `${BorderWidth.THIN}px solid ${colorSchemes[depth % colorSchemes.length].border}`,
        }}
      >
        {value.map((v, i) => (
          <div
            key={i}
            style={{ marginBottom: i < value.length - 1 ? Spacing.XS : 0 }}
          >
            {renderValue(v, depth + 1)}
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <Text type="secondary">{'{}'}</Text>;

    if (entries.length <= 3) {
      return (
        <div style={{ display: 'flex', gap: Spacing.SM, flexWrap: 'wrap' }}>
          {entries.map(([k, v]) => (
            <Text key={k} style={{ fontSize: FontSize.SM }}>
              <Text type="secondary">{k}:</Text> {renderValue(v, depth + 1)}
            </Text>
          ))}
        </div>
      );
    }

    return (
      <Descriptions
        size="small"
        column={1}
        style={{ fontSize: FontSize.SM }}
        items={entries.map(([key, val]) => ({
          key,
          label: key,
          children: renderValue(val, depth + 1),
        }))}
      />
    );
  }

  return <Text style={{ fontSize: FontSize.SM }}>{String(value)}</Text>;
};

export const GenericResultRenderer: React.FC<GenericResultRendererProps> = ({
  data,
  title,
}) => {
  if (!data) return null;

  return (
    <div>
      {title && (
        <Text
          strong
          style={{
            display: 'block',
            marginBottom: Spacing.XS,
            fontSize: FontSize.SM,
            color: Colors.TEXT.PRIMARY,
          }}
        >
          {title}
        </Text>
      )}
      {renderValue(data)}
    </div>
  );
};

export default GenericResultRenderer;
