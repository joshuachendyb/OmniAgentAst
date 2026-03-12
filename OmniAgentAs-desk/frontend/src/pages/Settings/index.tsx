/**
 * Settings 组件 - 系统设置页面
 *
 * 功能：模型配置管理（Provider 和 Model）
 *
 * ================================================================================
 * 【重要！绝对禁止硬编码 Provider 名称 - 所有代码编写人员必须遵守！】
 *
 * 禁止事项：
 * 1. 绝对禁止在代码中硬编码具体的 provider 名称（如"zhipuai"、"opencode"、"longcat"等）
 * 2. 所有 provider 必须从配置文件中动态遍历，不能写死
 * 3. 配置文件里有什么 provider，代码就支持什么 provider
 * 4. 这是通用程序，不是只给这几个 provider 用的！
 *
 * 正确做法：
 * 1. 使用动态类型，不限制具体值（删除 as "zhipuai" | "opencode" | "longcat"）
 * 2. 从配置文件中读取 provider 列表
 * 3. 动态遍历处理所有 provider
 *
 * 违反后果：
 * - 代码审查不通过
 * - 必须立即修复
 * - 严重者重新学习项目规范
 * ================================================================================
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
  WarningOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  DesktopOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
  CheckOutlined,
} from "@ant-design/icons";
import { configApi, chatApi } from "../../services/api";
import type { ProviderInfo } from "../../services/api";
import HealthCheck from "../../components/HealthCheck";

const { Text } = Typography;
const { TabPane } = Tabs;

/**
 * 全局配置区域组件（显示 display_name 列表）
 * @author 小新
 * @update 2026-03-03 重构为单一下拉框
 */
interface ModelOption {
  id: number;
  provider: string;
  model: string;
  display_name: string;
  current_model: boolean;
}

