// 编辑历史: 2026-09-20 小强 - 新建：底部保存栏（[保存本组]+[保存全部]；危险项二次确认与重启 Modal 内联）
// 2026-09-21 小欧 - P0-1：背景色→Colors.BG.PRIMARY（[58] P0-1）
// 2026-09-21 小欧 - P1-3：保存本组按钮带本组待存计数（[58] P1-3）
// 2026-09-21 小欧 - 第六章⑤⑥：危险保存确认 danger+⚠、重启通知结构化（[58] 第六章 6.2）
// 2026-09-21 小欧 - 核查修复：⑤ content 包 span 加 secondary 色、⑥ 标题 fontWeight BOLD 内容 fontSize SECONDARY（[58] v1.11 Step6.5/6.6）
// 2026-09-21 小欧 - 全文逐章核查：弹窗宽散落硬编码 480 → settingsModalWidth.confirm 令牌收口（[58] v1.12 第六章 6.1 规范一）
// 2026-09-21 小欧 - 全文逐章核查：规范二落地——⑤⑥弹窗标题显式 fontSize:PRIMARY(14)+fontWeight:BOLD；marginTop/padding/marginLeft 裸数字 → Spacing.LG/MD 令牌（[58] v1.12 第六章 6.1 规范二）
// 2026-09-21 小欧 - [59]F-9 修复：onSaveGroup/onSaveAll 改为返回 Promise；危险守卫 Modal.confirm 的 onOk 返回 async 函数，
//   antd 确认框 OK 按钮携带 Promise 自动 loading，杜绝「保存中」连点 OK 双发保存
import React from 'react';
import { Button, Modal } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsShadow, settingsModalWidth } from '@/theme/settingsTokens';

interface Props {
  canSaveGroup: boolean;
  canSaveAll: boolean;
  dirtyCount: number;
  groupDirtyCount: number;
  saving: boolean;
  restartKeys: string[];
  hasDangerousDirty: boolean;
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
  hasDangerousDirty,
  onSaveGroup,
  onSaveAll,
  onCloseRestart,
}) => {
  const confirmThen = (fn: () => Promise<unknown>) => {
    if (hasDangerousDirty) {
      Modal.confirm({
        title: (
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >
            ⚠ 含危险操作相关改动
          </span>
        ),
        content: (
          <span style={{ color: Colors.TEXT.SECONDARY }}>
            本次保存涉及危险操作/黑白名单配置，确认提交吗？
          </span>
        ),
        okText: '确认保存',
        okButtonProps: { danger: true },
        cancelText: '取消',
        width: settingsModalWidth.confirm,
        // [59]F-9 修复：onOk 返回 Promise → antd OK 按钮 loading，保存期间防连点双发
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
        onClick={() => confirmThen(onSaveGroup)}
      >
        保存本组{groupDirtyCount > 0 ? `（${groupDirtyCount} 项）` : ''}
      </Button>
      <Button
        type="primary"
        disabled={!canSaveAll || saving}
        loading={saving}
        style={{ marginLeft: Spacing.MD }}
        onClick={() => confirmThen(onSaveAll)}
      >
        保存全部{dirtyCount > 0 ? `（${dirtyCount} 项）` : ''}
      </Button>
      <Modal
        open={restartKeys.length > 0}
        title={
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >
            含重启生效项
          </span>
        }
        onOk={onCloseRestart}
        onCancel={onCloseRestart}
        okText="知道了"
        width={settingsModalWidth.confirm}
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        <div style={{ fontSize: FontSize.SECONDARY }}>
          以下改动需重启后端生效：
          <ul>
            {restartKeys.map((k) => (
              <li key={k} style={{ color: Colors.TEXT.SECONDARY }}>
                {k}
              </li>
            ))}
          </ul>
        </div>
      </Modal>
    </div>
  );
};
