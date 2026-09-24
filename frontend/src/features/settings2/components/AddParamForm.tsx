// 编辑历史: 2026-09-23 小欧 - 新建：模型参数区「+ 添加参数」内联表单（预定义+自定义混合）
// v1.1: 预设 5→8（加 top_p/frequency_penalty/presence_penalty，默认值对齐注册表）；确认按钮有效性门禁（禁空值/枚举必选/布尔严格）
// v1.6: 切 mode 重置 checked/values（防旧勾选与旧值残留）- 小欧-2026-09-23
// v1.10: 独立成 AddParamForm.tsx（组件一文件惯例）；容器色/圆角/控件宽全部令牌化
//   （#d9d9d9→Colors.BORDER.DEFAULT、#fafafa→Colors.BG.LIGHT、borderRadius:4→settingsRadius.SM、
//    宽 120/160/100→settingsControl 统一 180 族、文本 Input 误用 inputNumberWidth→inputWidth）；
//   values 初始表达式两处重复抽 initValues（DRY）- 小欧-2026-09-23
// 2026-09-23 小欧 - [65]§4.3.3 落码：按设计定稿实现（PARAM_PRESETS 8 项+existingKeys 主防+门禁+批量提交统一关表单）- 小欧-2026-09-23
// 2026-09-23 小欧 - UI 布局对齐整体页面风格（北京老陈指示）：①容器由横向挤压的 dashed 灰底工具条改纵向区块
//   （白底 Colors.BG.PRIMARY + 实线 Colors.BORDER.DEFAULT + settingsRadius.SM + Spacing 间距，对齐页面白底浅框语言）；
//   ②顶行 space-between：左=模式 Radio、右=「取消/确认」按钮组（右对齐操作位，按钮组 gap 间距）；
//   ③预设行/自定义输入行全宽纵向流（预设沿用 settingsRowStyle 行，自定义行对齐 label+控件行结构）- 小欧-2026-09-23
// 2026-09-23 小欧 - 行内顺序+列对齐（北京老陈指示，不引新控件）：预设行改「☐+名称 | 输入框 | 注释」三段——
//   名称收进 Checkbox children 且只放「名称 (key)」（settingsLabelStyle 固定 180，desc 不再挤名称），
//   输入框固定 settingsControl 180，desc+默认值收进注释列（flex:1 次要色小字），三段起点逐行对齐如表格；
//   行容器仍复用 settingsRowStyle（与 ModelParams 参数行同款）- 小欧-2026-09-23
// 2026-09-23 小欧 - 列对齐修正（北京老陈截图复核发现输入框起点参差）：名称 span 在 Checkbox 包裹层内是
//   inline 元素，width:180 被忽略（settingsLabelStyle 只对行 flex 直接子元素生效，ModelParams 即直接子元素）——
//   显式 display:'inline-block' 恢复定宽；宽度取本地 NAME_COL_WIDTH=240（最长「频次惩罚 (frequency_penalty)」
//   @14px≈205px，180 会折行破坏单行对齐），Checkbox 恒宽 + 名称列恒宽 → 输入框/注释列起点逐行对齐 - 小欧-2026-09-23
// 2026-09-23 小欧 - 自定义模式行修复（北京老陈截图复核）：原「label+控件」平铺有 4 处问题——
//   ①label「参数名/值」与 placeholder 文案重复；②flexWrap 把「值」输入框挤到第二行、label 孤悬第一行；
//   ③第二行单输入框大片留白；④与常用参数模式三列风格不一致。修复=删三个冗余 label（placeholder 已承担
//   说明，测试亦按 placeholder 查询），三控件「参数名|类型|值」单行 settingsRowStyle + gap:Spacing.LG，
//   行尾注释列 flex:1 与预设行注释列同位同色 - 小欧-2026-09-23
// 2026-09-24 小欧 - PARAM_PRESETS 显示顺序按北京老陈指定调整：
//   context_limit → temperature → max_tokens → reasoning_effort → top_p → seed → frequency_penalty → presence_penalty
//   （仅重排数组元素顺序，各预设字段内容不变；已存在的参数仍会被 existingKeys 过滤，剩余项保持新相对序）- 小欧-2026-09-24
// 2026-09-24 小欧 - top_p/seed 的 desc 改口语化（北京老陈反馈原说明不清楚）- 小欧-2026-09-24
// 2026-09-24 小欧 - seed desc 再改：补数字含义（北京老陈反馈看不出数字变化差异）- 小欧-2026-09-24
// 2026-09-24 22:56:21 小欧 - BZ-5 闭环：加 disabled prop（保存中禁用「确认」提交+handleAdd 守卫）——
//   三堂会审发现参数区/重置/入口按钮已锁 saving，但表单内批量 onAdd 未锁：保存 await 期间仍可注入
//   新键，与 saveModelGroup 闭包快照错位竞态（BZ-5 目标漏洞）；取消按钮不改 state 不禁 - 小欧-2026-09-24
import React, { useState } from 'react';
import { Button, Checkbox, Input, Radio, Select } from 'antd';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import {
  settingsControl,
  settingsRowStyle,
  settingsLabelStyle,
  settingsRadius,
} from '@/theme/settingsTokens';

