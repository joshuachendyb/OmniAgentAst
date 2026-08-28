// 编辑历史: 2026-08-26 小欧 - 8.13/L2 实施: 会话级模型覆盖选择器, 写sessionModel, 409冲突回读(5.1/5.2)
// 编辑历史: 2026-08-27 小欧 - 修复#11: 切L2模型不再以'新会话'污染后端会话标题(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 模型列表类型归一为ModelListItem; 删IIFE改直线find写法
// 编辑历史: 2026-08-27 小欧 - 去头像-C2: 删ModelPicker内RobotOutlined后缀图标, 回落Antd默认DownOutlined下拉箭头(更符下拉心智)
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
import { sessionApi } from '../../services/api/session.api';
import { configApi } from '../../services/api/config.api';
import type { SessionModelOverride, ModelListItem } from '../../types/chat';
import { showSaveError, showSessionConflict } from '../../utils/chatMessages';

interface ModelPickerProps {
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  sessionModelOverride: SessionModelOverride | null;
  setSessionModelOverride: (v: SessionModelOverride | null) => void;
  setSessionVersion: (v: number) => void;
}

const FOLLOW_GLOBAL = '__follow_global__';

const ModelPicker: React.FC<ModelPickerProps> = ({
  sessionId,
  sessionTitle,
  sessionVersion,
  sessionModelOverride,
  setSessionModelOverride,
  setSessionVersion,
}) => {
  const [models, setModels] = useState<ModelListItem[]>([]); // 2026-08-27 小欧 三堂会审: 模型列表类型归一为ModelListItem
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await configApi.getModelList();
        if (!cancelled && res.models) setModels(res.models);
      } catch {
        if (!cancelled) setModels([]);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const value = sessionModelOverride ? `${sessionModelOverride.provider}-${sessionModelOverride.model}` : FOLLOW_GLOBAL;

  const handleChange = async (val: string) => {
    if (!sessionId) return;
    // 2026-08-27 小欧 三堂会审: 删IIFE包裹, 直线写法取模型项
    const foundModel = val === FOLLOW_GLOBAL ? undefined : models.find((x) => `${x.provider}-${x.model}` === val);
    const next: SessionModelOverride | null = foundModel
      ? { provider: foundModel.provider, model: foundModel.model, display_name: foundModel.display_name }
      : null;
    if (!next && val !== FOLLOW_GLOBAL) return;
    const prev = sessionModelOverride;
    setLoading(true);
    try {
      const res = await sessionApi.updateSession(sessionId, sessionTitle, sessionVersion, next); // 2026-08-27 小欧 修复#11: 移除'新会话'字面量回退, 切L2模型不应污染后端会话标题
      if (res.version) setSessionVersion(res.version);
      setSessionModelOverride(next);
    } catch (err: unknown) {
      const e = err as { response?: { status: number } };
      if (e?.response?.status === 409) {
        showSessionConflict();
        try {
          const sd = await sessionApi.getSessionMessages(sessionId);
          if (sd.version) setSessionVersion(sd.version);
          if (sd.sessionModel !== undefined) setSessionModelOverride(sd.sessionModel as SessionModelOverride | null);
        } catch {
        // 回读失败时保持当前状态，静默处理 — 小欧 2026-08-22
      }
      } else {
        showSaveError('切换模型失败，请重试');
        setSessionModelOverride(prev);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Tooltip title={sessionModelOverride ? `${sessionModelOverride.provider} (${sessionModelOverride.model})` : '跟随全局模型'}>
      <Select
        size="small"
        value={value}
        onChange={handleChange}
        loading={loading}
        disabled={!sessionId || loading}
        style={{ minWidth: 180 }}
        placeholder="跟随全局"
        suffixIcon={<DownOutlined />}
        options={[
          { value: FOLLOW_GLOBAL, label: '跟随全局' },
          ...models.map((m) => ({
            value: `${m.provider}-${m.model}`,
            label: `${m.display_name || m.model} (${m.provider})`,
          })),
        ]}
      />
    </Tooltip>
  );
};

export default ModelPicker;
