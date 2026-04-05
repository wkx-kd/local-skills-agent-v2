import { useState } from 'react';
import { Card, Tabs, Typography } from 'antd';
import LoginForm from '../components/Auth/LoginForm';
import RegisterForm from '../components/Auth/RegisterForm';

const { Title } = Typography;

export default function LoginPage() {
  const [activeTab, setActiveTab] = useState('login');

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#131314',
      }}
    >
      <Card 
        style={{ 
          width: 420, 
          background: '#1e1f20',
          borderRadius: 24,
          border: 'none',
          padding: '24px 10px'
        }}
      >
        <Title level={2} style={{ textAlign: 'center', marginBottom: 32, color: '#e3e3e3' }}>
          LOCAL SKILLS AGENT
        </Title>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          centered
          items={[
            { key: 'login', label: 'SYS_LOGIN', children: <LoginForm /> },
            { key: 'register', label: 'SYS_REGISTER', children: <RegisterForm onSuccess={() => setActiveTab('login')} /> },
          ]}
        />
      </Card>
    </div>
  );
}
