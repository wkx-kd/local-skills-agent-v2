import { useRef, useCallback } from 'react';
import type { WSMessageSend, WSMessageReceive } from '../types/chat';

interface UseWebSocketOptions {
  onMessage: (data: WSMessageReceive) => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback((conversationId: string) => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/chat/ws/${conversationId}?token=${token}`;

    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data: WSMessageReceive = JSON.parse(event.data);
        options.onMessage(data);
      } catch {
        console.error('Failed to parse WS message:', event.data);
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      options.onClose?.();
    };

    ws.onerror = (error) => {
      options.onError?.(error);
    };

    wsRef.current = ws;
  }, [options]);

  const send = useCallback((data: WSMessageSend) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { connect, send, disconnect, ws: wsRef };
}
