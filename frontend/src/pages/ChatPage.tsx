import { Layout, Typography, Button, Dropdown } from 'antd';
import { UserOutlined, LogoutOutlined } from '@ant-design/icons';
import ConversationList from '../components/Sidebar/ConversationList';
import SkillPanel from '../components/Sidebar/SkillPanel';
import ChatWindow from '../components/Chat/ChatWindow';
import InputArea from '../components/Chat/InputArea';
import { useAuth } from '../hooks/useAuth';
import { useAuthStore } from '../stores/authStore';

const { Sider, Content, Header } = Layout;

export default function ChatPage() {
  useAuth();
  const { logout } = useAuthStore();

  return (
    <Layout style={{ height: '100vh', background: '#131314' }}>
      <Sider 
        width={260} 
        style={{ 
          background: '#1e1f20',
          borderRight: 'none',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <ConversationList />
          <SkillPanel />
        </div>
      </Sider>
      <Layout style={{ background: 'transparent' }}>
        <Header
          style={{
            background: 'transparent',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 64,
          }}
        >
          <Typography.Text style={{ fontSize: '1.25rem', color: '#e3e3e3' }}>
            Local Skills Agent
          </Typography.Text>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: 'Sign out',
                  onClick: logout
                }
              ]
            }}
            placement="bottomRight"
          >
            <Button shape="circle" icon={<UserOutlined />} style={{ background: '#2a2b2f', border: 'none', color: '#e3e3e3' }} />
          </Dropdown>
        </Header>
        <Content style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="chat-container" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <ChatWindow />
            <InputArea />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
