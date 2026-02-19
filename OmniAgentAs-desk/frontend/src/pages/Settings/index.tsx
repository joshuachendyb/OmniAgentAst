/**
 * Settings组件 - 系统设置页面
 * 
 * 功能：模型配置、安全配置、会话历史管理
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  Switch,
  Button,
  Tabs,
  List,
  Tag,
  Space,
  Typography,
  message,
  Divider,
  Alert,
  Popconfirm,
  Empty,
} from 'antd';
import {
  SettingOutlined,
  SafetyOutlined,
  HistoryOutlined,
  SaveOutlined,
  ReloadOutlined,
  DeleteOutlined,
  KeyOutlined,
} from '@ant-design/icons';
import { configApi, sessionApi } from '../../services/api';
import type { Config, Session } from '../../services/api';

const { Title, Text } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;
const { TextArea } = Input;

/**
 * 设置页面组件
 * 
 * 设计要点：
 * - 三栏Tab布局：模型配置、安全配置、会话历史
 * - 表单验证：必填项校验、格式校验
 * - 实时保存：配置变更自动保存
 * - 权限控制：敏感操作需要确认
 */
const Settings: React.FC = () => {
  // 模型配置状态
  const [modelConfig, setModelConfig] = useState<Partial<Config>>({});
  const [modelForm] = Form.useForm();
  const [savingModel, setSavingModel] = useState(false);

  // 安全配置状态
  const [securityConfig, setSecurityConfig] = useState<any>({});
  const [securityForm] = Form.useForm();
  const [savingSecurity, setSavingSecurity] = useState(false);

  // 会话历史状态
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);

  /**
   * 初始化加载所有配置
   */
  useEffect(() => {
    loadModelConfig();
    loadSecurityConfig();
    loadSessions();
  }, []);

  /**
   * 加载模型配置
   */
  const loadModelConfig = async () => {
    try {
      const config = await configApi.getConfig();
      setModelConfig(config);
      modelForm.setFieldsValue(config);
    } catch (error) {
      message.error('加载模型配置失败');
      console.error('加载模型配置失败:', error);
    }
  };

  /**
   * 加载安全配置
   * @author 小新
   * @update 2026-02-18 对接真实API，移除Mock
   */
  const loadSecurityConfig = async () => {
    try {
      const config = await configApi.getConfig();
      // 使用后端返回的安全配置，如果没有则使用默认值
      const securityConfig = config.security || {
        contentFilterEnabled: true,
        contentFilterLevel: 'medium',
        whitelistEnabled: false,
        commandWhitelist: '',
        commandBlacklist: 'rm -rf /\nsudo *\nchmod 777 *',
        confirmDangerousOps: true,
        maxFileSize: 100,
      };
      setSecurityConfig(securityConfig);
      securityForm.setFieldsValue(securityConfig);
    } catch (error) {
      message.error('加载安全配置失败');
      console.error('加载安全配置失败:', error);
    }
  };

  /**
   * 加载会话历史
   */
  const loadSessions = async () => {
    setLoadingSessions(true);
    try {
      const response = await sessionApi.listSessions(1, 50);
      setSessions(response.sessions);
    } catch (error) {
      message.error('加载会话历史失败');
      console.error('加载会话历史失败:', error);
    } finally {
      setLoadingSessions(false);
    }
  };

  /**
   * 保存模型配置
   */
  const handleSaveModelConfig = async (values: Partial<Config>) => {
    setSavingModel(true);
    try {
      await configApi.updateConfig(values);
      message.success('模型配置已保存');
      setModelConfig(values);
    } catch (error) {
      message.error('保存模型配置失败');
      console.error('保存模型配置失败:', error);
    } finally {
      setSavingModel(false);
    }
  };

  /**
   * 保存安全配置
   * @author 小新
   * @update 2026-02-18 对接真实API，移除Mock
   */
  const handleSaveSecurityConfig = async (values: any) => {
    setSavingSecurity(true);
    try {
      // 获取当前完整配置
      const currentConfig = await configApi.getConfig();
      // 更新安全配置
      const updateData = {
        ...currentConfig,
        security: values,
      };
      await configApi.updateConfig(updateData);
      message.success('安全配置已保存');
      setSecurityConfig(values);
    } catch (error) {
      message.error('保存安全配置失败');
      console.error('保存安全配置失败:', error);
    } finally {
      setSavingSecurity(false);
    }
  };

  /**
   * 删除会话
   */
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await sessionApi.deleteSession(sessionId);
      message.success('会话已删除');
      loadSessions(); // 刷新列表
    } catch (error) {
      message.error('删除会话失败');
      console.error('删除会话失败:', error);
    }
  };

  /**
   * 清空所有会话
   * @author 小新
   * @update 2026-02-18 已对接真实API
   */
  const handleClearAllSessions = async () => {
    try {
      // 逐个删除会话
      for (const session of sessions) {
        await sessionApi.deleteSession(session.id);
      }
      message.success('所有会话已清空');
      setSessions([]);
    } catch (error) {
      message.error('清空会话失败');
      console.error('清空会话失败:', error);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3}>
        <SettingOutlined /> 系统设置
      </Title>
      <Text type="secondary">配置模型参数、安全策略和会话管理</Text>

      <Card style={{ marginTop: 24 }}>
        <Tabs defaultActiveKey="model" type="card">
          {/* 模型配置Tab */}
          <TabPane
            tab={
              <span>
                <KeyOutlined /> 模型配置
              </span>
            }
            key="model"
          >
            <Form
              form={modelForm}
              layout="vertical"
              onFinish={handleSaveModelConfig}
              initialValues={modelConfig}
            >
              <Alert
                message="模型配置说明"
                description="配置AI模型提供商和参数。切换提供商时需要提供相应的API密钥。"
                type="info"
                showIcon
                style={{ marginBottom: 24 }}
              />

              <Form.Item
                label="模型提供商"
                name="provider"
                rules={[{ required: true, message: '请选择模型提供商' }]}
              >
                <Select placeholder="选择模型提供商">
                  <Option value="zhipuai">智谱AI (GLM)</Option>
                  <Option value="opencode">OpenCode (MiniMax)</Option>
                  <Option value="openai">OpenAI (GPT)</Option>
                  <Option value="anthropic">Anthropic (Claude)</Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="模型名称"
                name="model"
                rules={[{ required: true, message: '请输入模型名称' }]}
                extra="例如：glm-4-flash, gpt-4, claude-3-opus-20240229"
              >
                <Input placeholder="输入模型名称" />
              </Form.Item>

              <Form.Item
                label="API密钥"
                name="apiKey"
                rules={[{ required: true, message: '请输入API密钥' }]}
                extra="您的API密钥将被安全存储，不会在前端显示"
              >
                <Input.Password placeholder="输入API密钥" />
              </Form.Item>

              <Form.Item
                label="API地址"
                name="apiUrl"
                extra="可选，留空使用默认地址"
              >
                <Input placeholder="https://api.example.com/v1" />
              </Form.Item>

              <Form.Item
                label="温度参数 (temperature)"
                name="temperature"
                extra="控制输出随机性，范围0-2，值越大输出越随机"
              >
                <Select defaultValue={0.7}>
                  <Option value={0}>0 - 最确定</Option>
                  <Option value={0.3}>0.3 - 较确定</Option>
                  <Option value={0.7}>0.7 - 平衡</Option>
                  <Option value={1}>1 - 较随机</Option>
                  <Option value={1.5}>1.5 - 很随机</Option>
                  <Option value={2}>2 - 最随机</Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="最大Token数"
                name="maxTokens"
                extra="单次请求返回的最大token数"
              >
                <Select defaultValue={2048}>
                  <Option value={512}>512</Option>
                  <Option value={1024}>1024</Option>
                  <Option value={2048}>2048</Option>
                  <Option value={4096}>4096</Option>
                  <Option value={8192}>8192</Option>
                </Select>
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<SaveOutlined />}
                  loading={savingModel}
                >
                  保存模型配置
                </Button>
                <Button
                  style={{ marginLeft: 8 }}
                  icon={<ReloadOutlined />}
                  onClick={loadModelConfig}
                >
                  重置
                </Button>
              </Form.Item>
            </Form>
          </TabPane>

          {/* 安全配置Tab */}
          <TabPane
            tab={
              <span>
                <SafetyOutlined /> 安全配置
              </span>
            }
            key="security"
          >
            <Form
              form={securityForm}
              layout="vertical"
              onFinish={handleSaveSecurityConfig}
              initialValues={securityConfig}
            >
              <Alert
                message="安全配置说明"
                description="配置内容安全策略和访问控制。启用安全检查将过滤敏感内容和危险操作。"
                type="warning"
                showIcon
                style={{ marginBottom: 24 }}
              />

              <Form.Item
                label="启用内容安全"
                name="contentFilterEnabled"
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Form.Item
                label="敏感词过滤级别"
                name="contentFilterLevel"
                extra="严格级别越高，过滤越严格"
              >
                <Select defaultValue="medium">
                  <Option value="low">低 - 仅过滤明显违规内容</Option>
                  <Option value="medium">中 - 平衡安全与体验</Option>
                  <Option value="high">高 - 严格过滤所有敏感内容</Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="启用命令白名单"
                name="whitelistEnabled"
                valuePropName="checked"
                extra="开启后只允许执行白名单中的命令"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Form.Item
                label="命令白名单"
                name="commandWhitelist"
                extra="每行一个命令，支持通配符 * 和 ?"
              >
                <TextArea
                  rows={6}
                  placeholder={`示例：
ls *
cd *
cat *
git status
git log --oneline -10
`}
                />
              </Form.Item>

              <Form.Item
                label="命令黑名单"
                name="commandBlacklist"
                extra="优先级高于白名单，每行一个命令"
              >
                <TextArea
                  rows={4}
                  placeholder={`示例：
rm -rf /
sudo *
chmod 777 *
`}
                />
              </Form.Item>

              <Form.Item
                label="危险操作二次确认"
                name="confirmDangerousOps"
                valuePropName="checked"
                extra="删除文件、修改配置等操作需要二次确认"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" defaultChecked />
              </Form.Item>

              <Form.Item
                label="最大文件操作大小 (MB)"
                name="maxFileSize"
                extra="超过此大小的文件操作将被阻止"
              >
                <Select defaultValue={100}>
                  <Option value={10}>10 MB</Option>
                  <Option value={50}>50 MB</Option>
                  <Option value={100}>100 MB</Option>
                  <Option value={500}>500 MB</Option>
                  <Option value={1000}>1 GB</Option>
                </Select>
              </Form.Item>

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
          </TabPane>

          {/* 会话历史Tab */}
          <TabPane
            tab={
              <span>
                <HistoryOutlined /> 会话历史
              </span>
            }
            key="sessions"
          >
            <Alert
              message="会话管理"
              description="查看和管理历史对话会话。删除会话将永久清除该会话的所有消息记录。"
              type="info"
              showIcon
              style={{ marginBottom: 24 }}
            />

            <div style={{ marginBottom: 16 }}>
              <Popconfirm
                title="确定要清空所有会话吗？"
                description="此操作不可恢复，将删除所有历史对话记录。"
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

            <Divider />

            <List
              loading={loadingSessions}
              dataSource={sessions}
              locale={{
                emptyText: (
                  <Empty
                    description="暂无会话记录"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                ),
              }}
              renderItem={(session) => (
                <List.Item
                  actions={[
                    <Popconfirm
                      title="确定删除此会话吗？"
                      onConfirm={() => handleDeleteSession(session.id)}
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
                    title={
                      <Space>
                        <Text strong>{session.title || '未命名会话'}</Text>
                        <Tag color="blue">
                          AI助手
                        </Tag>
                        {session.message_count && (
                          <Tag>{session.message_count} 条消息</Tag>
                        )}
                      </Space>
                    }
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
                </List.Item>
              )}
            />
          </TabPane>
        </Tabs>
      </Card>
    </div>
  );
};

export default Settings;
