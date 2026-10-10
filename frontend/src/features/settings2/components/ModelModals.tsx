// 编辑历史: 2026-09-20 小强 - 新建：模型管理弹窗（添加模型/Provider + 删除确认含级联警告）
// 编辑历史: 2026-09-21 小强 - onSubmitAddModel 类型补齐 default_params?(Record<string, unknown>)——SettingsPage 提交处按参考扩展该字段，缺此声明 tsc 报错 — 小强-2026-09-21
// 编辑历史: 2026-09-21 小强 - 修复 BUG-A：mProvider 仅 useState 初始化一次，父级 selectedProvider 变化后弹窗仍指向旧 Provider（陈旧状态）；加 useEffect 联动
// 2026-09-21 小欧 - 实施：添加 Provider 弹窗增 api_key 输入框
// 2026-09-21 小欧 - 实施：弹窗视觉优化——描述行/danger/⚠/后果说明
// 2026-09-21 小欧 - 全文核查：①表单弹窗显式 form 宽、③确认弹窗宽散落 480 → settingsModalWidth.form/confirm 令牌收口（设计文档 v1.12 规范一）
// 2026-09-21 小欧 - 全文核查：规范二落地——①②③弹窗标题显式 fontSize:PRIMARY(14)+fontWeight:BOLD，弃用 antd 默认16px；描述行 marginBottom:12 → Spacing.LG（设计文档 v1.12 规范二）
// 2026-09-21 小强 - 设置页17问题复核修复：删除标题剥离 model:/provider: 内部前缀；添加弹窗 busy+confirmLoading 防连点双发、
//   失败不关窗不 reset（父级 rethrow）；onSubmitAddModel/Provider 类型改 Promise<void>（[设置页UI审计] 问题3/9）
// 2026-09-22 小欧 - 实施：添加模型弹窗加「参数模板」区——候选=所选Provider兄弟模型
//   default_params∪param_options key 并集；勾选即带入默认值（兄弟default_params，reasoning_effort→medium兜底），
//   控件按 opts→Select/数字→InputNumber/其他→Input；切Provider重算清空；成功重置。
//   Props onSubmitAddModel 加 range?/capabilities?/param_options?；handleAddModel 透传 collected.{params,options}
// 2026-09-22 小欧 - E2E 抓真bug修复：勾选行有兄弟 param_options 时, 仅写 collected.params 而 options 恒空
//   → handleAddModel 的 param_options 永远空 → 新模型 model_meta 不落 options → 回显无下拉。
//   修复：勾选时若 opts 存在同步带 options[key]=opts, 取消则删（POST 体含 param_options + config.yaml 落盘 + 回显下拉验证通过）
// 2026-09-22 小欧 - 实施：onSubmitAddProvider Props 加 timeout?/max_retries?；添加 Provider
//   弹窗表单 api_key 后新增 timeout(秒) min1 默认60占位、max_retries min0 默认3占位两个 InputNumber
//   （配合 model.api.ts addProvider 入参补两字段，创建时即可自定义超时/重试）
// 2026-09-22 小欧 - 控件宽度统一：参数模板区硬编码 minWidth:160/maxWidth:240 改用 settingsControl 令牌 - 小欧-2026-09-22
// 2026-09-22 小欧 - DRY 收口：参数模板区 Select/InputNumber/Input 三控件 onChange 的「勾选才收集+params合并」
//   重复 → 抽取 updateCollectedParam 单函数（函数式更新防闭包陈旧值）- 小欧-2026-09-22
// 2026-09-26 - 小欧 - 实施：添加 Provider 弹窗的 api_base 改必填（rules required +
//   自定义 validator 拒纯空白），未填不提交；与 api_key 的"未配置则留空"方向相反（api_key 允许先建后填）。
//   后端 add_provider 同步校验 → 400，前后端双闸。
// 2026-09-27 - 小欧 - 实施：提交前 trim api_key（与 ProviderConfig.doSave、后端 add_provider 同一口径）。
// 2026-10-03 小欧 - 添加 Provider 弹窗三处修（北京老陈截图指出）：
//   ①api_key 补 autoComplete="new-password" —— Input.Password 的 type=password 被 Chrome 密码
//     管理器自动填已存口令（浅蓝底+掩码点），不察觉直接保存会把浏览器口令写进 config.yaml；
//     口径对齐 SecretRevealInput:141。②onCancel 补 pForm.resetFields()，取消再打开不再残留上次
//   填写（此前只在提交成功后重置）。③timeout/max_retries 改 Row/Col 并排一行 — 小欧 2026-10-03
// 2026-10-10 小欧 - 添加模型弹窗四处（北京老陈截图指出）：①Provider/模型名改 Row/Col 并排一行（照抄本文件
//   timeout/max_retries 同款写法）；②删除「显示名」输入项——与模型名恒一致，无输入意义，提交 label 同步
//   恒等模型名；③参数模板候选追加 PARAM_PRESETS 且默认值/选项回落预设表——无兄弟模型时不再空白
//   （原仅取 sibModels[0]，且 reasoning_effort→medium 写死特例由预设 default 替代删除）；
//   ④模板行 key 定宽 180 对齐输入框起点（此前参差），布尔项改 Switch 渲染、旧字符串 "true" 仅管显示
//   提交一律布尔，seed 等 default:null 显示改 ?? '' 兜底（String(null) 会显示字面量 "null"）— 小欧-2026-10-10
// 编辑历史: 2026-10-10 小欧 - 添加 Provider 弹窗三项: ①名称/显示名改并排一行(Row+Col12, 同款 timeout/max_retries);
//   ②底部加「模型」区(输入框+＋按钮攒列表, 确定时随 models 字段一次提交, 后端 add_provider 原生透传无半成功窗口);
//   ③收紧留白(每个 Form.Item marginBottom 12px, antd 默认 24px 砍半)治纵向稀疏 — 小欧-2026-10-10

