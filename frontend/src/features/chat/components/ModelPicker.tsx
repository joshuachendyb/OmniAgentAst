// 编辑历史: 2026-08-26 小欧 - 8.13/L2 实施: 会话级模型覆盖选择器, 写sessionModel, 409冲突回读(5.1/5.2)
// 编辑历史: 2026-08-27 小欧 - 修复#11: 切L2模型不再以'新会话'污染后端会话标题(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 模型列表类型归一为ModelListItem; 删IIFE改直线find写法
// 编辑历史: 2026-08-27 小欧 - 去头像-C2: 删ModelPicker内RobotOutlined后缀图标, 回落Antd默认DownOutlined下拉箭头(更符下拉心智)
// 编辑历史: 2026-09-25 小欧 - 修双 provider 重复 + 列框自适应:
//   (1) provider 重复: 后端 get_models display_name 已含 "provider (model)", 原再拼 " (provider)"
//     → openai (gpt-4) (openai) 双 provider, 改直接用 display_name;
//   (2) 列框自适应: popupMatchSelectWidth=false 弹层宽度由最长选项决定(原默认=选中框 180 截断),
//     nowrap 防换行; 选中框保持 minWidth:180 — 小欧-2026-09-25
// 编辑历史: 2026-10-24 小欧 - SRP拆分: 删sessionTitle入参, 改调updateSessionModel(只发sessionModel+version), 消除"切模型"被迫传标题的耦合 - 小欧-2026-10-24
// 编辑历史: 2026-11-02 小欧 - 选中框minWidth:180改width:180定宽: 长模型名不再撑框挤占顶栏横排(flex gap8布局), 溢出走antd省略号+外层Tooltip见全名; 下拉弹层popupMatchSelectWidth=false自适应宽不动 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 会话级模型框宽度归常量SESSION_MODEL_SELECT_WIDTH=180(调宽只改一行),与顶部Layout各自持常量互不共享隔离 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 北京老陈令: 底部选中框回归minWidth下限语义(不许改定宽width),常量仅作minWidth下限,其余不动 - 小欧-2026-11-02
// 编辑历史: 2026-11-16 小欧 - [23]阶段D: 切换写库/409回读抽 switchSessionModel 公共实现(推荐条共用) — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 选项悬浮信息卡: 数据源改 modelApi.getModels(与模型库同源), 展示输入/输出模态、
//   上下文窗口、推理深度(取 model_params 配置值或 param_options 可调档位); 输出仅多模态时展示 — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 悬浮信息卡排版重排: 名称下加摘要徽标行(上下文/推理), 模态行标签右对齐定宽,
//   推理来源与可调档位拆为分割线下的独立列, 取消 · 拼接长串 — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 悬浮卡配色改令牌: 全站 Tooltip 为白底(#595959 字), 原白色半透明标签/胶囊/分割线
//   在白底不可见 → 统一换 Colors.TEXT.SECONDARY / BG.TERTIARY / BORDER.* — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 悬浮卡回归单列标签行布局: 输入/输出/上下文/推理 逐行对齐, 标签列 48px 右对齐;
//   推理值 + 来源同行, 可调档位换行缩进在值列 — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 悬浮卡两列统一左对齐(标签列/值列均 textAlign left), 列宽 48px 保持对齐 — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 推理"可调"兜底: 后端仅对已配置 reasoning_effort 的模型下发 param_options,
//   故无配置时按缺省低/中/高展示, 避免该行整行缺失 — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 选项 options 增 title:'' , 抑制 rc-select 由字符串 label 自动生成的原生 title 悬浮提示,
//   下拉项只保留自定义信息卡一个 tip — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 选中项 tip 升级: 原仅显示 provider(model) 纯文本, 改为按 sessionModelOverride 反查
//   模型元数据, 复用 ModelMetaTip 信息卡(输入/输出/上下文/推理); 跟随全局时仍显示文字 — 小欧-2026-11-16
// 编辑历史: 2026-11-16 小欧 - 悬浮卡样式归令牌: 字号/字重/行高/间距/圆角全部改引 FontSize/FontWeight/LineHeight/
//   Gap/Spacing/Radius/CONTROL_PADDING, 消除 14 处魔法值(columnGap:10 不在刻度/minWidth:248 裸字面量等);
//   marginBottom:8 改父容器 gap(铁律三), marginTop:3 改 flex+gap(铁律三) — 小欧-2026-11-16
/**
 * ModelPicker 组件 - 会话级模型覆盖(L2)选择器
 *
 * 功能：
 * - 展示当前会话模型覆盖(sessionModel)或"跟随全局"
 * - 从后端拉取可用模型列表(provider+model)
 * - 切换时调用 PUT /sessions/{id} 写 sessionModel(JSON), 本地同步 version
 * - 409 版本冲突时回读最新会话
 *
 * @author 小欧
 * @date 2026-08-22
 */

