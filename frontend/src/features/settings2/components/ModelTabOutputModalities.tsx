// 编辑历史: 2026-11-09 小欧 - 新建：② 输出模态只读行（声明橙标/未声明灰字/未知值灰标）自 SettingsPage 拆出 — 小欧-2026-11-09
import React from 'react';
import { Tag, Tooltip } from 'antd';
import { Colors, Spacing } from '@/utils/stepStyles';
import { settingsRowStyle, settingsLabelStyle } from '@/theme/settingsTokens';
import {
  OUTPUT_MODALITY_OPTIONS,
  KNOWN_OUTPUT_MODALITY_VALUES,
} from '../utils/modelUtils';

interface Props {
  value: string[];
}

export const ModelTabOutputModalities: React.FC<Props> = ({ value }) => (
  <div style={settingsRowStyle}>
    <Tooltip title="按厂商/配置声明只读展示（本页不可编辑，声明入口在添加模型流程）；实测见下一行「生成能力验证」">
      <span style={settingsLabelStyle}>输出模态</span>
    </Tooltip>
    <span style={{ flex: 1 }}>
      {OUTPUT_MODALITY_OPTIONS.map((o) => (
        <Tag
          key={o.value}
          // 声明值=生效卡同款橙色底徽标，未声明=灰字
          color={value.includes(o.value) ? 'orange' : undefined}
          style={{
            marginLeft: Spacing.XS,
            color: value.includes(o.value) ? undefined : Colors.TEXT.SECONDARY,
          }}
        >
          {o.label}
        </Tag>
      ))}
      {/* 非可选项（file 等未知值）灰色只读 Tag */}
      {value
        .filter((v) => !KNOWN_OUTPUT_MODALITY_VALUES.has(v))
        .map((v) => (
          <Tag
            key={v}
            style={{
              cursor: 'not-allowed',
              marginLeft: Spacing.XS,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            {v}
          </Tag>
        ))}
    </span>
  </div>
);
