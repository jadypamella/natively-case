"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import ChatMessage from "../../components/ChatMessage";
import ChatInput from "../../components/ChatInput";
import WebsitePreview from "../../components/WebsitePreview";
import ThinkingIndicator from "../../components/ThinkingIndicator";
import { Message } from "../../types";
import { apiClient } from "../../lib/api-client";
import { useAgentSession } from "../../hooks/useAgentSession";
import { Button } from "../../components/ui/button";
import { ScrollArea } from "../../components/ui/scroll-area";
import { Badge } from "../../components/ui/badge";
import { Sheet, SheetContent, SheetTrigger } from "../../components/ui/sheet";
import { AppSidebar } from "../../components/AppSidebar";
import { Menu, PanelLeft, Sparkles } from "lucide-react";

export default function ChatPage() {
  const router = useRouter();
  const params = useParams();
  const chatId = params.id as string;
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [agentSessionId, setAgentSessionId] = useState<string | null>(null);
  const [devUrl, setDevUrl] = useState<string | null>(null);
  const [iframeRefreshTrigger, setIframeRefreshTrigger] = useState(0);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Connect to agent session WebSocket
  const agentSession = useAgentSession(agentSessionId);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Watch for websocket events
  useEffect(() => {
    if (!agentSession.events.length) return;

    const latestEvent = agentSession.events[agentSession.events.length - 1];
    console.log('[Chat] Processing event:', latestEvent.event, latestEvent.data);
    
    // Handle Claude text events
    if (latestEvent.event === "claude_text") {
      const text = latestEvent.data?.text;
      if (text) {
        console.log('[Chat] Got text:', text.substring(0, 50));
        // Don't hide thinking yet - Claude might be thinking/using tools after text
        setMessages((prev) => {
          const streamingMsgId = "streaming-response";
          const existingIndex = prev.findIndex((m) => m.id === streamingMsgId);
          
          if (existingIndex >= 0) {
            const updated = [...prev];
            updated[existingIndex] = {
              ...updated[existingIndex],
              content: updated[existingIndex].content + text,
            };
            return updated;
          } else {
            // Remove placeholder "Building..." messages when real content arrives
            const filtered = prev.filter(m => 
              !m.content.includes("Building your website") && 
              !m.content.includes("Processing your request")
            );
            return [
              ...filtered,
              {
                id: streamingMsgId,
                role: "assistant",
                content: text,
                timestamp: new Date(),
              },
            ];
          }
        });
        // Show thinking after text (Claude might be thinking about next steps)
        setIsThinking(true);
      }
    }
    
    // Handle Claude thinking events
    if (latestEvent.event === "claude_thinking") {
      console.log('[Chat] Claude is thinking');
      setIsThinking(true);
    }
    
    // Handle Claude tool use events
    if (latestEvent.event === "claude_tool_use") {
      console.log('[Chat] Claude is using a tool:', latestEvent.data?.tool);
      setIsThinking(true);
    }
    
    // Handle Claude events (contains text in nested structure)
    if (latestEvent.event === "claude_event") {
      const eventType = latestEvent.data?.event_type;
      const data = latestEvent.data?.data;
      
      console.log('[Chat] Claude event type:', eventType);
      
      // Extract text from message content
      if (data?.message?.content && Array.isArray(data.message.content)) {
        for (const item of data.message.content) {
          if (item.type === "text" && item.text) {
            console.log('[Chat] Got text from content:', item.text.substring(0, 50));
            setMessages((prev) => {
              const streamingMsgId = "streaming-response";
              const existingIndex = prev.findIndex((m) => m.id === streamingMsgId);
              
              if (existingIndex >= 0) {
                const updated = [...prev];
                updated[existingIndex] = {
                  ...updated[existingIndex],
                  content: updated[existingIndex].content + item.text,
                };
                return updated;
              } else {
                // Remove placeholder messages when real content arrives
                const filtered = prev.filter(m => 
                  !m.content.includes("Building your website") && 
                  !m.content.includes("Processing your request")
                );
                return [
                  ...filtered,
                  {
                    id: streamingMsgId,
                    role: "assistant",
                    content: item.text,
                    timestamp: new Date(),
                  },
                ];
              }
            });
          }
        }
      }
    }
    
    // Handle dev server started
    if (latestEvent.event === "dev_server_started") {
      const url = latestEvent.data?.tunnel_url;
      if (url && !devUrl) {
        console.log('[Chat] Dev server started:', url);
        setDevUrl(url);
        
        const msg: Message = {
          id: `website-ready-${Date.now()}`,
          role: "assistant",
          content: "✨ Your website is ready! Check it out in the preview panel on the right.",
          timestamp: new Date(),
        };
        
        setMessages((prev) => {
          const exists = prev.some((m) => m.content.includes("website is ready"));
          return exists ? prev : [...prev, msg];
        });
        
        // Initial load of iframe
        console.log('[Chat] Initial iframe load');
        setIframeRefreshTrigger(prev => prev + 1);
      }
    }
    
    // Handle turn complete - finalize streaming message for this turn
    if (latestEvent.event === "turn_complete") {
      console.log('[Chat] Turn completed');
      setIsThinking(false);
      
      // Finalize streaming message for this turn
      setMessages((prev) => {
        const hasStreaming = prev.some(m => m.id === "streaming-response");
        if (!hasStreaming) return prev;
        
        return prev.map((msg) => {
          if (msg.id === "streaming-response") {
            return {
              ...msg,
              id: `response-${Date.now()}`,
            };
          }
          return msg;
        });
      });
      
      // Refresh iframe to show updated website
      if (devUrl) {
        console.log('[Chat] Refreshing iframe after turn complete');
        setIframeRefreshTrigger(prev => prev + 1);
      }
    }
    
    // Handle ready for input
    if (latestEvent.event === "ready_for_input") {
      console.log('[Chat] Ready for input');
      setIsThinking(false);
      
      // Also refresh iframe when ready for input
      if (devUrl) {
        console.log('[Chat] Refreshing iframe - ready for input');
        setIframeRefreshTrigger(prev => prev + 1);
      }
    }
    
    // Handle agent complete
    if (latestEvent.event === "agent_complete") {
      console.log('[Chat] Agent completed');
      
      // Finalize streaming message
      setMessages((prev) => {
        return prev.map((msg) => {
          if (msg.id === "streaming-response") {
            return {
              ...msg,
              id: `response-${Date.now()}`,
            };
          }
          return msg;
        });
      });
      
      setIsLoading(false);
      setIsThinking(false);
    }
    
    // Handle errors
    if (latestEvent.event === "agent_error") {
      console.log('[Chat] Agent error:', latestEvent.data?.error);
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `I encountered an error: ${latestEvent.data?.error || "Unknown error"}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
      setIsLoading(false);
      setIsThinking(false);
    }
  }, [agentSession.events, devUrl]);

  // Load initial message from sessionStorage if this is a new chat
  useEffect(() => {
    const initialMessage = sessionStorage.getItem(`chat-${chatId}-initial`);
    if (initialMessage && messages.length === 0) {
      sessionStorage.removeItem(`chat-${chatId}-initial`);
      handleSendMessage(initialMessage);
    }
  }, [chatId]);

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: content.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // If we have an existing session and are connected via WebSocket, send via WS
      if (agentSessionId && agentSession.isConnected && agentSession.sendPrompt) {
        console.log('[Chat] Sending follow-up prompt via WebSocket');
        const success = agentSession.sendPrompt(content.trim());
        
        if (!success) {
          throw new Error('Failed to send prompt via WebSocket');
        }
      } else {
        // First message or not connected - use API to create/get session
        console.log('[Chat] Creating new session via API');
        const response = await apiClient.chat({
          session_id: agentSessionId || undefined,
          message: content.trim(),
        });

        // Store session ID for subsequent messages
        if (!agentSessionId) {
          setAgentSessionId(response.session_id);
        }

        // Add building message
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "🚀 Building your website now... This will take a moment.",
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, assistantMessage]);
      }
      
    } catch (error) {
      console.error("Failed to send message:", error);
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Error: ${error instanceof Error ? error.message : "Failed to send message"}`,
        timestamp: new Date(),
      };
      
      setMessages((prev) => [...prev, errorMessage]);
      setIsThinking(false);
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="flex h-screen bg-background">
      {/* Desktop Sidebar */}
      {isSidebarOpen && (
        <aside className="hidden w-64 border-r lg:block">
          <AppSidebar onClose={() => setIsSidebarOpen(false)} />
        </aside>
      )}

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile Header with Menu */}
        <header className="flex h-12 items-center border-b px-3 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 lg:hidden">
          <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="sm" className="text-xs">
                <Menu className="mr-1.5 h-3.5 w-3.5" />
                App & Running
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <AppSidebar onClose={() => setIsMobileMenuOpen(false)} />
            </SheetContent>
          </Sheet>
        </header>

        {/* Main Content Area - Split Panel when dev server is available */}
        <div className="flex flex-1 overflow-hidden">
        {/* Desktop Sidebar Toggle */}
        {!isSidebarOpen && (
          <div className="hidden lg:flex items-center border-r">
            <Button 
              variant="ghost" 
              size="icon"
              onClick={() => setIsSidebarOpen(true)}
              className="m-2"
            >
              <PanelLeft className="h-4 w-4" />
            </Button>
          </div>
        )}
        {/* Left Panel - Chat */}
        <div className={`flex flex-col ${devUrl ? 'w-1/2 border-r' : 'w-full'} transition-all`}>
          {/* Messages Area */}
          <ScrollArea className="flex-1">
            <div className="max-w-3xl mx-auto px-4 py-6">
              {messages.length === 0 && (
                <div className="flex h-full items-center justify-center py-12">
                  <div className="w-full max-w-2xl space-y-8">
                    <div className="text-center space-y-4">
                      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-blue-500/10 to-cyan-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm font-medium mb-2">
                        <Sparkles className="h-4 w-4" />
                        <span>AI-Powered Website Builder</span>
                      </div>
                      <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-blue-600 to-cyan-600 dark:from-blue-400 dark:to-cyan-400 bg-clip-text text-transparent">
                        Build beautiful websites
                      </h1>
                      <p className="text-lg text-muted-foreground">
                        Describe your vision, watch it come to life
                      </p>
                    </div>

                    <div className="space-y-4">
                      <p className="text-sm text-muted-foreground text-center font-medium">Try an example</p>
                      <div className="flex flex-wrap gap-3 justify-center">
                        {[
                          "Portfolio website with dark mode",
                          "Landing page for a SaaS product",
                          "Blog with article cards",
                          "Restaurant menu website",
                        ].map((example, idx) => (
                          <Button
                            key={idx}
                            variant="outline"
                            size="default"
                            onClick={() => handleSendMessage(example)}
                            className="text-sm font-medium hover:bg-gradient-to-r hover:from-blue-500/10 hover:to-cyan-500/10 hover:border-blue-500/30 transition-all"
                          >
                            {example}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {messages.map((message) => (
                <ChatMessage 
                  key={message.id} 
                  message={message}
                  isStreaming={message.id === "streaming-response"}
                />
              ))}
              {isThinking && (
                <ThinkingIndicator />
              )}
              {isLoading && messages[messages.length - 1]?.role !== "assistant" && !isThinking && (
                <div className="mb-8 flex items-start gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 text-white shadow-md">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div className="flex-1 space-y-2">
                    <div className="text-xs font-semibold text-muted-foreground">
                      AI Assistant
                    </div>
                    <div className="flex gap-1.5 pt-1">
                      <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500 [animation-delay:-0.3s]"></div>
                      <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500 [animation-delay:-0.15s]"></div>
                      <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500"></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {agentSessionId && (
            <div className="absolute bottom-24 left-4 z-10 flex flex-col gap-2">
              {isLoading && (
                <Badge variant="outline" className="gap-2 bg-blue-500/10 border-blue-500/30 text-blue-600 dark:text-blue-400">
                  <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                  <span className="text-xs font-medium">Building...</span>
                </Badge>
              )}
              <Badge variant="outline" className="gap-2">
                <div className={`h-2 w-2 rounded-full ${agentSession.isConnected ? 'bg-green-500' : 'bg-gray-400'}`} />
                <span className="text-xs">{agentSession.isConnected ? 'Connected' : 'Connecting...'}</span>
              </Badge>
            </div>
          )}

          <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
        </div>

          {/* Right Panel - Website Preview */}
          {devUrl && (
            <div className="w-1/2 flex flex-col">
              <WebsitePreview devUrl={devUrl} refreshTrigger={iframeRefreshTrigger} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

