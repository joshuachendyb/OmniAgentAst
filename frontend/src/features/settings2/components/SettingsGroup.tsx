// 编辑历史: 2026-09-20 小强 - 新建：组渲染（7.3 动态渲染；6.2 局部脏态汇总；外观预览小卡内联）
// 2026-09-21 小强 - 关于页功能：system 组"关于"小节 header 处集成 AboutFiles（查看配置文件全文 / version 文件全文入口）
// 2026-09-21 小欧 - 实施：预览小卡色/圆角→令牌、提示文字色→Colors.TEXT.SECONDARY
// 2026-09-21 小欧 - 实施：预览小卡改为双态并排对比
// 2026-09-21 小欧 - 全文核查：marginBottom/padding 裸数字 → Spacing.LG/XS/MD 令牌（设计文档 v1.12 铁规）
// 2026-09-21 小欧 - 关于区排版修复：按钮从独立竖排块改为嵌入对应信息行右侧（排版修复）
// 2026-09-21 小欧 - 映射修正：aboutIdx 计数器改为 item.key.includes('path') 判断（防 schema 顺序变化映射错）
// 2026-09-21 小强 - 删死分支 group==='chat'：后端注册表已删 chat 组，该块永不渲染（分组对齐后端唯一源）
// 2026-09-21 小欧 - 渲染修复: sources 缺键回退 ?? 'yaml' → ?? 'default'（后端缺省 source='default'，缺键=默认值语义）
// 2026-09-21 小强 - 系统Tab 3 小节（运维日志/工程目录/关于）：sectionOf 按 logging./paths.logs→运维日志、paths.*→工程目录、app.*→系统参数、其余→关于（对齐后端 system 组 12 项结构）
// 2026-09-23 小欧 - LLM补充采样参数: sectionOf 加 general 组「模型参数」小节（llm.sampling.* + llm.context_length_default → '模型参数'）
// 2026-09-23 小欧 - trim/compaction配置化: sectionOf 加 tuning.trim.→'裁剪(Trim)'、tuning.compaction.→'压缩(Compaction)' 两独立分块
// 2026-09-23 小欧 - cors_origins 迁系统组: tuning 分支删 network 映射，改挂 system 分支「关于」上方；键名去 tuning 前缀 network.cors_origins — 小欧-2026-09-23
// 2026-09-24 21:36:38 小欧 - tuning.stream_task.→tuning.live_front. 前缀同步(组名改，分组显示名「前后端之间的流/任务/缓存」不动) — 小欧-2026-09-24
// 2026-09-26 小欧: appearance 组内分 2 块 ——
//   块1「登录与准入」= 访问口令 + 免口令 IP 白名单（后端 registry 已把这两项移到本组最前）
//   块2「外观」= 系统语言 / 主题 / 字号（原有项）
//   理由: 准入控制（谁能进得来）与界面外观（语言/主题/字号）是两件事，混在一块会误导 ——
//   例如以为"改外观设置就能改准入"。分组机制复用既有 sectionOf + SectionTitle（与 general/system/tuning 同款），
//   不新造第二套渲染分支。
//   连带: 预览小卡（服务于"字号"）从"组首无条件渲染"改为"随「外观」块首项渲染" ——
//   否则它会孤零零压在「登录与准入」块上方，位置与语义都不对。 — 小欧-2026-09-26
// 2026-09-28 小欧: general 组小节名「模型参数」→「通用兜底模型参数」——
//   该块是全局默认采样参数，单模型可在「模型」Tab 单独覆盖，原名易误读为"当前模型的参数"。纯显示名。 — 小欧-2026-09-28
// 2026-10-05 小欧 - appearance 组加前缀支, 新分节「step渲染控制」: 不加会被 return '外观' 吞掉 — 小欧-2026-10-05
// 编辑历史: 2026-10-06 小欧 - security 组加块2「安全策略说明」: sectionOf 归块 + items.map 后追加
//   DirectoryAccessNote(纯说明无配置项故不进 registry, 与 appearancePreview 同款做法)。 — 小欧-2026-10-06
// 2026-10-13 小欧 - 缩进修复: sandbox/tuning 两分支归位 sectionOf 内(此前顶格, 与块结构错位)。纯排版, 零行为。 — 小欧-2026-10-13
// 2026-10-18 小欧 - security 组由「一律归『人工确认』」改为按组名进键名前缀拆三节:
//   security.system.* → 系统 / security.hitl.* → HTL人工确认 / security.trust.* → 信任。
//   原写法把开关、延迟秒数、信任天数全塞进「人工确认」一节, 归属与实际语义不符。
//   前缀即可判归属, 故用 if 直判而非新增分组注册机制(仅三个前缀, 注册表属过度设计);
//   块2「安全策略说明」仍为纯说明无配置项, 不进 registry, 仍在 items.map 后追加 DirectoryAccessNote。
// 2026-10-18 小欧 - 危险键随子命名空间跟改: security.hitl_enabled → security.hitl.enabled、
//   security.confirmDangerousOps → security.system.confirm_dangerous_ops, DANGEROUS_KEYS/LABELS/EFFECTS 三处同步。
// 2026-10-18 小欧 - 注释精简冗余标注, 技术说明原样保留。
// 2026-11-01 小欧 - 键名统一: sectionOf 判据 llm.context_limit_default → llm.context_length_default
//   （后端 settings_registry 键已改名；此处不改则「通用兜底模型参数」小节永远匹配不到） — 小欧-2026-11-01
// 2026-11-03 小欧 - sectionOf system 分支增「数据治理」分组: system.chat_retention_days 匹配到后单列一节渲染 — 小欧-2026-11-03
// 2026-11-03 小欧 - 系统组现状更正(L10/L80 的「3 小节/12 项」已过期): 实际 5 小节 = 运维日志/工程目录/网络/
//   数据治理/关于, 共 13 项; 无 app.* 项故「系统参数」小节不渲染 — 小欧-2026-11-03
// 2026-11-08 小欧 - sectionOf 增 media 分支: 本机图片(上限/压缩) 与 外链图片(转发/探测地址) 分两节 — 小欧-2026-11-08
// 2026-11-09 小欧 - visibleItems 过滤 hidden 项(media.probe_image_url 已迁②Image_URL 行就地配置): 键仍留 schema 供读写链 — 小欧-2026-11-09
// 2026-11-11 小欧 - 三个验证素材地址(probe_image_url/video/audio)由 hidden 回媒体页直接显示: visibleItems 过滤逻辑保留
//   (防御性, 其它组仍可能注册 hidden 项), media 组现无 hidden 项 — 小欧-2026-11-11
// 2026-11-12 小欧 - 预览小卡按 [31] §4.5 重做: 拆「界面密度双档 + 阅读区字号三档」双区, 密度样例按真实
//   密度参数渲染(DENSITY_PAD 留白 + controlScale 控件高), 字号样例三行纯文字, 当前档加主色边框 — 小欧-2026-11-12
import React from 'react';
import { Card } from 'antd';
import { FontSize, Colors, Radius, Spacing } from '@/utils/stepStyles';
import {
  APPEARANCE_DENSITIES,
  APPEARANCE_FONT_SIZES,
  clampDensity,
  clampFontSize,
} from '@/constants/appearancePrefs';
import { DENSITY_PAD } from '@/utils/markdownStyles';
import { controlHeightByDensity } from '@/theme/controlScale';
import type {
  SettingSchemaItem,
  SettingSource,
} from '@/services/api/settings.api';
import { SettingRow } from './SettingRow';
import { SectionTitle } from './SectionTitle';
import { AboutFiles } from './AboutFiles';
import { DirectoryAccessNote } from './DirectoryAccessNote';

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
   * 2026-09-26 - 小欧 - secret 写成功后**不能**再用 onChange 去"刷新"——
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
    if (key.startsWith('llm.sampling.') || key === 'llm.context_length_default')
      return '通用兜底模型参数';
    return null; // 通用组其余项（workspace/logging/agent.*）保持无小节原样
  }
  if (group === 'system') {
    // 2026-09-21 小强 - 系统Tab 3 小节：运维日志(配置+日志目录只读) / 工程目录(6 只读) / 关于
    // 2026-11-03 小欧 - 更正: 现 5 小节(运维日志/工程目录/网络/数据治理/关于), system 组 13 项;
    //   无 app.* 项, 下方 app. 分支保留为将来扩展兜底 — 小欧-2026-11-03
    // 2026-09-23 小欧 - cors_origins 自 tuning 迁入系统组：关于上方新增「网络」分块，键名 network.cors_origins — 小欧-2026-09-23
    if (key.startsWith('logging.') || key === 'paths.logs') return '运维日志';
    if (key.startsWith('paths.')) return '工程目录';
    if (key.startsWith('app.')) return '系统参数';
    if (key.startsWith('network.')) return '网络';
    if (key === 'system.chat_retention_days') return '数据治理';
    return '关于';
  }
  // 2026-09-26 小欧: appearance 组分 2 块 ——
  //   块1「登录与准入」= 访问口令 + 免口令 IP 白名单（谁能进得来；由后端 registry 放在本组最前两项）
  //   块2「外观」= 系统语言 / 主题 / 字号（原有的界面外观项）
  //   语义切分理由同后端：准入控制 ≠ 外观偏好，混在一块会让人误以为"改外观就能改准入"。
  if (group === 'appearance') {
    if (key.startsWith('security.')) return '登录与准入';
    // 2026-10-05 小欧 - step渲染控制分组: 令两个 step 渲染开关独立成节,
    //   此前无前缀支 一律落 '外观' 兜底 与显示无关项混同; 前缀与后端 registry 同序同键名 - 小欧-2026-10-05
    if (key.startsWith('appearance.step_render.')) return 'step渲染控制';
    return '外观';
  }
  // 2026-10-18 小欧: security 组按**组名进键名前缀**拆三段(与 sandbox.tool.* 同一机制, 零新增渲染逻辑):
  //   security.system.* → 系统      —— 硬拦类: 要不要拦
  //   security.hitl.*   → HTL人工确认 —— 确认类: 要不要问
  //   security.trust.*  → 信任      —— 会话信任
  //   原为 security.* 四项一律归「人工确认」, 块 2「安全策略说明」是纯说明(无配置项故不进 registry),
  //   由 items.map 循环后追加 DirectoryAccessNote(见文件末)。
  if (group === 'security') {
    if (key.startsWith('security.hitl.')) return 'HTL人工确认';
    if (key.startsWith('security.trust.')) return '信任';
    return '系统';
  }
  // 2026-10-12 小欧: sandbox 组拆 3 块 — 运行控制(原有8项) / 工具(工具类扩展位) / 语法检测
  //   (sandbox.tool.syntax_check.*, 后端 2026-10-12 增; 沙箱页原为平铺8项, 偏空)
  if (group === 'sandbox') {
    if (key.startsWith('sandbox.tool.syntax_check.')) return '语法检测';
    if (key.startsWith('sandbox.tool.')) return '工具';
    return '运行控制';
  }
  // 2026-11-08 小欧: media 组按语义拆两段 —— 本机图片(上限/压缩) 与 外链(转发/探测地址) — 小欧-2026-11-08
  if (group === 'media') {
    if (key.startsWith('media.remote_url') || key.startsWith('media.probe_'))
      return '外链图片';
    return '本机图片';
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
  const fontSize = clampFontSize(values['appearance.fontSize']);
  // 2026-11-12 小欧 - 密度档取当前设置值(读侧单点 constants/appearancePrefs 的 clampDensity) — 小欧-2026-11-12
  const density = clampDensity(values['appearance.density']);
  // 2026-11-09 小欧 - hidden 项不渲染(已迁到功能行就地配置, 如 media.probe_image_url=②Image_URL 行)，
  //   键仍留 schema 供读写链(saveKeys/groupOfKey)工作 — 小欧-2026-11-09
  // 2026-11-11 小欧 - 三个验证素材地址已回媒体页直接显示(不再 hidden), media 组现无 hidden 项;
  //   过滤逻辑保留作防御(其它组仍可能注册 hidden 项) — 小欧-2026-11-11
  const visibleItems = items.filter((item) => !item.hidden);
  // 外观组分「登录与准入」/「外观」两块后，预览小卡（服务于"字号"这个外观项）
  //   必须随「外观」块一起渲染 —— 否则它会孤零零压在"登录与准入"上方，位置与语义都不对。
  //   故改为在渲染到「外观」块首项时再输出（appearance 组内顺序由后端 registry 保证：准入项在前、外观项在后）。
  // 2026-11-12 小欧 - 预览小卡按 [31] §4.5 重做: 一块卡片同时演示两个受控量, 各占一区互不混淆 ——
  //   上半「界面密度」: 左右两块用同一段示例文本, 按**真实密度参数**渲染(字号恒 14,
  //     阅读区留白按 DENSITY_PAD 缩放、控件高按 controlScale 刻度), 当前档加主色边框标示;
  //   下半「阅读区字号」: 12/14/16 三行纯文字样例(控件预览不是排版预览, 不接真实 Markdown),
  //     当前档加主色边框, 卡尾注明作用范围。
  //   原实现把「紧凑/舒适」两个标签贴在**字号**样例上(两格字号同值、只差 padding) —— 标签描述的是密度
  //     却挂在字号样例上, 是 [31] §4.1 判定的误导源头; 现两标签归位到密度样例块, 语义归位。
  // 小欧-2026-11-12
  const appearancePreview = (
    <Card
      size="small"
      style={{ marginBottom: Spacing.LG }}
      title="外观预览（拖动上面的控件，这里实时变）"
    >
      <div
        style={{
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.SECONDARY,
          marginBottom: Spacing.XS,
        }}
      >
        界面密度（控件高 / 阅读区间距）
      </div>
      <div
        style={{
          display: 'flex',
          gap: Spacing.MD,
          alignItems: 'flex-start',
          marginBottom: Spacing.LG,
        }}
      >
        {APPEARANCE_DENSITIES.map((d) => {
          const pad = DENSITY_PAD[d];
          const controlHeight = controlHeightByDensity(d).normal;
          const gap = Math.max(2, Math.round((Spacing.MD * pad) / 2) * 2);
          const active = d === density;
          return (
            <div
              key={d}
              style={{
                border: `1px solid ${active ? Colors.PRIMARY : Colors.BORDER.LIGHT}`,
                borderRadius: Radius.DEFAULT,
                padding: Spacing.XS,
              }}
            >
              <div
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.SECONDARY,
                  marginBottom: Spacing.XS,
                }}
              >
                {d === 'comfortable' ? '舒适' : '紧凑'}
              </div>
              <div
                style={{
                  fontSize: FontSize.PRIMARY,
                  lineHeight: 1.6,
                  padding: gap,
                  background: Colors.BG.SECONDARY,
                  borderRadius: Radius.SM,
                  marginBottom: gap,
                }}
              >
                示例消息气泡
              </div>
              <div
                style={{
                  height: controlHeight,
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0 8px',
                  fontSize: FontSize.PRIMARY,
                  background: Colors.BG.SECONDARY,
                  border: `1px solid ${Colors.BORDER.DEFAULT}`,
                  borderRadius: Radius.SM,
                }}
              >
                输入框样例
              </div>
            </div>
          );
        })}
      </div>
      <div
        style={{
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.SECONDARY,
          marginBottom: Spacing.XS,
        }}
      >
        阅读区字号（px）
      </div>
      {APPEARANCE_FONT_SIZES.map((px) => (
        <div
          key={px}
          style={{
            fontSize: px,
            lineHeight: 1.6,
            padding: Spacing.XS,
            border: `1px solid ${px === fontSize ? Colors.PRIMARY : 'transparent'}`,
            borderRadius: Radius.SM,
            color: Colors.TEXT.PRIMARY,
          }}
        >
          示例正文 {px}px
        </div>
      ))}
      <div
        style={{
          fontSize: FontSize.CAPTION,
          color: Colors.TEXT.SECONDARY,
          marginTop: Spacing.XS,
        }}
      >
        字号仅作用于阅读区（文件预览 / 说明弹框），不影响流水线正文与任务卡。
      </div>
    </Card>
  );
  return (
    <div>
      {visibleItems.map((item) => {
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
      {/* 2026-10-06 小欧 - 块2「安全策略说明」：纯说明(分类表 + 两个说明弹框), 无配置项故不进 registry,
          只能在此追加(与 appearancePreview 同款做法)。仅 security 组出现。 */}
      {group === 'security' && (
        <>
          <SectionTitle title="── 安全策略说明 ──" />
          <DirectoryAccessNote />
        </>
      )}
    </div>
  );
};
