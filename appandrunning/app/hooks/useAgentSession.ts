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
  sendPrompt: (prompt: string) => boolean;
}

export function useAgentSession(sessionId: string | null) {
  const [state, setState] = useState<AgentSessionState>({
    sessionId,
    status: 'idle',
    events: [],
    error: null,
    isConnected: false,
    websocketUrl: null,
    sendPrompt: () => false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const hasConnectedRef = useRef(false);
  const currentWsUrlRef = useRef<string | null>(null);
  const isConnectingRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);

  const handleMessage = useCallback((event: AgentEvent, sendFn: (prompt: string) => boolean) => {
    console.log('[WebSocket] Received event:', event.event);
    setState((prev) => ({
      ...prev,
      events: [...prev.events, event],
      status: event.data?.status || prev.status,
      sendPrompt: sendFn,
    }));

    // Keep polling active to detect follow-up prompts
  }, []);

  // Function to send a prompt via WebSocket
  const sendPrompt = useCallback((prompt: string): boolean => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[WebSocket] Cannot send prompt: not connected');
      return false;
    }

    try {
      const message = {
        type: 'prompt',
        message: prompt,
        timestamp: new Date().toISOString(),
      };
      wsRef.current.send(JSON.stringify(message));
      console.log('[WebSocket] Sent prompt:', prompt.substring(0, 100));
      return true;
    } catch (error) {
      console.error('[WebSocket] Error sending prompt:', error);
      return false;
    }
  }, []);

  // Connect to WebSocket
  const connectWebSocket = useCallback((sid: string, wsUrl: string, force = false) => {
    // If URL hasn't changed and we're already connected, skip
    if (!force && wsRef.current?.readyState === WebSocket.OPEN && currentWsUrlRef.current === wsUrl) {
      console.log('[WebSocket] Already connected to this URL');
      return;
    }

    // If we're currently connecting, skip
    if (isConnectingRef.current && !force) {
      console.log('[WebSocket] Connection already in progress');
      return;
    }

    // If URL has changed, close old connection
    if (currentWsUrlRef.current && currentWsUrlRef.current !== wsUrl) {
      console.log('[WebSocket] URL changed, closing old connection');
      console.log('[WebSocket] Old URL:', currentWsUrlRef.current);
      console.log('[WebSocket] New URL:', wsUrl);
      
      // Clear any pending reconnection attempts
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      hasConnectedRef.current = false;
      isConnectingRef.current = false;
      reconnectAttemptsRef.current = 0; // Reset retry counter for new URL
    }

    if (hasConnectedRef.current && !force) {
      console.log('[WebSocket] Already attempted connection');
      return;
    }

    console.log('[WebSocket] Connecting to:', wsUrl);
    hasConnectedRef.current = true;
    isConnectingRef.current = true;
    shouldReconnectRef.current = true; // Enable reconnection for this connection
    currentWsUrlRef.current = wsUrl;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WebSocket] Connected successfully');
        isConnectingRef.current = false;
        reconnectAttemptsRef.current = 0; // Reset retry counter on successful connection
        setState((prev) => ({
          ...prev,
          isConnected: true,
          error: null,
          sendPrompt,
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data, sendPrompt);
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        isConnectingRef.current = false;
        setState((prev) => ({
          ...prev,
          error: 'WebSocket connection error',
          isConnected: false,
          sendPrompt,
        }));
      };

      ws.onclose = () => {
        console.log('[WebSocket] Connection closed');
        isConnectingRef.current = false;
        setState((prev) => ({
          ...prev,
          isConnected: false,
          sendPrompt,
        }));

        // Retry indefinitely if we should reconnect
        if (sid && currentWsUrlRef.current && shouldReconnectRef.current) {
          reconnectAttemptsRef.current += 1;
          
          // Exponential backoff with cap at 30 seconds
          const delay = Math.min(1000 * Math.pow(2, Math.min(reconnectAttemptsRef.current - 1, 4)), 30000);
          
          console.log(`[WebSocket] Connection closed. Reconnecting in ${delay / 1000}s (attempt ${reconnectAttemptsRef.current})...`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (shouldReconnectRef.current && currentWsUrlRef.current) {
              hasConnectedRef.current = false;
              connectWebSocket(sid, currentWsUrlRef.current, true);
            }
          }, delay);
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
      isConnectingRef.current = false;
      setState((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Connection failed',
        sendPrompt,
      }));
    }
  }, [handleMessage, sendPrompt]);

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
          sendPrompt,
        }));

        // Connect to websocket if we have a URL
        if (status.websocket_url) {
          const isCurrentlyConnected = wsRef.current?.readyState === WebSocket.OPEN;
          const isSameUrl = currentWsUrlRef.current === status.websocket_url;
          
          // Only reconnect if URL changed AND we're not already connected to new URL
          if (!isSameUrl && currentWsUrlRef.current) {
            console.log('[Session] WebSocket URL changed, reconnecting...');
            connectWebSocket(sessionId, status.websocket_url);
          }
          // Or if we haven't connected yet and not currently connecting
          else if (!isCurrentlyConnected && !hasConnectedRef.current && !isConnectingRef.current) {
            console.log('[Session] Got websocket URL, connecting...');
            connectWebSocket(sessionId, status.websocket_url);
          }
          // Otherwise, skip - already connected or connecting
          else if (isCurrentlyConnected && isSameUrl) {
            // All good, no action needed
          }
        }

        // Keep polling even when completed to detect follow-up prompts
        // The polling will be cleaned up when the component unmounts
      } catch (error) {
        console.error('[Session] Failed to fetch status:', error);
      }
    };

    // Initial fetch
    fetchSessionStatus();
    
    // Poll less frequently once we have the basics
    pollIntervalRef.current = setInterval(fetchSessionStatus, 3000);

    return () => {
      // Disable reconnection when component unmounts
      shouldReconnectRef.current = false;
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      hasConnectedRef.current = false;
      currentWsUrlRef.current = null;
      isConnectingRef.current = false;
      reconnectAttemptsRef.current = 0;
    };
  }, [sessionId, connectWebSocket]);

  return state;
}

