import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Tag,
  Space,
  Typography,
  Modal,
  Select,
  Row,
  Col,
} from 'antd';
import {
  FolderOpenOutlined,
  FileTextOutlined,
  CheckOutlined,
  CheckCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { configApi } from '../../../services/api';
import {
  handleError,
  showSuccess,
  showMessage,
  ErrorType,
} from '../../../utils/errorHandler';
import type { ModelOption } from '../types';

const { Text } = Typography;

/**
 * 全局配置区域组件（显示 display_name 列表）
 * @author 小新
 * @update 2026-03-03 重构为单一下拉框
 */
export const GlobalConfigArea: React.FC<{
  modelList: ModelOption[];
  currentDisplayName: string;
  onDisplayNameChange: (option: ModelOption) => void;
}> = ({ modelList, currentDisplayName, onDisplayNameChange }) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [configPath, setConfigPath] = useState<any>(null);
  const [configContent, setConfigContent] = useState<string>('');
  const [showConfigModal, setShowConfigModal] = useState(false);

  useEffect(() => {
    const loadConfigPath = async () => {
      try {
        const pathData = await configApi.getConfigPath();
        setConfigPath(pathData);
      } catch (error) {
        console.error('加载配置文件路径失败:', error);
      }
    };
    loadConfigPath();
  }, []);

  const handleOpenConfigDir = async () => {
    try {
      await configApi.openConfigFolder();
    } catch (error) {
      console.error('打开配置目录失败:', error);
      handleError('打开配置目录失败');
    }
  };

  const handleViewConfig = async () => {
    try {
      const data = await configApi.readConfigFile();
      setConfigContent(data.config_content);
      setShowConfigModal(true);
    } catch (error) {
      console.error('读取配置文件失败:', error);
      handleError('读取配置文件失败');
    }
  };

  const handleValidateConfig = async () => {
    const currentOption = modelList.find((m) => m.current_model);
    if (!currentOption) {
      showMessage(ErrorType.INFO, '未找到当前使用的模型，无法检测');
      return;
    }
    try {
      const result = await configApi.validateConfig({
        provider: currentOption.provider,
        api_key: '',
      });
      if (result.valid) {
        showSuccess(result.message || '配置检测通过');
      } else {
        handleError({ message: result.message || '配置检测失败' });
      }
    } catch (error) {
      console.error('检测配置失败:', error);
      handleError('检测配置失败');
    }
  };

  return (
    <Card size="small" style={{ marginBottom: 24 }}>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          {/* 配置文件路径显示 - 上一行标签，下一行信息框 */}
          {configPath && (
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ display: 'block', marginBottom: 8 }}>
                配置文件路径：
              </Text>
              <Card size="small" style={{ backgroundColor: '#fafafa' }}>
                <div style={{ wordBreak: 'break-all', marginBottom: 8 }}>
                  <Text code>{configPath.config_path}</Text>
                </div>
                <Space>
                  <Button
                    type="primary"
                    size="small"
                    icon={<FolderOpenOutlined />}
                    onClick={handleOpenConfigDir}
                  >
                    打开配置目录
                  </Button>
                  <Button
                    size="small"
                    icon={<FileTextOutlined />}
                    onClick={handleViewConfig}
                  >
                    查看配置
                  </Button>
                  <Button
                    size="small"
                    icon={<CheckOutlined />}
                    onClick={handleValidateConfig}
                  >
                    检测配置
                  </Button>
                  {configPath.exists ? (
                    <Tag color="green" icon={<CheckCircleOutlined />}>
                      配置文件正常
                    </Tag>
                  ) : (
                    <Tag color="orange" icon={<WarningOutlined />}>
                      配置文件不存在
                    </Tag>
                  )}
                </Space>
              </Card>
            </div>
          )}

          {/* 当前模型 - 上一行标签，下一行下拉框 */}
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            当前模型:
          </Text>
          <Select
            value={currentDisplayName}
            onChange={(displayName) => {
              const option = modelList.find(
                (m) => m.display_name === displayName
              );
              if (option) {
                onDisplayNameChange(option);
              }
            }}
            style={{ width: '100%' }}
            placeholder="选择模型"
          >
            {modelList.map((m) => (
              <Select.Option
                key={`${m.provider}-${m.model}`}
                value={m.display_name}
              >
                {m.display_name} {m.current_model === true ? ' *' : ''}
              </Select.Option>
            ))}
          </Select>
        </Col>
      </Row>

      {/* 查看配置文件 Modal */}
      <Modal
        title="配置文件内容"
        open={showConfigModal}
        onCancel={() => setShowConfigModal(false)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setShowConfigModal(false)}>
            关闭
          </Button>,
        ]}
      >
        <pre
          style={{
            maxHeight: 500,
            overflow: 'auto',
            backgroundColor: '#f5f5f5',
            padding: 12,
            borderRadius: 4,
            fontSize: 12,
          }}
        >
          {configContent}
        </pre>
      </Modal>
    </Card>
  );
};
