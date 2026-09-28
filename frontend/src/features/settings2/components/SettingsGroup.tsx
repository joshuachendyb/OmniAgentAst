// 编辑历史: 2026-09-20 小强 - 新建：组渲染（7.3 动态渲染；6.2 局部脏态汇总；外观预览小卡内联）
// 2026-09-21 小强 - 关于页功能：system 组"关于"小节 header 处集成 AboutFiles（查看配置文件全文 / version 文件全文入口）
// 2026-09-21 小欧 - 实施：预览小卡色/圆角→令牌、提示文字色→Colors.TEXT.SECONDARY
// 2026-09-21 小欧 - 实施：预览小卡改为双态并排对比
// 2026-09-21 小欧 - 全文核查：marginBottom/padding 裸数字 → Spacing.LG/XS/MD 令牌（设计文档 v1.12 铁规）
// 2026-09-21 小欧 - 关于区排版修复：按钮从独立竖排块改为嵌入对应信息行右侧（排版修复）
// 2026-09-21 小欧 - 三堂会审修复：aboutIdx 计数器改为 item.key.includes('path') 判断（防 schema 顺序变化映射错）
// 2026-09-21 小强 - 删死分支 group==='chat'：后端注册表已删 chat 组，该块永不渲染（分组对齐后端唯一源）
// 2026-09-21 小欧 - 渲染修复: sources 缺键回退 ?? 'yaml' → ?? 'default'（后端缺省 source='default'，缺键=默认值语义）
// 2026-09-21 小强 - 系统Tab 3 小节（运维日志/工程目录/关于）：sectionOf 按 logging./paths.logs→运维日志、paths.*→工程目录、app.*→系统参数、其余→关于（对齐后端 system 组 12 项结构）
// 2026-09-23 小欧 - LLM补充采样参数: sectionOf 加 general 组「模型参数」小节（llm.sampling.* + llm.context_limit_default → '模型参数'）
// 2026-09-23 小欧 - trim/compaction配置化: sectionOf 加 tuning.trim.→'裁剪(Trim)'、tuning.compaction.→'压缩(Compaction)' 两独立分块
// 2026-09-23 小欧 - cors_origins 迁系统组: tuning 分支删 network 映射，改挂 system 分支「关于」上方；键名去 tuning 前缀 network.cors_origins — 小欧-2026-09-23
// 2026-09-24 21:36:38 小欧 - tuning.stream_task.→tuning.live_front. 前缀同步(组名改，分组显示名「前后端之间的流/任务/缓存」不动) — 小欧-2026-09-24
// 2026-09-26 小欧（北京老陈指示）: appearance 组内分 2 块 ——
//   块1「登录与准入」= 访问口令 + 免口令 IP 白名单（后端 registry 已把这两项移到本组最前）
//   块2「外观」= 系统语言 / 主题 / 字号（原有项）
//   理由: 准入控制（谁能进得来）与界面外观（语言/主题/字号）是两件事，混在一块会误导 ——
//   例如以为"改外观设置就能改准入"。分组机制复用既有 sectionOf + SectionTitle（与 general/system/tuning 同款），
//   不新造第二套渲染分支。
//   连带: 预览小卡（服务于"字号"）从"组首无条件渲染"改为"随「外观」块首项渲染" ——
//   否则它会孤零零压在「登录与准入」块上方，位置与语义都不对。 — 小欧-2026-09-26
// 2026-09-28 小欧（北京老陈指示）: general 组小节名「模型参数」→「通用兜底模型参数」——
//   该块是全局默认采样参数，单模型可在「模型」Tab 单独覆盖，原名易误读为"当前模型的参数"。纯显示名。 — 小欧-2026-09-28
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
  /**
   * 重新拉取全部设置（secret 项走专用通道落盘后刷新显示）。
   * 2026-09-26 - 小欧 - 三堂会审后修正: secret 写成功后**不能**再用 onChange 去"刷新"——
   *   onChange 是 settings 通道 setter，会把该 key 置脏（useSettings.setValue: baseline 不等 → dirtyKeys=true），
   *   而 secret 已被设计稿在 settings 写路径显式拒绝 → 用户随后"保存本组"必然整组失败。
   */
  onRefresh?: () => void;
}

// 2026-09-22 小欧 - tuning Tab 分块：sectionOf 加 tuning.* 前缀→8 个子组名映射
// 2026-09-23 小欧 - 现 9 个子组名映射（加 trim/compaction；network 迁系统组后剔除）— 小欧-2026-09-23
function sectionOf(group: string, key: string): string | null {
  // ✅ general 组加模型参数小节（仿 system/tuning 分支写法）— 小欧 2026-09-23
  if (group === 'general') {
    // 2026-09-28 小欧: 小节名改「通用兜底模型参数」（全局兜底默认值，单模型值以「模型」Tab 为准）— 小欧-2026-09-28
    if (key.startsWith('llm.sampling.') || key === 'llm.context_limit_default')
      return '通用兜底模型参数';
    return null; // 通用组其余项（workspace/logging/agent.*）保持无小节原样
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
  // 2026-09-26 小欧（北京老陈指示）: appearance 组分 2 块 ——
  //   块1「登录与准入」= 访问口令 + 免口令 IP 白名单（谁能进得来；由后端 registry 放在本组最前两项）
  //   块2「外观」= 系统语言 / 主题 / 字号（原有的界面外观项）
  //   语义切分理由同后端：准入控制 ≠ 外观偏好，混在一块会让人误以为"改外观就能改准入"。
  if (group === 'appearance') {
    if (key.startsWith('security.')) return '登录与准入';
    return '外观';
  }
  if (group === 'tuning') {
    if (key.startsWith('tuning.llm.')) return 'LLM 语义参数';
    if (key.startsWith('tuning.llm_net.')) return 'LLM 网络/超时/连接池';
    if (key.startsWith('tuning.concurrency.')) return '并发配额';
    if (key.startsWith('tuning.agent.')) return 'Agent 循环参数';
    if (key.startsWith('tuning.trim.')) return '裁剪(Trim)';
    if (key.startsWith('tuning.compaction.')) return '压缩(Compaction)';
    if (key.startsWith('tuning.live_front.')) return '前后端之间的流/任务/缓存'; // 2026-09-24 小欧 组名 stream_task→live_front — 小欧-2026-09-24
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
  onRefresh,
}) => {
  let lastSection: string | null = null;
  const fontSize = Number(values['appearance.fontSize'] ?? 14);
  // 外观组分「登录与准入」/「外观」两块后，预览小卡（服务于"字号"这个外观项）
  //   必须随「外观」块一起渲染 —— 否则它会孤零零压在"登录与准入"上方，位置与语义都不对。
  //   故改为在渲染到「外观」块首项时再输出（appearance 组内顺序由后端 registry 保证：准入项在前、外观项在后）。
  const appearancePreview = (
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
  );
  return (
    <div>
      {items.map((item) => {
        const section = sectionOf(group, item.key);
        const header = section && section !== lastSection ? section : null;
        lastSection = section;
        const isAbout = section === '关于';
        // 预览小卡随「外观」块首项输出（不再置于组首，避免压住「登录与准入」块）
        const showAppearancePreview =
          group === 'appearance' && header === '外观';
        return (
          <React.Fragment key={item.key}>
            {header && <SectionTitle title={`── ${header} ──`} />}
            {showAppearancePreview && appearancePreview}
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
                    onRefresh={onRefresh}
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
                onRefresh={onRefresh}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
