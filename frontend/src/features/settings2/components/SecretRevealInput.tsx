/**
 * SecretRevealInput — 密钥输入框 + "查看已保存明文"眼睛（第十二章 12.5）
 *
 * 编辑历史:
 *   2026-09-26 - 小欧 - [72]第十二章(12.5) 新建。从 ProviderConfig.tsx 原样迁出（拆分只改归属，
 *     不改业务逻辑——符合项目"能复制就复制、不重写"纪律）。
 *     迁出原因（SRP）：ProviderConfig 同时承担"配置表单 / 明文查看 / 连通性探测"三件事，
 *     组件膨胀到 500 行，任一功能改动都要读完整个组件。故把本职责独立成组件。
 *
 * 本组件只做一件事：安全地展示密钥。三条安全约束（[72] 12.5 已定决策）：
 *   ①二次确认：点眼睛先 Modal.confirm 告知"将显示明文，请勿截图或分享"，确认后才调接口取明文
 *   ②30 秒自动恢复打码 + 组件卸载清理定时器（防内存泄漏、防卸载后 setState）
 *   ③明文只在内存 state，不写 localStorage；明文态 readOnly 且 onChange 直接 return
 *     （避免把明文当新值提交出去）
 */
import React, { useEffect, useRef, useState } from 'react';
import { Button, Input, Modal } from 'antd';
import { ErrorType, showMessage } from '@/services/error/handler';
import { modelApi } from '@/services/api/model.api';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import { settingsSpacing } from '@/theme/settingsTokens';

/** 明文自动恢复打码的秒数（[72] 12.5 已定：30 秒） */
const REVEAL_TIMEOUT_MS = 30_000;

export interface SecretRevealInputProps {
  /** provider 名（取明文接口入参） */
  providerName: string;
  /** 输入框受控值（本次输入的 key，未保存） */
  value: string;
  /** 输入变化回调（明文态下不会触发） */
  onChange: (v: string) => void;
  /** 是否已配置过密钥（决定 placeholder 与是否显示眼睛） */
  configured: boolean;
  /** 打码描述：前4位 / 末4位（prefix 为空时只显示末4位） */
  maskedHint: string;
  /** 输入框宽度 */
  width: number | string;
}

export const SecretRevealInput: React.FC<SecretRevealInputProps> = ({
  providerName,
  value,
  onChange,
  configured,
  maskedHint,
  width,
}) => {
  const [revealed, setRevealed] = useState(false);
  const [plainKey, setPlainKey] = useState('');
  const revealTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 30 秒自动恢复打码（组件卸载时清理定时器，防内存泄漏与"卸载后仍回调 setState"）
  useEffect(
    () => () => {
      if (revealTimer.current) clearTimeout(revealTimer.current);
    },
    []
  );

  /** 眼睛点击：需二次确认，确认后才调接口取明文；再次点击立即清除明文。 */
  const onToggleReveal = async () => {
    if (revealed) {
      // 恢复打码：立即从 state 清除明文（不写 localStorage）
      setPlainKey('');
      setRevealed(false);
      if (revealTimer.current) clearTimeout(revealTimer.current);
      return;
    }
    Modal.confirm({
      title: '显示明文密钥',
      content: '将显示已保存的明文密钥，请勿截图或分享。30 秒后自动恢复打码。',
      okText: '显示',
      cancelText: '取消',
      onOk: async () => {
        try {
          const r = await modelApi.getApiKeyPlain(providerName);
          setPlainKey(r.api_key);
          setRevealed(true);
          if (revealTimer.current) clearTimeout(revealTimer.current);
          revealTimer.current = setTimeout(() => {
            setPlainKey('');
            setRevealed(false);
          }, REVEAL_TIMEOUT_MS);
        } catch (e) {
          showMessage(
            ErrorType.NETWORK_ERROR,
            `无法查看明文密钥：${e instanceof Error ? e.message : String(e)}`
          );
        }
      },
    });
  };

  return (
    <>
      <span style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
        <Input.Password
          // 2026-09-26 小欧 - 职责切分: revealed 时展示**已保存的明文**；否则展示本次输入
          //   （输入框初值恒为 ''，原生眼睛看不到已保存的 key，故与自定义眼睛并存会让人无法分辨）
          value={revealed ? plainKey : value}
          onChange={(e) => {
            if (revealed) return; // 明文态禁止编辑（避免把明文当新值提交）
            onChange(e.target.value);
          }}
          placeholder={configured ? '已配置，留空保持原值' : '未配置'}
          autoComplete="new-password"
          readOnly={revealed}
          // 2026-09-26 小欧 - [72]第十二章(12.4 起): 关闭 AntD 自带眼睛。
          //   原生眼睛只能显示"刚输入的字符"，与"看已保存明文"的眼睛并存会出现两个眼睛，
          //   用户无法分辨；本次输入内容的隐藏改由 autoComplete="new-password" 承担。
          visibilityToggle={false}
          style={{ width }}
        />
        {/* 自定义眼睛：查看已保存的明文（未配置时无密钥可看，不显示） */}
        {configured && (
          <Button
            size="small"
            type="text"
            aria-label={revealed ? '隐藏已保存的密钥' : '查看已保存的密钥'}
            onClick={() => void onToggleReveal()}
            style={{ marginLeft: Spacing.XS }}
          >
            {revealed ? '🙈' : '👁'}
          </Button>
        )}
      </span>
      <div
        style={{
          marginLeft: settingsSpacing.labelWidth,
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.SECONDARY,
          paddingTop: Spacing.XS,
        }}
      >
        {configured ? `已配置（${maskedHint}），留空=保持原值` : '未配置，留空=保持原值'}
      </div>
    </>
  );
};
