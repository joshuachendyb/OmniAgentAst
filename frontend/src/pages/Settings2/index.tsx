// 编辑历史: 2026-09-20 小强 - 新建：设置2版页面入口（同旧页骨架，白底 Card + Tabs 由 SettingsPage 承载）
// 2026-10-10 22:50 小欧 - 控件高度覆盖为 28（北京老陈指令：不许拿 UI 库默认高度当标准）。
//   推导与依据写在 settingsTokens.ts 的 SETTINGS_CONTROL_HEIGHT 注释里，此处只做落地。
//   作用域刻意只包设置页：聊天侧/其他页控件密度诉求不同，不被这一刀连带影响。
//   ⚠ 2026-11-12 小欧 - 该常量的推导正文已随控件规格迁至 theme/controlScale.ts（文档[32]：
//     控件规格是**全站**规格, 留在设置页令牌里会造成跨域反向依赖; 且控件高要随密度变化,
//     常量表达不了 → 由 controlScale 的 token 构造器按密度解算）。本行仅存历史说明。
// 2026-10-10 23:05 小欧 - 圆角统一 4px + 开关改 40x18（北京老陈指令：antd 各组件各自默认圆角/开关尺寸，
//   必须全量核查统一，不许沿用库的缺省值）。审计实测原状：
//   圆角 Input6/Select4/Btn默认4/Btn主键6/Btn链接6/Checkbox4/Tag4；开关 44x22 且带 1px 边框。
//   数值与推导依据都在 settingsTokens 定义，此处只做落地。
//   ⚠ 更正本文件 23:05 第一版：曾误加 token.controlHeightSM=18 想压开关轨道——该token 会连带压全页
//     所有 size="small" 控件（是错的），已移除。开关尺寸改走 CSS 精确覆盖，见下方 switchCss。
// 编辑历史: 2026-10-11 00:18:37 小欧 - 设置页视觉密度统一: 控件高 28/圆角 4px/开关 40x18 落地(ConfigProvider + CSS 精确覆盖 switchCss; 曾误加 controlHeightSM=18 会连带压全部 small 控件, 已移除; 推导见 settingsTokens) — 小欧-2026-10-11
import React from 'react';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

import SettingsPage from '@/features/settings2/components/SettingsPage';
import { SETTINGS_SWITCH } from '@/theme/settingsTokens';
// 2026-11-12 小欧 - 控件高改随界面密度(文档[32] 全站控件刻度统一):
//   本页 ConfigProvider 原硬写 controlHeight=28 + SETTINGS_RADIUS=4, 会**覆盖**根下发的
//   密度值 → 密度对本页无效; 且控件高/圆角真源散落两处(本页 + 根)。
//   现统一读 pageControlTokens(density): 控件高取全站刻度(normal 随密度), 圆角取本页
//   逐页审计结论(全档 4, 须显式补发 LG, 否则继承全局 8)。
import { useAppearancePrefs } from '@/hooks/useAppearancePrefs';
import { pageControlTokens } from '@/theme/controlScale';

/**
 * 开关轨道精确覆盖 —— 为什么必须用 CSS 而非 antd token：
 *   antd 的 Switch 组件 token 不暴露轨道 width/height/圆钮直径这三项，
 *   controlHeight 只影响部分派生值，无法稳定得到 40x18 + 14 钮。
 *   直接覆盖 .ant-switch 及其 .ant-switch-handle 是唯一可控口径（SLAP：改一处即全页生效）。
 *   数值与推导见 settingsTokens.SETTINGS_SWITCH（北京老陈指令："开关要瘦点扁"）。
 */
const switchCss = `
/* 设置页开关：轨道 40x18（横向 40 是宽度，非高度；高度 18 比输入框 28 矮，符合"开关装不下文字"的器件属性） */
.ant-switch {
  width: ${SETTINGS_SWITCH.width}px;
  height: ${SETTINGS_SWITCH.height}px;
  min-width: ${SETTINGS_SWITCH.width}px;
  padding: 0;
  background: #d9d9d9;
  border: none;
}
.ant-switch.ant-switch-checked { background: #1677ff; }
/* 开关圆钮：白底 + 正圆。
   ⚠ 2026-10-10 23:25 小欧 - 踩坑记录（实测诊断）：antd v5 的 handle 白底与圆形是从 token 派生的，
   一旦在 ConfigProvider 改了全局 borderRadius，派生链重算会把 handle 的 background 洗成
   rgba(0,0,0,0)、borderRadius 洗成 0 → 蓝轨上"看不见钮"（实测确实复现）。
   故此处显式给死颜色与形状，不再依赖 antd 派生值。 */
.ant-switch .ant-switch-handle {
  width: ${SETTINGS_SWITCH.knob}px;
  height: ${SETTINGS_SWITCH.knob}px;
  inset-inline-start: 2px;
  top: 2px;
  background: #ffffff;
  border: none;
  border-radius: 50%;
  box-shadow: none;
}
/* 选中：钮靠右留 2px（40 - 14 - 2 = 24） */
.ant-switch.ant-switch-checked .ant-switch-handle {
  inset-inline-start: calc(${SETTINGS_SWITCH.width}px - ${SETTINGS_SWITCH.knob}px - 2px);
  background: #ffffff;
}
/* 关掉内圈阴影：antd 原生钮内有一圈 ::before 阴影，配 14px 钮会显脏 */
.ant-switch .ant-switch-handle::before { content: none; }
/* loading 图标同步收小 */
.ant-switch .ant-switch-loading-icon { font-size: ${SETTINGS_SWITCH.knob - 4}px; }
/* 垂直居中：SettingRow 第二列是 column 布局，开关不居中会显得浮（上移量按轨道一半对齐控件中线） */
.ant-switch { align-self: center; }
`;

const Settings2: React.FC = () => {
  // 2026-11-12 小欧 - 控件高随密度(全站刻度, 文档[32])
  const { density } = useAppearancePrefs();
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: pageControlTokens(density),
      }}
    >
      <style>{switchCss}</style>
      <SettingsPage />
    </ConfigProvider>
  );
};

export default Settings2;