const GlobalConfigArea: React.FC<{
  modelList: ModelOption[];
  currentDisplayName: string;
  onDisplayNameChange: (option: ModelOption) => void;
}> = ({ modelList, currentDisplayName, onDisplayNameChange }) => {
  const [configPath, setConfigPath] = useState<any>(null);
  const [configContent, setConfigContent] = useState<string>("");
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    const loadConfigPath = async () => {
      try {
        const pathData = await configApi.getConfigPath();
        setConfigPath(pathData);
      } catch (error) {
        console.error("加载配置文件路径失败:", error);
      }
    };
    loadConfigPath();
  }, []);

  const handleOpenConfigDir = async () => {
    try {
      await configApi.openConfigFolder();
    } catch (error) {
      console.error("打开配置目录失败:", error);
      message.error("打开配置目录失败");
    }
  };

  const handleViewConfig = async () => {
    try {
      const result = await configApi.readConfigFile();
      setConfigContent(result.content);
      setShowConfigModal(true);
    } catch (error) {
      console.error("读取配置文件失败:", error);
      message.error("读取配置文件失败");
    }
  };

  const handleValidateConfig = async () => {
    setValidating(true);
    setValidationResult(null);
    try {
      // 同时获取配置内容和验证结果
      const [validationResult, contentResult] = await Promise.all([
        configApi.validateFullConfig(),
        configApi.readConfigFile()
      ]);
      setValidationResult(validationResult);
      setConfigContent(contentResult.content);
    } catch (error) {
      console.error("检测配置文件失败:", error);
      message.error("检测配置文件失败");
    } finally {
      setValidating(false);
    }
  };

  return (
    <Card size="small" style={{ marginBottom: 24 }}>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          {/* 配置文件路径显示 - 上一行标签，下一行信息框 */}
          {configPath && (
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ display: "block", marginBottom: 8 }}>
                配置文件路径：
              </Text>
              <Card size="small" style={{ backgroundColor: "#fafafa" }}>
                <div style={{ wordBreak: "break-all", marginBottom: 8 }}>
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
                    loading={validating}
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
          <Text strong style={{ display: "block", marginBottom: 8 }}>
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
            style={{ width: "100%" }}
            placeholder="选择模型"
          >
            {modelList.map((m) => (
              <Select.Option key={`${m.provider}-${m.model}`} value={m.display_name}>
                {m.display_name} {m.current_model === true ? " *" : ""}
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
        <pre style={{ 
          maxHeight: 500, 
          overflow: "auto", 
          backgroundColor: "#f5f5f5", 
          padding: 12,
          borderRadius: 4,
          fontSize: 12
        }}>
          {configContent}
        </pre>
      </Modal>

      {/* 检测配置结果 Modal */}
      <Modal
        title="配置检测结果"
        open={!!validationResult}
        onCancel={() => setValidationResult(null)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setValidationResult(null)}>
            关闭
          </Button>,
        ]}
      >
        {validationResult && (
          <div>
            {/* 检测状态 */}
            <Alert
              type={validationResult.success ? "success" : "error"}
              message={validationResult.success ? "配置检测通过" : "配置检测失败"}
              description={validationResult.message}
              showIcon
              style={{ marginBottom: 16 }}
            />

            {/* 当前配置 */}
            <div style={{ marginBottom: 16 }}>
              <Text strong>当前配置：</Text>
              <div style={{ marginTop: 8 }}>
                <Tag color="blue">Provider: {validationResult.provider}</Tag>
                <Tag color="green">Model: {validationResult.model}</Tag>
              </div>
            </div>

            {/* 错误列表 */}
            {validationResult.errors && validationResult.errors.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Text strong type="danger">错误列表：</Text>
                <ul style={{ color: "#ff4d4f", marginTop: 8 }}>
                  {validationResult.errors.map((err: string, idx: number) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 警告列表 */}
            {validationResult.warnings && validationResult.warnings.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Text strong type="warning">警告列表：</Text>
                <ul style={{ color: "#faad14", marginTop: 8 }}>
                  {validationResult.warnings.map((warn: string, idx: number) => (
                    <li key={idx}>{warn}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 配置文件全文 */}
            <div>
              <Text strong>配置文件全文：</Text>
              <pre style={{ 
                maxHeight: 300, 
                overflow: "auto", 
                backgroundColor: "#f5f5f5", 
                padding: 12,
                borderRadius: 4,
                fontSize: 12,
                marginTop: 8
              }}>
                {configContent}
              </pre>
            </div>
          </div>
        )}
      </Modal>
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
  onAdd?: () => void;
  modelList: ModelOption[];
}> = ({ providers, currentProvider, onSelect, onAdd, modelList }) => {
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
      <Space
        style={{
          marginBottom: 16,
          width: "100%",
          justifyContent: "space-between",
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
        style={{ marginBottom: 16,  }}
        onChange={(e) => setSearchKeyword(e.target.value)}
        prefix={<ApiOutlined />}
      />

      {filteredProviders.map((provider) => (
        <Card
          key={provider.name}
          size="small"
          style={{ marginBottom: 12, cursor: "pointer" }}
          onClick={() => onSelect(provider)}
          styles={{
            body: {
              backgroundColor:
                provider.name === currentProvider ? "#e6f7ff" : "transparent",
            },
          }}
        >
          <Space>
            <ApiOutlined />
            <Text strong>{provider.name}</Text>
            {/* ⭐ 修复：只显示真正正在使用的模型对应的Provider的"当前使用"标签 */}
            {modelList.some(m => m.provider === provider.name && m.current_model) && (
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

/**
 * Provider管理页面组件
 * @author 小新
 * @update 2026-02-26 重构：提取子组件
 */
const ProviderSettings: React.FC<{ shouldLoad?: boolean }> = ({ shouldLoad = true }) => {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [currentProvider, setCurrentProvider] = useState<string>("");
  // 模型列表（从 getModelList API 获取，包含 display_name）
  const [modelList, setModelList] = useState<ModelOption[]>([]);
  const [currentDisplayName, setCurrentDisplayName] = useState<string>("");
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
      // 获取完整配置
      const data = await configApi.getFullConfig();
      const providerList = Object.values(data.providers);
      setProviders(providerList);
      setCurrentProvider(data.current_provider);

      // 获取模型列表（包含 display_name）
      const modelData = await configApi.getModelList();
      console.log("从后端获取的模型列表：", JSON.stringify(modelData.models, null, 2));
      // 直接使用原始数据，不做任何修改
      setModelList(modelData.models);

      // 设置当前显示名称
      const currentModelOption = modelData.models.find((m) => m.current_model);
      if (currentModelOption) {
        setCurrentDisplayName(currentModelOption.display_name);
      }

      // 设置当前选中的Provider为当前使用的Provider或第一个Provider
      const current =
        providerList.find((p) => p.name === data.current_provider) ||
        (providerList.length > 0 ? providerList[0] : null);
      setSelectedProvider(current);
    } catch (error) {
      message.error("加载配置失败");
      console.error("加载配置失败:", error);
    } finally {
      setLoading(false);
    }
  };

  // 加载配置文件路径
  // 打开配置文件所在目录（在 GlobalConfigArea 组件中实现）

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

    // 验证AI服务可用性（触发后端备份清理）
    try {
      await chatApi.validateService();
    } catch (error) {
      console.warn("AI服务验证失败:", error);
    }
  };

  useEffect(() => {
    // ⭐ 老杨修复：按需加载 - 只在shouldLoad为true时加载
    if (shouldLoad) {
      handleLoadWithValidation();
    }
  }, [shouldLoad]);

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

      // 刷新配置
      loadConfig();

      // 验证配置文件
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (e) {
        console.warn("验证配置文件失败:", e);
      }

      // 验证服务可用性
      try {
        await chatApi.validateService();
      } catch (e) {
        console.warn("验证服务失败:", e);
      }

      message.success("Provider配置已更新");
      setEditModalVisible(false);
    } catch (error) {
      message.error("更新失败");
    }
  };

  // 删除Provider
  const handleDeleteProvider = async (providerName: string) => {
    try {
      await configApi.deleteProvider(providerName);

      // 刷新配置
      loadConfig();

      // 验证配置文件
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (e) {
        console.warn("验证配置文件失败:", e);
      }

      message.success("Provider已删除");
    } catch (error: any) {
      message.error(error.response?.data?.detail || "删除失败");
    }
  };

  // 编辑模型
  const [editingModel, setEditingModel] = useState<{provider: string, model: string} | null>(null);
  const [modelEditForm] = Form.useForm();

  const handleEditModel = async (providerName: string, modelName: string) => {
    setEditingModel({ provider: providerName, model: modelName });
    modelEditForm.setFieldsValue({ model: modelName });
    setEditModalVisible(true);
  };

  const handleUpdateModel = async (values: { model: string }) => {
    if (!editingModel) return;
    try {
      await configApi.updateModel(editingModel.provider, editingModel.model, values.model);

      // 刷新配置
      loadConfig();

      // 验证配置文件
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (e) {
        console.warn("验证配置文件失败:", e);
      }

      message.success("模型已更新");
      setEditModalVisible(false);
      setEditingModel(null);
      modelEditForm.resetFields();
    } catch (error: any) {
      message.error(error.response?.data?.detail || "更新失败");
    }
  };

  // 删除模型
  const handleDeleteModel = async (providerName: string, modelName: string) => {
    try {
      await configApi.deleteModel(providerName, modelName);

      // 刷新配置
      loadConfig();

      // 验证配置文件
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (e) {
        console.warn("验证配置文件失败:", e);
      }

      message.success("模型已删除");
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

    const controller = new AbortController();
    deleteControllerRef.current = controller;

    try {
      const deletePromises = models.map(async (modelName, index) => {
        // 检查是否已中止
        if (controller.signal.aborted) {
          return { success: false, model: modelName, cancelled: true };
        }

        try {
          // 传递 signal 参数以支持取消
          await configApi.deleteModel(providerName, modelName, {
            signal: controller.signal,
          });
          setDeleteProgress({ current: index + 1, total: models.length });
          return { success: true, model: modelName };
        } catch (error: any) {
          // 如果是取消错误
          if (error.name === "AbortError" || controller.signal.aborted) {
            return { success: false, model: modelName, cancelled: true };
          }
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

      if (controller.signal.aborted) {
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

      // 验证配置文件
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (e) {
        console.warn("验证配置文件失败:", e);
      }
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

      // 刷新配置
      loadConfig();

      // 验证配置文件
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (e) {
        console.warn("验证配置文件失败:", e);
      }

      // 验证服务可用性
      try {
        await chatApi.validateService();
      } catch (e) {
        console.warn("验证服务失败:", e);
      }

      message.success("模型已添加");
      setAddModelModalVisible(false);
      modelForm.resetFields();
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

      // 刷新配置
      loadConfig();

      // 验证配置文件
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (e) {
        console.warn("验证配置文件失败:", e);
      }

      // 验证服务可用性
      try {
        await chatApi.validateService();
      } catch (e) {
        console.warn("验证服务失败:", e);
      }

      message.success("Provider已添加");
      setAddProviderModalVisible(false);
      providerForm.resetFields();
    } catch (error: any) {
      message.error(error.response?.data?.detail || "添加失败");
    }
  };

  // 获取Provider显示名称 - 从配置文件动态获取
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

  // 全局配置 - 模型选择（同时更换 provider 和 model）
  const onDisplayNameChange = async (option: ModelOption) => {
    try {
      setCurrentProvider(option.provider);
      setCurrentDisplayName(option.display_name);

      // 更新配置（后端会自动创建备份）
      await configApi.updateConfig({
        ai_provider: option.provider,
        ai_model: option.model,
      });

      // 刷新配置
      loadConfig();

      // 刷新配置验证状态（根据小沈文档流程）
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (e) {
        console.warn("刷新验证状态失败:", e);
      }

      // 验证服务可用性（触发后端备份删除/恢复机制）
      try {
        await chatApi.validateService();
      } catch (e) {
        // 验证失败不影响切换成功提示
        console.warn("服务验证失败:", e);
      }

      message.success(`已切换到 ${option.display_name}`);
    } catch (error) {
      message.error("切换模型失败");
      console.error("切换模型失败:", error);
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
      {/* 配置验证提示 - 使用 Row/Col 布局与下方 Provider 配置区域对齐 */}
      {validationResult && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={16}>
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
              style={{ marginBottom: 0, cursor: "pointer" }}
              onClick={() => setValidationModalVisible(true)}
            />
          </Col>
        </Row>
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
        <Col xs={24} md={5}>
          <ProviderList
            providers={providers}
            currentProvider={currentProvider}
            onSelect={onSelectProvider}
            onAdd={() => setAddProviderModalVisible(true)}
            modelList={modelList}
          />
        </Col>

        {/* 右侧Provider详细信息 */}
        <Col xs={24} md={11}>
          <div style={{  }}>
          {selectedProvider ? (
            <div>
              <Typography.Title level={5} style={{ marginBottom: 24 }}>
                <Space style={{ width: "100%", justifyContent: "space-between" }}>
                  {/* 左侧: 标题内容 */}
                  <Space>
                    <ApiOutlined />
                    配置详情：
                    {getProviderDisplayName(selectedProvider.name, providers)}
                    <Tag color="blue">{selectedProvider.name}</Tag>
                    {selectedProvider.name === currentProvider && (
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
                      onConfirm={() => handleDeleteProvider(selectedProvider.name)}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button type="primary" danger size="small" icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                </Space>
              </Typography.Title>

              <Card size="small">
                {/* Provider基本信息 */}
                <Row gutter={[16, 8]} style={{ marginBottom: 16,  }}>
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
                          styles={{ body: { padding: "12px 16px" } }}
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

              </Card>
            </div>
          ) : (
            <Alert
              message="请选择一个Provider"
              description="在左侧列表中点击选择一个Provider以查看详细配置"
              type="info"
              showIcon
              style={{ marginBottom: 16,  }}
            />
          )}
          </div>
        </Col>
      </Row>

      {/* 批量删除确认弹框 */}
      <Modal
        title="批量删除"
        open={deleteModalVisible}
        onCancel={() => {
          // 调用 abort() 中止进行中的请求
          if (deleteControllerRef.current) {
            deleteControllerRef.current.abort();
          }
        }}
        footer={[
          <Button
            key="cancel"
            danger
            onClick={() => {
              // 调用 abort() 中止进行中的请求
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
          editingProvider?.name || "",
          providers
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

      {/* 编辑模型弹框 */}
      <Modal
        title="编辑模型"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false);
          setEditingModel(null);
          modelEditForm.resetFields();
        }}
        footer={null}
      >
        <Form form={modelEditForm} layout="vertical" onFinish={handleUpdateModel}>
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
                保存
              </Button>
              <Button onClick={() => setEditModalVisible(false)}>
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
        style={{ marginBottom: 16,  }}
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

/* eslint-disable @typescript-eslint/no-unused-vars */
/**
 * 设置页面
 *
 * 功能：
 * - Provider管理（添加、编辑、删除、切换）
 * - 模型管理（添加、编辑、删除）
 * - 配置文件操作（导入、导出、打开目录）
 * - 安全设置（安全检测v2.0配置）
 *
 * @author 小新
 * @update 2026-02-26 重构：提取子组件
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
  // 注意：React 18 自动批处理状态更新，无需手动优化
  // 多个 setState 调用会自动合并为一次重渲染
  const [activeKey, setActiveKey] = useState("model");
  const [isDirty, setIsDirty] = useState(false);
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
  const [pendingKey, setPendingKey] = useState<string>("");
  // ⭐ 老杨修复：按需加载 - 跟踪已加载的Tab
  const [loadedTabs, setLoadedTabs] = useState<Set<string>>(new Set(["model"])); // 默认"model"已加载
  // ⭐ 删除未使用的状态变量：configFilePath, fixingConfig, fixProgress, showFixModal

  /**
   * 加载配置信息（只读，不备份）
   * ⭐ 修复：启动时只验证配置，不修复/不备份
   */
  const loadConfigInfo = async () => {
    try {
      // 只读验证配置，不修改
      const validation = await configApi.validateFullConfig();
      console.log("📋 配置验证结果:", validation);
    } catch (error) {
      console.error("加载配置信息失败:", error);
    }
  };

  // ⭐ 删除未使用的函数：handleFixConfig

  // 清理定时器，防止内存泄漏
  useEffect(() => {
    return () => {
      // 组件卸载时清理所有可能的定时器
    };
  }, []);

  useEffect(() => {
    // ⭐ 修复：启动时只读验证，不备份
    loadConfigInfo();
  }, []);
  // Tab 切换处理
  const handleTabChange = (key: string) => {
    if (isDirty) {
      setPendingKey(key);
      setConfirmModalVisible(true);
    } else {
      setActiveKey(key);
      // ⭐ 老杨修复：按需加载 - 切换Tab时标记已加载
      setLoadedTabs(prev => new Set(prev).add(key));
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
              {/* ⭐ 老杨修复：按需加载 - 传递shouldLoad参数 */}
              <ProviderSettings shouldLoad={loadedTabs.has("model")} />
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

            <TabPane
              tab={
                <span>
                  <DesktopOutlined /> 系统状态
                </span>
              }
              key="system"
            >
              <HealthCheck />
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
    </div>
  );
};

export default Settings;
