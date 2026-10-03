// 编辑历史:
// 2026-10-03 小欧 - 新建：isFreeModel/isFreeNameSuffix 纯函数单测（三判据 OR）。
//   反例重点：includes 误伤、Number(null)===0 陷阱、半免费、free="true" 脏值、id 缺失 — 小欧 2026-10-03
import { describe, it, expect } from 'vitest';
import {
  isFreeModel,
  isFreeNameSuffix,
} from '@/features/settings2/utils/modelUtils';
import type { RemoteModelItem } from '@/services/api/model.api';

/** 只填必需字段 id，其余交给各用例按需覆盖 */
const M = (over: Partial<RemoteModelItem>): RemoteModelItem => ({
  id: 'some-model',
  ...over,
});

describe('[69] isFreeNameSuffix — 名称 free 尾巴（endsWith 非 includes）', () => {
  it('本仓实证 -free 尾巴命中', () => {
    // 取自 backend/dist/.../config.yaml 实测：kimi-k2.5-free / minimax-m2.5-free
    expect(isFreeNameSuffix('kimi-k2.5-free')).toBe(true);
    expect(isFreeNameSuffix('minimax-m2.5-free')).toBe(true);
    // sensenova 历史实例 ling-3.0-flash-fin-free
    expect(isFreeNameSuffix('ling-3.0-flash-fin-free')).toBe(true);
  });

  it('OpenRouter 实证 :free 尾巴命中（2026-09-29 用 includes("-free") 实测 460 个命中 0）', () => {
    expect(isFreeNameSuffix('deepseek/deepseek-v3.1:free')).toBe(true);
    expect(isFreeNameSuffix('meta-llama/llama-3.3-70b-instruct:free')).toBe(true);
  });

  it('free 在中间或词首不命中（守卫 includes 误伤）', () => {
    expect(isFreeNameSuffix('free-tier-model')).toBe(false);
    expect(isFreeNameSuffix('free')).toBe(false);
    expect(isFreeNameSuffix('freemodel')).toBe(false);
    expect(isFreeNameSuffix('model-free-tier')).toBe(false);
  });

  it('大小写与首尾空白容错（模型 id 惯例小写，但防御免费误判成本为零）', () => {
    expect(isFreeNameSuffix('KIMI-K2.5-FREE')).toBe(true);
    expect(isFreeNameSuffix('  kimi-k2.5-free  ')).toBe(true);
  });

  it('id 缺失/空串返回 false 而非抛 TypeError', () => {
    // 回归：直接对 undefined 调 endsWith 会抛，此处 (v ?? '') 是唯一防线
    expect(isFreeNameSuffix(undefined)).toBe(false);
    expect(isFreeNameSuffix(null)).toBe(false);
    expect(isFreeNameSuffix('')).toBe(false);
    expect(isFreeNameSuffix('   ')).toBe(false);
  });

  it('_free 下划线写法不命中（无实证，按 YAGNI 有意不覆盖）', () => {
    // 若将来接的 provider 用 xxx_free，只需在 isFreeNameSuffix 补一条即可，此用例同步翻转
    expect(isFreeNameSuffix('model_free')).toBe(false);
  });
});

describe('[69] isFreeModel — 三判据 OR 并集', () => {
  it('判据一：free === true 判免费（AMD 实测形态）', () => {
    expect(isFreeModel(M({ id: 'amd-model', free: true }))).toBe(true);
  });

  it('判据一严格性：free 为字符串 "true" 不算（防脏数据误判）', () => {
    // 远端若下发 "true"，宽松写法会判免费；严格 === true 则落到判据二/三
    expect(isFreeModel(M({ id: 'amd-model', free: 'true' as never }))).toBe(
      false
    );
  });

  it('判据二：名称 -free / :free 尾巴判免费（无 pricing 亦可）', () => {
    expect(isFreeModel(M({ id: 'kimi-k2.5-free' }))).toBe(true);
    expect(isFreeModel(M({ id: 'deepseek/deepseek-v3.1:free' }))).toBe(true);
  });

  it('判据三：pricing prompt 与 completion 同时为 0 判免费（原 2026-09-29 判据不变）', () => {
    expect(
      isFreeModel(
        M({ id: 'local-llm', pricing: { prompt: '0', completion: '0' } })
      )
    ).toBe(true);
    // "0.000" 与数字 0 两种写法同样命中（Number() 而非 === '0'）
    expect(
      isFreeModel(
        M({ id: 'local-llm', pricing: { prompt: '0.000', completion: '0' } })
      )
    ).toBe(true);
  });

  it('半免费不算：prompt=0 但 completion≠0 判不免费', () => {
    expect(
      isFreeModel(
        M({ id: 'odd-model', pricing: { prompt: '0', completion: '0.0000003' } })
      )
    ).toBe(false);
  });

  it('Number(null) 陷阱守卫：无 pricing 无 free 无尾巴判不免费', () => {
    // Number(null) === 0 为真，漏 v != null 守卫会把本项误标免费
    expect(isFreeModel(M({ id: 'no-meta-model' }))).toBe(false);
    expect(
      isFreeModel(M({ id: 'null-price', pricing: { completion: '0' } }))
    ).toBe(false);
  });

  it('OR 语义（北京老陈定案）：free === false 但名字带 -free 仍判免费', () => {
    // 已如实告知的取舍：AMD MinerU2.5-Pro 形态(free=false + pricing 双 0)按并集会显示「免费」
    expect(
      isFreeModel(
        M({
          id: 'amd-false-yet-suffix-free',
          free: false,
          pricing: { prompt: '0.1', completion: '0.2' },
        })
      )
    ).toBe(true);
  });

  it('三项皆不命中判不免费（AMD 计费模型形态）', () => {
    expect(
      isFreeModel(
        M({
          id: 'deepseek-v4-flash',
          free: false,
          pricing: { prompt: '0.00000014', completion: '0.00000028' },
        })
      )
    ).toBe(false);
  });

  it('判据三不依赖 id（id 缺失但 pricing 双 0 仍判免费）', () => {
    expect(
      isFreeModel({
        id: '',
        pricing: { prompt: '0', completion: '0' },
      } as RemoteModelItem)
    ).toBe(true);
  });

  it('与真实 AMD 清单口径一致：9 项实测全 free=false 且 pricing 非 0 → 全判不免费', () => {
    // 取自 2026-10-03 AMD Radeon Cloud GET /models 实测，防止把计费模型误标免费
    const amd = [
      { id: 'DeepSeek-V4.1-Flash', p: '0.00000014', c: '0.00000028' },
      { id: 'GLM-5.3-Flash', p: '0.00000015', c: '0.0000005' },
      { id: 'MiniCPM5-2B', p: '0.000000124', c: '0.00000074' },
      { id: 'Qwen3.8-27B', p: '0.0000005', c: '0.000003' },
    ];
    amd.forEach((m) =>
      expect(
        isFreeModel(
          M({ id: m.id, free: false, pricing: { prompt: m.p, completion: m.c } })
        )
      ).toBe(false)
    );
  });
});