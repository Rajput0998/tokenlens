import { useEffect, useRef, useCallback, useState } from "react";

interface UseWebSocketOptions {
  url: string;
  onMessage?: (data: unknown) => void;
  reconnect?: boolean;
  maxRetries?: number;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: unknown | null;
  reconnectAttempt: number;
  send: (data: unknown) => void;
}

export function useWebSocket({
  url,
  onMessage,
  reconnect = true,
  maxRetries = 10,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<unknown | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    let attempt = 0;

    function getBackoffDelay(n: number) {
      return Math.min(1000 * Math.pow(2, n), 30000);
    }

    function connect() {
      if (!mountedRef.current) return;

      try {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = url.startsWith("ws") ? url : `${protocol}//${window.location.host}${url}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!mountedRef.current) return;
          setIsConnected(true);
          attempt = 0;
          setReconnectAttempt(0);
        };

        ws.onmessage = (event) => {
          if (!mountedRef.current) return;
          try {
            const data = JSON.parse(event.data);
            setLastMessage(data);
            onMessageRef.current?.(data);
          } catch {
            // Non-JSON message, ignore
          }
        };

        ws.onclose = () => {
          if (!mountedRef.current) return;
          setIsConnected(false);
          wsRef.current = null;

          if (reconnect && attempt < maxRetries) {
            const delay = getBackoffDelay(attempt);
            attempt++;
            setReconnectAttempt(attempt);
            reconnectTimeoutRef.current = setTimeout(() => {
              if (mountedRef.current) {
                connect();
              }
            }, delay);
          }
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        // Connection failed
      }
    }

    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url, reconnect, maxRetries]);

  return { isConnected, lastMessage, reconnectAttempt, send };
}