import React, { useEffect, useState } from 'react';
import { Select, Tooltip } from 'antd';
import { DownOutlined } from '@ant-design/icons';
import { modelApi } from '../../../services/api/model.api';
import { settingsApi } from '../../../services/api/settings.api';
import type { SessionModelOverride } from '../../../types/chat';
import {
  Colors,
  FontSize,
  FontWeight,
  Radius,
  Spacing,
} from '../../../utils/stepStyles';
import { CONTROL_PADDING } from '../../../theme/controlScale';
import { Gap, LineHeight } from '../../../theme/spacing';
import { switchSessionModel } from '../utils/switchSessionModel';

interface ModelPickerProps {
  sessionId: string | null;
  sessionVersion: number;
  sessionModelOverride: SessionModelOverride | null;
  setSessionModelOverride: (v: SessionModelOverride | null) => void;
  setSessionVersion: (v: number) => void;
  /** 2026-11-18 opencode: 会话在途判据(切会话后丢弃旧请求回写) — opencode-2026-11-18 */
  isCurrentSession?: () => boolean;
}

const FOLLOW_GLOBAL = '__follow_global__';

// 2026-11-02 小欧 - 会话级模型选择框宽度唯一可调点(仅作minWidth下限): 改下限只改此一行; 与顶部Layout的TOP_MODEL_SELECT_WIDTH互不共享隔离 — 小欧-2026-11-02
const SESSION_MODEL_SELECT_WIDTH = 180;

interface ModelOptionMeta {
  provider: string;
  model: string;
  display_name: string;
  input_modalities: string[];
  output_modalities: string[];
  context_length?: number;
  model_params: Record<string, unknown>;
  param_options?: Record<string, string[]>;
}

const MODALITY_LABELS: Record<string, string> = {
  text: '文本',
  image: '图片',
  audio: '音频',
  video: '视频',
  file: '文件',
};

const EFFORT_LABELS: Record<string, string> = {
  none: '关闭',
  minimal: '极低',
  low: '低',
  medium: '中',
  high: '高',
  xhigh: '极高',
  max: '最高',
};

const TIP_LABEL_STYLE: React.CSSProperties = {
  color: Colors.TEXT.SECONDARY,
};

const TIP_TAG_STYLE: React.CSSProperties = {
  display: 'inline-block',
  padding: `0 ${CONTROL_PADDING.CHIP_X}px`,
  borderRadius: Radius.SM,
  background: Colors.BG.TERTIARY,
  lineHeight: LineHeight.BODY,
};

const TIP_ROW_LABEL_STYLE: React.CSSProperties = {
  color: Colors.TEXT.SECONDARY,
};

// 缺省推理档位(低/中/高), 与后端 DEFAULT_PARAM_OPTIONS.reasoning_effort 同源;
// 推理深度仅两层: 模型层(model_params.reasoning_effort) > 缺省层(本表), 模型层未设即按缺省 — 小欧-2026-11-16
// 悬浮信息卡最小宽度(px): 保证四行标签+值不折行
const TIP_CARD_MIN_W = 248;
const DEFAULT_EFFORT_OPTIONS = ['low', 'medium', 'high'];

const formatContext = (value?: number): string => {
  if (!value || value <= 0) return '未声明';
  if (value >= 1_000_000) return `${+(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}K`;
  return String(value);
};

const ModalityTags: React.FC<{ items: string[] }> = ({ items }) => {
  if (!items.length) return <span style={TIP_LABEL_STYLE}>未声明</span>;
  return (
    <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: Gap.ROW }}>
      {items.map((m) => (
        <span key={m} style={TIP_TAG_STYLE}>
          {MODALITY_LABELS[m] ?? m}
        </span>
      ))}
    </span>
  );
};

