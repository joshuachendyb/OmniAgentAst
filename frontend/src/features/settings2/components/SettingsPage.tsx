// 编辑历史:
// 2026-09-20 小强 - 新建：设置页壳（搜索+Tabs+全局脏角标+切 Tab 未保存确认内联+sticky 保存条）
// 2026-09-21 小强 - 对齐统一提示规范(no-restricted-syntax)：message.success/info 改走 errorHandler.showSuccess/showMessage
// 2026-09-21 小强 - 修复：模型删除确认的 target 精确匹配 provider::model（原 deleteTarget 未带 provider
//   前缀，确认句恒为 false 导致删除项参数名链上错误——匹配 SettingRow 的 key 形如 provider::model）
// 2026-09-21 小欧 - 背景色→Colors.BG.PRIMARY、字重→FontWeight.BOLD、间距→Spacing
// 2026-09-21 小欧 - 保存本组按钮带本组待存计数
// 2026-09-21 小欧 - 重置按钮上移到标题行右侧 + 顺带修正：无params隐藏/无脏态disabled
// 2026-09-21 小欧 - 当前生效模型高占位状态卡集成
// 2026-09-21 小欧 - 核查修复：小字可点跳模型 Tab；锚点滚动+高亮；重置确认弹窗 danger
// 2026-09-21 小欧 - 全文逐条核查：重置确认/Tab切换 弹窗宽散落 480 → settingsModalWidth.confirm 令牌收口
// 2026-09-21 小欧 - 排版重构：CurrentModelRefCard+参数区从模型Tab移到通用Tab；模型Tab区块编号顺移；删除Card顶部辅位小字（与通用Tab CurrentModelRefCard重复）；新增沙箱Tab
// 2026-09-21 小欧 - 模型Tab：选择器上方加"当前系统全局使用模型"行（与通用Tab CurrentModelRefCard 对应）；删废弃 jumpToModels
// 2026-09-21 小欧 - 修正排版重构失误：参数区（ModelParams/模型特殊参数）从通用Tab移回模型Tab，模型Tab恢复参数区；ProviderConfig补max_retries回退值
// 2026-09-21 小欧 - 删除无触发源死代码 highlightJump/flashSelector（YAGNI，消 eslint pre-existing warning）；
//   jumpToProviderConfig 修复跨Tab失效（CurrentModelRefCard 已移通用Tab，原 scrollTo 在模型Tab未渲染时静默失败）
// 2026-09-21 小欧 - 删除 Provider/模型成功后由 refreshModels 改整体 load()，焦点/全局卡/参数区重载对齐后端
//   （根治"删全局当前模型时前端仍悬浮已删模型，保存报错、全局卡显示假数据"）
// 2026-09-21 小强 - Tab 标题唯一源=后端注册表：删硬编码 TAB_TITLES（含死 chat:"聊天"），
//   Tab label 改用 state.schema[g].label（后端 settings_registry GROUPS[g].label）；GROUP_ORDER 由 useSettings 动态派生
// 2026-09-21 小强 - 关联清理：dangerousDirty 去掉已删键 whitelist/blacklist 死判断（键已从注册表移除，恒 false 死代码）
// 2026-09-21 小欧 - 修复：搜索跳转 jumpTo 与 Tab 切换统一走「当前组脏→确认」闸口，
//   不再绕过确认直接切 Tab（原 jumpTo 静默丢弃当前组未保存修改）；确认对话框记录待跳 tab+高亮 key，
//   保存成功后跳转并高亮；deleteTarget 解析改用首个 '::' 索引切片（原 split('::') 对含 '::' 的模型名截断误删）；
//   onSaveGroup/onSaveAll 返回 Promise，SaveBar confirmThen 的 Modal onOk await 化——OK 按钮自带 loading 防连点双保存
// 2026-09-21 小强 - 切 provider 表单值跟随修复：key 加在 ProviderConfig 组件层（整体重挂→useForm 全新实例→空仓库→新 initialValues 落盘；内层 key 经 rc-field-form 源码证伪无效已删）
// 2026-09-21 小强 - 设置页问题复核修复：
//   搜索跳转滚动到命中行(data-settings-key 锚点，双 rAF)；切Tab确认文案与"保存并切换"行为对齐；
//   危险确认拆分本组/全部(dangerousGroup/All)，危险键含 security.hitl_enabled；模型组脏计数按实际参数数；
//   添加/删除/Provider 保存失败不关窗并 rethrow（弹窗保留输入）；添加 Provider toast 引导切换；
//   jumpToProviderConfig 走脏确认闸口+保存后滚动锚点；删模型Tab"当前系统全局使用模型"冗余行
// 2026-09-22 小强 - ModelActions 传 envManaged（provider env 接管时隐藏「清空 api_key」，后端拒 clear）
// 2026-09-22 小欧 - ModelParams 传 options={state.model.paramOptions}（读链末端：state→组件；后续才消费渲染 Select）
// 2026-09-22 小欧 - onSubmitAddModel 透传 range/capabilities/param_options 到 modelApi.addModel
//   （原仅透 model_params，新模型建出即带元数据/选项，不必回参数区返工）
// 2026-09-22 小欧 - ProviderConfig fallback 加 label:''（providerConfig 类型补 label 后
//   fallback 对象须同构，否则选中未加载 Provider 时 ProviderConfig 表单缺显示名初值）
// 2026-09-22 小欧 - ProviderConfig fallback timeout 60→150（与后端常量/三层回落对齐，
//   缺省条目才触发，平时走 API 值；原 fallback 60≠运行时 150，切未加载 Provider 时表单显示 60 实际 150）
// 2026-09-22 小欧 - 参数区标题行加「管理选项」入口（param_options 非空才显示），
//   ModelModals 后渲染 ParamOptionsModal（open=paramOptionsModalOpen，保存后 refreshModels 重拉）
// 2026-09-22 小欧 - YAGNI+令牌收口：选择器锚点 div 删 borderRadius/padding/margin 无效死样式（padding+margin 恰恰抵消，视觉零效果）；「管理选项」按钮 marginRight:16 裸数字 → Spacing.XL - 小欧-2026-09-22
// 2026-09-23 小欧 - 标题行加「+ 添加参数」按钮；ModelParams 前条件渲染 AddParamForm；
//   ModelParams 后加「模型能力」多选行（Checkbox.Group+env 按 providerConfig.env 禁用+DirtyDot）——
//   import 合并追加（Checkbox 进 antd 行、settingsRowStyle/settingsLabelStyle 进 tokens 行、DirtyDot 并 icons 行、
//   CAPABILITY_OPTIONS/isCapsDirty 并 modelUtils 行、AddParamForm 新行，禁重复 import）- 小欧-2026-09-23
// 2026-09-23 小欧 - UI 风格对齐：「+ 添加参数」由手打加号的 type=link 改为整体页面添加类
//   动作标准款 = 默认 Button + PlusOutlined 图标（与 ModelSelector「添加模型/添加 Provider」同款），
//   主操作层级与右侧辅助 link（管理选项/重置为默认）拉开；PlusOutlined 并入 @ant-design/icons 独立 import - 小欧-2026-09-23
// 2026-09-23 小欧 - 标题行布局改三列 grid：space-between 多子项均分致
//   按钮漂移——改 gridTemplateColumns '1fr auto 1fr' = 标题左 | 添加参数居中 | 管理选项/重置右组
//   （右组包 flex 容器 gap:Spacing.XL，去掉两按钮各自 marginRight，按钮条件渲染变化不再影响中列位置）- 小欧-2026-09-23
// 2026-09-23 小欧 - 标题行三按钮合一组：添加参数/管理选项/重置为默认 = 同款默认 Button
//   （管理选项/重置原 type=link 去边框异款）+ 统一 width:120 等长 + gap:Spacing.SM 紧挨 + 中列整组居中；
//   原「标题|添加参数居中|右组」拆两处 → 组内条件渲染（无 param_options/无 params 仍隐藏，组始终居中）- 小欧-2026-09-23
// 2026-09-23 小欧 - 三按钮宽改 settingsControl.actionBtnWidth 令牌（消 width:120×3，
//   settingsControl 并入 tokens import 行）+ 能力行 DirtyDot 改 && 写法（与 ModelParams 同款）- 小欧-2026-09-23
// 2026-09-23 小欧 - 补漏：能力行 Checkbox.Group 右侧加未知能力值灰色只读 Tag
//   （yaml 手写 vision 等非枚举值——设计要点「看得见、本页不提供增删」，原实现未知值完全不可见；
//   Tag 无 closable + cursor:not-allowed；import 并入既有 antd/modelUtils 行，禁重复）- 小欧-2026-09-23
// 2026-09-24 小欧 - ModelParams 传 onDelete={s.removeParam}（参数行 × 删除按钮接线）- 小欧-2026-09-24
// 2026-09-29 小欧 - Tab 栏 tabBarStyle.marginBottom 归零：antd 自带 16px 与本行 marginBottom、
//   Card padding:24 三层叠加成 52px 纯空白。不动 Card padding(会波及 8 个 Tab) - 小欧-2026-09-29
// 2026-09-24 22:34:33 小欧 - groupDirtyCount 补能力脏 +1（与 useSettings dirtyCount/
//   isGroupDirty 同口径，原仅改能力时「保存本组」可点却显示 0 项计数失真）；删除确认前置
//   ensureModelSaved（删除成功后 load() 全量重建会静默丢当前焦点模型未落库改动，与 selectProvider/
//   selectModel 同款防线）；保存中(saving) 锁定参数区（ModelParams disabled + 添加参数/
//   管理选项/重置三按钮禁用，防保存 await 期间改 state 致闭包快照错位）；添加参数/管理选项
//   env 接管禁用 + envManaged 单点收口（能力行内联 env 判定表达式复用，防重复） — 小欧-2026-09-24
// 2026-09-24 22:56:21 小欧 - 保存中锁定闭环补漏（表单通道未锁）：AddParamForm/ParamOptionsModal
//   传 disabled={s.saving}（保存中禁提交）+「重置为默认」Modal.confirm onOk 加 saving 守卫——
//   堵死「弹窗通道在保存 await 期间仍改模型 state」的最后竞态窗口 - 小欧-2026-09-24
// 2026-09-24 小欧 - 模型库 Tab 落码：import ModelLibraryTab；抽 afterModelSaved 组件级收口
//   （syncMtime+refreshModels DRY，Provider 配置保存/清空 key/模型库保存 3 处共用）；
//   Tab 分支加 model_library 渲染 ModelLibraryTab（onSaved 直引 afterModelSaved 不内联）- 小欧-2026-09-24
// 2026-09-25 06:20:25 小健 - 参数区入口按钮文案「管理选项」→「管理推理深度」（语义直指
//   reasoning_effort 档位表）；宽度沿用 settingsControl.actionBtnWidth 120 保持三按钮等宽 - 小健-2026-09-25
// 2026-09-25 06:23:15 小健 - 同排入口按钮「添加参数」→「添加模型参数」（6 字与
//   「管理推理深度」等长，actionBtnWidth 120 内不挤压，三按钮等宽视觉不变）— 小健-2026-09-25
// 2026-09-27 小欧 - 掩码契约 {configured, masked}：ProviderConfig 的 fallback config 里 api_key 缺省值
//   为 {configured:false, masked:''}。该契约在项目内有 4 处声明（model.api.ts ProviderEntry /
//   ProviderConfig.config / settings2/types.ts / 本缺省值），少任一处 tsc 即报 masked 缺失，故四处同形
//   — 小欧-2026-09-27
// 2026-09-27 小欧 - Provider 配置改后底部保存栏亮起：
//   groupDirtyCount 模型组分支 += providerDraft 键数（与 useSettings dirtyCount 同口径）；
//   ProviderConfig 挂载传 onDraftChange={s.setProviderDraft}（字段 diff 上报→底部栏计数）；
//   自带保存按钮的 onSave 改走 s.saveProviderDraft(patch)——与底部保存栏同一条落盘链（统一链，
//   原内联 modelApi.updateProvider+afterModelSaved 三段逻辑收口进 hook，失败 rethrow 保留输入语义不变）- 小欧-2026-09-27
// 2026-09-27 07:38 小欧 - 修复三处：「清空 api_key」成功后同清 providerDraft（清空是 api_key 的第二个
//   写入口，原先只清后端，用户接着点保存会把刚清空的密钥写回）；未保存确认弹窗补 confirmLoading={s.saving}
//   （onOk 是 void...then() 不返 Promise，antd 不自带 loading，双击会连发两次 saveGroup）；
//   jumpToProviderConfig 判脏对象改 'model'（原判 state.activeTab，而唯一调用点在通用 Tab 恒为 general，
//   查错组致闸口形同虚设）- 小欧-2026-09-27
// 2026-10-03 小欧 - ModelLibraryTab 增「添加 Provider」入口，回调复用 :323 给 ModelSelector 的同一处（不新建弹窗/状态）— 小欧 2026-10-03
// 2026-10-03 小欧 - 修「模型库 Tab 点添加 Provider 无反应」：ModelModals 原挂在 renderModelTab 内，
//   model_library Tab 不调该函数致弹窗组件不挂载，置 open 也无人渲染；已上提到页面顶层（全 Tab 挂载）— 小欧 2026-10-03
// 2026-10-05 22:16:38 小欧 - 「安全开关」随 settings_registry 标签改名「HTL人工开关」，危险键判定处注释同步 — 小欧 2026-10-05
// 编辑历史: 2026-10-10 小欧 - 弹窗归一：切 Tab 未保存拦截 Modal → SettingsModal 标准壳（confirm=480
//   宽度档、双键「放弃切换/保存并切换」、discard 关闭语义）；业务逻辑与文案一字未改，只换壳。
//   实测：宽 480 / ESC 可关 / 双键文案正确，符合设计。
// 编辑历史: 2026-10-11 00:55:20 小欧 - 危险确认弹框展示「具体改了什么」+「改完意味着什么」: 新增 DANGER_LABELS/DANGER_EFFECTS(取值口径与 SettingsGroup 一致: values[key] 脏键缓冲值, 不回落已落盘值) — 小欧-2026-10-11
// 编辑历史: 2026-10-11 01:24:25 小欧 - dangerHints 扁平数组改 dangerHintByChange(按 label 索引): 多条变更各自成组挂后果(汇总成块分不清对应关系); 本文件侧调用改造(旧文件头历史块随重构迁移, 详见 git) — 小欧-2026-10-11
// 编辑历史: 2026-10-11 06:31:51 小欧 - 后果说明两个方向都给: DANGER_EFFECTS 值改 {on, off}(原只挂"关闭"方向, 开启方向说明区空白致弹框塌陷); 另 import confirmDanger(新增二次确认入口) — 小欧-2026-10-11
// 2026-10-18 小欧 - 危险键三表随 security 子命名空间跟改: security.hitl_enabled → security.hitl.enabled、
//   security.confirmDangerousOps → security.system.confirm_dangerous_ops, DANGEROUS_KEYS/DANGER_LABELS/
//   DANGER_EFFECTS 三处同步(只改键名字面, 判定与文案结构零变更)。
//   触发原因: 键名与后端 registry 不一致时 dangerousDirty 恒 false = 改了高危开关不进二次确认, 属静默失效。
// 2026-10-18 小欧 - 注释精简冗余标注, 技术说明原样保留。
// 2026-10-29 小欧 - 修 Bug2: 清空 api_key 成功后立即本地更新 providerConfig(configured=false, masked='')，
//   不等 reloadProviderCache 异步返回——否则期间 SecretRevealInput 回填旧掩码串 — 小欧-2026-10-29
// 2026-11-01 小欧 - 组级脏点（北京老陈批准主案）：撤头部「有 N 项未保存」橙贴——未保存信息行级点
//   与底栏保存按钮两处已答，头部属第三报且凭空出现会顶开内容；改 Tab 标签内常显组级圆点
//   （亮=该组有未保存），改哪组一眼定位、页面零跳变 — 小欧-2026-11-01
// 2026-11-01 小欧 - #4 条件按钮常显（北京老陈拍板）：②参数区「管理推理深度」「重置为默认」不再凭空
//   出现消失——判据提取 hasManagementOptions/hasModelParams 常算，无数据时按钮常显禁用 + Tooltip
//   说明原因；三按钮等宽组位置恒定（disabled 元素 span 包裹系 antd 官方约束）— 小欧-2026-11-01
// 2026-11-01 小欧 - ②参数区按钮改名「放弃修改」（北京老陈批准主案，原「重置为默认」名不符实——
//   只撤值修改、撤不掉×删键与能力勾选）：确认弹窗同步放弃语义（title「⚠ 放弃修改」/okText「确认放弃」/
//   content 三类全撤说明+已保存配置不受影响），Tooltip「参数无修改」→「无未保存修改」，按钮位置与
//   常显禁用规则不动，onOk 调用 s.resetParams() 名不变 — 小欧-2026-11-01
// 2026-11-01 小欧 - 灰态 Tip 文案人话化（北京老陈批「指路版」）：「当前模型没有参数」→
//   「此模型还没有参数——没东西可放弃，先点「添加模型参数」」；「无未保存修改」→「还没改过任何参数，
//   不用放弃」；管理推理深度「当前模型没有可管理的参数选项」→「此模型还没有参数——先加参数，
//   才有选项可管理」。灰按钮常显禁用不变，Tip 是点不动的唯一解释位，病在文案不在机制 — 小欧-2026-11-01
// 2026-11-01 小欧 - 「放弃修改」扩权全域（北京老陈批准）：管理页未保存修改原拆两本账（②参数/
//   能力 vs ③Provider 草稿），北京老陈实证改③区点放弃无反应、灰色 Tip 说瞎话。现点亮条件=
//   ②或③任一脏，onOk 清 providerDraft + providerResetSeq 自增令 ProviderConfig 重挂载（本地输入
//   按 config=已保存值重新回显，组件内部逻辑/保存链零改动），弹窗文案同步四类清单 — 小欧-2026-11-01
// 2026-11-01 小欧 - 键名统一（北京老陈令）：ModelParams.defaults → baseline、ParamOptionsModal 同；
//   onSubmitAddModel 透传 default_params → model_params；providerConfig fallback base_url → api_base。
//   详见 doc-11月优化/模型参数显示链路分析报告-小欧-2026-11-01.md - 小欧-2026-11-01
// 2026-11-08 小欧 - ①②③标题行布局统一：三列 grid（1fr 1fr 1fr）+ SectionTitle + 按钮组中列左对齐（justifySelf:'start'）；
//   ①按钮补 actionBtnWidth（与②等宽）；③ ProviderConfig 裸 span → SectionTitle、grid div 去 margin（消除 grid row 高度差异致按钮垂直错位）
// 2026-11-08 小欧 - 补全：输出模态行补非可选项灰标（text/audio 只读可见，与输入行同款） — 小欧-2026-11-08
// 2026-11-08 小欧 - 实测迁入②：新增「图片实测」行（紧贴输入模态），探测目标=①选中模型；取证后回读落库值并回填 mtime — 小欧-2026-11-08
import React, { useState } from 'react';
import {
  Button,
  Card,
  Checkbox,
  Modal,
  Result,
  Skeleton,
  Tabs,
  Tag,
  // 2026-11-01 小欧 - ②参数区按钮常显化（北京老陈拍板 #4）：不可用原因用 Tooltip 说明 — 小欧-2026-11-01
  Tooltip,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { Colors, FontSize, Spacing, FontWeight } from '@/utils/stepStyles';
import {
  settingsSpacing,
  settingsControl,
  settingsModalWidth,
  settingsRowStyle,
  settingsLabelStyle,
} from '@/theme/settingsTokens';
import { SettingsModal, confirmDanger } from '@/theme/SettingsModal'; // 2026-10-10 小欧: 未保存拦截弹窗归一到设置页壳; 10-11 补 confirmDanger
import { useSettings } from '../hooks/useSettings';
import { SettingsGroup } from './SettingsGroup';
import { SearchBox } from './SearchBox';
import { SaveBar } from './SaveBar';
import { SettingIcon, DirtyDot, TabDirtyDot } from './icons';
import { ModelSelector } from './ModelSelector';
import { ModelParams } from './ModelParams';
import { ProviderConfig } from './ProviderConfig';
import { ModelActions } from './ModelActions';
import { ModelModals } from './ModelModals';
import { SectionTitle } from './SectionTitle';
import { CurrentModelRefCard } from './CurrentModelRefCard';
import { ModelLibraryTab } from './ModelLibraryTab';
import { modelApi } from '@/services/api/model.api';
// 2026-11-08 小欧 - 实测写盘绕过保存链，取证后按后端 mtime 回填，防下一次保存被守卫拒一次 — 小欧-2026-11-08
import { settingsApi } from '@/services/api/settings.api';
import {
  acceptMain,
  acceptSub,
  acceptTip,
  urlTestedOf,
} from '../mediaProbeText';
import {
  ErrorType,
  handleApiError,
  // 2026-09-27 小欧 - handleError 随 onSave 收口进 saveProviderDraft 移除（全文件已无调用点）- 小欧-2026-09-27
  showMessage,
  showSuccess,
} from '@/services/error/handler';
import {
  isDirty,
  CAPABILITY_OPTIONS,
  isCapsDirty,
  KNOWN_CAPABILITY_VALUES,
  // 2026-11-08 小欧: 输出模态勾选枚举
  OUTPUT_MODALITY_OPTIONS,
  KNOWN_OUTPUT_MODALITY_VALUES,
} from '../utils/modelUtils';
import type { TabKey } from '../types';
// 2026-09-22 小欧 - 管理选项弹窗（标题行「管理选项」入口）
import { ParamOptionsModal } from './ParamOptionsModal';
// 2026-09-23 小欧 - 添加参数内联表单（组件一文件，独立 import）
import { AddParamForm } from './AddParamForm';

const SettingsPage: React.FC = () => {
  const s = useSettings();
  const { state } = s;
  const [pendingJump, setPendingJump] = useState<{
    tab: TabKey;
    key: string;
    anchor?: string | null;
  } | null>(null);
  // 2026-11-01 小欧 - 全域放弃（北京老陈批准扩权）：ProviderConfig 字段值存组件本地 useState
  //   （从 config props 初始化），父层只清 providerDraft 不会改它显示——用 key 合入自增序号，
  //   放弃修改时整体重挂载、按已保存配置重新回显（不碰组件内部逻辑，config 本身从未被编辑改写）
  //   — 小欧-2026-11-01
  const [providerResetSeq, setProviderResetSeq] = useState(0);
  // 2026-11-08 小欧 - 图片实测探测中态（hook 必须置顶：组件早 return 之后不能再调 useState）— 小欧-2026-11-08
  const [probing, setProbing] = useState(false);

  // 修复：requestTab 与 jumpTo（搜索高亮跳转）统一走「当前组脏→确认」闸口，
  // 原 jumpTo 直接切 Tab 绕过确认，会静默丢弃当前组未保存修改
  const requestTab = (tab: TabKey) => {
    if (tab !== state.activeTab && s.isGroupDirty(state.activeTab)) {
      setPendingJump({ tab, key: '' });
    } else {
      s.setActiveTab(tab);
      void s.checkMtime();
    }
  };

  // 修正(2026-09-21 小强)：搜索跳转滚动到命中行——原仅高亮无 scrollIntoView，跨 Tab/长列表定位不到
  // （[设置页UI审计] 问题1）；双 rAF 等目标 Tab DOM 挂载后滚动
  const scrollToKey = (itemKey: string) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = document.querySelector(`[data-settings-key="${itemKey}"]`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    });
  };

  const jumpTo = (tab: TabKey, key: string) => {
    if (tab !== state.activeTab && s.isGroupDirty(state.activeTab)) {
      setPendingJump({ tab, key });
    } else {
      s.setActiveTab(tab);
      s.setHighlightKey(key);
      scrollToKey(key);
    }
  };

  // S2/S3：滚动跳转（跨 Tab 锚点：先切到目标 Tab，等渲染完成后再滚动）
  const scrollTo = (dataSection: string) => {
    const el = document.querySelector(`[data-section="${dataSection}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
  // 修正(2026-09-21 小强)：jumpToProviderConfig 也走「当前组脏→确认」闸口——
  // 原直调 setActiveTab 绕过确认切到模型 Tab（[设置页UI审计] 问题11）
  const jumpToProviderConfig = () => {
    // 2026-09-27 小欧 - 修 F9：判脏对象应为跳转**目标组** model。原判 state.activeTab，
    // 而本函数唯一调用点在 renderGeneralTab（此时 activeTab 恒为 general）→ 闸口查错组，形同虚设。
    if (s.isGroupDirty('model')) {
      setPendingJump({ tab: 'model', key: '', anchor: 'provider-config' });
      return;
    }
    s.setActiveTab('model');
    requestAnimationFrame(() => scrollTo('provider-config'));
  };

  // 修正(2026-09-21 小强)：危险判定拆分「保存本组/保存全部」——原全局判定致保存其它组误弹；
  // 危险键=人工确认总开关/保存二次确认的变更（含关闭场景，原仅认 confirmDangerousOps）
  // （[设置页UI审计] 问题7/8）
  // 2026-10-18 小欧 - 键名按后端分组前缀跟改: security.hitl_enabled → security.hitl.enabled、
  //   security.confirmDangerousOps → security.system.confirm_dangerous_ops。
  //   三张表(DANGEROUS_KEYS/DANGER_LABELS/DANGER_EFFECTS)同步跟改。
  const DANGEROUS_KEYS = [
    'security.hitl.enabled',
    'security.system.confirm_dangerous_ops',
  ];
  const dangerousGroup =
    state.activeTab === 'security' &&
    DANGEROUS_KEYS.some((k) => state.dirtyKeys[k]);
  const dangerousAll = DANGEROUS_KEYS.some((k) => state.dirtyKeys[k]);

  // 2026-10-11 00:05 小欧 - 危险确认弹框要展示「具体改了什么」+「改完意味着什么」。
  // 改前只笼统说"涉及危险操作相关配置（HTL人工开关/危险操作确认）"，用户看不出提交内容，
  // 也不知道关闭 HTL 的后果——确认弹框的全部意义就是让人看清即将生效的变更。
  // 取值口径与 SettingsGroup 一致：values[key] 为准（脏键的缓冲值，不回落到已落盘值）。
  const DANGER_LABELS: Record<string, string> = {
    'security.hitl.enabled': '人工确认总开关',
    'security.system.confirm_dangerous_ops': '保存设置时二次确认',
  };
  // 2026-10-11 01:20 小欧 - 后果说明两个方向都给（开与关各挂对应后果）。
  //   原实现只在"关闭"方向挂说明、"开启"方向留空 → 只改一项且是开启方向时，说明区整片空白，
  //   弹框下半部塌陷、左右失衡。改为按 `${key}:${方向}` 取，开与关各有对应后果。
  const DANGER_EFFECTS: Record<string, { on: string[]; off: string[] }> = {
    'security.hitl.enabled': {
      on: [
        '开启后：每次高危操作都会弹窗请你人工确认，不会自动放行',
        '（更安全，代价是每次操作都要点一次）',
      ],
      off: [
        '关闭后：无需人工确认，无信任，自动延时确认安全检查',
        '（磁盘根、项目根等删除硬防线仍生效）',
      ],
    },
    'security.confirmDangerousOps': {
      on: ['开启后：高危操作会额外二次询问，多一步确认'],
      off: ['关闭后：高危操作将不再二次询问，直接执行'],
    },
  };
  const dangerDirtyKeys = DANGEROUS_KEYS.filter((k) => state.dirtyKeys[k]);
  // 2026-10-11 00:35 小欧 - 两处取值的实际形状与假设相反，均由浏览器实测抓出（不是理论推断）：
  //   dirtyKeys[key] 只是"该键脏了"的布尔标记（useSettings：`dirtyKeys[key] = true`），
  //      不是旧值。拿它当 from 会导致无论往哪个方向改都显示"开启→关闭"。
  //   state.values 是按组分层的 `{ [group]: { [key]: value } }`（useSettings 同源），
  //      不是扁平 `values[key]`。扁平取会恒为 undefined → to 恒为"关闭"。
  //   旧值权威在 state.baseline[tab][key]（与 L498 判脏那行同源），新值在 state.values[tab][key]。
  const readBool = (
    src: Record<string, Record<string, unknown>> | undefined,
    key: string
  ): boolean => {
    const tab = s.groupOfKey(key);
    const v = tab ? src?.[tab]?.[key] : undefined;
    return typeof v === 'boolean' ? v : v === 'true';
  };
  const dangerChanges = dangerDirtyKeys.map((k) => ({
    label: DANGER_LABELS[k] ?? k,
    from: readBool(state.baseline, k) ? '开启' : '关闭',
    to: readBool(state.values, k) ? '开启' : '关闭',
  }));
  // 后果按变更分组：**开与关两个方向都给说明**（只给关闭方向会导致"改一项且是开启方向"时说明区空白）
  const dangerHintByChange = Object.fromEntries(
    dangerDirtyKeys.map((k) => {
      const label = DANGER_LABELS[k] ?? k;
      const eff = DANGER_EFFECTS[k];
      const lines = eff ? (readBool(state.values, k) ? eff.on : eff.off) : [];
      return [label, lines];
    })
  );

  // 2026-09-24 小欧 - 收口：env 接管判定单点（能力行/添加参数/管理选项共用；providerConfig.env
  //   单一真相源——不用 envOverride，其 keys 来自 model_params，无参数模型会是 {} 判不出）
  const envManaged =
    state.model.providerConfig[state.model.selectedProvider]?.env === true;

  // 2026-09-24 小欧 - 落盘成功后同步 mtime+刷新模型列表（DRY：Provider 配置保存/清空 key/模型库保存共用收口）- 小欧-2026-09-24
  const afterModelSaved = async (mtime: number) => {
    s.syncMtime(mtime);
    await s.refreshModels();
  };

  // 修正(2026-09-21 小强)：模型组脏计数按实际脏参数数（原是 isDirty?1:0 恒 1 项误导）
  // 2026-09-24 小欧 - removedParams 计入模型组脏计数（删键是独立待存变更，与 dirtyCount 同口径）- 小欧-2026-09-24
  // 2026-09-24 小欧 - 修复：补能力脏 +1（与 useSettings dirtyCount/isGroupDirty 同口径——
  //   原仅改能力时「保存本组」可点却显示 0 项，计数失真）- 小欧-2026-09-24
  // 2026-09-27 小欧 - 补草稿键数（改了几个字段=几项，与 dirtyCount 同口径）- 小欧-2026-09-27
  const groupDirtyCount =
    state.activeTab === 'model'
      ? Object.values(
          isDirty(
            state.model.params,
            state.model.baseline,
            state.model.envOverride
          )
        ).filter(Boolean).length +
        state.model.removedParams.length +
        (isCapsDirty(
          state.model.inputModalities,
          state.model.inputModalitiesBaseline
        ) ||
        isCapsDirty(
          state.model.outputModalities,
          state.model.outputModalitiesBaseline
        )
          ? 1
          : 0) +
        Object.keys(state.model.providerDraft).length
      : Object.keys(state.dirtyKeys).filter(
          (k) => s.groupOfKey(k) === state.activeTab
        ).length;

  if (state.loading) {
    return (
      <div
        className="settings-page"
        style={{
          padding: settingsSpacing.pagePadding,
          background: Colors.BG.PRIMARY,
        }}
      >
        <Skeleton active />
      </div>
    );
  }
  if (state.loadError) {
    return (
      <div
        className="settings-page"
        style={{
          padding: settingsSpacing.pagePadding,
          background: Colors.BG.PRIMARY,
        }}
      >
        <Result
          status="error"
          title="设置加载失败"
          subTitle={state.loadError}
          extra={
            <Button
              onClick={() => {
                void s.load();
              }}
            >
              重试
            </Button>
          }
        />
      </div>
    );
  }

  const renderGeneralTab = () => (
    <div>
      <CurrentModelRefCard
        currentRef={state.currentRef}
        providers={state.model.providers}
        onModelSwitched={() => void s.load()}
        onAddProvider={jumpToProviderConfig}
      />
      <SettingsGroup
        group="general"
        items={state.schema['general']?.items ?? []}
        values={state.values['general'] ?? {}}
        sources={state.sources['general'] ?? {}}
        dirtyKeys={state.dirtyKeys}
        highlightKey={s.highlightKey}
        onChange={s.setValue}
      />
    </div>
  );

  // 2026-11-08 小欧 - 图片实测迁入②：探测目标 = ①选中的 provider+模型，unconclusive 不落库不给结论
  const runProbe = async () => {
    const provider = state.model.selectedProvider;
    const model = state.model.selectedModel;
    if (!provider || !model || probing) return;
    setProbing(true);
    try {
      const r = await modelApi.probeMedia(provider, model);
      // 未取证(限流/鉴权/5xx/无图像 token 字段)不当实测结果，也不覆盖已存结论 — 小欧-2026-11-08
      if (!r.conclusive) {
        showMessage(ErrorType.WARNING, r.message);
        return;
      }
      await s.refreshModels();
      // 探测写盘绕过保存链，页面缓存 mtime 已过期；回填后紧接着的保存不再被守卫拒 — 小欧-2026-11-08
      try {
        s.syncMtime(await settingsApi.getMtime());
      } catch {
        // mtime 回填失败只影响下一次保存的守卫比对，静默
      }
      if (r.ok) showSuccess(r.message);
      else showMessage(ErrorType.WARNING, r.message);
    } catch {
      showMessage(
        ErrorType.WARNING,
        '探测失败，请检查 Provider 配置的网络可达性'
      );
    } finally {
      setProbing(false);
    }
  };

  const renderModelTab = () => {
    // 2026-11-01 小欧 - #4 常显化判据：原条件渲染的布尔量提取，一次计算两处引用 — 小欧-2026-11-01
    const hasManagementOptions =
      Object.keys(state.model.paramOptions).length > 0;
    // 2026-11-01 小欧 - 全域放弃判据：③Provider 草稿纳入「放弃修改」点亮条件（账本拆分反人类病根，
    //   北京老陈实证：改了③区点放弃无反应）— 小欧-2026-11-01
    const hasProviderDraft = Object.keys(state.model.providerDraft).length > 0;
    // 2026-11-08 小欧 - 图片实测取值单源 = providers[].models[].media（取证即落库，页面不持临时结果）— 小欧-2026-11-08
    const selectedEntry = state.model.providers
      .find((p) => p.name === state.model.selectedProvider)
      ?.models.find((m) => m.name === state.model.selectedModel);
    const media = selectedEntry?.media;
    const accept = media?.accept?.image;
    const urlTested = urlTestedOf(media);
    const imageChecked = state.model.inputModalities.includes('image');
    // 未测时按勾选区分「未测 / 不适用」；已测则如实显示，与勾选状态解耦
    const showInapplicable = !accept && !imageChecked;
    const probeMain = showInapplicable ? '不适用' : acceptMain(accept);
    const probeSub = showInapplicable
      ? '未勾选「图片」输入模态'
      : acceptSub(accept, urlTested);
    const probeColor = !accept
      ? Colors.TEXT.WEAK
      : accept === 'none'
        ? Colors.ERROR
        : Colors.SUCCESS;
    let probeTip = acceptTip(accept, urlTested);
    if (showInapplicable) {
      probeTip =
        '未勾选「图片」输入模态——当前配置不会发送图片，实测无从谈起。勾选「图片」后此行恢复可用';
    } else if (!imageChecked) {
      probeTip = `${probeTip}（当前未勾选「图片」，图片不会发送）`;
    }
    return (
      <div>
        <div data-section="selector">
          {/* 修正(2026-09-21 小强)：删除「当前系统全局使用模型」冗余小字——该信息已由
            通用 Tab CurrentModelRefCard 完整展示（标题+卡内文案），此处重复（[设置页UI审计] 问题17） */}
          {/* ①标题行 = 三列 grid（1fr 1fr 1fr）：标题左列 | 按钮组中列左对齐 | 右列空 — ①②③统一布局 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              alignItems: 'center',
            }}
          >
            <SectionTitle title="── ① 选择器 ──" />
            <div
              style={{ display: 'flex', gap: Spacing.SM, justifySelf: 'start' }}
            >
              <Button
                icon={<PlusOutlined />}
                style={{ width: settingsControl.actionBtnWidth }}
                onClick={() => s.patchModel({ addModelModalOpen: true })}
              >
                添加模型
              </Button>
              <Button
                icon={<PlusOutlined />}
                style={{ width: settingsControl.actionBtnWidth }}
                onClick={() => s.patchModel({ addProviderModalOpen: true })}
              >
                添加 Provider
              </Button>
            </div>
          </div>
          <ModelSelector
            providers={state.model.providers}
            selectedProvider={state.model.selectedProvider}
            selectedModel={state.model.selectedModel}
            onSelectProvider={s.selectProvider}
            onSelectModel={s.selectModel}
          />
        </div>
        {/* ②标题行 = 三列 grid（1fr 1fr 1fr）：标题左列 | 按钮组中列左对齐 | 右列空 — ①②③统一布局 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            alignItems: 'center',
          }}
        >
          <SectionTitle title="── ② 选中模型参数 ──" />
          {/* 三按钮组：同款默认 Button + settingsControl.actionBtnWidth 等长（消 width:120×3）
            + gap SM 紧挨，整组居中；
            添加参数 = 管 model_params，管理选项 = 管 param_options，重置 = 回默认值 */}
          <div
            style={{ display: 'flex', gap: Spacing.SM, justifySelf: 'start' }}
          >
            <Button
              icon={<PlusOutlined />}
              style={{ width: settingsControl.actionBtnWidth }}
              // 2026-09-24 小欧 - env 接管禁添加（后端拒保存）+ 保存中禁（防保存期间改 state）— 小欧-2026-09-24
              disabled={s.saving || envManaged}
              onClick={() => s.patchModel({ addParamFormOpen: true })}
            >
              添加模型参数
            </Button>
            {/* 2026-11-01 小欧 - 终裁（北京老陈）：两颗灰钮不藏，常显——位置恒定不跳位。
              Tip 只解释「为什么灰」，严禁说「没有参数」（③区有值时那是瞎话）— 小欧-2026-11-01 */}
            <Tooltip
              title={
                !hasManagementOptions
                  ? '还没有可管理的参数选项——添加模型勾选「参数选项」后这里才可用'
                  : undefined
              }
            >
              <span style={{ display: 'inline-flex' }}>
                <Button
                  style={{ width: settingsControl.actionBtnWidth }}
                  // 2026-09-24 小欧：env 接管与保存中均禁（后端拒保存/防并发写）— 小欧-2026-09-24
                  disabled={s.saving || envManaged || !hasManagementOptions}
                  onClick={() => s.patchModel({ paramOptionsModalOpen: true })}
                >
                  管理推理深度
                </Button>
              </span>
            </Tooltip>
            {/* 2026-11-01 小欧 - 终裁（北京老陈）：本钮同样不藏、常显（同「管理推理深度」）。
              同日扩权：③Provider 草稿一并纳入点亮与放弃范围。灰态 Tip 一句真话，
              「此模型还没有参数」分支铲除（③区有值时说「没有参数」是瞎话）— 小欧-2026-11-01 */}
            <Tooltip
              title={
                !state.model.isDirty && !hasProviderDraft
                  ? '还没改过任何参数，不用放弃'
                  : undefined
              }
            >
              <span style={{ display: 'inline-flex' }}>
                <Button
                  style={{ width: settingsControl.actionBtnWidth }}
                  // 2026-09-24 小欧：保存中禁放弃修改（防保存期间改 state 致快照错位）— 小欧-2026-09-24
                  disabled={
                    (!state.model.isDirty && !hasProviderDraft) || s.saving
                  }
                  onClick={() => {
                    Modal.confirm({
                      title: (
                        <span
                          style={{
                            fontSize: FontSize.PRIMARY,
                            fontWeight: FontWeight.BOLD,
                          }}
                        >
                          ⚠ 放弃修改
                        </span>
                      ),
                      content: (
                        // 2026-11-01 小欧 - 排版整改（北京老陈）：四类各占一行、行距拉开——原四类连排
                        // 分号绕行糊成一片；关键词仍逐字保留，仅排版重排 — 小欧-2026-11-01
                        <div
                          style={{
                            color: Colors.TEXT.SECONDARY,
                            lineHeight: 2,
                          }}
                        >
                          <div>将放弃该页全部未保存修改：</div>
                          <div>①参数值还原为已保存值</div>
                          <div>②×删除的参数恢复回列表</div>
                          <div>③能力勾选还原为已保存勾选</div>
                          <div>
                            ④Provider
                            配置（地址/显示名/超时/重试/速率限制）还原为已保存值
                          </div>
                          <div style={{ marginTop: Spacing.SM }}>
                            已保存的配置不受影响，此操作只撤内存草稿、不改动后端。
                          </div>
                        </div>
                      ),
                      okText: '确认放弃',
                      okButtonProps: { danger: true },
                      cancelText: '取消',
                      width: settingsModalWidth.confirm,
                      onOk: () => {
                        // 2026-09-24 小欧 - 闭环：保存进行中确认放弃竞态守卫（防放弃覆写保存中快照）
                        // 2026-11-01 小欧 - 扩权：③Provider 草稿一并清 + ProviderConfig 重挂载
                        //   复位本地输入（重挂载后 effect 空diff上报，setProviderDraft 等值去重不干扰）
                        if (s.saving) return;
                        s.resetParams();
                        s.patchModel({ providerDraft: {} });
                        setProviderResetSeq((x) => x + 1);
                      },
                    });
                  }}
                >
                  放弃修改
                </Button>
              </span>
            </Tooltip>
          </div>
        </div>
        {/* 2026-09-23 小欧 - 「+ 添加参数」内联表单（勾选多个循环 onAdd，批量完调 onCancel 统一关） */}
        {state.model.addParamFormOpen && (
          <AddParamForm
            existingKeys={Object.keys(state.model.params)}
            onAdd={(key, value, meta) => {
              s.addParam(key, value, meta);
            }}
            onCancel={() => s.patchModel({ addParamFormOpen: false })}
            // 2026-09-24 小欧 - 闭环：保存中禁用表单确认 — 小欧-2026-09-24
            disabled={s.saving}
          />
        )}
        <ModelParams
          params={state.model.params}
          baseline={state.model.baseline}
          ranges={state.model.ranges}
          options={state.model.paramOptions}
          envOverride={state.model.envOverride}
          onChange={s.setParam}
          // 2026-09-24 小欧 - 接 removeParam：行尾 × 点即删（env 接管键组件内 disabled）- 小欧-2026-09-24
          onDelete={s.removeParam}
          // 2026-09-24 小欧 - 保存中(saving) 锁定参数区全部控件+×按钮，防闭包快照错位 — 小欧-2026-09-24
          disabled={s.saving}
        />
        {/* 2026-09-23 小欧 - 模型能力多选行（capabilities → model_meta 通道，与「+ 添加参数」并存）；
          env 接管按 providerConfig.env 禁用（后端 _raise_if_env_takeover 拒保存；不用 envOverride——
          其 keys 来自 model_params，无参数模型会是 {} 判不出）；脏判定走 isCapsDirty → DirtyDot */}
        {/* 2026-11-08 小欧: 输入模态行 → inputModalities，下方输出模态行 */}
        <div style={settingsRowStyle}>
          <span style={settingsLabelStyle}>输入模态</span>
          <span style={{ flex: 1 }}>
            <Checkbox.Group
              value={state.model.inputModalities}
              // 2026-09-24 小欧 - 收口：复用 envManaged 单点（原内联 providerConfig env 判定重复表达式）
              disabled={envManaged}
              options={CAPABILITY_OPTIONS}
              onChange={(v) => s.setInputModalities(v as string[])}
            />
            {/* 2026-09-23 小欧 - 未知能力值灰色只读 Tag（不可关、cursor:not-allowed）——
              yaml 手写非 5 枚举值看得见、本页不提供增删；有未知值才渲染，空则零开销 */}
            {state.model.inputModalities
              .filter((v) => !KNOWN_CAPABILITY_VALUES.has(v))
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
          {/* 2026-09-23 小欧 - && 写法（与 ModelParams 脏点同款，原三元异款） */}
          {isCapsDirty(
            state.model.inputModalities,
            state.model.inputModalitiesBaseline
          ) && <DirtyDot />}
        </div>
        {/* 2026-11-08 小欧 - 图片实测行：实测结论紧贴它所验证的「输入模态」声明——
          声明（厂商说它支持图片）与实测（真的发一张图、以 HTTP 200 且图像 token>0 判定）分列两处，
          冲突时以实测为准。按钮常显不跳位（同标题行灰钮规则），未勾「图片」禁用并说明原因 — 小欧-2026-11-08 */}
        <div style={settingsRowStyle}>
          <span style={settingsLabelStyle}>图片实测</span>
          {/* 结论区：主词（能接收/不能接收/未测/不适用）+ 限定词（通道），整段挂 Tooltip 讲判据与取证 */}
          <Tooltip
            title={
              <div
                style={{
                  fontSize: FontSize.SECONDARY,
                  lineHeight: 1.7,
                  maxWidth: 380,
                }}
              >
                <div>{probeTip}</div>
                {media?.probed_at && (
                  <div style={{ opacity: 0.85 }}>
                    实测于 {media.probed_at.replace('T', ' ')}
                  </div>
                )}
                {media?.evidence && (
                  <div style={{ opacity: 0.7 }}>
                    取证{' '}
                    {media.evidence.length > 140
                      ? `${media.evidence.slice(0, 140)}…`
                      : media.evidence}
                  </div>
                )}
              </div>
            }
          >
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'baseline',
                gap: Spacing.XS,
                cursor: 'help',
              }}
            >
              <span
                style={{
                  fontSize: FontSize.PRIMARY,
                  color: probeColor,
                  borderBottom: `1px dashed ${Colors.TEXT.WEAK}`,
                }}
              >
                {probeMain}
              </span>
              <span
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.WEAK,
                }}
              >
                {probeSub}
              </span>
            </span>
          </Tooltip>
          {/* 动作区靠右固定：结论文案四态长短不一，按钮位置不随文案浮动 */}
          <Tooltip
            title={
              !imageChecked
                ? '先勾选「图片」——图片不会随请求发送，实测无从谈起'
                : '把一张测试图真的发给厂商，以返回值判定：HTTP 200 且返回图像 token>0 才算真收到；200 但 token 为 0 属网关静默丢图。内联必测；外链需先在「媒体 → 外链检测用图片地址」填公网图片地址，否则只测内联'
            }
          >
            <span style={{ marginLeft: 'auto', display: 'inline-flex' }}>
              <Button
                style={{ width: settingsControl.actionBtnWidth }}
                loading={probing}
                disabled={s.saving || !imageChecked}
                onClick={runProbe}
              >
                实测
              </Button>
            </span>
          </Tooltip>
        </div>
        {/* 2026-11-08 小欧: 输出模态行（生成输出能力：生图/生视频，与输入模态分维度） */}
        <div style={settingsRowStyle}>
          <span style={settingsLabelStyle}>输出模态</span>
          <span style={{ flex: 1 }}>
            <Checkbox.Group
              value={state.model.outputModalities}
              disabled={envManaged}
              options={OUTPUT_MODALITY_OPTIONS}
              onChange={(v) => s.setOutputModalities(v as string[])}
            />
            {/* 2026-11-08 小欧: 非可选项（text/audio 等）灰色只读 Tag——与输入模态行同款 */}
            {state.model.outputModalities
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
          {isCapsDirty(
            state.model.outputModalities,
            state.model.outputModalitiesBaseline
          ) && <DirtyDot />}
        </div>
        <div data-section="provider-config">
          {/* 2026-09-24 小欧 - SectionTitle 移入 ProviderConfig（标题+保存按钮同行居中） */}
          <ProviderConfig
            // 2026-11-01 小欧 - key 合入自增序号：放弃修改后重挂载、按 config props（=已保存配置）
            //   重新初始化全部本地输入，达成③区视觉回滚（见本文件头部 providerResetSeq 注释）
            key={`${state.model.selectedProvider}#${providerResetSeq}`}
            name={state.model.selectedProvider}
            config={
              state.model.providerConfig[state.model.selectedProvider] ?? {
                // 2026-09-27 小欧 - 掩码契约 {configured, masked}，与 model.api.ts ProviderEntry /
                // ProviderConfig.config / settings2/types.ts 保持同一契约（缺 masked 键 tsc 直接报错）
                api_key: { configured: false, masked: '' },
                api_base: '',
                label: '',
                timeout: 150, // 缺省 fallback 与后端常量对齐（原 60≠运行时 150）
                max_retries: 3,
                env: false,
              }
            }
            onSave={async (patch) => {
              // 2026-09-27 小欧 - 收口统一落盘链：自带按钮与底部保存栏同走 saveProviderDraft
              //   （updateProvider→syncMtime→reloadProviderCache→清草稿；成功 toast/失败提示在 hook 内），
              //   失败 rethrow 保留 ProviderConfig 输入（原 [设置页UI审计] 问题6 语义不变）- 小欧-2026-09-27
              const r = await s.saveProviderDraft(patch);
              if (!r.ok) throw new Error('provider-config-save-failed');
            }}
            // 2026-09-27 小欧 - 字段 diff 上报：底部保存栏计数/亮起的数据源（空 diff=干净）- 小欧-2026-09-27
            onDraftChange={s.setProviderDraft}
          />
        </div>
        <SectionTitle title="── ④ 操作区 ──" />
        <ModelActions
          configured={
            state.model.providerConfig[state.model.selectedProvider]?.api_key
              ?.configured ?? false
          }
          // A3(2026-09-22 小强)：env 接管 provider 隐藏「清空 api_key」（后端拒 clear）
          // 2026-09-24 小欧 - 收口：复用 envManaged 单点（原独立 `?? false` 表达式与能力行重复）
          envManaged={envManaged}
          onClearApiKey={async () => {
            // 2026-10-11 01:50 小欧 - 补二次确认（删除类危险操作原无二次确认）。
            // 查证：三个危险按钮里「删除此模型」「删除此 Provider」都走 deleteConfirmOpen 有确认，
            // 只有「清空 api_key」直调 updateProvider({clear:true}) 一步到位 —— 危险度却最高：
            // 密钥一清空该 Provider 全部调用立即失败，且不可撤销、只能重新配置才能恢复。
            // 统一走 dangerConfirm 口径（与删除确认同一套壳/危险键），文案说明后果。
            confirmDanger({
              title: '确定清空 api_key？',
              content: (
                <div
                  style={{
                    fontSize: FontSize.SECONDARY,
                    color: Colors.TEXT.SECONDARY,
                  }}
                >
                  清空后：
                  <ul
                    style={{ margin: `${Spacing.SM}px 0 0`, paddingLeft: 20 }}
                  >
                    <li>
                      「{state.model.selectedProvider}」的密钥被抹除，不可撤销
                    </li>
                    <li>该 Provider 的全部模型将立即无法调用</li>
                    <li>需重新填写 api_key 才能恢复使用</li>
                  </ul>
                </div>
              ),
              okText: '确认清空',
              onOk: async () => {
                try {
                  const r = await modelApi.updateProvider(
                    state.model.selectedProvider,
                    { clear: true }
                  );
                  showSuccess('api_key 已清空');
                  // 2026-09-27 小欧 - 修 F7：清空是 api_key 的第二个写入口，须同清草稿，
                  //   否则用户接着点保存会把刚清空的密钥写回。ProviderConfig 的 apiKey 由 masked 变化自动复位。
                  // 2026-10-29 小欧 - 修 Bug2: 立即更新本地 providerConfig 的 api_key(configured=false, masked='')，
                  //   不等 reloadProviderCache 异步返回——否则期间 masked 仍为旧掩码, SecretRevealInput 回填旧串;
                  //   reload 返回后会再次覆盖(此时值已一致, 无副作用) — 小欧-2026-10-29
                  const prevCfg =
                    state.model.providerConfig[state.model.selectedProvider];
                  s.patchModel({
                    providerConfig: {
                      ...state.model.providerConfig,
                      [state.model.selectedProvider]: {
                        ...prevCfg,
                        api_key: { configured: false, masked: '' },
                      },
                    },
                    providerDraft: {},
                  });
                  await afterModelSaved(r.mtime);
                } catch (e) {
                  handleApiError(e);
                }
              },
            });
          }}
          onDeleteModel={() =>
            s.patchModel({
              deleteConfirmOpen: true,
              deleteTarget: `model:${state.model.selectedProvider}::${state.model.selectedModel}`,
            })
          }
          onDeleteProvider={() =>
            s.patchModel({
              deleteConfirmOpen: true,
              deleteTarget: `provider:${state.model.selectedProvider}`,
            })
          }
        />
        {/* 2026-09-22 小欧 - 管理选项弹窗（②区标题行「管理选项」入口；保存后
          refreshModels 重拉 param_options + baseline，与添加模型后回显同通道） */}
        <ParamOptionsModal
          open={state.model.paramOptionsModalOpen}
          provider={state.model.selectedProvider}
          model={state.model.selectedModel}
          paramOptions={state.model.paramOptions}
          baseline={state.model.baseline}
          onClose={() => s.patchModel({ paramOptionsModalOpen: false })}
          // 2026-09-24 小欧 - 闭环：保存中禁用弹窗提交 — 小欧-2026-09-24
          disabled={s.saving}
          onSaved={async () => {
            if (state.model.selectedProvider && state.model.selectedModel)
              await s.refreshModels({
                provider: state.model.selectedProvider,
                model: state.model.selectedModel,
              });
          }}
        />
      </div>
    );
  };

  return (
    <div
      className="settings-page"
      style={{
        padding: settingsSpacing.pagePadding,
        background: Colors.BG.PRIMARY,
      }}
    >
      {/* 2026-10-03 小欧 - ModelModals 由 renderModelTab 内提到页面顶层：原挂在 model Tab 渲染函数
          (310-633) 里，而 model_library Tab 不调该函数 -> 弹窗组件根本不挂载，置
          addProviderModalOpen=true 也无人渲染，表现为「点了没反应」。弹窗走 portal 挂
          document.body，移出不影响 DOM 位置，也不改 model Tab 原行为。 */}
      <ModelModals
        providers={state.model.providers}
        addModelOpen={state.model.addModelModalOpen}
        addProviderOpen={state.model.addProviderModalOpen}
        deleteOpen={state.model.deleteConfirmOpen}
        deleteTarget={state.model.deleteTarget}
        selectedProvider={state.model.selectedProvider}
        onCloseAddModel={() => s.patchModel({ addModelModalOpen: false })}
        onCloseAddProvider={() => s.patchModel({ addProviderModalOpen: false })}
        onCloseDelete={() =>
          s.patchModel({ deleteConfirmOpen: false, deleteTarget: null })
        }
        onSubmitAddModel={async (d) => {
          try {
            const res = await modelApi.addModel({
              provider: d.provider,
              model: d.model,
              label: d.label,
              ...(d.model_params ? { model_params: d.model_params } : {}),
              ...(d.range ? { range: d.range } : {}),
              ...(d.input_modalities
                ? { input_modalities: d.input_modalities }
                : {}),
              ...(d.output_modalities
                ? { output_modalities: d.output_modalities }
                : {}),
              ...(d.param_options ? { param_options: d.param_options } : {}),
            });
            s.syncMtime(res.mtime);
            showSuccess('模型已添加');
            await s.refreshModels({ provider: d.provider, model: d.model });
            // 修正(2026-09-21 小强)：成功才关窗（原 catch 外统一关，保存失败也关+输入被清）；失败 rethrow 让弹窗保留输入（[设置页UI审计] 问题9）
            s.patchModel({ addModelModalOpen: false });
          } catch (e) {
            handleApiError(e);
            throw e;
          }
        }}
        onSubmitAddProvider={async (d) => {
          try {
            const res = await modelApi.addProvider(d);
            s.syncMtime(res.mtime);
            // 修正(2026-09-21 小强)：添加后引导切换新 Provider 配置区——原无任何引导、停留旧 Provider
            showSuccess('Provider 已添加，请在选择器切换到新 Provider 配置');
            await s.refreshModels();
            s.patchModel({ addProviderModalOpen: false });
          } catch (e) {
            handleApiError(e);
            throw e;
          }
        }}
        onConfirmDelete={async () => {
          // 2026-09-24 小欧 - 删除前先强制保存模型 Tab 未落库改动——删除成功后的 load() 会全量
          //   重建 model 态（baseline/params/能力/删除名单全部重载），不保存会静默丢弃当前焦点模型的
          //   未存参数/能力/删除意图；与 selectProvider/selectModel 同款防线（复用 ensureModelSaved）
          if (!(await s.ensureModelSaved())) return;
          const target = state.model.deleteTarget ?? '';
          try {
            let res;
            if (target.startsWith('provider:')) {
              res = await modelApi.deleteProvider(
                target.slice('provider:'.length)
              );
              if (res.switched_to)
                showMessage(
                  ErrorType.INFO,
                  `已切换回默认 Provider：${res.switched_to}`
                );
            } else {
              // 修复：模型名可含 '/'（如 z-ai/glm-4.7），改用 '::' 分隔解析，杜绝删除错位；
              // 改用首个 '::' 索引切片，模型名含 '::' 时不再被 split 截断误删
              const rest = target.slice('model:'.length);
              const sepIndex = rest.indexOf('::');
              const p = sepIndex >= 0 ? rest.slice(0, sepIndex) : '';
              const m = sepIndex >= 0 ? rest.slice(sepIndex + 2) : rest;
              res = await modelApi.deleteModel(p, m);
              if (res.switched_to)
                showMessage(
                  ErrorType.INFO,
                  `已切换回默认模型：${res.switched_to}`
                );
            }
            s.syncMtime(res.mtime);
            // 小欧 2026-09-21: 删除后整体 load()——焦点(selectedProvider/Model)/currentRef/参数区
            //   全部重载对齐后端，杜绝「删的是全局当前模型时前端仍停在已删模型上(悬空+保存报错)」
            await s.load();
            // 修正(2026-09-21 小强)：成功才关删除确认（原 catch 外统一关，失败也关，用户看不到错因）（[设置页UI审计] 问题9）
            s.patchModel({ deleteConfirmOpen: false, deleteTarget: null });
          } catch (e) {
            handleApiError(e);
          }
        }}
      />
      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: Spacing.SM,
          }}
        >
          <span>
            <Tabs
              type="line"
              activeKey={state.activeTab}
              onChange={(k) => requestTab(k as TabKey)}
              // antd Tab 栏自带 margin-bottom:16px，与本行 marginBottom、Card padding:24
              // 三层叠加成 52px 纯空白。归零后由外层间距统一控制；不动 Card padding(会波及 8 个 Tab) - 小欧 2026-09-29
              tabBarStyle={{ marginBottom: 0 }}
              items={s.GROUP_ORDER.map((g) => ({
                key: g,
                // 2026-11-01 小欧 - 组级脏点常显占位（北京老陈批准主案）：亮=该组有未保存，
                //   灭=透明占位保持列宽零跳变；「有 N 项未保存」计数归底部保存按钮 — 小欧-2026-11-01
                label: (
                  <span
                    style={{ display: 'inline-flex', alignItems: 'center' }}
                  >
                    {SettingIcon[g]} {state.schema[g]?.label ?? g}
                    <TabDirtyDot on={s.isGroupDirty(g)} />
                  </span>
                ),
              }))}
            />
          </span>
          <SearchBox schema={state.schema} onJump={jumpTo} />
        </div>
        {state.activeTab === 'model' ? (
          renderModelTab()
        ) : state.activeTab === 'general' ? (
          renderGeneralTab()
        ) : state.activeTab === 'model_library' ? (
          <ModelLibraryTab
            providers={state.model.providers}
            onSaved={afterModelSaved}
            // 2026-10-03 小欧 - 与 :322 给 ModelSelector 的回调逐字相同，复用同一弹窗与同一状态
            onAddProvider={() => s.patchModel({ addProviderModalOpen: true })}
          />
        ) : (
          <SettingsGroup
            group={state.activeTab}
            items={state.schema[state.activeTab]?.items ?? []}
            values={state.values[state.activeTab] ?? {}}
            sources={state.sources[state.activeTab] ?? {}}
            dirtyKeys={state.dirtyKeys}
            // 2026-09-21 小强 - 修复类型瑕疵：highlightKey 为 useSettings 独立 state（非 SettingsState 字段），直接引用返回值等价
            highlightKey={s.highlightKey}
            onChange={s.setValue}
            // 2026-09-26 - 小欧 - secret 项（api_key / 访问口令）走各自专用通道
            //   落盘后，用 load() 重新拉取以刷新掩码与"已配置"状态。**不能用 setValue 充当刷新**——
            //   它会把该 key 置脏，而 secret 已在 settings 写路径显式拒绝，
            //   用户随后点"保存本组"会因这个脏 secret 而整组失败（改 A 坏 B）。
            // 2026-09-26 小欧 - 传 keepModel —— 只刷新设置区以更新掩码/已配置态，
            //   保住模型区未保存的参数/能力/env/provider 切换（load 默认会重建模型区并静默丢弃它们）— 小欧-2026-09-26
            onRefresh={() => void s.load({ keepModel: true })}
          />
        )}
        <SaveBar
          canSaveGroup={s.isGroupDirty(state.activeTab)}
          canSaveAll={s.dirtyCount > 0}
          dirtyCount={s.dirtyCount}
          groupDirtyCount={groupDirtyCount}
          saving={s.saving}
          restartKeys={s.restartKeys}
          dangerousGroup={dangerousGroup}
          dangerousAll={dangerousAll}
          dangerChanges={dangerChanges}
          dangerHintByChange={dangerHintByChange}
          // 修复：直接透出 Promise，SaveBar 确认弹窗 onOk await 化后自带 loading 防连点
          onSaveGroup={() => s.saveGroup(state.activeTab)}
          onSaveAll={() => s.saveAll()}
          onCloseRestart={() => s.setRestartKeys([])}
        />
      </Card>
      <SettingsModal
        open={pendingJump !== null}
        title="有未保存的修改"
        width="confirm"
        // 2026-09-27 小欧 - 修 F8：onOk 走 void ...then() 不返回 Promise，antd 不会自带 loading，
        //   双击「保存并切换」会连发两次 saveGroup。复现 SaveBar 同源：saving → confirmLoading
        confirmLoading={s.saving}
        onCancel={() => setPendingJump(null)}
        // 2026-10-11 01:35 小欧 - 三键（原两键缺"不保存直接切走"这条路）
        //   改前只有「保存并切换」/「留在本页」：用户想**不保存直接切走**时无路可走，
        //   只能先保存或被迫留在本页 → 功能缺口（非视觉问题）。
        //   现三键覆盖三种意图，且危险度递减排列：
        //     留在本页（次要，= 关闭弹窗，改动保留）
        //     放弃修改并切换（默认键但 danger，明确告知会丢弃）
        //     保存并切换（primary，= 主动作）
        //   走 footer 数组而非 ok/cancel 两键，SettingsModal 已支持 footer 直传。
        footer={[
          <Button key="stay" onClick={() => setPendingJump(null)}>
            留在本页
          </Button>,
          <Button
            key="discard"
            danger
            onClick={() => {
              const jump = pendingJump;
              setPendingJump(null);
              // 放弃当前组未保存改动：load(reset) 清 dirtyKeys/values 回基线，与 SettingsPage 其它复位同源
              s.load({ reset: true });
              if (!jump) return;
              s.setActiveTab(jump.tab);
              if (jump.key) {
                s.setHighlightKey(jump.key);
                scrollToKey(jump.key);
              }
              if (jump.anchor)
                requestAnimationFrame(() => scrollTo(jump.anchor as string));
            }}
          >
            放弃修改并切换
          </Button>,
          <Button
            key="save"
            type="primary"
            loading={s.saving}
            onClick={() => {
              const jump = pendingJump;
              if (!jump) return;
              void s.saveGroup(state.activeTab).then((r) => {
                if ((r as { ok: boolean }).ok) {
                  s.setActiveTab(jump.tab);
                  if (jump.key) {
                    s.setHighlightKey(jump.key);
                    scrollToKey(jump.key);
                  }
                  if (jump.anchor)
                    requestAnimationFrame(() =>
                      scrollTo(jump.anchor as string)
                    );
                }
                setPendingJump(null);
              });
            }}
          >
            保存并切换
          </Button>,
        ]}
      >
        {/* 2026-10-11 01:35 小欧 - 文案随之改三行，与三个按钮一一对应（按钮名由按钮承载，
            正文只讲后果，避免复述）。保留"修改不会丢失"的准确语义
            （修正2026-09-21 小强，[设置页UI审计] 问题4）。 */}
        <div
          style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}
        >
          当前组有未保存的修改：
          <ul style={{ margin: `${Spacing.SM}px 0 0`, paddingLeft: 20 }}>
            <li>保存并切换：－改动写入配置文件后跳转</li>
            <li>放弃修改并切换：－本次改动丢弃、不可恢复，直接跳转</li>
            <li>留在本页：－改动保留不丢，弹窗关闭</li>
          </ul>
        </div>
      </SettingsModal>
    </div>
  );
};

export default SettingsPage;
