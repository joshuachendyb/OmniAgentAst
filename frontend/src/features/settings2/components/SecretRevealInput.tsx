/**
 * SecretRevealInput — 密钥输入框 + "查看已保存明文"眼睛（第十二章 12.5）
 *
 * 编辑历史:
 *   2026-09-26 - 小欧 - [72]12.5 新建，从 ProviderConfig.tsx 原样迁出（拆分只改归属，不改逻辑；
 *     迁出原因 SRP：ProviderConfig 同时承担"配置表单/明文查看/连通性探测"三件事、膨胀到 500 行）。
 *   2026-09-26 - 小欧 - 修 P0-1 readOnly 死锁：displayReadOnly 含 !value，而 value 初值恒为 ''、
 *     唯一来源是敲键（又被 readOnly 挡死）⇒ 一个字符都输不进去；单测用 fireEvent.change 能绕过
 *     readOnly，故当时 11 条全绿是假绿。改用 focused 判定"正在输入"（见 displayValue 上方注释）。
 *   2026-09-26 - 小欧 - 修 P0-2 丢焦点：原先在 <Input> 与 <Input.Password> 之间换组件，Password 多一层
 *     span 包裹 ⇒ 第 1 个字符落地即重建 DOM、焦点掉到 body。改为常驻单 <Input> 只切 type 属性。
 *     顺带删死代码 startOverwrite 的 `if (!revealed) setPlainKey('')`（!revealed 时必为 ''，YAGNI）。
 *   2026-09-26 - 小欧 - 修掩码与后端两档契约错位：len<8 改返 prefix="****"，旧写法渲染成 10 个星。
 *   2026-09-27 - 小欧 - [72]三堂会审: 补「value 清空即退出输入态」effect —— 父层保存成功置空 value
 *     后若焦点仍在，框内显示空白可编辑而非打码提示，用户会误以为没保存成功。
 *
 * 本组件只做一件事：安全地展示密钥。三条安全约束（[72] 12.5 已定决策）：
 *   ①二次确认：点眼睛先 Modal.confirm 告知"将显示明文，请勿截图或分享"，确认后才调接口取明文
 *   ②30 秒自动恢复打码 + 组件卸载清理定时器（防内存泄漏、防卸载后 setState）
 *   ③明文只在内存 state，不写 localStorage；明文态 readOnly 且 onChange 直接 return
 *     （避免把明文当新值提交出去）
 * 另：[72]12.2 要求打码显示在输入框内（前4位+星号+末4位），故 maskedDisplay 作为 value
 *   参与三态互斥（见 displayValue / inputType 处注释）。
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
   * 掩码前后缀（[72]12.5 三键恒定契约）。后端 mask_secret_value 两档（北京老陈 2026-09-26 裁定）：
   * len>=8 给真前 4 位；len<8 给 "****" 字面量。两种情形均显示末 4 位，详见下方 maskedDisplay。
   */
  prefix: string;
  /** 掩码末 4 位 */
  suffix: string;
  /** 输入框宽度 */
  width: number | string;
}

export const SecretRevealInput: React.FC<SecretRevealInputProps> = ({
  providerName,
  value,
  onChange,
  configured,
  prefix,
  suffix,
  width,
}) => {
  const [revealed, setRevealed] = useState(false);
  const [plainKey, setPlainKey] = useState('');
  const revealTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 打码显示（后端 mask_secret_value 为唯一权威，两档：北京老陈 2026-09-26 裁定）：
  //   len>=8 → prefix=真前4位 → 前4+6星+末4；len<8 → prefix="****" 字面量 → 直接 prefix+末4
  //   （裁定「小于8的 显示后4位, 前面加4个*」，此路径再插 6 星会渲染成 10 个星）；prefix 空同走兜底。
  const maskedDisplay = configured
    ? prefix && prefix !== '****'
      ? `${prefix}${'*'.repeat(6)}${suffix}`
      : `****${suffix}`
    : '';

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
  //   两条不可动摇的实现约束（P0-1/P0-2 修复留下的）：
  //     ①isTyping 不能拿 `value !== ''` 单独当判据 —— value 初值恒 '' 且放行输入后才可能非空，
  //       拿它当 readOnly 判据会自锁（框恒只读，一个字符都进不来）。
  //     ②必须常驻同一个 <Input>、只切 type 属性，**绝不换组件** —— 在 <Input> 与 <Input.Password>
  //       间切换等于换 DOM 结构（后者多一层 span），第 1 个字符即卸载重建、焦点掉到 body。
  const [focused, setFocused] = useState(false);
  // 是否处于"输入新 key"态；明文态恒否（已保存明文只读展示，不可被当新值提交）
  const isTyping = !revealed && (focused || value !== '');
  const displayValue = revealed ? plainKey : isTyping ? value : maskedDisplay;
  // 只读：①明文态恒只读（安全约束③）②非输入态（打码串/空框）只读，防误改已保存 key
  const displayReadOnly = revealed || !isTyping;
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
