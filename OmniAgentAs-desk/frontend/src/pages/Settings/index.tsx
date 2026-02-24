/**
 * Settings组件 - 系统设置页面
 * 
 * 功能：模型配置管理（Provider和Model）
 * 
 * @author 小欧
 * @version 2.0.0
 * @since 2026-02-22
 */

import React, { useState, useEffect } from 'react';
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
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  ApiOutlined,
  SafetyOutlined,
  HistoryOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
} from '@ant-design/icons';
import { configApi, sessionApi } from '../../services/api';
import type { ProviderInfo, Session } from '../../services/api';

const { Text } = Typography;
const { TabPane } = Tabs;

/**
 * Provider管理页面组件
 */
const ProviderSettings: React.FC = () => {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [currentProvider, setCurrentProvider] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [validationModalVisible, setValidationModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [addModelModalVisible, setAddModelModalVisible] = useState(false);
  const [addProviderModalVisible, setAddProviderModalVisible] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderInfo | null>(null);
  const [selectedProviderForModel, setSelectedProviderForModel] = useState<string>('');
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({}); // 控制每个Provider的API Key显示
  
  const [form] = Form.useForm();
  const [modelForm] = Form.useForm();
  const [providerForm] = Form.useForm();

  // 切换API Key显示/隐藏
  const toggleShowApiKey = (providerName: string) => {
    setShowApiKey(prev => ({ ...prev, [providerName]: !prev[providerName] }));
  };

  // 加载配置
  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await configApi.getFullConfig();
      const providerList = Object.values(data.providers);
      setProviders(providerList);
      setCurrentProvider(data.current_provider);
    } catch (error) {
      message.error('加载配置失败');
      console.error('加载配置失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 加载配置时同时进行验证
  const handleLoadWithValidation = async () => {
    await loadConfig();
    try {
      const result = await configApi.validateFullConfig();
      setValidationResult(result);
    } catch (error) {
      console.error('配置验证失败:', error);
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
      model: provider.model,
      timeout: provider.timeout,
      max_retries: provider.max_retries,
    });
    setEditModalVisible(true);
  };

  // 保存Provider编辑
  const handleSaveProvider = async (values: any) => {
    try {
      await configApi.updateProvider(editingProvider!.name, values);
      message.success('Provider配置已更新');
      setEditModalVisible(false);
      loadConfig();
    } catch (error) {
      message.error('更新失败');
    }
  };

  // 删除Provider
  const handleDeleteProvider = async (providerName: string) => {
    try {
      await configApi.deleteProvider(providerName);
      message.success('Provider已删除');
      loadConfig();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 删除模型
  const handleDeleteModel = async (providerName: string, modelName: string) => {
    try {
      await configApi.deleteModel(providerName, modelName);
      message.success('模型已删除');
      loadConfig();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 添加模型
  const handleAddModel = async (values: { model: string }) => {
    try {
      await configApi.addModel(selectedProviderForModel, values);
      message.success('模型已添加');
      setAddModelModalVisible(false);
      modelForm.resetFields();
      loadConfig();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '添加失败');
    }
  };

  // 添加Provider
  const handleAddProvider = async (values: any) => {
    try {
      await configApi.addProvider({
        name: values.name,
        api_base: values.api_base,
        api_key: values.api_key || '',
        model: values.model || '',
        models: values.model ? [values.model] : [],
        timeout: values.timeout || 60,
        max_retries: values.max_retries || 3,
      });
      message.success('Provider已添加');
      setAddProviderModalVisible(false);
      providerForm.resetFields();
      loadConfig();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '添加失败');
    }
  };

  // 切换当前Provider
  const handleSwitchProvider = async (providerName: string, modelName: string) => {
    try {
      await configApi.updateConfig({
        ai_provider: providerName as 'zhipuai' | 'opencode' | 'longcat',
        ai_model: modelName,
      });
      message.success(`已切换到 ${providerName} (${modelName})`);
      loadConfig();
    } catch (error) {
      message.error('切换失败');
    }
  };

  // 获取Provider显示名称
  const getProviderDisplayName = (name: string) => {
    const nameMap: Record<string, string> = {
      zhipuai: '智谱GLM',
      opencode: 'OpenCode',
      longcat: 'LongCat',
    };
    return nameMap[name] || name;
  };

  return (
    <div>
      {/* 配置验证提示 - 成功/失败都显示 */}
      {validationResult && (
        <Alert
          message={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {validationResult.success ? (
                <>
                  <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  <strong>配置验证成功</strong>
                </>
              ) : (
                <>
                  <ReloadOutlined style={{ color: '#faad14' }} />
                  <strong>配置验证发现问题</strong>
                </>
              )}
              <span style={{ marginLeft: 8, cursor: 'pointer', textDecoration: 'underline' }}>
                点击查看详情
              </span>
            </div>
          }
          description={validationResult.message}
          type={validationResult.success ? 'success' : 'warning'}
          showIcon
          style={{ marginBottom: 16, cursor: 'pointer' }}
          onClick={() => setValidationModalVisible(true)}
        />
      )}

      {/* 验证详情弹框 */}
      <Modal
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {validationResult?.success ? (
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
            ) : (
              <ReloadOutlined style={{ color: '#faad14', fontSize: 18 }} />
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
          <Button key="revalidate" onClick={handleLoadWithValidation} loading={loading}>
            重新验证
          </Button>,
        ]}
        width={600}
      >
        {validationResult && (
          <div>
            <Alert 
              message={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {validationResult.success ? (
                    <>
                      <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      <strong>配置验证成功</strong>
                    </>
                  ) : (
                    <>
                      <ReloadOutlined style={{ color: '#faad14' }} />
                      <strong>配置验证发现问题</strong>
                    </>
                  )}
                </div>
              }
              description={validationResult.message}
              type={validationResult.success ? 'success' : 'warning'} 
              showIcon 
              style={{ marginBottom: 24 }}
            />
            
            {/* 配置信息卡片 */}
            <div style={{ 
              background: '#fafafa', 
              padding: 16, 
              borderRadius: 8, 
              marginBottom: 24 
            }}>
              <div style={{ display: 'flex', gap: 24 }}>
                <div>
                  <span style={{ color: '#666', fontSize: 12 }}>当前 Provider</span>
                  <div style={{ fontSize: 16, fontWeight: 500, marginTop: 4 }}>
                    {validationResult.provider}
                  </div>
                </div>
                <div>
                  <span style={{ color: '#666', fontSize: 12 }}>当前 Model</span>
                  <div style={{ fontSize: 16, fontWeight: 500, marginTop: 4 }}>
                    {validationResult.model}
                  </div>
                </div>
              </div>
            </div>
            
            {validationResult.errors && validationResult.errors.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 8, 
                  marginBottom: 12,
                  color: '#ff4d4f',
                  fontSize: 14,
                  fontWeight: 500
                }}>
                  <span style={{ fontSize: 18 }}>❌</span>
                  错误 ({validationResult.errors.length})
                </div>
                <div style={{ 
                  background: '#fff1f0', 
                  border: '1px solid #ffa39e', 
                  borderRadius: 6, 
                  padding: '12px 16px'
                }}>
                  <ul style={{ 
                    margin: 0, 
                    paddingLeft: 20, 
                    color: '#ff4d4f',
                    fontSize: 14,
                    lineHeight: 1.8
                  }}>
                    {validationResult.errors.map((err: string, idx: number) => (
                      <li key={idx}>{err}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            
            {validationResult.warnings && validationResult.warnings.length > 0 && (
              <div>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 8, 
                  marginBottom: 12,
                  color: '#faad14',
                  fontSize: 14,
                  fontWeight: 500
                }}>
                  <span style={{ fontSize: 18 }}>⚠️</span>
                  警告 ({validationResult.warnings.length})
                </div>
                <div style={{ 
                  background: '#fffbe6', 
                  border: '1px solid #ffe58f', 
                  borderRadius: 6, 
                  padding: '12px 16px'
                }}>
                  <ul style={{ 
                    margin: 0, 
                    paddingLeft: 20, 
                    color: '#faad14',
                    fontSize: 14,
                    lineHeight: 1.8
                  }}>
                    {validationResult.warnings.map((warn: string, idx: number) => (
                      <li key={idx}>{warn}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 右上角添加按钮 */}
      <div style={{ marginBottom: 16, textAlign: 'right' }}>
        <Button 
          type="primary" 
          icon={<PlusOutlined />}
          onClick={() => setAddProviderModalVisible(true)}
        >
          新增Provider
        </Button>
      </div>

      {/* Provider列表 */}
      <List
        loading={loading}
        dataSource={providers}
        renderItem={(provider) => (
          <Card 
            size="small" 
            style={{ marginBottom: 16 }}
            title={
              <Space>
                <ApiOutlined />
                <span style={{ fontWeight: 'bold' }}>{getProviderDisplayName(provider.name)}</span>
                <Tag color="blue">{provider.name}</Tag>
                {provider.name === currentProvider && (
                  <Tag icon={<CheckCircleOutlined />} color="success">当前使用</Tag>
                )}
              </Space>
            }
            extra={
              <Space>
                <Button 
                  type="link" 
                  icon={<EditOutlined />} 
                  onClick={() => handleEditProvider(provider)}
                >
                  编辑
                </Button>
                <Popconfirm
                  title={`确定删除 ${getProviderDisplayName(provider.name)} 吗？`}
                  description="删除后无法恢复"
                  onConfirm={() => handleDeleteProvider(provider.name)}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button type="link" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            }
          >
            {/* Provider基本信息 */}
            <Row gutter={[16, 8]} style={{ marginBottom: 16 }}>
              <Col span={24}>
                <Text type="secondary">API地址：</Text>
                <Text code>{provider.api_base}</Text>
              </Col>
              <Col span={24}>
                <Space>
                  <Text type="secondary">API密钥：</Text>
                  <Text>
                    {provider.api_key 
                      ? (showApiKey[provider.name] ? provider.api_key : '******' + provider.api_key.slice(-4)) 
                      : '未设置'}
                  </Text>
                  {provider.api_key && (
                    <Button 
                      type="text" 
                      size="small" 
                      icon={showApiKey[provider.name] ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                      onClick={() => toggleShowApiKey(provider.name)}
                    />
                  )}
                </Space>
              </Col>
              <Col span={24}>
                <Text type="secondary">当前模型：</Text>
                <Text strong>{provider.model}</Text>
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
                    setSelectedProviderForModel(provider.name);
                    setAddModelModalVisible(true);
                  }}
                >
                  添加模型
                </Button>
              </Space>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {provider.models.map((model) => (
                  <Tag
                    key={model}
                    color={model === provider.model ? 'geekblue' : 'default'}
                    closable
                    onClose={(e) => {
                      e.preventDefault();
                      handleDeleteModel(provider.name, model);
                    }}
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSwitchProvider(provider.name, model)}
                  >
                    {model === provider.model && <CheckCircleOutlined style={{ marginRight: 4 }} />}
                    {model}
                  </Tag>
                ))}
              </div>
            </div>
          </Card>
        )}
      />

      {/* 编辑Provider弹框 */}
      <Modal
        title={`编辑 ${getProviderDisplayName(editingProvider?.name || '')} 配置`}
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSaveProvider}
        >
          <Form.Item
            label="API地址"
            name="api_base"
            rules={[{ required: true, message: '请输入API地址' }]}
          >
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>

          <Form.Item
            label="API密钥"
            name="api_key"
          >
            <Input.Password placeholder="留空保持原密钥不变" />
          </Form.Item>

          <Form.Item
            label="当前使用模型"
            name="model"
            rules={[{ required: true, message: '请输入模型名称' }]}
          >
            <Input placeholder="glm-4-flash" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="超时时间(秒)"
                name="timeout"
              >
                <Input type="number" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="最大重试次数"
                name="max_retries"
              >
                <Input type="number" />
              </Form.Item>
            </Col>
          </Row>

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
        <Form
          form={modelForm}
          layout="vertical"
          onFinish={handleAddModel}
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

          <Form.Item
            label="API密钥"
            name="api_key"
          >
            <Input.Password placeholder="可选" />
          </Form.Item>

          <Form.Item
            label="默认模型"
            name="model"
          >
            <Input placeholder="glm-4-flash" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="超时时间(秒)"
                name="timeout"
                initialValue={60}
              >
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

  const loadSecurityConfig = async () => {
    try {
      const config = await configApi.getConfig();
      const security = config.security || {
        contentFilterEnabled: true,
        contentFilterLevel: 'medium',
        whitelistEnabled: false,
        commandWhitelist: '',
        blacklistEnabled: false,
        commandBlacklist: 'rm -rf /\nsudo *\nchmod 777 *',
        confirmDangerousOps: true,
        maxFileSize: 100,
      };
      setSecurityConfig(security);
      securityForm.setFieldsValue(security);
    } catch (error) {
      message.error('加载安全配置失败');
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
      message.success('安全配置已保存');
      setSecurityConfig(values);
    } catch (error) {
      message.error('保存安全配置失败');
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
          <Form.Item
            label="敏感词过滤级别"
            name="contentFilterLevel"
          >
            <Select>
              <Select.Option value="low">低</Select.Option>
              <Select.Option value="medium">中</Select.Option>
              <Select.Option value="high">高</Select.Option>
            </Select>
          </Form.Item>
        </Col>

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
            label="危险操作二次确认"
            name="confirmDangerousOps"
            valuePropName="checked"
          >
            <Switch checkedChildren="开" unCheckedChildren="关" />
          </Form.Item>
        </Col>

        <Col xs={24} sm={12}>
          <Form.Item
            label="最大文件操作大小(MB)"
            name="maxFileSize"
          >
            <Select>
              <Select.Option value={10}>10</Select.Option>
              <Select.Option value={50}>50</Select.Option>
              <Select.Option value={100}>100</Select.Option>
              <Select.Option value={500}>500</Select.Option>
            </Select>
          </Form.Item>
        </Col>
      </Row>

      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          icon={<SafetyOutlined />}
          loading={savingSecurity}
        >
          保存安全配置
        </Button>
        <Button
          style={{ marginLeft: 8 }}
          icon={<ReloadOutlined />}
          onClick={loadSecurityConfig}
        >
          重置
        </Button>
      </Form.Item>
    </Form>
  );
};

/**
 * 会话历史页面组件
 */
const SessionHistory: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);

  const loadSessions = async () => {
    setLoadingSessions(true);
    try {
      const response = await sessionApi.listSessions(1, 50);
      setSessions(response.sessions);
    } catch (error) {
      message.error('加载会话历史失败');
    } finally {
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await sessionApi.deleteSession(sessionId);
      message.success('会话已删除');
      loadSessions();
    } catch (error) {
      message.error('删除会话失败');
    }
  };

  const handleClearAllSessions = async () => {
    try {
      for (const session of sessions) {
        await sessionApi.deleteSession(session.session_id);
      }
      message.success('所有会话已清空');
      setSessions([]);
    } catch (error) {
      message.error('清空会话失败');
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Popconfirm
          title="确定要清空所有会话吗？"
          description="此操作不可恢复"
          onConfirm={handleClearAllSessions}
          okText="确定"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button danger icon={<DeleteOutlined />}>
            清空所有会话
          </Button>
        </Popconfirm>
        <Button
          style={{ marginLeft: 8 }}
          icon={<ReloadOutlined />}
          onClick={loadSessions}
          loading={loadingSessions}
        >
          刷新列表
        </Button>
      </div>

      <List
        loading={loadingSessions}
        dataSource={sessions}
        locale={{ emptyText: '暂无会话记录' }}
        renderItem={(session) => (
          <List.Item
            actions={[
              <Popconfirm
                title="确定删除此会话吗？"
                onConfirm={() => handleDeleteSession(session.session_id)}
                okText="删除"
                cancelText="取消"
              >
                <Button type="link" danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>,
            ]}
          >
            <List.Item.Meta
              title={session.title || '未命名会话'}
              description={
                <Space direction="vertical" size={0}>
                  <Text type="secondary">
                    创建于: {new Date(session.created_at).toLocaleString()}
                  </Text>
                  {session.updated_at && (
                    <Text type="secondary">
                      最后更新: {new Date(session.updated_at).toLocaleString()}
                    </Text>
                  )}
                </Space>
              }
            />
            <Tag>{session.message_count} 条消息</Tag>
          </List.Item>
        )}
      />
    </div>
  );
};

/**
 * 设置页面主组件
 */
const Settings: React.FC = () => {
  return (
    <div style={{ padding: 0, margin: 0 }}>
      <Card style={{ marginTop: 0 }}>
        <Tabs defaultActiveKey="model" type="card">
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

          <TabPane
            tab={
              <span>
                <HistoryOutlined /> 会话历史
              </span>
            }
            key="sessions"
          >
            <SessionHistory />
          </TabPane>
        </Tabs>
      </Card>
    </div>
  );
};

export default Settings;
