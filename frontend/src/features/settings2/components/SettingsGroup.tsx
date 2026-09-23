// 编辑历史: 2026-09-20 小强 - 新建：组渲染（7.3 动态渲染；6.2 局部脏态汇总；外观预览小卡内联）
// 2026-09-21 小强 - 关于页功能：system 组"关于"小节 header 处集成 AboutFiles（查看配置文件全文 / version 文件全文入口）
// 2026-09-21 小欧 - P0-2+P0-3：预览小卡色/圆角→令牌、提示文字色→Colors.TEXT.SECONDARY（[58] P0-2/P0-3）
// 2026-09-21 小欧 - P2-5：预览小卡改为双态并排对比（[58] P2-5）
// 2026-09-21 小欧 - 全文逐章核查：marginBottom/padding 裸数字 → Spacing.LG/XS/MD 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小欧 - 关于区排版修复：按钮从独立竖排块改为嵌入对应信息行右侧（排版修复）
// 2026-09-21 小欧 - 三堂会审修复：aboutIdx 计数器改为 item.key.includes('path') 判断（防 schema 顺序变化映射错）
// 2026-09-21 小强 - 删死分支 group==='chat'：后端注册表已删 chat 组，该块永不渲染（分组对齐后端唯一源）
// 2026-09-21 小欧 - [59]B-10 渲染: sources 缺键回退 ?? 'yaml' → ?? 'default'（后端缺省 source='default'，缺键=默认值语义）
// 2026-09-21 小强 - 系统Tab 3 小节（运维日志/工程目录/关于）：sectionOf 按 logging./paths.logs→运维日志、paths.*→工程目录、app.*→系统参数、其余→关于（对齐后端 system 组 12 项结构）
// 2026-09-23 小欧 - [64] LLM补充采样参数: sectionOf 加 general 组「模型参数」小节（llm.sampling.* + llm.context_limit_default → '模型参数'）
// 2026-09-23 小欧 - trim/compaction配置化: sectionOf 加 tuning.trim.→'裁剪(Trim)'、tuning.compaction.→'压缩(Compaction)' 两独立分块
// 2026-09-23 小欧 - cors_origins 迁系统组: tuning 分支删 network 映射，改挂 system 分支「关于」上方；键名去 tuning 前缀 network.cors_origins — 小欧-2026-09-23
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

// 2026-09-22 小欧 - [61] tuning Tab 分块：sectionOf 加 tuning.* 前缀→8 个子组名映射
// 2026-09-23 小欧 - 现 9 个子组名映射（加 trim/compaction；network 迁系统组后剔除）— 小欧-2026-09-23
function sectionOf(group: string, key: string): string | null {
  // ✅ general 组加模型参数小节（仿 system/tuning 分支写法）— 小欧 2026-09-23
  if (group === 'general') {
    if (key.startsWith('llm.sampling.') || key === 'llm.context_limit_default') return '模型参数';
    return null;  // 通用组其余项（workspace/logging/agent.*）保持无小节原样
  }
  if (group === 'system') {
    // 2026-09-21 小强 - 系统Tab 3 小节：运维日志(配置+日志目录只读) / 工程目录(6 只读) / 关于
    // 2026-09-23 小欧 - cors_origins 自 tuning 迁入系统组：关于上方新增「网络」分块，键名 network.cors_origins — 小欧-2026-09-23
    if (key.startsWith('logging.') || key === 'paths.logs') return '运维日志';
    if (key.startsWith('paths.')) return '工程目录';
    if (key.startsWith('app.')) return '系统参数';
    if (key.startsWith('network.')) return '网络';
    return '关于';
  }
  if (group === 'tuning') {
    if (key.startsWith('tuning.llm.')) return 'LLM 语义参数';
    if (key.startsWith('tuning.llm_net.')) return 'LLM 网络/超时/连接池';
    if (key.startsWith('tuning.concurrency.')) return '并发配额';
    if (key.startsWith('tuning.agent.')) return 'Agent 循环参数';
    if (key.startsWith('tuning.trim.')) return '裁剪(Trim)';
    if (key.startsWith('tuning.compaction.')) return '压缩(Compaction)';
    if (key.startsWith('tuning.stream_task.')) return '流/任务/缓存';
    if (key.startsWith('tuning.hitl.')) return '人工确认';
    if (key.startsWith('tuning.content.')) return '内容截断';
  }
  return null;
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
          <div
            style={{
              display: 'flex',
              gap: Spacing.MD,
              alignItems: 'flex-start',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.SECONDARY,
                  marginBottom: Spacing.XS,
                }}
              >
                紧凑
              </div>
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
              <div
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.SECONDARY,
                  marginBottom: Spacing.XS,
                }}
              >
                舒适
              </div>
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
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: Spacing.SM,
                }}
              >
                <div style={{ flex: 1 }}>
                  <SettingRow
                    item={item}
                    value={values[item.key]}
                    source={sources[item.key] ?? 'default'}
                    dirty={!!dirtyKeys[item.key]}
                    highlight={highlightKey === item.key}
                    onChange={(v) => onChange(group, item.key, v)}
                  />
                </div>
                <AboutFiles
                  kind={item.key.includes('path') ? 'config' : 'version'}
                />
              </div>
            ) : (
              <SettingRow
                item={item}
                value={values[item.key]}
                source={sources[item.key] ?? 'default'}
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