// 行内名称列宽（☐ 右侧）：最长预设名「频次惩罚 (frequency_penalty)」@14px≈205px，取 240 保单行+列对齐
// （settingsLabelStyle.width=180 装不下会折行；不改共享令牌以免影响 ModelParams 等既有行）- 小欧-2026-09-23
const NAME_COL_WIDTH = 240;

/** 预定义参数表：从项目实际使用的模型参数中提取（v1.9：补 8 项 desc 字段，对齐 §2.3/v1.2；显示顺序按北京老陈指定 - 小欧-2026-09-24） */
const PARAM_PRESETS = [
  {
    key: 'context_limit',
    type: 'number' as const,
    default: 262144,
    range: { min: 1000, max: 900000 },
    label: '上下文限制',
    desc: '上下文窗口上限，超限裁剪旧轮',
  },
  {
    key: 'temperature',
    type: 'number' as const,
    default: 0.7,
    range: { min: 0, max: 2 },
    label: '温度',
    desc: '采样温度：0=完全确定，2=最随机',
  },
  {
    key: 'max_tokens',
    type: 'number' as const,
    default: 16384,
    range: { min: 1, max: 100000 },
    label: '最大Token',
    desc: 'LLM的单次最大输出 token 数，超长截断',
  },
  {
    key: 'reasoning_effort',
    type: 'enum' as const,
    default: 'medium',
    options: ['low', 'medium', 'high'],
    label: '推理深度',
    desc: '推理深度模式选择,，仅推理模型有效',
  },
  {
    key: 'top_p',
    type: 'number' as const,
    default: 1.0,
    range: { min: 0, max: 1 },
    label: '核采样',
    desc: '只从概率最高的前 p 部分词里选词；1=全都不筛，调小=更保守、只留高概率词',
  },
  {
    key: 'seed',
    type: 'number' as const,
    default: null,
    range: { min: 0, max: 999999 },
    label: '随机种子',
    desc: '数字本身无好坏：同一数字=每次结果固定不变，换一个数字=换一组新的随机结果；留空=每次都不固定',
  },
  {
    key: 'frequency_penalty',
    type: 'number' as const,
    default: 0,
    range: { min: -2, max: 2 },
    label: '频次惩罚',
    desc: '正值减少重复（更多样），负值增加重复，0=不启用',
  },
  {
    key: 'presence_penalty',
    type: 'number' as const,
    default: 0,
    range: { min: -2, max: 2 },
    label: '存在惩罚',
    desc: '正值鼓励新话题，负值鼓励重复，0=不启用',
  },
];

interface AddParamFormProps {
  onAdd: (
    key: string,
    value: unknown,
    meta?: { range?: { min: number; max: number }; options?: string[] }
  ) => void;
  onCancel: () => void;
  existingKeys: string[]; // v1.3：已存在参数不再列出（addParam 内 key in params 判重仅作安全网）
  // 2026-09-24 小欧 - BZ-5 闭环：保存中(saving) 禁用确认，防保存期间注入新键致快照错位 — 小欧-2026-09-24
  disabled?: boolean;
}

