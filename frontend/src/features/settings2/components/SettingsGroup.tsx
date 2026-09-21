// 编辑历史: 2026-09-20 小强 - 新建：组渲染（7.3 动态渲染；6.2 局部脏态汇总；外观预览小卡内联）
// 2026-09-21 小强 - 关于页功能：system 组"关于"小节 header 处集成 AboutFiles（查看配置文件全文 / version 文件全文入口）
// 2026-09-21 小欧 - P0-2+P0-3：预览小卡色/圆角→令牌、提示文字色→Colors.TEXT.SECONDARY（[58] P0-2/P0-3）
// 2026-09-21 小欧 - P2-5：预览小卡改为双态并排对比（[58] P2-5）
// 2026-09-21 小欧 - 全文逐章核查：marginBottom/padding 裸数字 → Spacing.LG/XS/MD 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小欧 - 关于区排版修复：按钮从独立竖排块改为嵌入对应信息行右侧（排版修复）
// 2026-09-21 小欧 - 三堂会审修复：aboutIdx 计数器改为 item.key.includes('path') 判断（防 schema 顺序变化映射错）
// 2026-09-21 小强 - 删死分支 group==='chat'：后端注册表已删 chat 组，该块永不渲染（分组对齐后端唯一源）
import React from 'react';
import { Card } from 'antd';
import { FontSize, Colors, Radius, Spacing } from '@/utils/stepStyles';
import type {
  SettingSchemaItem,
  SettingSource,
} from '@/services/api/settings.api';
import { SettingRow } from './SettingRow';
import { SectionTitle } from './SectionTitle';
import { AboutFiles } from './AboutFiles';

interface Props {
  group: string;
  items: SettingSchemaItem[];
  values: Record<string, unknown>;
  sources: Record<string, SettingSource>;
  dirtyKeys: Record<string, boolean>;
  highlightKey: string | null;
  onChange: (group: string, key: string, value: unknown) => void;
}

function sectionOf(group: string, key: string): string | null {
  if (group !== 'system') return null;
  if (key.startsWith('app.')) return '系统参数';
  if (key.startsWith('logging.')) return '运维日志';
  return '关于';
}

export const SettingsGroup: React.FC<Props> = ({
  group,
  items,
  values,
  sources,
  dirtyKeys,
  highlightKey,
  onChange,
}) => {
  let lastSection: string | null = null;
  const fontSize = Number(values['appearance.fontSize'] ?? 14);
  return (
    <div>
      {group === 'appearance' && (
        <Card
          size="small"
          style={{ marginBottom: Spacing.LG }}
          title="预览小卡（改下面控件，这里实时变）"
        >
          <div style={{ display: 'flex', gap: Spacing.MD, alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY, marginBottom: Spacing.XS }}>紧凑</div>
              <div
                style={{
                  fontSize,
                  padding: Spacing.XS,
                  background: Colors.BG.TERTIARY,
                  borderRadius: Radius.DEFAULT,
                }}
              >
                示例消息气泡 4px
              </div>
            </div>
            <div>
              <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY, marginBottom: Spacing.XS }}>舒适</div>
              <div
                style={{
                  fontSize,
                  padding: Spacing.LG,
                  background: Colors.BG.TERTIARY,
                  borderRadius: Radius.DEFAULT,
                }}
              >
                示例消息气泡 12px
              </div>
            </div>
          </div>
        </Card>
      )}
      {items.map((item) => {
        const section = sectionOf(group, item.key);
        const header = section && section !== lastSection ? section : null;
        lastSection = section;
        const isAbout = section === '关于';
        return (
          <React.Fragment key={item.key}>
            {header && <SectionTitle title={`── ${header} ──`} />}
            {isAbout ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: Spacing.SM }}>
                <div style={{ flex: 1 }}>
                  <SettingRow
                    item={item}
                    value={values[item.key]}
                    source={sources[item.key] ?? 'yaml'}
                    dirty={!!dirtyKeys[item.key]}
                    highlight={highlightKey === item.key}
                    onChange={(v) => onChange(group, item.key, v)}
                  />
                </div>
                <AboutFiles kind={item.key.includes('path') ? 'config' : 'version'} />
              </div>
            ) : (
              <SettingRow
                item={item}
                value={values[item.key]}
                source={sources[item.key] ?? 'yaml'}
                dirty={!!dirtyKeys[item.key]}
                highlight={highlightKey === item.key}
                onChange={(v) => onChange(group, item.key, v)}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
