/**
 * ExecutionPanel组件 - 执行过程可视化
 * 
 * 功能：展示ReAct循环的执行步骤，包括思考、工具调用、观察结果
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import React, { useState } from 'react';
import { Collapse, Timeline, Card, Tag, Spin, Button, Space, Tooltip, Typography } from 'antd';
import {
  CaretRightOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  CodeOutlined,
  EyeOutlined,
  ThunderboltOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import type { ExecutionStep } from '../../services/api';

const { Text } = Typography;

interface ExecutionPanelProps {
  steps: ExecutionStep[];
  isActive?: boolean;
  totalTime?: number; // 毫秒
  onViewRaw?: () => void;
  onExport?: () => void;
}

/**
 * 执行过程面板组件
 * 
 * 设计要点：
 * - 默认折叠，点击展开
 * - 时间线展示执行步骤
 * - 不同步骤类型用不同颜色标识
 * - 支持查看原始数据和导出
 * 
 * @param steps - 执行步骤数组
 * @param isActive - 是否正在执行
 * @param totalTime - 总耗时（毫秒）
 */
const ExecutionPanel: React.FC<ExecutionPanelProps> = ({
  steps,
  isActive = false,
  totalTime,
  onViewRaw,
  onExport,
}) => {
  const [activeKey, setActiveKey] = useState<string | string[]>('1');

  /**
   * 获取步骤图标
   */
  const getStepIcon = (type: ExecutionStep['type']) => {
    switch (type) {
      case 'thought':
        return <ThunderboltOutlined style={{ color: '#faad14' }} />;
      case 'action':
        return <CodeOutlined style={{ color: '#1890ff' }} />;
      case 'observation':
        return <EyeOutlined style={{ color: '#52c41a' }} />;
      case 'final':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return <CaretRightOutlined />;
    }
  };

  /**
   * 获取步骤颜色
   */
  const getStepColor = (type: ExecutionStep['type']) => {
    switch (type) {
      case 'thought':
        return '#faad14';
      case 'action':
        return '#1890ff';
      case 'observation':
        return '#52c41a';
      case 'final':
        return '#52c41a';
      case 'error':
        return '#ff4d4f';
      default:
        return '#999';
    }
  };

  /**
   * 获取步骤标签
   */
  const getStepLabel = (type: ExecutionStep['type']) => {
    switch (type) {
      case 'thought':
        return '思考';
      case 'action':
        return '行动';
      case 'observation':
        return '观察';
      case 'final':
        return '完成';
      case 'error':
        return '错误';
      default:
        return '步骤';
    }
  };

  /**
   * 格式化耗时
   */
  const formatDuration = (ms?: number) => {
    if (!ms) return '';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  /**
   * 渲染步骤内容
   */
  const renderStepContent = (step: ExecutionStep, _index: number) => {
    switch (step.type) {
      case 'thought':
        return (
          <div style={{ color: '#666', fontStyle: 'italic', padding: '8px 0' }}>
            {step.content}
          </div>
        );

      case 'action':
        return (
          <Card 
            size="small" 
            title={
              <Space>
                <CodeOutlined style={{ color: '#1890ff' }} />
                <span>{step.tool}</span>
              </Space>
            }
            style={{ marginTop: 8, background: '#f6ffed' }}
            bodyStyle={{ padding: 12 }}
          >
            <div style={{ marginBottom: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>参数：</Text>
              <pre
                style={{
                  margin: '4px 0 0 0',
                  padding: 8,
                  background: '#fff',
                  borderRadius: 4,
                  fontSize: 11,
                  overflow: 'auto',
                  maxHeight: 150,
                }}
              >
                {JSON.stringify(step.params, null, 2)}
              </pre>
            </div>
            {step.result && (
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>结果：</Text>
                <div
                  style={{
                    marginTop: 4,
                    padding: 8,
                    background: '#fff',
                    borderRadius: 4,
                    color: '#52c41a',
                    fontSize: 12,
                  }}
                >
                  {typeof step.result === 'string' 
                    ? step.result 
                    : JSON.stringify(step.result)}
                </div>
              </div>
            )}
          </Card>
        );

      case 'observation':
        return (
          <div
            style={{
              padding: 12,
              background: '#f6ffed',
              borderRadius: 4,
              borderLeft: '3px solid #52c41a',
              marginTop: 8,
            }}
          >
            <EyeOutlined style={{ color: '#52c41a', marginRight: 8 }} />
            <span style={{ color: '#389e0d' }}>
              {typeof step.result === 'string' 
                ? step.result 
                : JSON.stringify(step.result)}
            </span>
          </div>
        );

      case 'final':
        return (
          <div
            style={{
              padding: 12,
              background: '#f6ffed',
              borderRadius: 4,
              borderLeft: '3px solid #52c41a',
              marginTop: 8,
            }}
          >
            <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
            <span>{step.content}</span>
          </div>
        );

      case 'error':
        return (
          <div
            style={{
              padding: 12,
              background: '#fff1f0',
              borderRadius: 4,
              borderLeft: '3px solid #ff4d4f',
              marginTop: 8,
              color: '#cf1322',
            }}
          >
            <CloseCircleOutlined style={{ marginRight: 8 }} />
            <span>{step.content}</span>
          </div>
        );

      default:
        return null;
    }
  };

  // 计算步骤数
  const stepCount = steps.length;
  const hasError = steps.some(s => s.type === 'error');

  return (
    <Collapse
      activeKey={activeKey}
      onChange={setActiveKey}
      style={{
        marginTop: 12,
        background: '#fafafa',
        borderRadius: 8,
        overflow: 'hidden',
      }}
      items={[
        {
          key: '1',
          label: (
            <Space>
              {isActive ? (
                <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} />
              ) : hasError ? (
                <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
              ) : (
                <CheckCircleOutlined style={{ color: '#52c41a' }} />
              )}
              <span>
                {isActive ? '正在执行' : '执行详情'}
                {stepCount > 0 && ` (${stepCount}步${totalTime ? `，耗时${formatDuration(totalTime)}` : ''})`}
              </span>
              {hasError && <Tag color="error">有错误</Tag>}
            </Space>
          ),
          extra: (
            <Space onClick={(e) => e.stopPropagation()}>
              {onViewRaw && (
                <Tooltip title="查看原始数据">
                  <Button
                    type="text"
                    size="small"
                    icon={<CodeOutlined />}
                    onClick={onViewRaw}
                  />
                </Tooltip>
              )}
              {onExport && (
                <Tooltip title="导出">
                  <Button
                    type="text"
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={onExport}
                  />
                </Tooltip>
              )}
            </Space>
          ),
          children: (
            <Timeline
              mode="left"
              style={{ padding: '16px 8px' }}
            >
              {steps.map((step, index) => (
                <Timeline.Item
                  key={index}
                  dot={getStepIcon(step.type)}
                  color={getStepColor(step.type)}
                  label={
                    <Tag 
                      color={getStepColor(step.type)}
                      style={{ fontSize: 11 }}
                    >
                      {getStepLabel(step.type)}
                    </Tag>
                  }
                >
                  {renderStepContent(step, index)}
                </Timeline.Item>
              ))}
              {isActive && (
                <Timeline.Item
                  dot={<LoadingOutlined spin />}
                  color="#1890ff"
                >
                  <span style={{ color: '#1890ff' }}>执行中...</span>
                </Timeline.Item>
              )}
            </Timeline>
          ),
        },
      ]}
    />
  );
};

export default ExecutionPanel;
