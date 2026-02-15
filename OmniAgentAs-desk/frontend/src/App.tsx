import React from 'react';
import { Layout, Typography, Space } from 'antd';
import HealthCheck from './components/HealthCheck';
import Chat from './components/Chat';

const { Header, Content } = Layout;
const { Title } = Typography;

const App: React.FC = () => {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px' }}>
        <Title level={3} style={{ color: 'white', margin: '16px 0' }}>
          OmniAgentAst. 桌面版
        </Title>
      </Header>
      
      <Content style={{ padding: 24, maxWidth: 1000, margin: '0 auto', width: '100%' }}>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <HealthCheck />
          <Chat />
          
          <div style={{ padding: 16, background: '#f0f2f5', borderRadius: 8 }}>
            <h3>欢迎使用 OmniAgentAst</h3>
            <p>这是一个AI智能助手桌面应用。</p>
            <p>当前阶段: 1.2 AI模型接入 (已完成)</p>
            <p>支持的AI提供商: 智谱GLM, OpenCode Zen</p>
          </div>
        </Space>
      </Content>
    </Layout>
  );
};

export default App;
