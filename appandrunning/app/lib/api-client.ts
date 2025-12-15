/**
 * API Client for Website Builder Modal API
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ChatRequest {
  session_id?: string;
  message: string;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  status: string;
  sandbox_id?: string;
  websocket_url?: string;
  dev_url?: string;
}

export interface SessionStatus {
  session_id: string;
  status: string;
  sandbox_id?: string;
  created_at: string;
  last_activity: string;
  websocket_url?: string;
  dev_url?: string;
}

export interface AgentEvent {
  event: string;
  timestamp: string;
  data: Record<string, any>;
}

export class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Send a chat message and optionally start a new session
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Get session status
   */
  async getSession(sessionId: string): Promise<SessionStatus> {
    const response = await fetch(`${this.baseUrl}/api/sessions/${sessionId}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  /**
   * List all sessions
   */
  async listSessions(): Promise<{ sessions: SessionStatus[]; total: number }> {
    const response = await fetch(`${this.baseUrl}/api/sessions`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Delete a session
   */
  async deleteSession(sessionId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/sessions/${sessionId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  /**
   * Connect to WebSocket for real-time updates
   */
  connectWebSocket(
    sessionId: string,
    websocketUrl: string | null,
    onMessage: (event: AgentEvent) => void,
    onError?: (error: Event) => void,
    onClose?: () => void
  ): WebSocket | null {
    if (!websocketUrl) {
      console.log('No websocket URL available yet, will retry when available');
      return null;
    }

    const ws = new WebSocket(websocketUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError?.(error);
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
      onClose?.();
    };

    return ws;
  }
}

// Singleton instance
export const apiClient = new APIClient();

