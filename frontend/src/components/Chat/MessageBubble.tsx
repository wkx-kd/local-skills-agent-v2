import { Typography, Tag } from 'antd';
import { UserOutlined, RobotOutlined, ToolOutlined } from '@ant-design/icons';
import type { Message } from '../../types/chat';
import MarkdownRenderer from '../common/MarkdownRenderer';

const { Text, Paragraph } = Typography;

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';

  const getText = () => {
    if (typeof message.content === 'string') return message.content;
    if (Array.isArray(message.content)) {
      return message.content
        .filter((block: any) => block.type === 'text')
        .map((block: any) => block.text)
        .join('\n');
    }
    return JSON.stringify(message.content);
  };

  const icon = isUser ? <UserOutlined /> : isTool ? <ToolOutlined /> : <RobotOutlined />;
  const label = isUser ? 'User' : isTool ? 'Tool' : 'Agent';
  const bgColor = isUser ? '#2a2b2f' : 'transparent';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 16,
      }}
    >
      <Tag icon={icon} style={{ marginBottom: 4 }}>
        {label}
      </Tag>
      <div
        style={{
          background: bgColor,
          borderRadius: 24,
          padding: isUser ? '12px 16px' : '4px 0',
          maxWidth: '80%',
          wordBreak: 'break-word',
          fontSize: '1rem',
          lineHeight: '1.5',
          whiteSpace: isUser || isTool ? 'pre-wrap' : 'normal',
        }}
      >
        {isUser || isTool ? (
          <Paragraph style={{ margin: 0, color: '#e3e3e3' }}>{getText()}</Paragraph>
        ) : (
          <MarkdownRenderer content={getText()} />
        )}
      </div>
      <Text type="secondary" style={{ fontSize: 11, marginTop: 2 }}>
        {new Date(message.created_at).toLocaleTimeString()}
      </Text>
    </div>
  );
}
