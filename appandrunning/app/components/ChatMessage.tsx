import { Message } from "../types";
import { Sparkles, User } from "lucide-react";

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}

export default function ChatMessage({ message, isStreaming = false }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  // Don't render system messages - they're just for status tracking
  if (message.role === "system") {
    return null;
  }

  return (
    <div className="group mb-8 flex items-start gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-gradient-to-br from-purple-500 to-pink-500 text-white"
            : "bg-gradient-to-br from-blue-500 to-cyan-500 text-white"
        } shadow-md`}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
      </div>

      {/* Message Content */}
      <div className="flex-1 space-y-2 min-w-0">
        <div className="text-xs font-semibold text-muted-foreground">
          {isUser ? "You" : "AI Assistant"}
        </div>
        <div className="text-base leading-relaxed whitespace-pre-wrap text-foreground">
          {message.content}
          {isStreaming && <span className="inline-block w-1 h-4 bg-blue-500 ml-1 animate-pulse" />}
        </div>
      </div>
    </div>
  );
}
