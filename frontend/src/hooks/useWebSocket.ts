import { useRef, useCallback } from 'react';
import type { WSMessageSend, WSMessageReceive } from '../types/chat';

interface UseWebSocketOptions {
  onMessage: (data: WSMessageReceive) => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);

  // Returns a promise that resolves when the connection is open
  const connect = useCallback((conversationId: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const token = localStorage.getItem('access_token');
      if (!token) { reject(new Error('No token')); return; }

      // Close any existing connection first
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/chat/ws/${conversationId}?token=${token}`;

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        wsRef.current = ws;
        resolve();
      };

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
        reject(error);
      };
    });
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
