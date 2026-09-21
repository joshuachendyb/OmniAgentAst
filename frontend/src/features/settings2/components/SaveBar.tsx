// 编辑历史: 2026-09-20 小强 - 新建：底部保存栏（[保存本组]+[保存全部]；危险项二次确认与重启 Modal 内联）
// 2026-09-21 小欧 - P0-1：背景色→Colors.BG.PRIMARY（[58] P0-1）
// 2026-09-21 小欧 - P1-3：保存本组按钮带本组待存计数（[58] P1-3）
// 2026-09-21 小欧 - 第六章⑤⑥：危险保存确认 danger+⚠、重启通知结构化（[58] 第六章 6.2）
import React from 'react';
import { Button, Modal } from 'antd';
import { Colors } from '@/utils/stepStyles';
import { settingsShadow } from '@/theme/settingsTokens';

interface Props {
  canSaveGroup: boolean;
  canSaveAll: boolean;
  dirtyCount: number;
  groupDirtyCount: number;
  saving: boolean;
  restartKeys: string[];
  hasDangerousDirty: boolean;
  onSaveGroup: () => void;
  onSaveAll: () => void;
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
  const confirmThen = (fn: () => void) => {
    if (hasDangerousDirty) {
      Modal.confirm({
        title: '⚠ 含危险操作相关改动',
        content: '本次保存涉及危险操作/黑白名单配置，确认提交吗？',
        okText: '确认保存',
        okButtonProps: { danger: true },
        cancelText: '取消',
        onOk: fn,
      });
    } else {
      fn();
    }
  };
  return (
    <div
      style={{
        position: 'sticky',
        bottom: 0,
        marginTop: 12,
        padding: '12px 0 0',
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
        style={{ marginLeft: 8 }}
        onClick={() => confirmThen(onSaveAll)}
      >
        保存全部{dirtyCount > 0 ? `（${dirtyCount} 项）` : ''}
      </Button>
      <Modal
        open={restartKeys.length > 0}
        title="含重启生效项"
        onOk={onCloseRestart}
        onCancel={onCloseRestart}
        okText="知道了"
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        以下改动需重启后端生效：
        <ul>
          {restartKeys.map((k) => (
            <li key={k} style={{ color: Colors.TEXT.SECONDARY }}>{k}</li>
          ))}
        </ul>
      </Modal>
    </div>
  );
};
