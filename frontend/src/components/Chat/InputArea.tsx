import { useState } from 'react';
import { Input, Button, Upload, Tooltip, Tag } from 'antd';
import { SendOutlined, PaperClipOutlined, StopOutlined, LoadingOutlined, GlobalOutlined } from '@ant-design/icons';
import { useChatStore } from '../../stores/chatStore';
import { useChat } from '../../hooks/useChat';
import { filesApi } from '../../api/files';

const { TextArea } = Input;

export default function InputArea() {
  const [text, setText] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<Array<{ id: string; name: string }>>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [useWebSearch, setUseWebSearch] = useState(false);

  const { isGenerating, currentConversation } = useChatStore();
  const { sendMessage, stopGeneration } = useChat();

  const handleUpload = async (file: File) => {
    if (!currentConversation) return false;
    setIsUploading(true);
    try {
      const res = await filesApi.upload(file, currentConversation.id);
      setAttachedFiles(prev => [...prev, { id: res.data.id, name: res.data.filename }]);
    } catch (err) {
      console.error('File upload failed:', err);
    } finally {
      setIsUploading(false);
    }
    return false;
  };

  const handleSend = () => {
    const content = text.trim();
    if (!content || !currentConversation) return;
    const fileIds = attachedFiles.map(f => f.id);
    sendMessage(content, fileIds.length > 0 ? fileIds : undefined, useWebSearch);
    setText('');
    setAttachedFiles([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ padding: '0 24px 24px', background: 'transparent' }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          background: '#1e1f20',
          borderRadius: 32,
          padding: '8px 16px',
        }}
      >
        {attachedFiles.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, paddingTop: 4 }}>
            {attachedFiles.map(f => (
              <Tag
                key={f.id}
                closable
                onClose={() => setAttachedFiles(prev => prev.filter(x => x.id !== f.id))}
                style={{ margin: 0 }}
              >
                {f.name}
              </Tag>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <Tooltip title={useWebSearch ? "Disable Web Search" : "Enable Web Search"}>
            <Button
              shape="circle"
              type="text"
              icon={
                <GlobalOutlined style={{ color: useWebSearch ? '#8ab4f8' : '#e3e3e3' }} />
              }
              onClick={() => setUseWebSearch(!useWebSearch)}
              disabled={!currentConversation || isGenerating}
            />
          </Tooltip>
          <Tooltip title="Attach File">
            <Upload
              showUploadList={false}
              beforeUpload={handleUpload}
              accept=".txt,.pdf,.md,.csv,.json,.py,.docx,.xlsx"
            >
              <Button
                shape="circle"
                type="text"
                icon={
                  isUploading
                    ? <LoadingOutlined style={{ color: '#e3e3e3' }} />
                    : <PaperClipOutlined style={{ color: '#e3e3e3' }} />
                }
                disabled={!currentConversation || isUploading || isGenerating}
              />
            </Upload>
          </Tooltip>
          <TextArea
            className="pill-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={currentConversation ? 'Ask Local Skills Agent...' : 'Select or create a conversation'}
            autoSize={{ minRows: 1, maxRows: 6 }}
            disabled={!currentConversation || isGenerating}
            style={{ flex: 1, color: '#e3e3e3' }}
          />
          {isGenerating ? (
            <Button shape="circle" type="text" danger icon={<StopOutlined />} onClick={stopGeneration} />
          ) : (
            <Button
              shape="circle"
              type="text"
              icon={<SendOutlined style={{ color: text.trim() ? '#8ab4f8' : '#5f6368' }} />}
              onClick={handleSend}
              disabled={!text.trim() || !currentConversation}
            />
          )}
        </div>
      </div>
    </div>
  );
}
