// 编辑历史: 2026-08-27 小欧 - 三堂会审: 删9色彩虹(colorSchemes), 嵌套块改单色左边线(Colors.BORDER.DEFAULT)+淡底(Colors.BG.LIGHT), 去色去框(KISS/DRY)
/**
 * 通用结果数据渲染器（第13章设计方案）
 * 统一渲染工具返回的结构化数据
 * 嵌套块统一中性左边线+淡底，禁止深色背景与多色彩虹
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

// 2026-08-27 小欧 三堂会审C12: 魔法数字提取为命名常量
const MAX_STRING_LENGTH = 100; // 字符串截断阈值
const MAX_INLINE_TAGS = 5; // 数组Tag内联上限
const MAX_INLINE_ENTRIES = 3; // 对象键值内联上限

interface GenericResultRendererProps {
  data?: Record<string, unknown> | null;
  title?: string;
}

// 2026-08-27 小欧 三堂会审: 去9色彩虹, 嵌套块统一中性左边线+淡底(去色去框, KISS/DRY/禁止backward)
// 2026-08-28 小欧 - ④A/a3: 嵌套左线 DEFAULT #d9d9d9→VERTICAL #e8e8e8 与 Pipeline 统一
// 2026-08-28 小欧 v1.3(P1-H1): 嵌套块底由 Colors.BG.LIGHT(#fafafa)填充→transparent, 与 Pipeline/Code 透明左线统一, 消同语义双皮肤
const NEST_BLOCK_BG = 'transparent';            // v1.3 去#fafafa填充, 仅留左线
const NEST_BLOCK_LINE = Colors.BORDER.VERTICAL;  // #e8e8e8 单色左边线

const renderValue = (value: unknown): React.ReactNode => {
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
    if (value.length > MAX_STRING_LENGTH) {
      return (
        <Paragraph
          style={{ margin: 0, fontSize: FontSize.SECONDARY }}
          ellipsis={{ rows: 2, expandable: true }}
        >
          {value}
        </Paragraph>
      );
    }
    return <Text style={{ fontSize: FontSize.SECONDARY }}>{value}</Text>;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return (
      <Text style={{ fontSize: FontSize.SECONDARY }}>{String(value)}</Text>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <Text type="secondary">[]</Text>;
    if (
      value.length <= MAX_INLINE_TAGS &&
      value.every((v) => typeof v !== 'object')
    ) {
      return (
        <div style={{ display: 'flex', gap: Spacing.XS, flexWrap: 'wrap' }}>
          {value.map((v, i) => (
            <Tag key={i} style={{ margin: 0, fontSize: FontSize.TERTIARY }}>
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
          background: NEST_BLOCK_BG,
          borderRadius: Radius.SM,
            borderLeft: `${BorderWidth.THIN}px solid ${NEST_BLOCK_LINE}`,
        }}
      >
        {value.map((v, i) => (
          <div
            key={i}
            style={{ marginBottom: i < value.length - 1 ? Spacing.XS : 0 }}
          >
              {renderValue(v)}
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <Text type="secondary">{'{}'}</Text>;

    if (entries.length <= MAX_INLINE_ENTRIES) {
      return (
        <div style={{ display: 'flex', gap: Spacing.SM, flexWrap: 'wrap' }}>
          {entries.map(([k, v]) => (
            <Text key={k} style={{ fontSize: FontSize.SECONDARY }}>
              <Text type="secondary">{k}:</Text> {renderValue(v)}
            </Text>
          ))}
        </div>
      );
    }

    return (
      <Descriptions
        size="small"
        column={1}
        style={{ fontSize: FontSize.SECONDARY }}
        items={entries.map(([key, val]) => ({
          key,
          label: key,
            children: renderValue(val),
        }))}
      />
    );
  }

  return <Text style={{ fontSize: FontSize.SECONDARY }}>{String(value)}</Text>;
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
            fontSize: FontSize.SECONDARY,
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