import React, { useEffect, useState } from 'react';
import {
  Button,
  Checkbox,
  Col,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Typography,
} from 'antd';
import {
  DeleteOutlined,
  ExclamationCircleFilled,
  PlusOutlined,
} from '@ant-design/icons'; // 2026-10-10 小欧: 模型增删行图标; 22:15 删除确认 emoji⚠ 换矢量图标
import { SettingsModal, ModalSection, CodeChip } from '@/theme/SettingsModal'; // 2026-10-10 小欧: 3个弹窗归一到底壳; 22:15 补 ModalSection/CodeChip
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsControl, settingsModalWidth } from '@/theme/settingsTokens';
import type { ProviderEntry } from '@/services/api/model.api';
import { PARAM_PRESETS } from '../utils/modelUtils';

/**
 * 2026-10-10 22:15 小欧 - 模板区分组顺序：枚举 → 数值/文本 → 开关。
 * 枚举最需选值排最前，开关只勾选无值排最后；顺序即"操作密度"从高到低。
 * 三组互斥且并集覆盖全部候选 key（判定见 collectDefaultVal/collectOpts），无第四组。
 */
const PARAM_GROUPS = [
  { kind: 'enum', label: '枚举参数（可多选）' },
  { kind: 'value', label: '数值 / 文本参数' },
  { kind: 'bool', label: '开关参数' },
] as const;

interface Props {
  providers: ProviderEntry[];
  addModelOpen: boolean;
  addProviderOpen: boolean;
  deleteOpen: boolean;
  deleteTarget: string | null;
  selectedProvider: string;
  onCloseAddModel: () => void;
  onCloseAddProvider: () => void;
  onCloseDelete: () => void;
  onSubmitAddModel: (data: {
    provider: string;
    model: string;
    label: string;
    default_params?: Record<string, unknown>;
    range?: Record<string, { min: number; max: number }>;
    capabilities?: string[];
    param_options?: Record<string, string[]>;
  }) => Promise<void>;
  onSubmitAddProvider: (data: {
    name: string;
    label: string;
    api_base: string;
    api_key?: string;
    timeout?: number;
    max_retries?: number;
    // 2026-10-10 小欧 - models 随 Provider 一并提交（后端 add_provider 原生透传 req.models，
    //   一次调用；此前此处置空、靠循环调 N 次单模型接口，又慢又有半成功窗口）
    models?: string[];
  }) => Promise<void>;
  onConfirmDelete: () => void;
}

