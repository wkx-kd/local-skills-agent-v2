import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface Props {
  content: string;
}

export default function MarkdownRenderer({ content }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          return match ? (
            <SyntaxHighlighter
              style={oneDark as any}
              language={match[1]}
              PreTag="div"
              customStyle={{ borderRadius: 8, fontSize: '0.875rem', margin: '8px 0' }}
            >
              {String(children).replace(/\n$/, '')}
            </SyntaxHighlighter>
          ) : (
            <code
              style={{
                background: 'rgba(255,255,255,0.1)',
                padding: '2px 6px',
                borderRadius: 4,
                fontFamily: 'monospace',
                fontSize: '0.875em',
              }}
              {...props}
            >
              {children}
            </code>
          );
        },
        p: ({ children }) => (
          <p style={{ margin: '0 0 8px', color: '#e3e3e3', lineHeight: 1.6 }}>{children}</p>
        ),
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: '#8ab4f8' }}>
            {children}
          </a>
        ),
        ul: ({ children }) => (
          <ul style={{ margin: '0 0 8px', paddingLeft: 20, color: '#e3e3e3' }}>{children}</ul>
        ),
        ol: ({ children }) => (
          <ol style={{ margin: '0 0 8px', paddingLeft: 20, color: '#e3e3e3' }}>{children}</ol>
        ),
        li: ({ children }) => <li style={{ marginBottom: 4 }}>{children}</li>,
        h1: ({ children }) => <h1 style={{ color: '#e3e3e3', margin: '12px 0 6px' }}>{children}</h1>,
        h2: ({ children }) => <h2 style={{ color: '#e3e3e3', margin: '10px 0 5px' }}>{children}</h2>,
        h3: ({ children }) => <h3 style={{ color: '#e3e3e3', margin: '8px 0 4px' }}>{children}</h3>,
        blockquote: ({ children }) => (
          <blockquote
            style={{
              borderLeft: '3px solid #5f6368',
              margin: '8px 0',
              paddingLeft: 12,
              color: '#9aa0a6',
            }}
          >
            {children}
          </blockquote>
        ),
        hr: () => <hr style={{ border: 'none', borderTop: '1px solid #3c4043', margin: '12px 0' }} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
