// 编辑历史: 2026-09-20 小强 - 新建：模型操作区（删除模型/Provider 入口；添加入口在选择器）
import React from 'react';
import { Button } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';

interface Props {
  onDeleteModel: () => void;
  onDeleteProvider: () => void;
}

export const ModelActions: React.FC<Props> = ({
  onDeleteModel,
  onDeleteProvider,
}) => (
  <div style={{ display: 'flex', gap: 8 }}>
    <Button danger icon={<DeleteOutlined />} onClick={onDeleteModel}>
      删除此模型
    </Button>
    <Button danger icon={<DeleteOutlined />} onClick={onDeleteProvider}>
      删除此 Provider
    </Button>
  </div>
);
