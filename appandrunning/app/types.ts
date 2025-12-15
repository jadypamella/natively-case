export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  metadata?: {
    type?: "coding_start" | "coding_end" | "dev_server_started" | "error" | "agent_error" | "agent_complete" | "connected" | "claude_text" | "claude_tool_use" | "claude_tool_result" | "claude_event" | "claude_session_end";
    exitCode?: number;
    prompt?: string;
    workDir?: string;
    tunnelUrl?: string;
    data?: Record<string, unknown>;
  };
}

