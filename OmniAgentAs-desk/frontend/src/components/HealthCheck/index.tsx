import React, { useState, useEffect } from 'react';
import { Card, Tag, Button, Input, message } from 'antd';
import { healthApi, EchoResponse } from '../../services/api';

const HealthCheck: React.FC = () => {
  const [status, setStatus] = useState<string>('checking');
  const [version, setVersion] = useState<string>('');
  const [testMessage, setTestMessage] = useState<string>('');
  const [echoResponse, setEchoResponse] = useState<EchoResponse | null>(null);

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const data = await healthApi.checkHealth();
      setStatus(data.status);
      setVersion(data.version);
    } catch (error) {
      setStatus('error');
      console.error('Health check failed:', error);
    }
  };

  const handleEchoTest = async () => {
    if (!testMessage.trim()) {
      message.warning('请输入测试消息');
      return;
    }
    
    try {
      const response = await healthApi.echo(testMessage);
      setEchoResponse(response);
      message.success('通信测试成功');
    } catch (error) {
      message.error('通信测试失败');
      console.error('Echo test failed:', error);
    }
  };

  return (
    <Card title="系统状态" style={{ marginBottom: 16 }}>
      <div style={{ marginBottom: 16 }}>
        <span style={{ marginRight: 8 }}>后端状态:</span>
        {status === 'ok' ? (
          <Tag color="success">正常</Tag>
        ) : status === 'checking' ? (
          <Tag color="processing">检查中...</Tag>
        ) : (
          <Tag color="error">异常</Tag>
        )}
        {version && <span style={{ marginLeft: 16 }}>版本: {version}</span>}
      </div>

      <div style={{ marginBottom: 16 }}>
        <h4>通信测试</h4>
        <Input
          placeholder="输入测试消息"
          value={testMessage}
          onChange={(e) => setTestMessage(e.target.value)}
          style={{ width: 300, marginRight: 8 }}
          onPressEnter={handleEchoTest}
        />
        <Button type="primary" onClick={handleEchoTest}>
          发送测试
        </Button>
      </div>

      {echoResponse && (
        <div style={{ background: '#f6ffed', padding: 12, borderRadius: 4 }}>
          <div><strong>后端回复:</strong> {echoResponse.received}</div>
          <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
            时间戳: {new Date(echoResponse.timestamp).toLocaleString()}
          </div>
        </div>
      )}

      <Button onClick={checkHealth} style={{ marginTop: 16 }}>
        重新检查
      </Button>
    </Card>
  );
};

export default HealthCheck;
