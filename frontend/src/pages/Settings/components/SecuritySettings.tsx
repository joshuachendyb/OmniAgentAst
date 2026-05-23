import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Typography,
  Popconfirm,
  Form,
  Input,
  Select,
  Row,
  Col,
  Switch,
  Collapse,
} from 'antd';
import { SafetyOutlined, ReloadOutlined, ApiOutlined } from '@ant-design/icons';
import { configApi, SecurityConfig } from '../../../services/api';
import { handleError, showSuccess } from '../../../utils/errorHandler';

const { Text } = Typography;

/**
 * 安全设置页面组件
 */
export const SecuritySettings: React.FC = () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [securityConfig, setSecurityConfig] = useState<any>({});
  const [securityForm] = Form.useForm();
  const [savingSecurity, setSavingSecurity] = useState(false);
  const [advancedCollapse, setAdvancedCollapse] = useState<string[]>([]);

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
      handleError('加载安全配置失败');
    }
  };

  useEffect(() => {
    loadSecurityConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSaveSecurityConfig = async (values: SecurityConfig) => {
    setSavingSecurity(true);
    try {
      const currentConfig = await configApi.getConfig();
      const updateData = {
        ...currentConfig,
        security: values,
      };
      await configApi.updateConfig(updateData);
      showSuccess('安全配置已保存');
      setSecurityConfig(values);
    } catch (error) {
      handleError('保存安全配置失败');
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
              key: 'command',
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
                              securityForm.getFieldValue('whitelistEnabled');
                            if (
                              whitelistEnabled &&
                              (!value || value.trim() === '')
                            ) {
                              return Promise.reject(
                                new Error('启用白名单时必须配置命令白名单')
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
                          !securityForm.getFieldValue('whitelistEnabled')
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
                              securityForm.getFieldValue('blacklistEnabled');
                            if (
                              blacklistEnabled &&
                              (!value || value.trim() === '')
                            ) {
                              return Promise.reject(
                                new Error('启用黑名单时必须配置命令黑名单')
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
                          !securityForm.getFieldValue('blacklistEnabled')
                        }
                      />
                    </Form.Item>
                  </Col>
                </Row>
              ),
            },
            {
              key: 'advanced',
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
