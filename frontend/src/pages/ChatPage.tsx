import { useState } from 'react';
import { Layout, Typography, Button, Dropdown, Drawer } from 'antd';
import { UserOutlined, LogoutOutlined, MenuOutlined, PlusOutlined } from '@ant-design/icons';
import ConversationList from '../components/Sidebar/ConversationList';
import SkillPanel from '../components/Sidebar/SkillPanel';
import ChatWindow from '../components/Chat/ChatWindow';
import InputArea from '../components/Chat/InputArea';
import { useAuth } from '../hooks/useAuth';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';
import { useSkillStore } from '../stores/skillStore';
import { useIsMobile } from '../hooks/useIsMobile';

const { Sider, Content, Header } = Layout;

export default function ChatPage() {
  useAuth();
  const { logout } = useAuthStore();
  const { createConversation, fetchMessages } = useChatStore();
  const { selectedGroupId, skillGroups } = useSkillStore();
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const handleNewChat = async () => {
    const conv = await createConversation({ skill_group_id: selectedGroupId ?? null });
    await fetchMessages(conv.id);
    if (isMobile) setDrawerOpen(false);
  };

  const sidebarContent = (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {isMobile && (
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #444746' }}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            block
            onClick={handleNewChat}
          >
            新对话{selectedGroupId ? `（${skillGroups.find(g => g.id === selectedGroupId)?.name ?? ''}）` : ''}
          </Button>
        </div>
      )}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <ConversationList onSelect={() => { if (isMobile) setDrawerOpen(false); }} />
      </div>
      <SkillPanel />
    </div>
  );

  return (
    <Layout style={{ height: '100vh', background: '#131314' }}>
      {/* 桌面端侧边栏 */}
      {!isMobile && (
        <Sider
          width={260}
          style={{
            background: '#1e1f20',
            borderRight: 'none',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {sidebarContent}
        </Sider>
      )}

      {/* 移动端抽屉 */}
      {isMobile && (
        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          style={{ width: 280 }}
          styles={{
            header: { display: 'none' },
            body: { padding: 0, background: '#1e1f20', display: 'flex', flexDirection: 'column' },
            wrapper: { background: '#1e1f20' },
          }}
        >
          {sidebarContent}
        </Drawer>
      )}

      <Layout style={{ background: 'transparent' }}>
        <Header
          style={{
            background: 'transparent',
            padding: isMobile ? '0 12px' : '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 56,
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {isMobile && (
              <Button
                shape="circle"
                type="text"
                icon={<MenuOutlined style={{ color: '#e3e3e3' }} />}
                onClick={() => setDrawerOpen(true)}
                style={{ background: '#2a2b2f', border: 'none' }}
              />
            )}
            <Typography.Text style={{ fontSize: isMobile ? '1rem' : '1.25rem', color: '#e3e3e3' }}>
              Local Skills Agent
            </Typography.Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {isMobile && (
              <Button
                shape="circle"
                type="text"
                icon={<PlusOutlined style={{ color: '#e3e3e3' }} />}
                onClick={handleNewChat}
                style={{ background: '#2a2b2f', border: 'none' }}
              />
            )}
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'logout',
                    icon: <LogoutOutlined />,
                    label: 'Sign out',
                    onClick: logout,
                  },
                ],
              }}
              placement="bottomRight"
            >
              <Button
                shape="circle"
                icon={<UserOutlined />}
                style={{ background: '#2a2b2f', border: 'none', color: '#e3e3e3' }}
              />
            </Dropdown>
          </div>
        </Header>
        <Content style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div
            className="chat-container"
            style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
          >
            <ChatWindow />
            <InputArea />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
