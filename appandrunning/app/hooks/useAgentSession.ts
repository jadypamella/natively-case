/**
 * React hook for managing agent sessions with WebSocket updates
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient, AgentEvent, SessionStatus } from '../lib/api-client';

export interface AgentSessionState {
  sessionId: string | null;
  status: string;
  events: AgentEvent[];
  error: string | null;
  isConnected: boolean;
  websocketUrl: string | null;
}

export function useAgentSession(sessionId: string | null) {
  const [state, setState] = useState<AgentSessionState>({
    sessionId,
    status: 'idle',
    events: [],
    error: null,
    isConnected: false,
    websocketUrl: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const hasConnectedRef = useRef(false);

  const handleMessage = useCallback((event: AgentEvent) => {
    console.log('[WebSocket] Received event:', event.event);
    setState((prev) => ({
      ...prev,
      events: [...prev.events, event],
      status: event.data?.status || prev.status,
    }));

    if (event.event === 'agent_complete' || event.event === 'session_complete') {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }
  }, []);

  // Connect to WebSocket
  const connectWebSocket = useCallback((sid: string, wsUrl: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('[WebSocket] Already connected');
      return;
    }

    if (hasConnectedRef.current) {
      console.log('[WebSocket] Already attempted connection');
      return;
    }

    console.log('[WebSocket] Connecting to:', wsUrl);
    hasConnectedRef.current = true;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WebSocket] Connected successfully');
        setState((prev) => ({
          ...prev,
          isConnected: true,
          error: null,
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setState((prev) => ({
          ...prev,
          error: 'WebSocket connection error',
          isConnected: false,
        }));
      };

      ws.onclose = () => {
        console.log('[WebSocket] Connection closed');
        setState((prev) => ({
          ...prev,
          isConnected: false,
        }));

        // Try to reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          if (sid && wsUrl) {
            hasConnectedRef.current = false;
            connectWebSocket(sid, wsUrl);
          }
        }, 3000);
      };
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
      setState((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Connection failed',
      }));
    }
  }, [handleMessage]);

  // Poll for session status to get websocket URL
  useEffect(() => {
    if (!sessionId) return;

    const fetchSessionStatus = async () => {
      try {
        const status = await apiClient.getSession(sessionId);
        
        setState((prev) => ({
          ...prev,
          status: status.status,
          websocketUrl: status.websocket_url || prev.websocketUrl,
        }));

        // Connect to websocket if we have a URL and haven't connected yet
        if (status.websocket_url && !wsRef.current && !hasConnectedRef.current) {
          console.log('[Session] Got websocket URL, connecting...');
          connectWebSocket(sessionId, status.websocket_url);
        }

        // Stop polling if completed
        if (status.status === 'completed' || status.status === 'error') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      } catch (error) {
        console.error('[Session] Failed to fetch status:', error);
      }
    };

    fetchSessionStatus();
    pollIntervalRef.current = setInterval(fetchSessionStatus, 2000);

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      hasConnectedRef.current = false;
    };
  }, [sessionId, connectWebSocket]);

  return state;
}
