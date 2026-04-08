import { useEffect } from 'react';
import { List, Button, Popconfirm, Typography, Tag } from 'antd';
import { PlusOutlined, DeleteOutlined, MessageOutlined } from '@ant-design/icons';
import { useChatStore } from '../../stores/chatStore';
import { useSkillStore } from '../../stores/skillStore';

const { Text } = Typography;

interface Props {
  onSelect?: () => void;
}

export default function ConversationList({ onSelect }: Props) {
  const {
    conversations, currentConversation,
    fetchConversations, setCurrentConversation,
    createConversation, deleteConversation, fetchMessages,
  } = useChatStore();

  const { selectedGroupId, skillGroups } = useSkillStore();

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleSelect = async (conv: typeof conversations[0]) => {
    setCurrentConversation(conv);
    await fetchMessages(conv.id);
    onSelect?.();
  };

  const handleCreate = async () => {
    // 将当前侧边栏选中的 skill 分组关联到新会话
    const conv = await createConversation({
      skill_group_id: selectedGroupId ?? null,
    });
    await fetchMessages(conv.id);
  };

  // 获取会话关联的分组名称
  const getGroupName = (conv: typeof conversations[0]) => {
    if (!conv.skill_group_id) return null;
    return skillGroups.find(g => g.id === conv.skill_group_id)?.name ?? null;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #444746' }}>
        <Button type="primary" icon={<PlusOutlined />} block onClick={handleCreate}>
          新对话{selectedGroupId ? `（${skillGroups.find(g => g.id === selectedGroupId)?.name ?? ''}）` : ''}
        </Button>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <List
          dataSource={conversations}
          renderItem={(conv) => {
            const groupName = getGroupName(conv);
            return (
              <List.Item
                onClick={() => handleSelect(conv)}
                style={{
                  cursor: 'pointer',
                  padding: '8px 16px',
                  borderRadius: 8,
                  margin: '2px 8px',
                  background: currentConversation?.id === conv.id ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                }}
                actions={[
                  <Popconfirm
                    title="确定删除此对话？"
                    onConfirm={(e) => { e?.stopPropagation(); deleteConversation(conv.id); }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  avatar={<MessageOutlined />}
                  title={<Text ellipsis style={{ color: '#e3e3e3' }}>{conv.title}</Text>}
                  description={
                    <div>
                      {groupName && (
                        <Tag color="blue" style={{ fontSize: 10, marginBottom: 2 }}>{groupName}</Tag>
                      )}
                      <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                        {new Date(conv.updated_at).toLocaleString()}
                      </Text>
                    </div>
                  }
                />
              </List.Item>
            );
          }}
        />
      </div>
    </div>
  );
}
