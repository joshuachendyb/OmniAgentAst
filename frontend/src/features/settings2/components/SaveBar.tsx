// 编辑历史: 2026-09-20 小强 - 新建：底部保存栏（[保存本组]+[保存全部]；危险项二次确认与重启 Modal 内联）
import React from 'react';
import { Button, Modal } from 'antd';
import { Colors } from '@/utils/stepStyles';

interface Props {
  canSaveGroup: boolean;
  canSaveAll: boolean;
  dirtyCount: number;
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
        title: '含危险操作相关改动',
        content: '本次保存涉及危险操作/黑白名单配置，确认提交吗？',
        okText: '确认保存',
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
        background: '#fff',
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
      }}
    >
      <Button
        disabled={!canSaveGroup || saving}
        loading={saving}
        onClick={() => confirmThen(onSaveGroup)}
      >
        保存本组
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
            <li key={k}>{k}</li>
          ))}
        </ul>
      </Modal>
    </div>
  );
};
