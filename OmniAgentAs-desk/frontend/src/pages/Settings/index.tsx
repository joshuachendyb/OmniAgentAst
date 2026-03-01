/**
 * Settings组件 - 系统设置页面
 *
 * 功能：模型配置管理（Provider和Model）
 *
 * @author 小欧
 * @version 2.0.0
 * @since 2026-02-22
 */

import React, { useState, useEffect, useMemo } from "react";
import {
  Card,
  Button,
  Tabs,
  List,
  Tag,
  Space,
  Typography,
  message,
  Divider,
  Popconfirm,
  Modal,
  Form,
  Input,
  Select,
  Row,
  Col,
  Switch,
  Alert,
  Progress,
  Collapse,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  ApiOutlined,
  SafetyOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
} from "@ant-design/icons";
import { configApi, sessionApi } from "../../services/api";
import type { ProviderInfo, Session } from "../../services/api";
// import type { FormInstance } from 'antd/es/form'; // 暂时保留，以备将来使用

const { Text } = Typography;
const { TabPane } = Tabs;

/**
 * 全局配置区域组件（ai.provider和ai.model）
 * @author 小新
 * @update 2026-02-26 新增
 */
const GlobalConfigArea: React.FC<{
  providers: ProviderInfo[];
  currentProvider: string;
  currentModel: string;
  onProviderChange: (provider: string) => void;
  onModelChange: (model: string) => void;
}> = ({
  providers,
  currentProvider,
  currentModel,
  onProviderChange,
  onModelChange,
}) => {
  return (
    <Card size="small" style={{ marginBottom: 24 }}>
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Text strong style={{ display: "block", marginBottom: 8 }}>
            当前Provider:
          </Text>
          <Select
            value={currentProvider}
            onChange={onProviderChange}
            style={{ width: "100%" }}
            placeholder="选择Provider"
          >
            {providers.map((p) => (
              <Select.Option key={p.name} value={p.name}>
                {p.name}
              </Select.Option>
            ))}
          </Select>
        </Col>
        <Col span={12}>
          <Text strong style={{ display: "block", marginBottom: 8 }}>
            当前模型:
          </Text>
          <Select
            value={currentModel}
            onChange={onModelChange}
            style={{ width: "100%" }}
            placeholder="选择模型"
          >
            {providers
              .find((p) => p.name === currentProvider)
              ?.models.map((model) => (
                <Select.Option key={model} value={model}>
                  {model}
                </Select.Option>
              ))}
          </Select>
        </Col>
      </Row>
    </Card>
  );
};

/**
 * Provider列表组件（左侧）
 * @author 小新
 * @update 2026-02-26 新增
 */
