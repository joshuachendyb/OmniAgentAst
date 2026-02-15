import React from 'react';
import { Layout, Typography } from 'antd';
import HealthCheck from './components/HealthCheck';

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
      
      <Content style={{ padding: 24, maxWidth: 800, margin: '0 auto', width: '100%' }}>
        <HealthCheck />
        
        <div style={{ marginTop: 24, padding: 16, background: '#f0f2f5', borderRadius: 8 }}>
          <h3>欢迎使用 OmniAgentAst</h3>
          <p>这是一个AI智能助手桌面应用。</p>
          <p>当前阶段: 1.1 基础架构搭建</p>
        </div>
      </Content>
    </Layout>
  );
};

export default App;
