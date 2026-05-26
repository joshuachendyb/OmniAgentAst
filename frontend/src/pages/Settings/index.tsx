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

import React, { useState, useEffect } from 'react';
import { Card, Tabs, Modal } from 'antd';
import {
  KeyOutlined,
  SafetyOutlined,
  DesktopOutlined,
} from '@ant-design/icons';
import HealthCheck from '../../components/HealthCheck';
import { ProviderSettings } from './components/ProviderSettings';
import { SecuritySettings } from './components/SecuritySettings';

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
 * 配置文件路径功能 [2026-02-28]
 *
 * 当前状态：
 * - handleOpenConfigDir 已实现并在第113行定义
 * - 在第168行已绑定到按钮点击事件
 *
 * @author 小欧
 * @update 2026-04-12 更新状态
 */
const Settings: React.FC = () => {
  const [activeKey, setActiveKey] = useState('model');
  const [isDirty, setIsDirty] = useState(false);
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
  const [pendingKey, setPendingKey] = useState<string>('');
  const [loadedTabs, setLoadedTabs] = useState<Set<string>>(new Set(['model']));

  const loadConfigInfo = async () => {
    try {
      console.log('📋 加载配置信息完成');
    } catch (error) {
      console.error('加载配置信息失败:', error);
    }
  };

  useEffect(() => {
    return () => undefined;
  }, []);

  useEffect(() => {
    loadConfigInfo();
  }, []);

  const handleTabChange = (key: string) => {
    if (isDirty) {
      setPendingKey(key);
      setConfirmModalVisible(true);
    } else {
      setActiveKey(key);
      setLoadedTabs((prev) => new Set(prev).add(key));
    }
  };

  const handleConfirmSwitch = () => {
    setIsDirty(false);
    setActiveKey(pendingKey);
    setConfirmModalVisible(false);
  };

  const handleCancelSwitch = () => {
    setConfirmModalVisible(false);
  };

  const tabItems = [
    {
      key: 'model',
      label: <span><KeyOutlined /> 模型配置</span>,
      children: <ProviderSettings shouldLoad={loadedTabs.has('model')} />,
    },
    {
      key: 'security',
      label: <span><SafetyOutlined /> 安全配置</span>,
      children: <SecuritySettings />,
    },
    {
      key: 'system',
      label: <span><DesktopOutlined /> 系统状态</span>,
      children: <HealthCheck />,
    },
  ];

  return (
    <div
      className="settings-page"
      style={{ padding: '25px', background: '#fff' }}
    >
      <Card style={{ marginTop: 0 }}>
        <div style={{ padding: '0 5px' }}>
          <Tabs activeKey={activeKey} onChange={handleTabChange} type="line" items={tabItems} />
        </div>
      </Card>

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
