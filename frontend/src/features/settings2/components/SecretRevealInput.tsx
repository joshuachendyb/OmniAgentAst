/**
 * SecretRevealInput — 密钥输入框 + "查看已保存明文"眼睛
 *
 * 编辑历史:
 *   2026-09-26 小欧 - 从 ProviderConfig.tsx 迁出（SRP：父组件原兼三职）。
 *   2026-09-26 小欧 - 修 P0-1 readOnly 死锁（原 readOnly 条件含 !value 而 value 初值恒空，
 *     唯一来源是敲键又被 readOnly 挡死，一个字符都输不进去；fireEvent.change 能绕过故当时是假绿）；
 *     修 P0-2 丢焦点（原在 Input/Input.Password 间换组件会重建 DOM，改为常驻单 Input 只切 type）。
 *   2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}：打码串由后端生成，本组件只回显。
 *   2026-09-27 07:38 小欧 - 修 F1：isTyping 改由「值是否非空」驱动，不再由 focused 驱动。原式
 *     focused||value!=='' 让只读掩码框被点一下/Tab 一下就进入输入态（掩码消失、翻 password、提示语变），
 *     用户误以为密钥没配而重新输入覆盖。现改为聚焦即可编辑、但在敲下字符前仍显示掩码。
 *   2026-09-27 小欧 - 补「value 清空即退出输入态」effect（父层保存成功置空 value 后，
 *     否则框内空白可编辑，用户会误以为没保存成功）。
 *
 * 四条安全约束：①点眼睛先 Modal.confirm 确认才取明文 ②明文 30 秒自动打码+卸载清 timer
 *   ③明文只存内存（不写 localStorage）、明文态 readOnly 且 onChange 直接 return（不当作新值提交）
 *   ④掩码纯回显 masked（前端不判断档位、不拼星号）
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
  /** 是否已配置过密钥（决定框内打码显示与是否显示眼睛） */
  configured: boolean;
  /**
   * 掩码串（[72]12.5 契约）。**由后端 mask_secret_value 一次生成、三档规则已定稿**，
   * 前端只负责显示，不做任何档位判断或拼接（DRY：掩码规则只此一处）。
   */
  masked: string;
  /** 输入框宽度 */
  width: number | string;
}

export const SecretRevealInput: React.FC<SecretRevealInputProps> = ({
  providerName,
  value,
  onChange,
  configured,
  masked,
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

  // 2026-09-27 - 小欧 - value 被清空即退出输入态：父层保存成功会置空 value，若焦点仍在则 isTyping 仍为 true，
  // 框内显示空白且可编辑，用户看不到"已配置"打码提示会误以为没保存成功。case: settings2-after-save-mask
  useEffect(() => {
    if (value === '') setFocused(false);
  }, [value]);

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

  // ★ 打码串与已保存明文必须用 type="text" 展示（密码模式会把每个字符渲染成圆点，前4后4看不见），
  //   只有"本次正在输入的新 key"才遮蔽，否则二者长得一样、功能失效。
  //   P0-2 修复留下的硬约束：必须常驻同一个 <Input>、只切 type 属性，**绝不换组件** ——
  //   在 <Input> 与 <Input.Password> 间切换等于换 DOM 结构（后者多一层 span），
  //   第 1 个字符即卸载重建、焦点掉到 body。
  const [focused, setFocused] = useState(false);
  // 2026-09-27 小欧 - 修 F1：isTyping 改由「值是否非空」驱动，不再由 focused 驱动。
  //   原式 focused||value!=='' 让"只读掩码态被点一下/Tab 一下"也进入输入态 → 掩码被抹成空白、
  //   输入框翻成 password、提示语换掉，用户以为密钥没配而重新输入覆盖。
  //   现在：聚焦即可编辑（P0-1 要求的"不因 readOnly 自锁，一个字符都输不进去"由 displayReadOnly
  //   交给 focused 保证），但在真的敲下字符前，框内仍显示掩码、仍是明文可见的 text。
  // 是否处于"输入新 key"态；明文态恒否（已保存明文只读展示，不可被当新值提交）
  const isTyping = !revealed && value !== '';
  const displayValue = revealed ? plainKey : isTyping ? value : masked;
  // 只读：①明文态恒只读（安全约束③）②未聚焦即只读，防误改已保存 key
  const displayReadOnly = revealed || !focused;
  // 输入中遮蔽本次输入；展示打码串/明文必须 text，否则前后 4 位看不见（12.2）
  const inputType = isTyping ? 'password' : 'text';

  const startOverwrite = (next: string) => {
    // 安全约束③：明文态直接 return —— 绝不把已保存明文当新值提交出去
    if (revealed) return;
    onChange(next);
  };

  return (
    <>
      <span style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
        {/* 常驻单个 Input：type 只在 text/password 间切换，DOM 节点不重建（修 P0-2） */}
        <Input
          type={inputType}
          value={displayValue}
          readOnly={displayReadOnly}
          onChange={(e) => startOverwrite(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          // 新密钥一律不让浏览器自动填充（防把已保存口令填进覆盖框）
          autoComplete="new-password"
          placeholder={
            isTyping
              ? '输入新密钥以覆盖'
              : configured
                ? '已配置，留空保持原值'
                : '未配置'
          }
          style={{
            width,
            // 明文态用等宽字体，便于逐字符核对密钥
            fontFamily: revealed ? 'monospace' : undefined,
          }}
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
        {configured
          ? '留空=保持原值（上方为已保存密钥的掩码）'
          : '未配置，留空=保持原值'}
      </div>
    </>
  );
};
