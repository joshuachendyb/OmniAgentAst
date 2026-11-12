// 编辑历史: 2026-11-09 小欧 - 新建：设置项写入通道（脏键批量保存），原 useSettings 保存逻辑原样搬迁 — 小欧-2026-11-09
// 2026-11-11 小欧 - 移除 saveProbeImageUrl(Image_URL 即存链): 三个验证素材地址已回媒体页直接编辑(走组保存),
//   Image_URL 不再即存, 直写通道连同 PROBE_IMAGE_URL_KEY import 一并移除 — 小欧-2026-11-11
import {
  useCallback,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import {
  settingsApi,
  type SettingSchemaItem,
} from '@/services/api/settings.api';
import { SETTINGS_SAVED_EVT } from '@/constants/settingsEvents';
import { validate } from '../utils/modelUtils';
import { findGroupOfKey, normalizeSecret } from '../utils/settingsShape';
import {
  ErrorType,
  handleApiError,
  showMessage,
  showSuccess,
} from '@/services/error/handler';
import type { SaveResult, SettingsState } from '../types';

interface SettingsWritesDeps {
  state: SettingsState;
  setState: Dispatch<SetStateAction<SettingsState>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setRestartKeys: Dispatch<SetStateAction<string[]>>;
  mtimeRef: MutableRefObject<number>;
  syncMtime: (mtime: number | undefined | null) => void;
  load: (opts?: { reset?: boolean; keepModel?: boolean }) => Promise<void>;
  setHighlightKeyTtl: (key: string | null) => void;
}

export function useSettingsWrites({
  state,
  setState,
  setSaving,
  setRestartKeys,
  mtimeRef,
  syncMtime,
  load,
  setHighlightKeyTtl,
}: SettingsWritesDeps) {
  /** 写（参数配置）：schema 校验 → PUT /settings。 */
  // 修复：①schema 已删键/值为 undefined/env 接管键一律归 ghost —— 不提交、清脏、提示，
  //   杜绝 {key:undefined} 被 JSON 序列化丢键的假保存 与 env 接管键被后端跳过后的假保存；
  //   ②有效键(found)为空则直接返回，不再调 API 制造空 patch 假成功
  const saveKeys = useCallback(
    async (
      keys: string[],
      opts?: { skipMtimeCheck?: boolean }
    ): Promise<SaveResult> => {
      const items: SettingSchemaItem[] = [];
      const values: Record<string, unknown> = {};
      const found: string[] = [];
      const ghost: string[] = [];
      keys.forEach((ck) => {
        for (const g of Object.keys(state.schema)) {
          const item = state.schema[g]?.items.find((i) => i.key === ck);
          if (!item) continue;
          const v = state.values[g]?.[ck];
          const src = state.sources[g]?.[ck];
          if (v !== undefined && src !== 'env') {
            items.push(item);
            values[ck] = v;
            found.push(ck);
          } else {
            ghost.push(ck);
          }
          return;
        }
        ghost.push(ck);
      });
      if (ghost.length) {
        setState((s) => {
          const dirtyKeys = { ...s.dirtyKeys };
          const values = { ...s.values };
          // ghost 键要连 values 一起复位到 baseline：原实现只删 dirtyKeys，值还留着改后内容，
          //   界面照显却已不算未保存（脏标记与可见值脱节，用户以为改生效了）。
          ghost.forEach((k) => {
            const g = findGroupOfKey(s.schema, k);
            if (!g) return;
            delete dirtyKeys[k];
            values[g] = { ...values[g], [k]: s.baseline[g]?.[k] };
          });
          return { ...s, dirtyKeys, values };
        });
        showMessage(
          ErrorType.INFO,
          `已忽略不存在或环境变量接管的配置项：${ghost.join(', ')}`
        );
      }
      const bad = validate(items, values);
      if (bad) {
        setHighlightKeyTtl(bad.key);
        showMessage(ErrorType.WARNING, bad.message);
        return { ok: false, firstError: bad.key };
      }
      if (!found.length) return { ok: true };
      setSaving(true);
      try {
        // 保存前校验 mtime：后端已被外部更新则刷新并中止，杜绝本地静默覆盖且用户无感知。
        //   skipMtimeCheck 仅 saveAll 第二路用——同一次 saveAll 里前一路自己落盘 bump 的 mtime 不算外部更新。
        if (!opts?.skipMtimeCheck) {
          const curMtime = await settingsApi.getMtime();
          if (curMtime !== state.mtime) {
            await load({ reset: true });
            showMessage(
              ErrorType.WARNING,
              '配置已被外部更新，已重新加载，请核对后重新保存'
            );
            return { ok: false };
          }
        }
        const patch = Object.fromEntries(
          found.map((ck) => [
            ck,
            state.values[findGroupOfKey(state.schema, ck) ?? '']?.[ck],
          ])
        );
        const result = await settingsApi.updateSettings(patch);
        if (!result.ok) {
          result.errors.forEach((m) =>
            showMessage(ErrorType.VALIDATE_CONFIG_FAILED, m)
          );
          // 后端校验错误高亮定位：错误文案首 token 形如 "agent.max_rounds 应为整数" 的 key 前缀，
          //   命中 schema 键则 setHighlightKeyTtl（原只弹 toast 无红框定位，用户找不到错项）
          const firstTok = result.errors[0]?.split(/\s+/)[0] ?? '';
          if (
            firstTok &&
            Object.values(state.schema).some((g) =>
              g.items.some((i) => i.key === firstTok)
            )
          ) {
            setHighlightKeyTtl(firstTok);
          }
          return { ok: false };
        }
        // 修复：后端 warnings 全为空文案时给固定兜底提示，避免空文案被 showMessage 静默吞掉后用户误以为干净保存
        const warnMsgs = result.warnings.filter((m) => (m ?? '').trim());
        if (result.warnings.length && !warnMsgs.length) {
          showMessage(
            ErrorType.WARNING,
            '部分配置项由环境变量接管，已跳过保存'
          );
        } else {
          warnMsgs.forEach((m) => showMessage(ErrorType.WARNING, m));
        }
        if (result.need_restart.length) setRestartKeys(result.need_restart);
        else showSuccess('保存成功');
        setState((s) => {
          const dirtyKeys = { ...s.dirtyKeys };
          found.forEach((k) => {
            delete dirtyKeys[k];
          });
          // 2026-09-21 修复：secret 项保存成功后把明文/clear 归一回 {configured,suffix}，
          // 保证再渲染正确显示且再次保存不重复提交明文
          const values = { ...s.values };
          const baseline = { ...s.baseline };
          items.forEach((it) => {
            if (!it.secret) return;
            const g = findGroupOfKey(s.schema, it.key);
            if (!g) return;
            values[g] = {
              ...(values[g] ?? {}),
              [it.key]: normalizeSecret(values[g]?.[it.key]),
            };
          });
          // 成功保存后把已保存键的基线同步为落盘值（含 secret 归一），回滚判定才有正确参照
          items.forEach((it) => {
            const g = findGroupOfKey(s.schema, it.key);
            if (!g || values[g] == null) return;
            baseline[g] = {
              ...(baseline[g] ?? {}),
              [it.key]: values[g][it.key],
            };
          });
          return { ...s, dirtyKeys, values, baseline };
        });
        // 用落盘后 mtime 覆盖缓存，防假后门刷新误判
        syncMtime(result.mtime);
        // 保存成功后广播设置保存事件：chat 页 hook 的 appearance.step_render.* 只有设置页能改，受影响页需重读；
        //   事件名取自 @/constants/settingsEvents（唯一定义点，禁前端硬编码第二份字符串） — 小欧-2026-10-05
        window.dispatchEvent(new Event(SETTINGS_SAVED_EVT));
        return { ok: true };
      } catch (e) {
        handleApiError(e);
        return { ok: false };
      } finally {
        setSaving(false);
      }
    },
    [
      state.schema,
      state.values,
      state.sources,
      state.mtime,
      load,
      syncMtime,
      setHighlightKeyTtl,
      setState,
      setSaving,
      setRestartKeys,
    ]
  );

  return { saveKeys };
}
