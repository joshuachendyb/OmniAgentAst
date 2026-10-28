/**
 * SecretRevealInput — 密钥输入框 + "查看已保存明文"眼睛
 *
 * 编辑历史:
 *   2026-09-26 小欧 - 从 ProviderConfig.tsx 迁出（SRP：父组件原兼三职）。
 *   2026-09-26 小欧 - 修 readOnly 死锁（原 readOnly 条件含 !value 而 value 初值恒空，
 *     唯一来源是敲键又被 readOnly 挡死，一个字符都输不进去；fireEvent.change 能绕过故当时是假绿）；
 *     修丢焦点（原在 Input/Input.Password 间换组件会重建 DOM，改为常驻单 Input 只切 type）。
 *   2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}：打码串由后端生成，本组件只回显。
 *   2026-09-27 07:38 小欧 - 修 F1：isTyping 改由「值是否非空」驱动，不再由 focused 驱动。原式
 *     focused||value!=='' 让只读掩码框被点一下/Tab 一下就进入输入态（掩码消失、翻 password、提示语变），
 *     用户误以为密钥没配而重新输入覆盖。现改为聚焦即可编辑、但在敲下字符前仍显示掩码。
 *   2026-09-27 小欧 - 补「value 清空即退出输入态」effect（父层保存成功置空 value 后，
 *     否则框内空白可编辑，用户会误以为没保存成功）。
 *   2026-10-22 小欧 - 硬编码 'monospace' 收敛到 FontFamily.MONO 令牌(DRY) — 小欧-2026-10-22
 *   2026-10-29 小欧 - 修清空 api_key 后输入框残留/死锁四 Bug:
 *     Bug1 displayValue: configured=false 时恒空, 不回填旧 masked(即使时序未更新);
 *     Bug2(在 SettingsPage.tsx) 清空成功后立即本地更新 providerConfig, 不等异步 reload;
 *     Bug3 displayReadOnly+useEffect: configured=false 时恒可编辑 + 不复位 focused — 小欧-2026-10-29
 *     Bug4 明文态清空: revealed=true时configured变false,补effect强制退出明文态(清plainKey+revealed+定时器) — 小欧-2026-10-29
 *
 * 四条安全约束：①点眼睛先 Modal.confirm 确认才取明文 ②明文 30 秒自动打码+卸载清 timer
 *   ③明文只存内存（不写 localStorage）、明文态 readOnly 且 onChange 直接 return（不当作新值提交）
 *   ④掩码纯回显 masked（前端不判断档位、不拼星号）
 */
import React, { useEffect, useRef, useState } from 'react';
import { Button, Input, Modal } from 'antd';
import { ErrorType, showMessage } from '@/services/error/handler';
import { modelApi } from '@/services/api/model.api';
import { Colors, FontFamily, FontSize, Spacing } from '@/utils/stepStyles';
import { settingsSpacing } from '@/theme/settingsTokens';

/** 明文自动恢复打码的秒数（设计稿已定：30 秒） */
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
   * 掩码串（后端契约）。**由后端 mask_secret_value 一次生成、三档规则已定稿**，
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
  //   框内显示空白且可编辑，用户看不到"已配置"打码提示会误以为没保存成功。case: settings2-after-save-mask
  // 2026-10-29 小欧 - 修 Bug3: 仅 configured 时才复位 focused——清空 api_key 后 configured=false,
  //   不复位 focused 保持可编辑态; 且 masked 已空不会回填旧串 — 小欧-2026-10-29
  // 2026-10-29 小欧 - 修 Bug4: 明文态(revealed=true)下清空 api_key 时 configured 变 false,
  //   但 revealed/plainKey 未复位 → displayValue 仍显示旧明文 + displayReadOnly 恒 true(死锁) +
  //   眼睛按钮 {configured && ...} 消失无法手动关闭明文态; 补 effect: configured 变 false 时
  //   强制退出明文态(清 plainKey + revealed + 定时器) — 小欧-2026-10-29
  useEffect(() => {
    if (value === '' && configured) setFocused(false);
  }, [value, configured]);
  useEffect(() => {
    if (!configured && revealed) {
      setPlainKey('');
      setRevealed(false);
      if (revealTimer.current) clearTimeout(revealTimer.current);
    }
  }, [configured, revealed]);

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

  // 打码串与已保存明文必须 type="text"（密码模式把每字符渲染成圆点，前4后4看不见），只有本次输入才遮蔽。
  // 硬约束：常驻同一个 <Input>、只切 type 属性 —— 换 Input.Password 会重建 DOM，焦点掉到 body。
  const [focused, setFocused] = useState(false);
  // 2026-09-27 小欧 - 修 F1：isTyping 由「值非空」驱动而非 focused。原先点一下/Tab 一下即进输入态，
  //   掩码被抹成空白并翻 password，用户误以为密钥没配而重输覆盖。现在聚焦即可编辑、敲字符前仍显掩码。
  const isTyping = !revealed && value !== '';
  // 2026-10-29 小欧 - 修 Bug1: configured=false 时 displayValue 恒空——清空 api_key 后
  //   configured=false, 不再回填旧 masked(即使 masked 因时序尚未更新); configured=true 时
  //   未输入仍回显掩码(F1: 聚焦可编辑但敲字符前显掩码, 示意"有 key 可覆盖") — 小欧-2026-10-29
  const displayValue = revealed
    ? plainKey
    : isTyping
      ? value
      : configured
        ? masked
        : '';
  // 只读：①明文态恒只读（安全约束③）②configured 且未聚焦时只读（防误改已保存 key）;
  //   configured=false 时恒可编辑（无保存 key 可保护, 清空后立即可输入新 key） — 小欧-2026-10-29
  const displayReadOnly = revealed || (configured && !focused);
  const inputType = isTyping ? 'password' : 'text';

  const startOverwrite = (next: string) => {
    // 安全约束③：明文态直接 return —— 绝不把已保存明文当新值提交出去
    if (revealed) return;
    onChange(next);
  };

  return (
    <>
      <span style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
        {/* 常驻单个 Input：type 只在 text/password 间切换，DOM 节点不重建（修丢焦点） */}
        <Input
          type={inputType}
          value={displayValue}
          readOnly={displayReadOnly}
          onChange={(e) => startOverwrite(e.target.value)}
          onFocus={(e) => {
            setFocused(true);
            // 聚焦时全选掩码：不清空掩码的前提下，不全选则首字符会追加在掩码之后（混合串被当新 key 提交）
            if (!revealed && value === '' && masked) e.currentTarget.select();
          }}
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
            fontFamily: revealed ? FontFamily.MONO : undefined,
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
