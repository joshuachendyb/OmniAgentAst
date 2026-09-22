// 编辑历史: 2026-09-20 小强 - 新建：模型操作区（删除模型/Provider 入口；添加入口在选择器）
// 2026-09-21 小欧 - 全文逐章核查：gap 裸数字 → Spacing.MD 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小欧 - 重组区块：清空api_key从ProviderConfig移入操作区（方案C）
// 2026-09-22 小强 - A3：加 envManaged 契约——env 接管 provider 的 api_key 由 {NAME}_API_KEY 环境变量管控，
//   「清空 api_key」后端必拒（clear 走 update_provider_config 被 _raise_if_env_takeover 拦截），隐藏该假操作按钮
import React from 'react';
import { Button, Divider } from 'antd';
import { DeleteOutlined, ClearOutlined } from '@ant-design/icons';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

interface Props {
  configured: boolean;
  envManaged?: boolean;
  onClearApiKey: () => void;
  onDeleteModel: () => void;
  onDeleteProvider: () => void;
}

export const ModelActions: React.FC<Props> = ({
  configured,
  envManaged,
  onClearApiKey,
  onDeleteModel,
  onDeleteProvider,
}) => (
  <div>
    <Divider
      plain
      style={{
        margin: `0 0 ${Spacing.MD}px`,
        color: Colors.TEXT.TERTIARY,
        fontSize: FontSize.SECONDARY,
      }}
    >
      危险操作
    </Divider>
    <div style={{ display: 'flex', gap: Spacing.MD }}>
      {configured && !envManaged && (
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
