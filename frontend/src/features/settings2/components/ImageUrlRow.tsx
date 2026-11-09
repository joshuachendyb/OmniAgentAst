// 编辑历史: 2026-11-09 小欧 - 新建：Image_URL 外链检测地址行（registry hidden 项就地配置，失焦/回车即存） — 小欧-2026-11-09
import React from 'react';
import { Input } from 'antd';
import { settingsRowStyle, settingsControl } from '@/theme/settingsTokens';
import { HelpLabel, TipContent } from './Hint';

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
}

export const ImageUrlRow: React.FC<Props> = ({ value, onChange, onSave }) => (
  <div style={settingsRowStyle}>
    <HelpLabel
      title={
        <TipContent>
          外链验证腿把这里的公网图片地址交给厂商，由厂商接口自己抓取
          <div style={{ opacity: 0.8 }}>留空＝只测内联（外链不写结论）</div>
        </TipContent>
      }
    >
      Image_URL
    </HelpLabel>
    <span style={{ flex: 1 }}>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onSave}
        onPressEnter={(e) => (e.target as HTMLInputElement).blur()}
        style={{ width: settingsControl.baseUrlWidth }}
      />
    </span>
  </div>
);
