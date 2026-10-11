// 编辑历史: 2026-09-20 小强 - 新建：底部保存栏（[保存本组]+[保存全部]；危险项二次确认与重启 Modal 内联）
// 2026-09-21 小欧 - 实施：背景色→Colors.BG.PRIMARY
// 2026-09-21 小欧 - 实施：保存本组按钮带本组待存计数
// 2026-09-21 小欧 - 实施：危险保存确认 danger+⚠、重启通知结构化
// 2026-09-21 小欧 - 核查修复：⑤ content 包 span 加 secondary 色、⑥ 标题 fontWeight BOLD 内容 fontSize SECONDARY（设计文档 v1.11）
// 2026-09-21 小欧 - 全文核查：弹窗宽散落硬编码 480 → settingsModalWidth.confirm 令牌收口（设计文档 v1.12 规范一）
// 2026-09-21 小欧 - 全文核查：规范二落地——⑤⑥弹窗标题显式 fontSize:PRIMARY(14)+fontWeight:BOLD；marginTop/padding/marginLeft 裸数字 → Spacing.LG/MD 令牌（设计文档 v1.12 规范二）
// 2026-09-21 小欧 - 修复：onSaveGroup/onSaveAll 改为返回 Promise；危险守卫 Modal.confirm 的 onOk 返回 async 函数，
//   antd 确认框 OK 按钮携带 Promise 自动 loading，杜绝「保存中」连点 OK 双发保存
// 2026-09-21 小强 - 设置页17问题复核修复：危险确认拆分 dangerousGroup/dangerousAll（保存其他组不再误弹）；
//   content 去残留「黑白名单」文案（黑白名单键已从注册表删除）（[设置页UI审计] 问题7/8/10）
// 2026-10-05 22:16:38 小欧 - 「安全开关」随 settings_registry 标签改名「HTL人工开关」，危险操作确认弹窗文案同步 - 小欧-2026-10-05
// 2026-10-10 小欧 - 弹窗归一：重启生效提示 Modal → SettingsModal 标准壳，confirm 宽度档 480、单主键「知道了」
//   （cancelButtonProps 隐藏）、discard 关闭语义；Modal.confirm 危险确认保留原样（L49 走 confirmThen，非标准壳范围）。
// 编辑历史: 2026-10-11 00:55:20 小欧 - 危险确认迁至 SettingsModal.dangerConfirm + 展示「具体变更+后果」: 本文件侧调用改造(传具体变更与后果, 不再只笼统提示); 旧文件头历史块随重构迁移, 详见 git — 小欧-2026-10-11
// 编辑历史: 2026-10-11 01:24:25 小欧 - dangerHints 扁平数组改 dangerHintByChange(按 label 索引): 多条变更各自成组挂后果 — 小欧-2026-10-11
import React from 'react';
// 2026-10-11 00:05 小欧 - 危险确认迁至 SettingsModal.dangerConfirm 后，
//   本文件不再直接用 antd Modal，也不再自己算 480 宽度 —— 一并清掉这两个失效 import。
import { Button } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsShadow } from '@/theme/settingsTokens';
import { SettingsModal, CodeChip, dangerConfirm } from '@/theme/SettingsModal'; // 2026-10-10 小欧: 归一到设置页弹窗壳; 22:15 补 CodeChip; 10-11 补 dangerConfirm

interface Props {
  canSaveGroup: boolean;
  canSaveAll: boolean;
  dirtyCount: number;
  groupDirtyCount: number;
  saving: boolean;
  restartKeys: string[];
  // 修正(2026-09-21 小强)：危险确认拆分「保存本组/保存全部」两态——原 hasDangerousDirty 全局判定，
  // 安全组危险键脏时保存其它组也误弹（[设置页UI审计] 问题7/8）
  dangerousGroup: boolean;
  dangerousAll: boolean;
  // 2026-10-11 00:05 小欧 - 危险确认要展示「具体改了什么」+「后果」，
  //   由 SettingsPage 按 dirtyKeys 实算后下传（本组件不认 schema，避免重复实现取值口径）。
  dangerChanges: { label: string; from: string; to: string }[];
  dangerHintByChange: Record<string, string[]>;
  onSaveGroup: () => Promise<unknown>;
  onSaveAll: () => Promise<unknown>;
  onCloseRestart: () => void;
}

