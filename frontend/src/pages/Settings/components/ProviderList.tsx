import React, { useState, useMemo } from 'react';
import { Card, Button, Space, Typography, Tag, Input, Alert } from 'antd';
import { PlusOutlined, ApiOutlined } from '@ant-design/icons';
import type { ProviderInfo } from '../../../services/api';
import type { ModelOption } from '../types';

const { Text } = Typography;

/**
 * Provider列表组件（左侧）
 * @author 小新
 * @update 2026-02-26 新增
 */
export const ProviderList: React.FC<{
  providers: ProviderInfo[];
  currentProvider: string;
  onSelect: (provider: ProviderInfo) => void;
  onAdd?: () => void;
  modelList: ModelOption[];
}> = ({ providers, currentProvider, onSelect, onAdd, modelList }) => {
  const [searchKeyword, setSearchKeyword] = useState('');

  const filteredProviders = useMemo(
    () =>
      providers.filter((provider) =>
        provider.name.toLowerCase().includes(searchKeyword.toLowerCase())
      ),
    [providers, searchKeyword]
  );

  return (
    <div style={{ borderRight: '1px solid #f0f0f0', paddingRight: 16 }}>
      <Space
        style={{
          marginBottom: 16,
          width: '100%',
          justifyContent: 'space-between',
        }}
      >
        <Typography.Title level={5} style={{ marginBottom: 0 }}>
          Provider列表
        </Typography.Title>
        {onAdd && (
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={onAdd}
          >
            添加
          </Button>
        )}
      </Space>

      {/* 搜索框 */}
      <Input
        placeholder="搜索Provider..."
        allowClear
        style={{ marginBottom: 16 }}
        onChange={(e) => setSearchKeyword(e.target.value)}
        prefix={<ApiOutlined />}
      />

      {filteredProviders.map((provider) => (
        <Card
          key={provider.name}
          size="small"
          style={{ marginBottom: 12, cursor: 'pointer' }}
          onClick={() => onSelect(provider)}
          styles={{
            body: {
              backgroundColor:
                provider.name === currentProvider ? '#e6f7ff' : 'transparent',
            },
          }}
        >
          <Space>
            <ApiOutlined />
            <Text strong>{provider.name}</Text>
            {/* ⭐ 修复：只显示真正正在使用的模型对应的Provider的"当前使用"标签 */}
            {modelList.some(
              (m) => m.provider === provider.name && m.current_model
            ) && (
              <Tag
                color="success"
                style={{ lineHeight: '16px', padding: '0 4px' }}
              >
                ✓
              </Tag>
            )}
          </Space>
        </Card>
      ))}

      {filteredProviders.length === 0 && (
        <Alert
          message="未找到匹配的Provider"
          description="尝试调整搜索关键词"
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
        />
      )}
    </div>
  );
};
