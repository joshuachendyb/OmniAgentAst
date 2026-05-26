import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
} from 'react';
import {
  Card,
  Button,
  Tag,
  Space,
  Typography,
  Divider,
  Popconfirm,
  Modal,
  Form,
  Input,
  Row,
  Col,
  Progress,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
} from '@ant-design/icons';
import { configApi } from '../../../services/api';
import type { ProviderInfo } from '../../../services/api';
import {
  handleError,
  showSuccess,
  ErrorType,
} from '../../../utils/errorHandler';
import type { ModelOption } from '../types';
import { GlobalConfigArea } from './GlobalConfigArea';
import { ProviderList } from './ProviderList';

const { Text } = Typography;

const getProviderDisplayName = (
  name: string,
  providerList?: ProviderInfo[]
) => {
  if (providerList && providerList.length > 0) {
    const provider = providerList.find((p) => p.name === name);
    if (provider && provider.display_name) {
      return provider.display_name;
    }
  }
  return name;
};

/**
 * Provider管理页面组件
 * @author 小新
 * @update 2026-02-26 重构：提取子组件
 */
export const ProviderSettings: React.FC<{
  shouldLoad?: boolean;
  forceRefresh?: boolean;
}> = ({ shouldLoad = true, forceRefresh }) => {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [modelList, setModelList] = useState<ModelOption[]>([]);
  const [currentDisplayName, setCurrentDisplayName] = useState<string>('');
  const [selectedProvider, setSelectedProvider] = useState<ProviderInfo | null>(
    null
  );
  const [_loading, setLoading] = useState(false);
  const [editProviderModalVisible, setEditProviderModalVisible] =
    useState(false);
  const [editModelModalVisible, setEditModelModalVisible] = useState(false);
  const [addModelModalVisible, setAddModelModalVisible] = useState(false);
  const [addProviderModalVisible, setAddProviderModalVisible] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderInfo | null>(
    null
  );
  const [selectedProviderForModel, setSelectedProviderForModel] =
    useState<string>('');
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({});
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [deleteProgress, setDeleteProgress] = useState<{
    current: number;
    total: number;
  }>({ current: 0, total: 0 });
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const deleteControllerRef = useRef<AbortController | null>(null);

  const [form] = Form.useForm();
  const [modelForm] = Form.useForm();
  const [providerForm] = Form.useForm();

  const toggleShowApiKey = (providerName: string) => {
    setShowApiKey((prev) => ({ ...prev, [providerName]: !prev[providerName] }));
  };

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const data = await configApi.getFullConfig();
      const providerList = Object.values(data.providers);
      setProviders(providerList);

      const modelData = await configApi.getModelList();
      console.log(
        '从后端获取的模型列表：',
        JSON.stringify(modelData.models, null, 2)
      );
      setModelList(modelData.models);

      const currentModelOption = modelData.models.find(
        (m: ModelOption) => m.current_model
      );
      if (currentModelOption) {
        setCurrentDisplayName(currentModelOption.display_name);
      } else {
        const currentProviderInfo = providerList.find(
          (p: ProviderInfo) => p.name === data.current_provider
        );
        if (currentProviderInfo && currentProviderInfo.display_name) {
          setCurrentDisplayName(currentProviderInfo.display_name + ' (默认)');
        } else if (data.current_provider) {
          setCurrentDisplayName(data.current_provider);
        } else {
          setCurrentDisplayName('未设置');
        }
      }

      const current =
        providerList.find((p) => p.name === data.current_provider) ||
        (providerList.length > 0 ? providerList[0] : null);
      setSelectedProvider(current);
    } catch (error) {
      handleError('加载配置失败');
      console.error('加载配置失败:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const onSelectProvider = (provider: ProviderInfo) => {
    setSelectedProvider(provider);
  };

  useEffect(() => {
    if (shouldLoad || forceRefresh) {
      loadConfig();
    }
  }, [shouldLoad, forceRefresh, loadConfig]);

  const handleEditProvider = (provider: ProviderInfo) => {
    setEditingProvider(provider);
    form.setFieldsValue({
      api_base: provider.api_base,
      api_key: provider.api_key,
      timeout: provider.timeout,
      max_retries: provider.max_retries,
    });
    setEditProviderModalVisible(true);
  };

  const handleSaveProvider = async (values: Record<string, unknown>) => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      await configApi.updateProvider(
        editingProvider!.name,
        values as Record<string, unknown>
      );

      const data = await configApi.getFullConfig();
      setProviders(Object.values(data.providers));
      const modelData = await configApi.getModelList();
      setModelList(modelData.models);

      setEditProviderModalVisible(false);
      form.resetFields();
      setEditingProvider(null);

      setTimeout(() => {
        showSuccess('Provider配置已更新');
      }, 150);
    } catch (error) {
      console.error('更新Provider失败:', error);
      handleError('更新失败');
    }
  };

  const handleDeleteProvider = async (providerName: string) => {
    try {
      await configApi.deleteProvider(providerName);
      await loadConfig();
      showSuccess('Provider已删除');
    } catch (error) {
      const err = error as { response?: { data?: { detail?: string } } };
      handleError(err?.response?.data?.detail || '删除失败');
    }
  };

  const [editingModel, setEditingModel] = useState<{
    provider: string;
    model: string;
  } | null>(null);
  const [modelEditForm] = Form.useForm();

  const handleEditModel = async (providerName: string, modelName: string) => {
    setEditingModel({ provider: providerName, model: modelName });
    modelEditForm.setFieldsValue({ model: modelName });
    setEditModelModalVisible(true);
  };

  const handleUpdateModel = async (values: { model: string }) => {
    if (!editingModel) return;
    try {
      const cleanModelName = values.model.trim().replace(/\s+/g, ' ');
      await configApi.updateModel(
        editingModel.provider,
        editingModel.model,
        cleanModelName
      );

      const data = await configApi.getFullConfig();
      setProviders(Object.values(data.providers));
      const modelData = await configApi.getModelList();
      setModelList(modelData.models);

      const providerArray = Object.values(data.providers) as ProviderInfo[];
      const updatedProvider = providerArray.find(
        (p) => p.name === editingModel.provider
      );
      if (updatedProvider) {
        setSelectedProvider(updatedProvider);
      }

      showSuccess('模型已更新');
      setEditModelModalVisible(false);
      setEditingModel(null);
      modelEditForm.resetFields();
    } catch (error: unknown) {
      console.error('更新模型失败:', error);
      handleError('更新失败');
    }
  };

  const handleDeleteModel = async (providerName: string, modelName: string) => {
    try {
      await configApi.deleteModel(providerName, modelName);

      const data = await configApi.getFullConfig();
      setProviders(Object.values(data.providers));
      const modelData = await configApi.getModelList();
      setModelList(modelData.models);

      const providerArray = Object.values(data.providers) as ProviderInfo[];
      const updatedProvider = providerArray.find(
        (p) => p.name === providerName
      );
      if (updatedProvider) {
        setSelectedProvider(updatedProvider);
      }
      console.log('删除模型后刷新列表:', modelData.models);

      showSuccess('模型已删除');
    } catch (error: unknown) {
      console.error('删除模型失败:', error);
      handleError('删除失败');
    }
  };

  const handleBatchDeleteModels = async (
    providerName: string,
    models: string[]
  ) => {
    setDeleteProgress({ current: 0, total: models.length });
    setDeleteModalVisible(true);

    const controller = new AbortController();
    deleteControllerRef.current = controller;

    try {
      const deletePromises = models.map(async (modelName, index) => {
        if (controller.signal.aborted) {
          return { success: false, model: modelName, cancelled: true };
        }

        try {
          await configApi.deleteModel(providerName, modelName, {
            signal: controller.signal,
          });
          setDeleteProgress({ current: index + 1, total: models.length });
          return { success: true, model: modelName };
        } catch (error) {
          const err = error as { name?: string };
          if (err?.name === 'AbortError' || controller.signal.aborted) {
            return { success: false, model: modelName, cancelled: true };
          }
          throw error;
        }
      });

      const results = await Promise.all(deletePromises);
      const successCount = results.filter((r) => r.success).length;
      const failCount = results.filter(
        (r) => !r.success && !r.cancelled
      ).length;
      const cancelledCount = results.filter((r) => r.cancelled).length;

      const data = await configApi.getFullConfig();
      setProviders(Object.values(data.providers));
      const modelData = await configApi.getModelList();
      setModelList(modelData.models);

      const providerArray = Object.values(data.providers) as ProviderInfo[];
      const updatedProvider = providerArray.find(
        (p) => p.name === providerName
      );
      if (updatedProvider) {
        setSelectedProvider(updatedProvider);
      }

      setSelectedModels(new Set());

      if (cancelledCount > 0) {
        handleError({
          message: `批量删除已取消：${successCount} 成功，${cancelledCount} 未执行`,
          error_type: ErrorType.WARNING,
        });
      } else if (failCount > 0) {
        handleError({
          message: `批量删除完成：${successCount} 成功，${failCount} 失败`,
          error_type: ErrorType.WARNING,
        });
      } else {
        showSuccess(`成功删除 ${successCount} 个模型`);
      }
    } catch (error) {
      const err = error as { name?: string };
      if (err?.name === 'AbortError') {
        handleError({
          message: '批量删除已取消',
          error_type: ErrorType.WARNING,
        });
      } else {
        handleError('批量删除失败');
      }
    } finally {
      setDeleteProgress({ current: 0, total: 0 });
      setDeleteModalVisible(false);
      deleteControllerRef.current = null;
    }
  };

  const handleAddModel = async (values: { model: string }) => {
    try {
      const cleanModelName = values.model.trim().replace(/\s+/g, ' ');
      const result = await configApi.addModel(selectedProviderForModel, {
        model: cleanModelName,
      });
      console.log('添加模型结果:', result);

      setAddModelModalVisible(false);
      modelForm.resetFields();
      setSelectedProviderForModel('');

      const data = await configApi.getFullConfig();
      setProviders(Object.values(data.providers));
      const modelData = await configApi.getModelList();
      setModelList(modelData.models);

      const providerName = selectedProviderForModel || selectedProvider?.name;
      const providerArray = Object.values(data.providers) as ProviderInfo[];
      const updatedProvider = providerArray.find(
        (p) => p.name === providerName
      );
      if (updatedProvider) {
        setSelectedProvider(updatedProvider);
      }
      console.log('添加模型后刷新列表:', modelData.models);

      showSuccess('模型已添加');
    } catch (error: unknown) {
      console.error('添加模型失败:', error);
      handleError('添加失败');
    }
  };

  const handleAddProvider = async (values: Record<string, unknown>) => {
    try {
      await configApi.addProvider({
        name: values.name as string,
        api_base: values.api_base as string,
        api_key: (values.api_key as string) || '',
        model: (values.model as string) || '',
        models: values.model ? [values.model as string] : [],
        timeout: (values.timeout as number) || 60,
        max_retries: (values.max_retries as number) || 3,
      });

      const data = await configApi.getFullConfig();
      setProviders(Object.values(data.providers));
      const modelData = await configApi.getModelList();
      setModelList(modelData.models);

      setAddProviderModalVisible(false);
      setTimeout(() => {
        providerForm.resetFields();
        showSuccess('Provider已添加');
      }, 100);
    } catch (error) {
      const err = error as { response?: { data?: { detail?: string } } };
      handleError(err?.response?.data?.detail || '添加失败');
    }
  };

  const onDisplayNameChange = async (option: ModelOption) => {
    try {
      setCurrentDisplayName(option.display_name);

      await configApi.updateConfig({
        ai_provider: option.provider,
        ai_model: option.model,
      });

      await loadConfig();

      showSuccess(`已切换到 ${option.display_name}`);
    } catch (error) {
      handleError('切换模型失败');
      console.error('切换模型失败:', error);
    }
  };

  return (
    <div>
      {/* 全局配置区域 - 使用 Row/Col 布局与下方 Provider 配置区域对齐 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={16}>
          <GlobalConfigArea
            modelList={modelList}
            currentDisplayName={currentDisplayName}
            onDisplayNameChange={onDisplayNameChange}
          />
        </Col>
      </Row>
      {/* Provider配置区域 */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        {/* 左侧Provider列表 */}
        <Col xs={24} md={5}>
          <ProviderList
            providers={providers}
            currentProvider={selectedProvider?.name || ''}
            onSelect={onSelectProvider}
            onAdd={() => setAddProviderModalVisible(true)}
            modelList={modelList}
          />
        </Col>

        {/* 右侧Provider详细信息 */}
        <Col xs={24} md={12}>
          {selectedProvider ? (
            <div>
              <Typography.Title level={5} style={{ marginBottom: 24 }}>
                <Space
                  style={{ width: '100%', justifyContent: 'space-between' }}
                >
                  {/* 左侧: 标题内容 */}
                  <Space>
                    配置详情:{' '}
                    {selectedProvider.display_name || selectedProvider.name}
                    {selectedProvider.display_name && (
                      <Tag color="blue">{selectedProvider.name}</Tag>
                    )}
                    {modelList.some(
                      (m) =>
                        m.provider === selectedProvider.name && m.current_model
                    ) && (
                      <Tag icon={<CheckCircleOutlined />} color="success">
                        当前使用
                      </Tag>
                    )}
                  </Space>

                  {/* 右侧: 操作按钮 */}
                  <Space>
                    <Button
                      type="primary"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => handleEditProvider(selectedProvider)}
                    >
                      编辑
                    </Button>
                    <Popconfirm
                      title={`确定删除 ${getProviderDisplayName(
                        selectedProvider.name,
                        providers
                      )} 吗？`}
                      description="删除后无法恢复"
                      onConfirm={() =>
                        handleDeleteProvider(selectedProvider.name)
                      }
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button
                        type="primary"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                      >
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                </Space>
              </Typography.Title>

              <Card size="small">
                {/* Provider基本信息 */}
                <Row gutter={[16, 8]} style={{ marginBottom: 16 }}>
                  <Col span={24}>
                    <Text type="secondary">API地址：</Text>
                    <Text code>{selectedProvider.api_base}</Text>
                  </Col>
                  <Col span={24}>
                    <Space>
                      <Text type="secondary">API密钥：</Text>
                      <Text>
                        {selectedProvider.api_key
                          ? showApiKey[selectedProvider.name]
                            ? selectedProvider.api_key
                            : `******${selectedProvider.api_key.slice(-4)}`
                          : '未设置'}
                      </Text>
                      {selectedProvider.api_key && (
                        <Button
                          type="text"
                          size="small"
                          icon={
                            showApiKey[selectedProvider.name] ? (
                              <EyeInvisibleOutlined />
                            ) : (
                              <EyeOutlined />
                            )
                          }
                          onClick={() =>
                            toggleShowApiKey(selectedProvider.name)
                          }
                        />
                      )}
                    </Space>
                  </Col>
                  <Col span={24}>
                    <Space size="large">
                      <Text type="secondary">超时时间：</Text>
                      <Text>{selectedProvider.timeout || 60} 秒</Text>
                      <Text type="secondary">最大重试：</Text>
                      <Text>{selectedProvider.max_retries || 3} 次</Text>
                    </Space>
                  </Col>
                  <Col span={24}>
                    <Text type="secondary">当前模型：</Text>
                    <Text strong>
                      {modelList.find(
                        (m) =>
                          m.provider === selectedProvider.name &&
                          m.current_model
                      )?.display_name ||
                        selectedProvider.model ||
                        '未设置'}
                    </Text>
                  </Col>
                </Row>

                <Divider style={{ margin: '12px 0' }} />

                {/* 模型列表 */}
                <div style={{ marginBottom: 8 }}>
                  <Space style={{ marginBottom: 8 }}>
                    <Text strong>模型列表：</Text>
                    <Button
                      type="link"
                      size="small"
                      icon={<PlusOutlined />}
                      onClick={() => {
                        setSelectedProviderForModel(selectedProvider.name);
                        setAddModelModalVisible(true);
                      }}
                    >
                      添加模型
                    </Button>
                    {selectedModels.size > 0 && (
                      <Popconfirm
                        title={`确定删除选中的 ${selectedModels.size} 个模型吗？`}
                        onConfirm={() =>
                          handleBatchDeleteModels(
                            selectedProvider.name,
                            Array.from(selectedModels)
                          )
                        }
                        okText="确定"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                      >
                        <Button type="link" danger icon={<DeleteOutlined />}>
                          批量删除 ({selectedModels.size})
                        </Button>
                      </Popconfirm>
                    )}
                  </Space>

                  {/* 模型卡片列表 */}
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}
                  >
                    {selectedProvider.models.map((model) => {
                      const isActive = modelList.some(
                        (m) =>
                          m.provider === selectedProvider.name &&
                          m.model === model &&
                          m.current_model
                      );

                      return (
                        <Card
                          key={model}
                          size="small"
                          style={{
                            cursor: 'pointer',
                            borderLeft: isActive
                              ? '4px solid #1890ff'
                              : '1px solid #d9d9d9',
                            backgroundColor: isActive ? '#e6f7ff' : '#fafafa',
                          }}
                          styles={{ body: { padding: '12px 16px' } }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                            }}
                          >
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                              }}
                            >
                              {isActive && (
                                <CheckCircleOutlined
                                  style={{ color: '#52c41a' }}
                                />
                              )}
                              <Text strong={isActive}>{model}</Text>
                              {isActive && (
                                <Tag color="success" style={{ marginLeft: 4 }}>
                                  当前使用
                                </Tag>
                              )}
                            </div>

                            <Space>
                              {/* 编辑按钮 */}
                              <Button
                                type="text"
                                size="small"
                                icon={<EditOutlined />}
                                onClick={(e) => {
                                  e?.stopPropagation();
                                  handleEditModel(selectedProvider.name, model);
                                }}
                              >
                                编辑
                              </Button>
                              {/* 删除按钮 */}
                              <Popconfirm
                                title={`确定删除模型 ${model} 吗？`}
                                onConfirm={(e) => {
                                  e?.stopPropagation();
                                  handleDeleteModel(
                                    selectedProvider.name,
                                    model
                                  );
                                }}
                                okText="确定"
                                cancelText="取消"
                                okButtonProps={{ danger: true }}
                              >
                                <Button
                                  type="text"
                                  size="small"
                                  icon={<DeleteOutlined />}
                                  danger
                                  onClick={(e) => e?.stopPropagation()}
                                >
                                  删除
                                </Button>
                              </Popconfirm>
                            </Space>
                          </div>
                        </Card>
                      );
                    })}
                  </div>
                </div>
              </Card>
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center' }}>
              <Typography.Title level={5} type="secondary">
                <ApiOutlined /> 暂无选中的Provider
              </Typography.Title>
              <p>请从左侧列表选择Provider，或添加新的Provider</p>
            </div>
          )}
        </Col>
      </Row>

      {/* 批量删除确认弹框 */}
      <Modal
        title="批量删除"
        open={deleteModalVisible}
        onCancel={() => {
          if (deleteControllerRef.current) {
            deleteControllerRef.current.abort();
          }
        }}
        footer={[
          <Button
            key="cancel"
            danger
            onClick={() => {
              if (deleteControllerRef.current) {
                deleteControllerRef.current.abort();
              }
            }}
            disabled={deleteProgress.current >= deleteProgress.total}
          >
            取消
          </Button>,
        ]}
      >
        <p>正在删除 {deleteProgress.total} 个模型，请稍候...</p>
        <div style={{ marginTop: 16 }}>
          <Progress
            percent={
              deleteProgress.total > 0
                ? Math.round(
                    (deleteProgress.current / deleteProgress.total) * 100
                  )
                : 0
            }
            status={
              deleteProgress.current >= deleteProgress.total
                ? 'success'
                : 'active'
            }
          />
          <div style={{ marginTop: 8, color: '#666', fontSize: 12 }}>
            已完成: {deleteProgress.current} / {deleteProgress.total}
          </div>
        </div>
      </Modal>

      {/* 编辑Provider弹框 */}
      <Modal
        title={`编辑 ${getProviderDisplayName(
          editingProvider?.name || '',
          providers
        )} 配置`}
        open={editProviderModalVisible}
        onCancel={() => {
          setEditProviderModalVisible(false);
          form.resetFields();
        }}
        footer={null}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSaveProvider}>
          <Form.Item
            label="API地址"
            name="api_base"
            rules={[{ required: true, message: '请输入API地址' }]}
          >
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>

          <Form.Item label="API密钥" name="api_key">
            <Input.Password placeholder="留空保持原密钥不变" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="超时时间(秒)" name="timeout">
                <Input type="number" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="最大重试次数" name="max_retries">
                <Input type="number" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
              <Button
                onClick={() => {
                  setEditProviderModalVisible(false);
                  form.resetFields();
                }}
              >
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 添加模型弹框 */}
      <Modal
        title="添加模型"
        open={addModelModalVisible}
        onCancel={() => {
          setAddModelModalVisible(false);
          modelForm.resetFields();
        }}
        footer={null}
      >
        <Form form={modelForm} layout="vertical" onFinish={handleAddModel}>
          <Form.Item
            label="模型名称"
            name="model"
            rules={[{ required: true, message: '请输入模型名称' }]}
          >
            <Input placeholder="glm-4-flash" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                添加
              </Button>
              <Button onClick={() => setAddModelModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑模型弹框 */}
      <Modal
        title="编辑模型"
        open={editModelModalVisible}
        onCancel={() => {
          setEditModelModalVisible(false);
          setEditingModel(null);
          modelEditForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={modelEditForm}
          layout="vertical"
          onFinish={handleUpdateModel}
        >
          <Form.Item
            label="模型名称"
            name="model"
            rules={[{ required: true, message: '请输入模型名称' }]}
          >
            <Input placeholder="glm-4-flash" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
              <Button onClick={() => setEditModelModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 添加Provider弹框 */}
      <Modal
        title="添加新Provider"
        open={addProviderModalVisible}
        destroyOnClose
        onCancel={() => {
          setAddProviderModalVisible(false);
          providerForm.resetFields();
        }}
        footer={null}
        width={600}
        maskClosable={false}
      >
        <Form
          form={providerForm}
          layout="vertical"
          onFinish={handleAddProvider}
        >
          <Form.Item
            label="Provider名称"
            name="name"
            rules={[{ required: true, message: '请输入Provider名称' }]}
          >
            <Input placeholder="例如: zhipuai, opencode, longcat" />
          </Form.Item>

          <Form.Item
            label="API地址"
            name="api_base"
            rules={[{ required: true, message: '请输入API地址' }]}
          >
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>

          <Form.Item label="API密钥" name="api_key">
            <Input.Password placeholder="可选" />
          </Form.Item>

          <Form.Item label="默认模型" name="model">
            <Input placeholder="glm-4-flash" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="超时时间(秒)" name="timeout" initialValue={60}>
                <Input type="number" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="最大重试次数"
                name="max_retries"
                initialValue={3}
              >
                <Input type="number" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                添加
              </Button>
              <Button onClick={() => setAddProviderModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