const readGlobalEffort = (
  groups: Record<string, { data?: Record<string, unknown> }>
): string => {
  for (const group of Object.values(groups ?? {})) {
    const value = group.data?.['llm.sampling.reasoning_effort'];
    if (typeof value === 'string' && value) return value;
  }
  return '';
};

const ModelMetaTip: React.FC<{
  meta: ModelOptionMeta;
  globalEffort: string;
}> = ({ meta, globalEffort }) => {
  const output = meta.output_modalities ?? [];
  const showOutput = output.some((m) => m !== 'text');
  const configuredOptions = meta.param_options?.reasoning_effort ?? [];
  const hasModelEffort = Object.prototype.hasOwnProperty.call(
    meta.model_params,
    'reasoning_effort'
  );
  const rawEffort = meta.model_params?.reasoning_effort;

  let effortValue = '';
  let effortSource = '';
  if (hasModelEffort) {
    if (rawEffort === null || rawEffort === false) {
      effortValue = '关闭';
      effortSource = '模型';
    } else if (rawEffort !== '') {
      effortValue = EFFORT_LABELS[String(rawEffort)] ?? String(rawEffort);
      effortSource = '模型';
    }
  } else if (globalEffort) {
    effortValue = EFFORT_LABELS[globalEffort] ?? globalEffort;
    effortSource = '缺省';
  }
  const effortOptions = configuredOptions.length
    ? configuredOptions
    : DEFAULT_EFFORT_OPTIONS;
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: Gap.SECTION,
        minWidth: TIP_CARD_MIN_W,
      }}
    >
      <div
        style={{
          fontWeight: FontWeight.BOLD,
          paddingBottom: Spacing.SM,
          borderBottom: `1px solid ${Colors.BORDER.VERTICAL}`,
        }}
      >
        {meta.display_name}
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '48px 1fr',
          rowGap: Gap.STACK,
          columnGap: Spacing.MD,
          fontSize: FontSize.SECONDARY,
          lineHeight: LineHeight.LOOSE,
          alignItems: 'start',
        }}
      >
        <span style={TIP_ROW_LABEL_STYLE}>输入</span>
        <ModalityTags items={meta.input_modalities ?? []} />
        {showOutput && (
          <>
            <span style={TIP_ROW_LABEL_STYLE}>输出</span>
            <ModalityTags items={output} />
          </>
        )}
        <span style={TIP_ROW_LABEL_STYLE}>上下文</span>
        <span>{formatContext(meta.context_length)}</span>
        {(effortValue || effortOptions.length > 0) && (
          <>
            <span style={TIP_ROW_LABEL_STYLE}>推理</span>
            <span
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: Gap.ROW,
              }}
            >
              <span>
                {effortValue && (
                  <span style={{ fontWeight: FontWeight.MEDIUM }}>
                    {effortValue}
                  </span>
                )}
                {effortSource && (
                  <span style={TIP_LABEL_STYLE}>（{effortSource}）</span>
                )}
              </span>
              {effortOptions.length > 0 && (
                <span style={TIP_LABEL_STYLE}>
                  可调{' '}
                  {effortOptions.map((e) => EFFORT_LABELS[e] ?? e).join(' / ')}
                </span>
              )}
            </span>
          </>
        )}
      </div>
    </div>
  );
};