export const ModelModals: React.FC<Props> = (props) => {
  const { providers, addModelOpen, addProviderOpen, deleteOpen, deleteTarget } =
    props;
  const [mForm] = Form.useForm();
  const [pForm] = Form.useForm();
  const [mProvider, setMProvider] = useState(props.selectedProvider);
  // 修正(2026-09-21 小强)：busy 态驱动 Modal confirmLoading 防连点双发（原 onOk 走 .then() 无 loading，
  // 双击触发两次提交）；失败父级 rethrow 不关窗，输入保留（[设置页UI审计] 问题9）
  const [busy, setBusy] = useState<'model' | 'provider' | null>(null);
  // 2026-10-10 小欧 - Provider 弹窗底部顺带加模型：输入框 + 按钮攒列表，
  //   确定时先建 Provider 再逐个调 onSubmitAddModel（复用既有单模型接口，不新增后端）。
  //   失败任一即停并保留输入（与 handleAddProvider 同款"输入保留、弹窗不关"）。
  const [newModels, setNewModels] = useState<string[]>([]);
  const [modelInput, setModelInput] = useState('');
  const [modelErr, setModelErr] = useState('');
  // 2026-09-21 BUG-A 修复：父级切换所选 Provider 时联动弹窗内 Provider 下拉，防陈旧值
  useEffect(() => {
    setMProvider(props.selectedProvider);
  }, [props.selectedProvider]);

  // 模板区：候选 = 所选 Provider 已有模型 default_params ∪ param_options key 并集
  const sibModels = providers.find((p) => p.name === mProvider)?.models ?? [];
  const candKeys = Array.from(
    new Set([
      ...sibModels.flatMap((m) => [
        ...Object.keys(m.default_params ?? {}),
        ...Object.keys(m.param_options ?? {}),
      ]),
      ...PARAM_PRESETS.map((p) => p.key),
    ])
  );
  // 勾选状态 + 值收集（勾中才送后端，未勾不送该 key——与现状 {} 兼容）
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [collected, setCollected] = useState<{
    params: Record<string, unknown>;
    options: Record<string, string[]>;
  }>({ params: {}, options: {} });
  // 切 Provider 重算候选并清空已勾（与 BUG-A 的 mProvider 联动放一处）
  useEffect(() => {
    setChecked({});
    setCollected({ params: {}, options: {} });
  }, [mProvider]);

  // 修正(2026-09-21 小强)：删除标题剥离 model:/provider: 内部前缀——原 deleteTarget 直接注入标题，
  // 显示 "model:openai::gpt-4o" 泄漏内部格式（[设置页UI审计] 问题3）
  const deleteLabel = (t: string | null): string => {
    if (!t) return '';
    const idx = t.indexOf(':');
    return idx > 0 ? t.slice(idx + 1) : t;
  };

  const handleAddModel = async () => {
    if (busy) return;
    const v = await mForm.validateFields().catch(() => null);
    if (!v) return;
    setBusy('model');
    try {
      // 模板区勾选项由 collected.{params,options} 供给——勾了才送，未勾不送该 key
      await props.onSubmitAddModel({
        provider: mProvider,
        model: v.model,
        label: v.model,
        ...(Object.keys(collected.params).length
          ? { default_params: collected.params }
          : {}),
        ...(Object.keys(collected.options).length
          ? { param_options: collected.options }
          : {}),
      });
      mForm.resetFields();
      // 成功重置模板区勾选/收集
      setChecked({});
      setCollected({ params: {}, options: {} });
    } catch {
      /* 保存失败：输入保留、弹窗不关（父级已弹错） */
    } finally {
      setBusy(null);
    }
  };

  const handleAddProvider = async () => {
    if (busy) return;
    const v = await pForm.validateFields().catch(() => null);
    if (!v) return;
    // 2026-09-27 - 小欧 - 实施: api_key 落盘前 trim（与 ProviderConfig.doSave 同一口径）。
    //   后端 add_provider 已同步 strip（此前只有后端兜底、前端不回传），此处为体验一致；
    //   留空仍是"未配置"，不因 trim 变成空串以外的值。
    if (typeof v.api_key === 'string') v.api_key = v.api_key.trim();
    setBusy('provider');
    try {
      // 2026-10-10 小欧 - 一次提交：Provider + 模型列表随 models 字段一并发送。
      //   后端 add_provider 原生透传 req.models（M13），一次调用无半成功窗口；
      //   此前循环调 N 次单模型接口，又慢又可能 Provider 建成而模型部分失败。
      await props.onSubmitAddProvider({ ...v, models: newModels });
      pForm.resetFields();
      setNewModels([]);
      setModelInput('');
      setModelErr('');
    } catch {
      /* 保存失败：输入保留、弹窗不关（父级已弹错） */
    } finally {
      setBusy(null);
    }
  };
  // 2026-09-22 小欧 - DRY 收口：模板区三个控件（Select/InputNumber/Input）onChange 都走「勾选才收集 + params 合并」，
  //   抽取单函数，杜绝三处 `checked[key] && setCollected({...})` 重复（函数式更新防闭包陈旧值）
  const updateCollectedParam = (key: string, value: unknown) => {
    if (!checked[key]) return;
    setCollected((c) => ({ ...c, params: { ...c.params, [key]: value } }));
  };

  // 2026-10-10 22:15 小欧 - DRY：模板区取值/勾选/控件分派三件事从内联 map 抽成函数。
  //   内联版既难读，也让"按类型分组"无从下手（分组判定与渲染耦合在一处），抽出后 map 只负责排版。
  const collectOpts = (key: string): string[] | undefined => {
    const preset = PARAM_PRESETS.find((p) => p.key === key);
    return sibModels[0]?.param_options?.[key] ?? preset?.options;
  };

  const collectDefaultVal = (key: string): unknown => {
    const preset = PARAM_PRESETS.find((p) => p.key === key);
    return (
      collected.params[key] ?? sibModels[0]?.default_params?.[key] ?? preset?.default
    );
  };

  const toggleParam = (key: string, next: boolean) => {
    const opts = collectOpts(key);
    const dv = collectDefaultVal(key);
    setChecked((c) => ({ ...c, [key]: next }));
    setCollected((c) => {
      const params = { ...c.params };
      const options = { ...c.options };
      if (next) {
        // 勾选即带入当前默认值（不含则保持未送）
        if (dv !== undefined) params[key] = dv;
        // 兄弟有枚举则一并带入新模型（回显下拉）
        if (opts) options[key] = opts;
      } else {
        delete params[key];
        delete options[key];
      }
      return { params, options };
    });
  };

  /** 模板行：标签改CodeChip 等宽（机器键名不该和中文说明同字体），三列定宽对齐 */
  const renderParamRow = (key: string) => {
    const opts = collectOpts(key);
    const defaultVal = collectDefaultVal(key);
    // 布尔判定一次求值：兄弟模型旧数据可能是字符串 "true"（与布尔同义，显示不错位）
    const isBoolVal =
      typeof defaultVal === 'boolean' ||
      defaultVal === 'true' ||
      defaultVal === 'false';
    return (
      <div
        key={key}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.MD,
          marginBottom: Spacing.SM,
        }}
      >
        <Checkbox
          checked={!!checked[key]}
          onChange={(e) => toggleParam(key, e.target.checked)}
        >
          <span style={{ display: 'inline-block', width: 140 }}>
            <CodeChip>{key}</CodeChip>
          </span>
        </Checkbox>
        {opts ? (
          <Select
            value={
              typeof defaultVal === 'string'
                ? defaultVal
                : String(defaultVal ?? '')
            }
            options={opts.map((v) => ({ label: v, value: v }))}
            style={{ width: settingsControl.selectWidth }}
            onChange={(v) => updateCollectedParam(key, v)}
          />
        ) : typeof defaultVal === 'number' ? (
          <InputNumber
            value={defaultVal as number}
            style={{ width: settingsControl.inputNumberWidth }}
            onChange={(v) => updateCollectedParam(key, v)}
          />
        ) : isBoolVal ? (
          <Switch
            checked={defaultVal === true || defaultVal === 'true'}
            onChange={(v) => updateCollectedParam(key, v)}
          />
        ) : (
          <Input
            value={String(defaultVal ?? '')}
            style={{ width: settingsControl.inputWidth }}
            onChange={(e) => updateCollectedParam(key, e.target.value)}
          />
        )}
      </div>
    );
  };

  return (
    <>
      <SettingsModal
        open={addModelOpen}
        title="添加模型"
        // 2026-10-10 23:50 小欧 - 宽档 form(520)→display(800)：与「添加 Provider」统一为同一套版式
        //   （北京老陈："两个弹框自己截图仔细分析UI布局"）。此前本窗竖排 label（表单项 58px）、
        //   那个 520 宽（label 28px），填一个字段一个高 58、一个高 28，明显不是一套设计；
        //   且本窗正文 446 可视 / 572 内容，溢出 126px 必须滚动。
        //   改 800 + label 左置 + 参数模板分两列后，纵向大幅压缩。
        width="display"
        confirmLoading={busy === 'model'}
        onCancel={props.onCloseAddModel}
        onOk={() => void handleAddModel()}
        okText="保存"
        cancelText="取消"
      >
        <div
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
            marginBottom: Spacing.LG,
          }}
        >
          为指定 Provider 添加新模型，创建后可在①选择器中选用
        </div>
        {/* 2026-10-10 23:50 小欧 - vertical → horizontal：label 左置，与「添加 Provider」同款。
            23:55 小欧 - labelCol 4→5：实测 span4 时 label 可用宽 ≈65px，而"Provider"8 个
            拉丁字符需 ≈60px，paddingRight 被挤没、下拉框紧贴 label（实测截图确认）。
            span5 ≈81px 才留得出间距。
            10-11 01:58 小欧 - textAlign right → left（北京老陈标红四条竖线要求）：
            原右对齐让标签右边缘贴住控件，同一列里「名称/API 地址/timeout」长短不一、
            左边缘参差；改左对齐后标签列起点统一（竖线1/竖线3），控件起点统一（竖线2/竖线4）。 */}
        <Form
          form={mForm}
          layout="horizontal"
          labelCol={{ span: 5, style: { textAlign: 'left', paddingRight: Spacing.LG } }}
          wrapperCol={{ span: 19 }}
          colon={false}
        >
          {/* Provider/模型名并排；显示名删除（详见文件头编辑历史） */}
          <Row gutter={Spacing.MD}>
            <Col span={12}>
              <Form.Item label="Provider" required style={{ marginBottom: 0 }}>
                <Select value={mProvider} onChange={setMProvider}>
                  {providers.map((p) => (
                    <Select.Option key={p.name} value={p.name}>
                      {p.label || p.name}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="model"
                label="模型名"
                style={{ marginBottom: 0 }}
                rules={[{ required: true, message: '请输入模型名' }]}
              >
                <Input />
              </Form.Item>
            </Col>
          </Row>
          {/* 参数模板：勾选即带入，候选=兄弟模型 default_params ∪ param_options key 并集
              2026-10-10 22:15 小欧 - 视觉优化：①裸排的11 行套 ModalSection 弱容器，与必填表单分层
              （原为一行灰字浮在表单下，11 行 checkbox+input 连成一片"墙"，看不出这是可选区）；
              ②按 枚举/数值/开关 三类分组（用户能按类型定位，不再逐行扫）；
              ③行内键名改等宽 chip，机器标识符与中文说明一眼可分。 */}
          {candKeys.length > 0 && (
            <ModalSection
              title="参数模板"
              hint="勾选即带入新模型，不勾则不写入"
              style={{ marginTop: Spacing.MD }}
            >
              {PARAM_GROUPS.map((grp) => {
                const keys = candKeys.filter((key) => {
                  const preset = PARAM_PRESETS.find((p) => p.key === key);
                  const opts =
                    sibModels[0]?.param_options?.[key] ?? preset?.options;
                  const dv = collectDefaultVal(key);
                  if (grp.kind === 'enum') return !!opts;
                  if (grp.kind === 'bool')
                    return (
                      !opts &&
                      (typeof dv === 'boolean' || dv === 'true' || dv === 'false')
                    );
                  return !opts && typeof dv !== 'boolean';
                });
                if (!keys.length) return null;
                return (
                  <div key={grp.kind} style={{ marginBottom: Spacing.MD }}>
                    <div
                      style={{
                        fontSize: FontSize.CAPTION,
                        color: Colors.TEXT.TERTIARY,
                        lineHeight: '16px',
                        marginBottom: 4,
                      }}
                    >
                      {grp.label}
                    </div>
                    {/* 2026-10-10 23:50 小欧 - 组内分两列：弹窗改 800 宽后单列排 11 行会让
                        参数模板区纵向 451px 独占整个弹窗（实测正文溢出 126px）。
                        组内按 Col span=12 两列排，纵向行数约减半。 */}
                    <Row gutter={Spacing.MD}>
                      {keys.map((k) => (
                        <Col span={12} key={k}>
                          {renderParamRow(k)}
                        </Col>
                      ))}
                    </Row>
                  </div>
                );
              })}
            </ModalSection>
          )}
        </Form>
      </SettingsModal>
      <SettingsModal
        open={addProviderOpen}
        // 2026-10-03 小欧 - 关闭即清空：此前只在提交成功后 resetFields，取消再打开会留着上次填的
        //   名称/地址/密钥，属"添加"弹窗不该有的残留（易误提交成第二个 Provider）。
        onCancel={() => {
          pForm.resetFields();
          setNewModels([]);
          setModelInput('');
          setModelErr('');
          props.onCloseAddProvider();
        }}
        title="添加 Provider"
        // 2026-10-10 23:30 小欧 - 宽档 520→800：北京老陈"这个页面弹框高度很金贵"。
        //   原 520 窄弹窗被迫 label 在上、控件在下，每个字段独占 label 行 22px，
        //   四块分区实测 558px 且仍要滚动。800 宽弹窗改 label 左置后，
        //   身份/连接/性能三块各只剩"标题行 + 一行控件"，高度砍掉约 150px。
        width="display"
        confirmLoading={busy === 'provider'}
        onOk={() => void handleAddProvider()}
        okText="保存"
        cancelText="取消"
      >
        <div
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
            marginBottom: Spacing.LG,
          }}
        >
          创建后可在③Provider配置区修改 API Key / API 地址
        </div>
        {/* 2026-10-10 23:30 小欧 - vertical → horizontal：label 左置与控件同行。
            23:35 小欧 - labelCol 5→9 / 加 wrapperCol：span 是相对所在 Col 的百分比，
            Form.Item 在 Col span=12 内，9/24≈37.5% 约 105px，够放"API 地址"。
            10-11 01:58 小欧 - textAlign right → left（北京老陈标红四条竖线要求）：
            右对齐时标签右边缘贴控件、同列左边缘参差；左对齐后标签列起点统一、
            控件起点统一，「名称/API 地址/timeout」三块形成三条对齐竖线。 */}
        <Form
          form={pForm}
          layout="horizontal"
          labelCol={{ span: 9, style: { textAlign: 'left', paddingRight: Spacing.LG } }}
          wrapperCol={{ span: 15 }}
          colon={false}
        >
          {/* 2026-10-10 22:15 小欧 - 视觉优化：四个语义块套 ModalSection 分区。
              原为 6 个 Form.Item 平铺，"模型（可选…）"与 timeout 同权重平铺，用户读不出
              「身份 / 连接 / 性能 / 批量模型」是四件事。分块后层级立刻成立。
              块内 Form.Item 一律 marginBottom:0（末项）——此前每项都写 marginBottom:Spacing.LG，
              与 Row 的 gutter 叠加后出现 40/74/74 三种间距（问题#5），现由 ModalSection 内距统一。 */}
          <ModalSection title="身份" hint="名称即配置文件里的 key，创建后不可改">
            <Row gutter={Spacing.MD}>
              <Col span={12}>
                <Form.Item
                  name="name"
                  label="名称"
                  style={{ marginBottom: 0 }}
                  rules={[{ required: true, message: '请输入名称' }]}
                >
                  <Input />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="label"
                  label="显示名"
                  style={{ marginBottom: 0 }}
                >
                  <Input />
                </Form.Item>
              </Col>
            </Row>
          </ModalSection>

          <ModalSection
            title="连接"
            style={{ marginTop: Spacing.MD }}
          >
            {/* 小欧 2026-09-26: base_url 必填 — URL 是 Provider 的必要配置，
                无地址即无法调用；未填不允许提交(与 api_key 的"留空=保持原值"方向相反)
                2026-10-10 22:35 小欧 - API 地址/API Key 改并排（原上下排把「批量模型」块
                顶出可视区，滚动区正好切在输入框中间像坏掉了）。
                23:40 小欧 - 14/10 改回 12/12：三个分区（身份/连接/性能）都是两列，但本块
                原用 14/10，切分点比另两块右移 36px，三块的竖向分隔线对不齐（"不齐整"）。
                统一按中线对半分，三块竖线贯通。API Key 分到半宽仍远超输入所需。 */}
            <Row gutter={Spacing.MD}>
              <Col span={12}>
                <Form.Item
                  name="api_base"
                  label="API 地址"
                  style={{ marginBottom: 0 }}
                  rules={[
                    { required: true, message: '请输入 API 地址' },
                    {
                      validator: (_rule, value: string) =>
                        value && value.trim() === ''
                          ? Promise.reject(new Error('API 地址不能为空白'))
                          : Promise.resolve(),
                    },
                  ]}
                >
                  <Input placeholder="https://api.deepseek.com" />
                </Form.Item>
              </Col>
              <Col span={12}>
                {/* 2026-10-03 小欧 - 补 autoComplete="new-password"：新增 Provider 时该框必须为空，
                    而 Input.Password 渲染 type="password" 会被 Chrome 密码管理器自动填入已存口令
                    （表现为浅蓝底 + 掩码点，且不察觉直接保存就把浏览器口令写进 config.yaml 当 api_key）。
                    口径与 SecretRevealInput:141 同款 —「新密钥一律不让浏览器自动填充」。 */}
                <Form.Item name="api_key" label="API Key" style={{ marginBottom: 0 }}>
                  <Input.Password
                    placeholder="未配置则留空"
                    autoComplete="new-password"
                  />
                </Form.Item>
              </Col>
            </Row>
          </ModalSection>

          {/* 创建 Provider 可自定义 timeout/max_retries（后端 DTO 默认 60/3，留空走默认）。
              2026-10-03 小欧 - 两项改并排一行；22:15 小欧 - 独立成「性能」块。 */}
          <ModalSection
            title="性能"
            hint="留空走默认 60 秒 / 3 次"
            style={{ marginTop: Spacing.MD }}
          >
            <Row gutter={Spacing.MD}>
              <Col span={12}>
                <Form.Item label="timeout(秒)" name="timeout" style={{ marginBottom: 0 }}>
                  <InputNumber min={1} placeholder="默认60" style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="max_retries"
                  name="max_retries"
                  style={{ marginBottom: 0 }}
                >
                  <InputNumber min={0} placeholder="默认3" style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
          </ModalSection>

          {/* 2026-10-10 小欧 - 底部顺带加模型：输入框 + 按钮攒列表，确定时随 Provider 一并提交。
              只攒名字（label 与 model 同值）；复杂参数去模型弹窗里配，此处不展开（KISS）。
              22:15 小欧 - 独立成「批量模型」块（此前裸奔在 timeout 下方，语义层级缺失）。 */}
          <ModalSection
            title="批量模型"
            hint="可选，保存时随 Provider 一并创建"
            style={{ marginTop: Spacing.MD }}
          >
            <Space.Compact style={{ width: '100%', marginBottom: Spacing.SM }}>
            <Input
              style={{ flex: 1 }}
              placeholder="输入模型名，回车添加"
              status={modelErr ? 'error' : undefined}
              value={modelInput}
              onChange={(e) => {
                setModelInput(e.target.value);
                setModelErr('');
              }}
              onPressEnter={() => {
                const v = modelInput.trim();
                if (!v) {
                  setModelErr('请输入模型名');
                  return;
                }
                setModelErr('');
                setNewModels((ps) => (ps.includes(v) ? ps : [...ps, v]));
                setModelInput('');
              }}
            />
            <Button
              icon={<PlusOutlined />}
              onClick={() => {
                const v = modelInput.trim();
                if (!v) {
                  setModelErr('请输入模型名');
                  return;
                }
                setModelErr('');
                setNewModels((ps) => (ps.includes(v) ? ps : [...ps, v]));
                setModelInput('');
              }}
              aria-label="添加模型"
            />
          </Space.Compact>
          {modelErr && (
            <div style={{ fontSize: FontSize.SECONDARY, color: Colors.ERROR }}>
              {modelErr}
            </div>
          )}
          {newModels.length > 0 && (
            <List
              size="small"
              style={{ marginTop: Spacing.SM }}
              dataSource={newModels}
              renderItem={(m) => (
                <List.Item
                  actions={[
                    <Button
                      key="del"
                      type="text"
                      danger
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={() =>
                        setNewModels((ps) => ps.filter((x) => x !== m))
                      }
aria-label={`移除${m}`}
                    />
                  ]}
                >
                  <Typography.Text style={{ fontSize: FontSize.SECONDARY }}>
                    {m}
                  </Typography.Text>
                </List.Item>
              )}
            />
          )}
          </ModalSection>
        </Form>
      </SettingsModal>
      <SettingsModal
        open={deleteOpen}
        width="confirm"
        // 2026-10-10 22:15 小欧 - 视觉优化（问题#9/#10/#11）：
        //   ①标题的 deleteLabel(deleteTarget) 是 provider::model 结构化键，原与中文标题同字体，
        //     读不出是标识符 → 改 CodeChip（tone=danger 红底，破坏性语境更醒目）；
        //   ②⚠ emoji 换 ExclamationCircleFilled + Colors.ERROR —— emoji 跨平台形态不一
        //     （Windows 彩色/安卓彩色/Mac 单色），且与 danger 按钮语义重复；
        //   ③后果文案由单段灰字拆成"逐条列项 + 后果分级"，危险提示不再被淹没在说明里。
        title={
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <ExclamationCircleFilled style={{ color: Colors.ERROR }} />
            确定要删除
            <CodeChip tone="danger">{deleteLabel(deleteTarget)}</CodeChip>
            ？
          </span>
        }
        danger
        onCancel={props.onCloseDelete}
        onOk={() => void props.onConfirmDelete()}
        okText="删除"
        cancelText="取消"
      >
        <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}>
          删除后：
          <ul style={{ margin: `${Spacing.SM}px 0 0`, paddingLeft: 20 }}>
            <li>若它是当前使用的模型，将自动切换到默认模型</li>
            <li>若是 Provider，将级联删除其下所有模型</li>
          </ul>
          <span style={{ color: Colors.TEXT.TERTIARY, fontSize: FontSize.SMALL }}>
            该操作不可撤销
          </span>
        </div>
      </SettingsModal>
    </>
  );
};
