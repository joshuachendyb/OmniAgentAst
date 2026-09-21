// 编辑历史: 2026-09-20 小强 - 新建：模型操作区（删除模型/Provider 入口；添加入口在选择器）
// 2026-09-21 小欧 - 全文逐章核查：gap 裸数字 → Spacing.MD 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小欧 - 重组区块：清空api_key从ProviderConfig移入操作区（方案C）
import React from 'react';
import { Button, Divider } from 'antd';
import { DeleteOutlined, ClearOutlined } from '@ant-design/icons';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

interface Props {
  configured: boolean;
  onClearApiKey: () => void;
  onDeleteModel: () => void;
  onDeleteProvider: () => void;
}

export const ModelActions: React.FC<Props> = ({
  configured,
  onClearApiKey,
  onDeleteModel,
  onDeleteProvider,
}) => (
  <div>
    <Divider plain style={{ margin: `0 0 ${Spacing.MD}px`, color: Colors.TEXT.TERTIARY, fontSize: FontSize.SECONDARY }}>
      危险操作
    </Divider>
    <div style={{ display: 'flex', gap: Spacing.MD }}>
      {configured && (
        <Button danger icon={<ClearOutlined />} onClick={onClearApiKey}>
          清空 api_key
        </Button>
      )}
      <Button danger icon={<DeleteOutlined />} onClick={onDeleteModel}>
        删除此模型
      </Button>
      <Button danger icon={<DeleteOutlined />} onClick={onDeleteProvider}>
        删除此 Provider
      </Button>
    </div>
  </div>
);