const ModelPicker: React.FC<ModelPickerProps> = ({
  sessionId,
  sessionVersion,
  sessionModelOverride,
  setSessionModelOverride,
  setSessionVersion,
  isCurrentSession,
}) => {
  const [models, setModels] = useState<ModelOptionMeta[]>([]);
  const [globalEffort, setGlobalEffort] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const [modelsResult, settingsResult] = await Promise.allSettled([
        modelApi.getModels(),
        settingsApi.getAll(),
      ]);
      if (cancelled) return;
      if (settingsResult.status === 'fulfilled') {
        setGlobalEffort(readGlobalEffort(settingsResult.value.groups));
      }
      if (modelsResult.status !== 'fulfilled') {
        setModels([]);
        return;
      }
      const list = (modelsResult.value.providers ?? []).flatMap((p) =>
        (p.models ?? []).map((m) => {
          const paramCtx = m.model_params?.context_length;
          const ctx =
            typeof m.context_length === 'number'
              ? m.context_length
              : typeof paramCtx === 'number'
                ? paramCtx
                : undefined;
          return {
            provider: p.name,
            model: m.name,
            display_name: `${p.name} (${m.name})`,
            input_modalities: m.input_modalities ?? [],
            output_modalities: m.output_modalities ?? [],
            context_length: ctx,
            model_params: m.model_params ?? {},
            param_options: m.param_options,
          };
        })
      );
      setModels(list);
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = sessionModelOverride
    ? `${sessionModelOverride.provider}-${sessionModelOverride.model}`
    : FOLLOW_GLOBAL;

  const handleChange = async (val: string) => {
    if (!sessionId) return;
    // 2026-08-27 小欧 三堂会审: 删IIFE包裹, 直线写法取模型项
    const foundModel =
      val === FOLLOW_GLOBAL
        ? undefined
        : models.find((x) => `${x.provider}-${x.model}` === val);
    const next: SessionModelOverride | null = foundModel
      ? {
          provider: foundModel.provider,
          model: foundModel.model,
          display_name: foundModel.display_name,
        }
      : null;
    if (!next && val !== FOLLOW_GLOBAL) return;
    setLoading(true);
    try {
      // 2026-11-16 小欧 [23]阶段D: 切换写库/409 回读收口 switchSessionModel(推荐条共用唯一实现) — 小欧-2026-11-16
      await switchSessionModel({
        sessionId,
        next,
        version: sessionVersion,
        setSessionVersion,
        setSessionModelOverride,
        isCurrent: isCurrentSession,
      });
    } finally {
      setLoading(false);
    }
  };

  // 选中项 tip: 复用下拉项同一张信息卡, 按 sessionModelOverride 反查模型元数据 — 小欧-2026-11-16
  const selectedMeta = sessionModelOverride
    ? models.find(
        (m) =>
          m.provider === sessionModelOverride.provider &&
          m.model === sessionModelOverride.model
      )
    : undefined;

  return (
    <Tooltip
      title={
        selectedMeta ? (
          <ModelMetaTip meta={selectedMeta} globalEffort={globalEffort} />
        ) : sessionModelOverride ? (
          `${sessionModelOverride.provider} (${sessionModelOverride.model})`
        ) : (
          '跟随全局模型'
        )
      }
      styles={{ body: { maxWidth: 360 } }}
    >
      <Select
        size="small"
        // title:'' 抑制选中项容器由 rc-select getTitle 自动生成的原生 title, 选中项 tip 只保留外层自定义信息卡 — 小欧-2026-11-16
        title=""
        value={value}
        onChange={handleChange}
        loading={loading}
        disabled={!sessionId || loading}
        style={{ minWidth: SESSION_MODEL_SELECT_WIDTH }}
        placeholder="跟随全局"
        suffixIcon={<DownOutlined />}
        // 2026-09-25 小欧 弹层宽自适应取最长选项 nowrap 防换行; 2026-11-02 小欧 选中框回归 minWidth 下限语义(北京老陈令: min 不许改定宽), 常量仅作下限 — 小欧-2026-11-02
        popupMatchSelectWidth={false}
        popupRender={(menu) => (
          <div style={{ whiteSpace: 'nowrap' }}>{menu}</div>
        )}
        optionRender={(option) => {
          const meta = (option.data as { meta?: ModelOptionMeta }).meta;
          if (!meta) return option.label;
          return (
            <Tooltip
              title={<ModelMetaTip meta={meta} globalEffort={globalEffort} />}
              placement="rightTop"
              mouseEnterDelay={0.25}
              styles={{ body: { maxWidth: 360 } }}
            >
              <span style={{ display: 'block', width: '100%' }}>
                {option.label}
              </span>
            </Tooltip>
          );
        }}
        options={[
          { value: FOLLOW_GLOBAL, label: '跟随全局', title: '' },
          ...models.map((m) => ({
            value: `${m.provider}-${m.model}`,
            label: m.display_name || `${m.provider} (${m.model})`,
            // title:'' 抑制 rc-select 由字符串 label 自动生成的原生 title 悬浮提示, 只保留自定义信息卡 — 小欧-2026-11-16
            title: '',
            meta: m,
          })),
        ]}
      />
    </Tooltip>
  );
};

export default ModelPicker;