// v1.10 DRY：values 初始表达式原本 useState 与切 mode 两处重复，抽单函数
const initValuesOf = (presets: (typeof PARAM_PRESETS)[number][]) =>
  Object.fromEntries(
    presets.map((p) => [p.key, p.default !== null ? String(p.default) : ''])
  );

export const AddParamForm: React.FC<AddParamFormProps> = ({
  onAdd,
  onCancel,
  existingKeys,
  disabled = false,
}) => {
  const [mode, setMode] = useState<'preset' | 'custom'>('preset');
  // v1.3：已存在 key 不列出（主防），addParam 内判重为安全网
  const presets = PARAM_PRESETS.filter((p) => !existingKeys.includes(p.key));
  // v1.2 勾选清单：checked 勾选态，values 每行输入值（初始=默认值转字符串，null 填空）
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>(() =>
    initValuesOf(presets)
  );
  const [customKey, setCustomKey] = useState('');
  const [customType, setCustomType] = useState<'string' | 'number' | 'boolean'>(
    'number'
  );
  const [value, setValue] = useState<string>('');

  const presetValid = (
    p: (typeof PARAM_PRESETS)[number],
    v: string
  ): boolean => {
    if (v === '') return false;
    if (p.type === 'number') {
      const n = Number(v);
      return !isNaN(n) && n >= p.range.min && n <= p.range.max;
    }
    if (p.type === 'enum') return (p.options ?? []).includes(v);
    return true;
  };

  // v1.1 有效性门禁：勾选至少一个且所勾行全有效；自定义空值/非法禁确认（不落 null、不存空串；布尔只认 true/false）
  const canConfirm = (() => {
    if (mode === 'preset') {
      const keys = Object.keys(checked).filter((k) => checked[k]);
      if (!keys.length) return false;
      return keys.every((k) => {
        const p = presets.find((x) => x.key === k);
        return p ? presetValid(p, values[k] ?? '') : false;
      });
    }
    if (!customKey.trim()) return false;
    if (value === '') return false;
    if (customType === 'number') return !isNaN(Number(value));
    if (customType === 'boolean') return value === 'true' || value === 'false';
    return true;
  })();

  const handleAdd = () => {
    // 2026-09-24 小欧 - BZ-5 闭环：保存中禁用提交（防保存期间批量 onAdd 注入 vs saveModelGroup 闭包竞态）
    if (!canConfirm || disabled) return;
    if (mode === 'preset') {
      Object.keys(checked)
        .filter((k) => checked[k])
        .forEach((k) => {
          const p = presets.find((x) => x.key === k);
          if (!p) return;
          const v: unknown =
            p.type === 'number' ? Number(values[k]) : values[k];
          onAdd(p.key, v, { range: p.range, options: p.options });
        });
    } else {
      const key = customKey.trim();
      if (!key) return;
      let v: unknown = value;
      if (customType === 'number') v = Number(value);
      if (customType === 'boolean') v = value === 'true';
      onAdd(key, v);
    }
    onCancel(); // 批量提交完统一关表单（不在 onAdd 回调里逐次关）
  };

  const inputStyle = { width: settingsControl.inputWidth }; // v1.10：文本 Input 用 inputWidth

  return (
    <div
      style={{
        // 2026-09-23 UI 布局对齐：纵向区块（白底浅框圆角），替代横向挤压 dashed 工具条
        display: 'flex',
        flexDirection: 'column',
        gap: Spacing.MD,
        padding: Spacing.MD,
        margin: `${Spacing.SM}px 0`,
        border: `1px solid ${Colors.BORDER.DEFAULT}`,
        borderRadius: settingsRadius.SM,
        background: Colors.BG.PRIMARY,
      }}
    >
      {/* 顶行：左=模式切换，右=操作按钮组（右对齐，页面操作位惯例） */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: Spacing.MD,
          flexWrap: 'wrap',
        }}
      >
        <Radio.Group
          value={mode}
          onChange={(e) => {
            setMode(e.target.value);
            setValue('');
            setCustomKey('');
            setChecked({});
            setValues(initValuesOf(presets));
          }} // v1.6：切 mode 清勾选与输入，防旧勾选/旧值残留
          size="small"
        >
          <Radio.Button value="preset">常用参数</Radio.Button>
          <Radio.Button value="custom">自定义</Radio.Button>
        </Radio.Group>
        <div style={{ display: 'flex', gap: Spacing.SM }}>
          <Button size="small" autoInsertSpace={false} onClick={onCancel}>
            取消
          </Button>
          <Button
            type="primary"
            size="small"
            autoInsertSpace={false}
            onClick={handleAdd}
            disabled={!canConfirm || disabled}
          >
            确认
          </Button>
        </div>
      </div>

      {/* 内容区：预设=「☐+名称 | 输入框 | 注释」三段行（settingsRowStyle 同 ModelParams）；自定义=label+控件行 */}
      {mode === 'preset' ? (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {presets.map((p) => (
            <div key={p.key} style={settingsRowStyle}>
              {/* 列1+2：☐ + 名称（inline-block 定宽 240——inline 时 width 被忽略致输入框参差，见文件头修正记录） */}
              <Checkbox
                checked={!!checked[p.key]}
                onChange={(e) =>
                  setChecked((c) => ({ ...c, [p.key]: e.target.checked }))
                }
              >
                <span
                  style={{
                    ...settingsLabelStyle,
                    display: 'inline-block',
                    width: NAME_COL_WIDTH,
                  }}
                >
                  {p.label} ({p.key})
                </span>
              </Checkbox>
              {/* 列3：输入框（固定 180） */}
              {p.type === 'enum' ? (
                <Select
                  value={values[p.key] || undefined}
                  onChange={(v) => setValues((s) => ({ ...s, [p.key]: v }))}
                  style={{ width: settingsControl.selectWidth }}
                  options={(p.options ?? []).map((o) => ({
                    value: o,
                    label: o,
                  }))}
                />
              ) : (
                <Input
                  value={values[p.key] ?? ''}
                  placeholder={
                    p.range ? `${p.range.min} ~ ${p.range.max}` : undefined
                  }
                  onChange={(e) =>
                    setValues((s) => ({ ...s, [p.key]: e.target.value }))
                  }
                  style={inputStyle}
                />
              )}
              {/* 列4：注释（desc + 默认值，次要色小字，弹性列） */}
              <span
                style={{
                  flex: 1,
                  marginLeft: Spacing.LG,
                  paddingRight: Spacing.XS,
                  color: Colors.TEXT.SECONDARY,
                  fontSize: FontSize.SECONDARY,
                }}
              >
                {p.desc}（默认 {p.default !== null ? String(p.default) : '空'}）
              </span>
            </div>
          ))}
        </div>
      ) : (
        /* 自定义行：三控件单行（删冗余 label，placeholder 说明），注释列与预设行同位 */
        <div style={{ ...settingsRowStyle, gap: Spacing.LG }}>
          <Input
            placeholder="参数名"
            value={customKey}
            onChange={(e) => setCustomKey(e.target.value)}
            style={inputStyle}
          />
          <Select
            value={customType}
            onChange={setCustomType}
            style={{ width: settingsControl.selectWidth }}
            options={[
              { value: 'number', label: '数字' },
              { value: 'string', label: '文本' },
              { value: 'boolean', label: '布尔' },
            ]}
          />
          <Input
            placeholder="值"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            style={inputStyle}
          />
          <span
            style={{
              flex: 1,
              paddingRight: Spacing.XS,
              color: Colors.TEXT.SECONDARY,
              fontSize: FontSize.SECONDARY,
            }}
          >
            填参数名与值、选类型后点确认，新参数将加入下方列表
          </span>
        </div>
      )}
    </div>
  );
};
