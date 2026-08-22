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
import { RobotOutlined } from '@ant-design/icons';
import { sessionApi, configApi } from '../../services/api';
import type { SessionModelOverride } from '../../types/chat';
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
  const [models, setModels] = useState<{ provider: string; model: string; display_name: string }[]>([]);
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
    const next: SessionModelOverride | null = val === FOLLOW_GLOBAL
      ? null
      : (() => {
          const m = models.find((x) => `${x.provider}-${x.model}` === val);
          return m ? { provider: m.provider, model: m.model, display_name: m.display_name } : null;
        })();
    if (!next && val !== FOLLOW_GLOBAL) return;
    const prev = sessionModelOverride;
    setLoading(true);
    try {
      const res = await sessionApi.updateSession(sessionId, sessionTitle || '新会话', sessionVersion, next);
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
        suffixIcon={<RobotOutlined />}
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