export const SaveBar: React.FC<Props> = ({
  canSaveGroup,
  canSaveAll,
  dirtyCount,
  groupDirtyCount,
  saving,
  restartKeys,
  dangerousGroup,
  dangerousAll,
  dangerChanges,
  dangerHintByChange,
  onSaveGroup,
  onSaveAll,
  onCloseRestart,
}) => {
  /**
   * 2026-10-11 00:05 小欧 - 危险确认改为「具体变更 + 后果」，并收进 SettingsModal 标准壳。
   *
   * 改前实测的问题（北京老陈审核后批准）：
   *   ① 双图标重复——antd Modal.confirm 自动加一个矢量图标，title 里又手写了一个 emoji ⚠，
   *      同一意思画两遍；且 emoji 跨平台形态不一（与删除确认弹框早已改掉的是同一毛病，此处漏改）。
   *   ② 只说"涉及危险操作相关配置（HTL人工开关/危险操作确认）"，用户看不出**具体要提交什么**。
   *      危险确认弹框存在的全部意义就是让人看清即将提交的变更。
   *   ③ 不说后果——设置页那行 notice 写明"关闭后无需人工确认…"，但弹窗里没有，用户点确认时
   *      不知道自己正在放弃人工确认这道防线。
   *   ④ 与删除确认弹框两套实现（那边已是 SettingsModal 标准壳）。
   *
   * 改法：dangerKeys 传入实际变更的键名，逐条列「键名：旧值 → 新值」；
   *   键名走 CodeChip（与删除确认同款等宽 chip）；正文改 label:value 对齐；
   *   标题不再手写图标（交回标准壳/antd 默认 danger 图标）。
   */
  const confirmThen = (
    fn: () => Promise<unknown>,
    dangerous: boolean,
    changes: { label: string; from: string; to: string }[]
  ) => {
    if (dangerous) {
      dangerConfirm({
        title: '含危险操作相关改动',
        changes,
        hintByChange: dangerHintByChange,
        okText: '确认保存',
        onOk: async () => {
          await fn();
        },
      });
    } else {
      void fn();
    }
  };
  return (
    <div
      style={{
        position: 'sticky',
        bottom: 0,
        marginTop: Spacing.LG,
        padding: `${Spacing.LG}px 0 0`,
        background: Colors.BG.PRIMARY,
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
        boxShadow: settingsShadow,
        zIndex: 10,
      }}
    >
      <Button
        disabled={!canSaveGroup || saving}
        loading={saving}
        onClick={() => confirmThen(onSaveGroup, dangerousGroup, dangerChanges)}
      >
        保存本组{groupDirtyCount > 0 ? `（${groupDirtyCount} 项）` : ''}
      </Button>
      <Button
        type="primary"
        disabled={!canSaveAll || saving}
        loading={saving}
        style={{ marginLeft: Spacing.MD }}
        onClick={() => confirmThen(onSaveAll, dangerousAll, dangerChanges)}
      >
        保存全部{dirtyCount > 0 ? `（${dirtyCount} 项）` : ''}
      </Button>
      <SettingsModal
        open={restartKeys.length > 0}
        width="confirm"
        title="含重启生效项"
        // 2026-10-10 22:15 小欧 - 视觉优化（问题#12）：键名列表由 <ul> bullet 改 CodeChip 行。
        //   原为一条 bullet 列表：单条时 bullet 过重，且 sandbox.enabled 这类机器键与中文说明同字体。
        onOk={onCloseRestart}
        onCancel={onCloseRestart}
        okText="知道了"
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}>
          以下改动需重启后端生效：
        </div>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: Spacing.SM,
            marginTop: Spacing.MD,
          }}
        >
          {restartKeys.map((k) => (
            <CodeChip key={k}>{k}</CodeChip>
          ))}
        </div>
      </SettingsModal>
    </div>
  );
};