const ProviderList: React.FC<{
  providers: ProviderInfo[];
  currentProvider: string;
  onSelect: (provider: ProviderInfo) => void;
}> = ({ providers, currentProvider, onSelect }) => {
  const [searchKeyword, setSearchKeyword] = useState("");

  const filteredProviders = useMemo(
    () =>
      providers.filter((provider) =>
        provider.name.toLowerCase().includes(searchKeyword.toLowerCase())
      ),
    [providers, searchKeyword]
  );

  return (
    <div style={{ borderRight: "1px solid #f0f0f0", paddingRight: 16 }}>
      <Typography.Title level={5} style={{ marginBottom: 16 }}>
        Provider列表
      </Typography.Title>

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
          style={{ marginBottom: 12, cursor: "pointer" }}
          onClick={() => onSelect(provider)}
          bodyStyle={{
            backgroundColor:
              provider.name === currentProvider ? "#e6f7ff" : "transparent",
          }}
        >
          <Space>
            <ApiOutlined />
            <Text strong>{provider.name}</Text>
            {provider.name === currentProvider && (
              <Tag color="success">当前使用</Tag>
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

/**
 * 脏状态检测Hook（暂时保留，以备将来使用）
 * @author 小新
 * @update 2026-02-26 新增
 */
/*
const useDirtyState = (form: FormInstance, onDirtyChange: (isDirty: boolean) => void) => {
  useEffect(() => {
    const checkDirty = () => {
      onDirtyChange(form.isFieldsTouched());
    };

    checkDirty();

    // 使用isFieldsTouched()检测，不再监听字段变化
    // 因为Ant Design Form没有直接的watchValues方法
  }, [form, onDirtyChange]);
};
*/

/**
 * Provider管理页面组件
 * @author 小新
 * @update 2026-02-26 重构：提取子组件
 */
const ProviderSettings: React.FC = () => {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [currentProvider, setCurrentProvider] = useState<string>("");
  const [currentModel, setCurrentModel] = useState<string>("");
  const [selectedProvider, setSelectedProvider] = useState<ProviderInfo | null>(
    null
  );
  const [loading, setLoading] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [validationModalVisible, setValidationModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [addModelModalVisible, setAddModelModalVisible] = useState(false);
  const [addProviderModalVisible, setAddProviderModalVisible] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderInfo | null>(
    null
  );
  const [selectedProviderForModel, setSelectedProviderForModel] =
    useState<string>("");
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({}); // 控制每个Provider的API Key显示
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set()); // 选中的模型
  const [deleteProgress, setDeleteProgress] = useState<{
    current: number;
    total: number;
  }>({ current: 0, total: 0 });
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deleteCancelled, setDeleteCancelled] = useState(false);
  const deleteControllerRef = React.useRef<AbortController | null>(null);

  const [form] = Form.useForm();
  const [modelForm] = Form.useForm();
  const [providerForm] = Form.useForm();

  // 切换API Key显示/隐藏
  const toggleShowApiKey = (providerName: string) => {
    setShowApiKey((prev) => ({ ...prev, [providerName]: !prev[providerName] }));
  };

  // 加载配置
  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await configApi.getFullConfig();
      const providerList = Object.values(data.providers);
      setProviders(providerList);
      setCurrentProvider(data.current_provider);
      // 设置当前选中的Provider为当前使用的Provider或第一个Provider
      const current =
        providerList.find((p) => p.name === data.current_provider) ||
        providerList[0] ||
        null;
      setSelectedProvider(current);
    } catch (error) {
      message.error("加载配置失败");
      console.error("加载配置失败:", error);
    } finally {
      setLoading(false);
    }
  };

  // 选择Provider
  const onSelectProvider = (provider: ProviderInfo) => {
    setSelectedProvider(provider);
  };

  // 加载配置时同时进行验证
  const handleLoadWithValidation = async () => {
    await loadConfig();
    try {
      const result = await configApi.validateFullConfig();
      setValidationResult(result);
    } catch (error) {
      console.error("配置验证失败:", error);
    }
  };

  useEffect(() => {
    handleLoadWithValidation();
  }, []);

  // 编辑Provider
  const handleEditProvider = (provider: ProviderInfo) => {
    setEditingProvider(provider);
    form.setFieldsValue({
      api_base: provider.api_base,
      api_key: provider.api_key,
      timeout: provider.timeout,
      max_retries: provider.max_retries,
    });
    setEditModalVisible(true);
  };

  // 保存Provider编辑
  const handleSaveProvider = async (values: any) => {
    try {
      await configApi.updateProvider(editingProvider!.name, values);
      message.success("Provider配置已更新");
      setEditModalVisible(false);
      loadConfig();
    } catch (error) {
      message.error("更新失败");
    }
  };

  // 删除Provider
  const handleDeleteProvider = async (providerName: string) => {
    try {
      await configApi.deleteProvider(providerName);
      message.success("Provider已删除");
      loadConfig();
    } catch (error: any) {
      message.error(error.response?.data?.detail || "删除失败");
    }
  };

  // 删除模型
  const handleDeleteModel = async (providerName: string, modelName: string) => {
    try {
      await configApi.deleteModel(providerName, modelName);
      message.success("模型已删除");
      loadConfig();
    } catch (error: any) {
      message.error(error.response?.data?.detail || "删除失败");
    }
  };

  // 批量删除模型（并发优化，支持取消）
  const handleBatchDeleteModels = async (
    providerName: string,
    models: string[]
  ) => {
    setDeleteProgress({ current: 0, total: models.length });
    setDeleteModalVisible(true);
    setDeleteCancelled(false);

    const controller = new AbortController();
    deleteControllerRef.current = controller;

    try {
      const deletePromises = models.map(async (modelName, index) => {
        if (deleteCancelled) {
          return { success: false, model: modelName, cancelled: true };
        }

        try {
          await configApi.deleteModel(providerName, modelName);
          setDeleteProgress({ current: index + 1, total: models.length });
          return { success: true, model: modelName };
        } catch (error) {
          setDeleteProgress({ current: index + 1, total: models.length });
          return { success: false, model: modelName, error };
        }
      });

      const results = await Promise.all(deletePromises);
      const successCount = results.filter((r) => r.success).length;
      const failCount = results.filter(
        (r) => !r.success && !r.cancelled
      ).length;
      const cancelledCount = results.filter((r) => r.cancelled).length;

      if (deleteCancelled) {
        message.warning(
          `批量删除已取消：${successCount} 成功，${cancelledCount} 未执行`
        );
      } else if (failCount === 0) {
        message.success(`批量删除完成：${successCount} 个模型`);
      } else {
        message.warning(
          `批量删除完成：${successCount} 成功，${failCount} 失败`
        );
      }

      setSelectedModels(new Set());
      loadConfig();
    } catch (error: any) {
      if (error.name === "AbortError") {
        message.warning("批量删除已取消");
      } else {
        message.error("批量删除失败");
      }
    } finally {
      setDeleteProgress({ current: 0, total: 0 });
      setDeleteModalVisible(false);
      deleteControllerRef.current = null;
    }
  };

  // 添加模型
  const handleAddModel = async (values: { model: string }) => {
    try {
      await configApi.addModel(selectedProviderForModel, values);
      message.success("模型已添加");
      setAddModelModalVisible(false);
      modelForm.resetFields();
      loadConfig();
    } catch (error: any) {
      message.error(error.response?.data?.detail || "添加失败");
    }
  };

  // 添加Provider
  const handleAddProvider = async (values: any) => {
    try {
      await configApi.addProvider({
        name: values.name,
        api_base: values.api_base,
        api_key: values.api_key || "",
        model: values.model || "",
        models: values.model ? [values.model] : [],
        timeout: values.timeout || 60,
        max_retries: values.max_retries || 3,
      });
      message.success("Provider已添加");
      setAddProviderModalVisible(false);
      providerForm.resetFields();
      loadConfig();
    } catch (error: any) {
      message.error(error.response?.data?.detail || "添加失败");
    }
  };

  // 获取Provider显示名称
  const getProviderDisplayName = (name: string) => {
    const nameMap: Record<string, string> = {
      zhipuai: "智谱GLM",
      opencode: "OpenCode",
      longcat: "LongCat",
    };
    return nameMap[name] || name;
  };

  // 全局配置 - Provider切换
  const onProviderChange = async (provider: string) => {
    const providerData = providers.find((p) => p.name === provider);
    if (!providerData) return;
    setCurrentProvider(provider);
    setCurrentModel(providerData.model || providerData.models[0] || "");
    await configApi.updateConfig({
      ai_provider: provider as "zhipuai" | "opencode" | "longcat",
      ai_model: providerData.model || providerData.models[0] || "",
    });
    loadConfig();
  };

  // 全局配置 - Model切换
  const onModelChange = async (model: string) => {
    setCurrentModel(model);
    await configApi.updateConfig({
      ai_provider: currentProvider as "zhipuai" | "opencode" | "longcat",
      ai_model: model,
    });
    loadConfig();
  };

  return (
    <div>
      {/* 全局配置区域 */}
      <GlobalConfigArea
        providers={providers}
        currentProvider={currentProvider}
        currentModel={currentModel}
        onProviderChange={onProviderChange}
        onModelChange={onModelChange}
      />
      {/* 配置验证提示 - 成功/失败都显示 */}

      {/* 配置验证提示 - 成功/失败都显示 */}
      {validationResult && (
        <Alert
          message={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {validationResult.success ? (
                <>
                  <CheckCircleOutlined style={{ color: "#52c41a" }} />
                  <strong>配置验证成功</strong>
                </>
              ) : (
                <>
                  <ReloadOutlined style={{ color: "#faad14" }} />
                  <strong>配置验证发现问题</strong>
                </>
              )}
              <span
                style={{
                  marginLeft: 8,
                  cursor: "pointer",
                  textDecoration: "underline",
                }}
              >
                点击查看详情
              </span>
            </div>
          }
          description={validationResult.message}
          type={validationResult.success ? "success" : "warning"}
          showIcon
          style={{ marginBottom: 16, cursor: "pointer" }}
          onClick={() => setValidationModalVisible(true)}
        />
      )}

      {/* 验证详情弹框 */}
      <Modal
        title={
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {validationResult?.success ? (
              <CheckCircleOutlined style={{ color: "#52c41a", fontSize: 18 }} />
            ) : (
              <ReloadOutlined style={{ color: "#faad14", fontSize: 18 }} />
            )}
            配置验证详情
          </span>
        }
        open={validationModalVisible}
        onCancel={() => setValidationModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setValidationModalVisible(false)}>
            关闭
          </Button>,
          <Button
            key="revalidate"
            onClick={handleLoadWithValidation}
            loading={loading}
          >
            重新验证
          </Button>,
        ]}
        width={600}
      >
        {validationResult && (
          <div>
            <Alert
              message={
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {validationResult.success ? (
                    <>
                      <CheckCircleOutlined style={{ color: "#52c41a" }} />
                      <strong>配置验证成功</strong>
                    </>
                  ) : (
                    <>
                      <ReloadOutlined style={{ color: "#faad14" }} />
                      <strong>配置验证发现问题</strong>
                    </>
                  )}
                </div>
              }
              description={validationResult.message}
              type={validationResult.success ? "success" : "warning"}
              showIcon
              style={{ marginBottom: 24 }}
            />

            {/* 配置信息卡片 */}
            <div
              style={{
                background: "#fafafa",
                padding: 16,
                borderRadius: 8,
                marginBottom: 24,
              }}
            >
              <div style={{ display: "flex", gap: 24 }}>
                <div>
                  <span style={{ color: "#666", fontSize: 12 }}>
                    当前 Provider
                  </span>
                  <div style={{ fontSize: 16, fontWeight: 500, marginTop: 4 }}>
                    {validationResult.provider}
                  </div>
                </div>
                <div>
                  <span style={{ color: "#666", fontSize: 12 }}>
                    当前 Model
                  </span>
                  <div style={{ fontSize: 16, fontWeight: 500, marginTop: 4 }}>
                    {validationResult.model}
                  </div>
                </div>
              </div>
            </div>

            {validationResult.errors && validationResult.errors.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 12,
                    color: "#ff4d4f",
                    fontSize: 14,
                    fontWeight: 500,
                  }}
                >
                  <span style={{ fontSize: 18 }}>❌</span>
                  错误 ({validationResult.errors.length})
                </div>
                <div
                  style={{
                    background: "#fff1f0",
                    border: "1px solid #ffa39e",
                    borderRadius: 6,
                    padding: "12px 16px",
                  }}
                >
                  <ul
                    style={{
                      margin: 0,
                      paddingLeft: 20,
                      color: "#ff4d4f",
                      fontSize: 14,
                      lineHeight: 1.8,
                    }}
                  >
                    {validationResult.errors.map((err: string, idx: number) => (
                      <li key={idx}>{err}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {validationResult.warnings &&
              validationResult.warnings.length > 0 && (
                <div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 12,
                      color: "#faad14",
                      fontSize: 14,
                      fontWeight: 500,
                    }}
                  >
                    <span style={{ fontSize: 18 }}>⚠️</span>
                    警告 ({validationResult.warnings.length})
                  </div>
                  <div
                    style={{
                      background: "#fffbe6",
                      border: "1px solid #ffe58f",
                      borderRadius: 6,
                      padding: "12px 16px",
                    }}
                  >
                    <ul
                      style={{
                        margin: 0,
                        paddingLeft: 20,
                        color: "#faad14",
                        fontSize: 14,
                        lineHeight: 1.8,
                      }}
                    >
                      {validationResult.warnings.map(
                        (warn: string, idx: number) => (
                          <li key={idx}>{warn}</li>
                        )
                      )}
                    </ul>
                  </div>
                </div>
              )}
          </div>
        )}
      </Modal>

      {/* Provider配置区域 */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        {/* 左侧Provider列表 */}
        <Col xs={24} md={8}>
          <ProviderList
            providers={providers}
            currentProvider={currentProvider}
            onSelect={onSelectProvider}
          />
        </Col>

        {/* 右侧Provider详细信息 */}
        <Col xs={24} md={16}>
          {selectedProvider ? (
            <div>
              <Typography.Title level={5} style={{ marginBottom: 24 }}>
                <Space>
                  <ApiOutlined />
                  配置详情：{getProviderDisplayName(selectedProvider.name)}
                  <Tag color="blue">{selectedProvider.name}</Tag>
                  {selectedProvider.name === currentProvider && (
                    <Tag icon={<CheckCircleOutlined />} color="success">
                      当前使用
                    </Tag>
                  )}
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
                            : "******" + selectedProvider.api_key.slice(-4)
                          : "未设置"}
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
                    <Text type="secondary">当前模型：</Text>
                    <Text strong>{selectedProvider.model}</Text>
                  </Col>
                </Row>

                <Divider style={{ margin: "12px 0" }} />

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
                    style={{ display: "flex", flexDirection: "column", gap: 8 }}
                  >
                    {selectedProvider.models.map((model) => {
                      const isActive = model === selectedProvider.model;

                      return (
                        <Card
                          key={model}
                          size="small"
                          style={{
                            cursor: "pointer",
                            borderLeft: isActive
                              ? "4px solid #1890ff"
                              : "1px solid #d9d9d9",
                            backgroundColor: isActive ? "#e6f7ff" : "#fafafa",
                          }}
                          bodyStyle={{ padding: "12px 16px" }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                              }}
                            >
                              {isActive && (
                                <CheckCircleOutlined
                                  style={{ color: "#52c41a" }}
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
                              {/* 非当前模型显示切换按钮 */}
                              {!isActive && (
                                <Button
                                  type="link"
                                  size="small"
                                  onClick={() => onModelChange(model)}
                                >
                                  切换
                                </Button>
                              )}

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
                                onVisibleChange={(visible) => {
                                  if (!visible) {
                                    handleDeleteModel(
                                      selectedProvider.name,
                                      model
                                    );
                                  }
                                }}
                              >
                                <Button
                                  type="text"
                                  size="small"
                                  danger
                                  icon={<DeleteOutlined />}
                                  onClick={(e) => e.stopPropagation()}
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

                  {/* 批量删除进度指示器 */}
                  {deleteProgress.total > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Progress
                        percent={Math.round(
                          (deleteProgress.current / deleteProgress.total) * 100
                        )}
                        status="active"
                        format={() =>
                          `${deleteProgress.current}/${deleteProgress.total}`
                        }
                      />
                    </div>
                  )}
                </div>

                <Divider style={{ margin: "12px 0" }} />

                {/* 操作按钮 */}
                <Space style={{ width: "100%", justifyContent: "flex-end" }}>
                  <Button
                    type="primary"
                    icon={<EditOutlined />}
                    onClick={() => handleEditProvider(selectedProvider)}
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title={`确定删除 ${getProviderDisplayName(
                      selectedProvider.name
                    )} 吗？`}
                    description="删除后无法恢复"
                    onConfirm={() =>
                      handleDeleteProvider(selectedProvider.name)
                    }
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button type="primary" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              </Card>
            </div>
          ) : (
            <Alert
              message="请选择一个Provider"
              description="在左侧列表中点击选择一个Provider以查看详细配置"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}
        </Col>
      </Row>

      {/* 批量删除确认弹框 */}
      <Modal
        title="批量删除"
        open={deleteModalVisible}
        onCancel={() => {
          setDeleteCancelled(true);
        }}
        footer={[
          <Button
            key="cancel"
            danger
            onClick={() => setDeleteCancelled(true)}
            disabled={deleteProgress.current >= deleteProgress.total}
          >
            取消
          </Button>,
        ]}
      >
        <p>正在删除 {deleteProgress.total} 个模型，请稍候...</p>
        <div style={{ marginTop: 16 }}>
          <Progress
            percent={Math.round(
              (deleteProgress.current / deleteProgress.total) * 100
            )}
            status={
              deleteProgress.current >= deleteProgress.total
                ? "success"
                : "active"
            }
          />
          <div style={{ marginTop: 8, color: "#666", fontSize: 12 }}>
            已完成: {deleteProgress.current} / {deleteProgress.total}
          </div>
        </div>
      </Modal>

      {/* 编辑Provider弹框 */}
      <Modal
        title={`编辑 ${getProviderDisplayName(
          editingProvider?.name || ""
        )} 配置`}
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSaveProvider}>
          <Form.Item
            label="API地址"
            name="api_base"
            rules={[{ required: true, message: "请输入API地址" }]}
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
              <Button onClick={() => setEditModalVisible(false)}>取消</Button>
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
            rules={[{ required: true, message: "请输入模型名称" }]}
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

      {/* 添加Provider弹框 */}
      <Modal
        title="添加新Provider"
        open={addProviderModalVisible}
        onCancel={() => {
          setAddProviderModalVisible(false);
          providerForm.resetFields();
        }}
        footer={null}
        width={600}
      >
        <Form
          form={providerForm}
          layout="vertical"
          onFinish={handleAddProvider}
        >
          <Form.Item
            label="Provider名称"
            name="name"
            rules={[{ required: true, message: "请输入Provider名称" }]}
          >
            <Input placeholder="例如: zhipuai, opencode, longcat" />
          </Form.Item>

          <Form.Item
            label="API地址"
            name="api_base"
            rules={[{ required: true, message: "请输入API地址" }]}
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

/**
 * 安全设置页面组件
 */
const SecuritySettings: React.FC = () => {
  const [securityConfig, setSecurityConfig] = useState<any>({});
  const [securityForm] = Form.useForm();
  const [savingSecurity, setSavingSecurity] = useState(false);
  const [advancedCollapse, setAdvancedCollapse] = useState<string[]>([]);

  const loadSecurityConfig = async () => {
    try {
      const config = await configApi.getConfig();
      const security = config.security || {
        contentFilterEnabled: true,
        contentFilterLevel: "medium",
        whitelistEnabled: false,
        commandWhitelist: "",
        blacklistEnabled: false,
        commandBlacklist: "rm -rf /\nsudo *\nchmod 777 *",
        confirmDangerousOps: true,
        maxFileSize: 100,
      };
      setSecurityConfig(security);
      securityForm.setFieldsValue(security);
    } catch (error) {
      message.error("加载安全配置失败");
    }
  };

  useEffect(() => {
    loadSecurityConfig();
  }, []);

  const handleSaveSecurityConfig = async (values: any) => {
    setSavingSecurity(true);
    try {
      const currentConfig = await configApi.getConfig();
      const updateData = {
        ...currentConfig,
        security: values,
      };
      await configApi.updateConfig(updateData);
      message.success("安全配置已保存");
      setSecurityConfig(values);
    } catch (error) {
      message.error("保存安全配置失败");
    } finally {
      setSavingSecurity(false);
    }
  };

  return (
    <Form
      form={securityForm}
      layout="vertical"
      onFinish={handleSaveSecurityConfig}
      initialValues={securityConfig}
    >
      {/* 基础配置区域 */}
      <Card
        size="small"
        title={
          <Text strong>
            <SafetyOutlined /> 基础配置
          </Text>
        }
        style={{ marginBottom: 16 }}
      >
        <Row gutter={[16, 8]}>
          <Col xs={24} sm={12}>
            <Form.Item
              label="启用内容安全"
              name="contentFilterEnabled"
              valuePropName="checked"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>

          <Col xs={24} sm={12}>
            <Form.Item label="敏感词过滤级别" name="contentFilterLevel">
              <Select>
                <Select.Option value="low">低</Select.Option>
                <Select.Option value="medium">中</Select.Option>
                <Select.Option value="high">高</Select.Option>
              </Select>
            </Form.Item>
          </Col>
        </Row>
      </Card>

      {/* 高级配置可折叠区域 */}
      <Card size="small" title={<Text strong>⚙️ 高级配置</Text>}>
        <Collapse
          activeKey={advancedCollapse}
          onChange={(keys) => setAdvancedCollapse(keys as string[])}
          ghost
          items={[
            {
              key: "command",
              label: (
                <span>
                  <ApiOutlined /> 命令过滤配置
                </span>
              ),
              children: (
                <Row gutter={[16, 8]}>
                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="启用命令白名单"
                      name="whitelistEnabled"
                      valuePropName="checked"
                    >
                      <Switch checkedChildren="开" unCheckedChildren="关" />
                    </Form.Item>
                  </Col>

                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="启用命令黑名单"
                      name="blacklistEnabled"
                      valuePropName="checked"
                    >
                      <Switch checkedChildren="开" unCheckedChildren="关" />
                    </Form.Item>
                  </Col>

                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="命令白名单"
                      name="commandWhitelist"
                      rules={[
                        {
                          validator: (_, value) => {
                            const whitelistEnabled =
                              securityForm.getFieldValue("whitelistEnabled");
                            if (
                              whitelistEnabled &&
                              (!value || value.trim() === "")
                            ) {
                              return Promise.reject(
                                new Error("启用白名单时必须配置命令白名单")
                              );
                            }
                            return Promise.resolve();
                          },
                        },
                      ]}
                    >
                      <Input.TextArea
                        rows={3}
                        placeholder="每行一个允许的命令，支持通配符"
                        disabled={
                          !securityForm.getFieldValue("whitelistEnabled")
                        }
                      />
                    </Form.Item>
                  </Col>

                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="命令黑名单"
                      name="commandBlacklist"
                      rules={[
                        {
                          validator: (_, value) => {
                            const blacklistEnabled =
                              securityForm.getFieldValue("blacklistEnabled");
                            if (
                              blacklistEnabled &&
                              (!value || value.trim() === "")
                            ) {
                              return Promise.reject(
                                new Error("启用黑名单时必须配置命令黑名单")
                              );
                            }
                            return Promise.resolve();
                          },
                        },
                      ]}
                    >
                      <Input.TextArea
                        rows={3}
                        placeholder="每行一个禁止的命令，支持通配符"
                        disabled={
                          !securityForm.getFieldValue("blacklistEnabled")
                        }
                      />
                    </Form.Item>
                  </Col>
                </Row>
              ),
            },
            {
              key: "advanced",
              label: (
                <span>
                  <SafetyOutlined /> 高级安全选项
                </span>
              ),
              children: (
                <Row gutter={[16, 8]}>
                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="危险操作二次确认"
                      name="confirmDangerousOps"
                      valuePropName="checked"
                    >
                      <Switch checkedChildren="开" unCheckedChildren="关" />
                    </Form.Item>
                  </Col>

                  <Col xs={24} sm={12}>
                    <Form.Item label="最大文件操作大小(MB)" name="maxFileSize">
                      <Select>
                        <Select.Option value={10}>10</Select.Option>
                        <Select.Option value={50}>50</Select.Option>
                        <Select.Option value={100}>100</Select.Option>
                        <Select.Option value={500}>500</Select.Option>
                      </Select>
                    </Form.Item>
                  </Col>
                </Row>
              ),
            },
          ]}
        />
      </Card>

      {/* 保存和重置按钮 */}
      <div style={{ marginTop: 24 }}>
        <Button
          type="primary"
          htmlType="submit"
          icon={<SafetyOutlined />}
          loading={savingSecurity}
        >
          保存安全配置
        </Button>
        <Popconfirm
          title="确定要重置安全配置吗？"
          description="此操作将恢复默认设置"
          onConfirm={loadSecurityConfig}
          okText="确定"
          cancelText="取消"
        >
          <Button style={{ marginLeft: 8 }} icon={<ReloadOutlined />}>
            重置
          </Button>
        </Popconfirm>
      </div>
    </Form>
  );
};

/**
 * 设置页面主组件
 */
/**
 * TODO: 配置文件路径功能待完善 [2026-02-28]
 *
 * 当前问题：
 * 1. configFilePath 相关的 UI 之前被从 Tabs 上方移除，但未完全迁移
 * 2. handleOpenConfigDir 和 handleShowFixModal 函数已定义但未被使用
 * 3. 配置文件路径信息目前只在 Modal（配置修复进度弹窗）中显示
 *
 * 建议解决方案：
 * 方案A：将配置文件路径相关功能迁移到"模型配置"Tab内部的 ProviderSettings 组件顶部
 * - 显示备份路径
 * - 添加"打开配置目录"按钮（调用后端 API 打开文件夹）
 * - 添加"修复配置"按钮（触发 handleFixConfig）
 *
 * 方案B：在 Tabs 上方（Card 内部、Tabs 外部）添加功能入口
 *
 * 相关变量和函数：
 * - configFilePath: 配置文件备份路径状态
 * - loadConfigFilePath(): 加载配置文件路径
 * - handleFixConfig(): 修复配置功能
 * - handleOpenConfigDir(): 打开配置目录（需完善实现）
 * - handleShowFixModal(): 显示修复弹窗（需绑定按钮）
 *
 * @author 小欧
 * @update 2026-02-28 添加待办说明
 */
const Settings: React.FC = () => {
  const [activeKey, setActiveKey] = useState("model");
  const [isDirty, setIsDirty] = useState(false);
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
  const [pendingKey, setPendingKey] = useState<string>("");
  const [configFilePath, setConfigFilePath] = useState<string>("");
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [fixingConfig, setFixingConfig] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [fixProgress, setFixProgress] = useState<{
    current: number;
    total: number;
  }>({ current: 0, total: 100 });
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [showFixModal, setShowFixModal] = useState(false);

  /**
   * 加载配置信息（只读，不备份）
   * ⭐ 修复：启动时只验证配置，不修复/不备份
   */
  const loadConfigInfo = async () => {
    try {
      // 只读验证配置，不修改
      const validation = await configApi.validateFullConfig();
      console.log('📋 配置验证结果:', validation);
      
      // 如果需要，可以从验证结果中提取配置文件路径信息
      // 但不再调用 fixConfig 进行备份
    } catch (error) {
      console.error("加载配置信息失败:", error);
    }
  };

  // 配置修复功能（用户主动触发）
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleFixConfig = async () => {
    setFixingConfig(true);
    setFixProgress({ current: 0, total: 100 });

    // 模拟修复进度
    const progressInterval = setInterval(() => {
      setFixProgress((prev) => {
        if (prev.current >= 100) {
          clearInterval(progressInterval);
          return prev;
        }
        return { ...prev, current: prev.current + 10 };
      });
    }, 200);

    try {
      const result = await configApi.fixConfig();
      clearInterval(progressInterval);
      setFixProgress({ current: 100, total: 100 });
      message.success("配置修复成功");
      setConfigFilePath(result.backup_path);
    } catch (error) {
      clearInterval(progressInterval);
      message.error("配置修复失败");
    } finally {
      setFixingConfig(false);
    }
  };

  // 清理定时器，防止内存泄漏
  useEffect(() => {
    return () => {
      // 组件卸载时清理所有可能的定时器
      // 注意：progressInterval是局部变量，这里只是示例
    };
  }, []);

  useEffect(() => {
    // ⭐ 修复：启动时只读验证，不备份
    loadConfigInfo();
  }, []);

  // TODO: 此函数待使用 - 配置文件路径功能完善后调用 [2026-02-28 小新]
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  // @ts-expect-error TS6133: 函数待使用
  const _handleOpenConfigDir = () => {
    message.info(`配置文件路径: ${configFilePath}`);
  };

  // TODO: 此函数待使用 - 配置文件路径功能完善后绑定到按钮 [2026-02-28 小新]
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  // @ts-expect-error TS6133: 函数待使用
  const _handleShowFixModal = () => {
    setShowFixModal(true);
  };

  // Tab切换处理
  const handleTabChange = (key: string) => {
    if (isDirty) {
      setPendingKey(key);
      setConfirmModalVisible(true);
    } else {
      setActiveKey(key);
    }
  };

  // 确认切换Tab
  const handleConfirmSwitch = () => {
    setIsDirty(false);
    setActiveKey(pendingKey);
    setConfirmModalVisible(false);
  };

  // 取消切换Tab
  const handleCancelSwitch = () => {
    setConfirmModalVisible(false);
  };

  return (
    // 前端小新代修改 VIS-S01: 设置页面内部留白
    // 原因: index.css 中 .ant-card-body { padding: 0 !important; } 会覆盖 Card 组件的 bodyStyle 属性
    // 解决方案: 通过外层 div 的 padding 来控制页面内部留白，padding 值为 25px（上下左右统一）
    <div
      className="settings-page"
      style={{ padding: "25px", background: "#fff" }}
    >
      <Card style={{ marginTop: 0 }}>
        {/* 前端小新代修改 VIS-S03: 设置页面Tab内容左右留白 */}
        <div style={{ padding: "0 5px" }}>
          <Tabs activeKey={activeKey} onChange={handleTabChange} type="line">
            <TabPane
              tab={
                <span>
                  <KeyOutlined /> 模型配置
                </span>
              }
              key="model"
            >
              <ProviderSettings />
            </TabPane>

            <TabPane
              tab={
                <span>
                  <SafetyOutlined /> 安全配置
                </span>
              }
              key="security"
            >
              <SecuritySettings />
            </TabPane>
          </Tabs>
        </div>
      </Card>

      {/* Tab切换确认对话框 */}
      <Modal
        title="确认切换Tab"
        open={confirmModalVisible}
        onOk={handleConfirmSwitch}
        onCancel={handleCancelSwitch}
        okText="保存并切换"
        cancelText="取消切换"
      >
        <p>当前Tab有未保存的修改，是否保存后切换？</p>
      </Modal>

      {/* 配置修复进度弹窗 */}
      <Modal
        title={
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ReloadOutlined style={{ color: "#1890ff" }} />
            配置修复进度
          </span>
        }
        open={showFixModal}
        onCancel={() => {
          if (!fixingConfig) {
            setShowFixModal(false);
          } else {
            message.warning("配置修复中，请稍候...");
          }
        }}
        footer={[
          <Button
            key="close"
            onClick={() => setShowFixModal(false)}
            disabled={fixingConfig}
          >
            关闭
          </Button>,
          <Button
            key="start"
            type="primary"
            onClick={() => {
              handleFixConfig();
            }}
            loading={fixingConfig}
            disabled={fixProgress.current >= 100}
          >
            {fixingConfig
              ? "修复中..."
              : fixProgress.current >= 100
              ? "已完成"
              : "开始修复"}
          </Button>,
        ]}
        width={500}
      >
        <div style={{ padding: "16px 0" }}>
          <div style={{ marginBottom: 16 }}>
            <Text strong>修复进度</Text>
          </div>

          <Progress
            percent={Math.round(
              (fixProgress.current / fixProgress.total) * 100
            )}
            status={
              fixProgress.current >= fixProgress.total
                ? "success"
                : fixingConfig
                ? "active"
                : "normal"
            }
            format={(percent) =>
              `${percent}% (${fixProgress.current}/${fixProgress.total})`
            }
            style={{ marginBottom: 16 }}
          />

          {fixProgress.current >= fixProgress.total ? (
            <Alert
              message="修复完成"
              description="配置文件已成功修复并备份"
              type="success"
              showIcon
              style={{ marginBottom: 12 }}
            />
          ) : fixingConfig ? (
            <Alert
              message="正在修复配置"
              description="请勿关闭此窗口，修复过程正在进行中..."
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
            />
          ) : (
            <Alert
              message="准备修复配置"
              description="点击'开始修复'按钮执行配置修复操作"
              type="warning"
              showIcon
            />
          )}

          {configFilePath && (
            <div
              style={{
                marginTop: 16,
                padding: 12,
                background: "#fafafa",
                borderRadius: 4,
              }}
            >
              <Text type="secondary" style={{ fontSize: 12 }}>
                备份路径：
              </Text>
              <div>
                <Text code style={{ fontSize: 12 }}>
                  {configFilePath}
                </Text>
              </div>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default Settings;
