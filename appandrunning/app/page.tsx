"use client"

import { useState } from "react"
import ChatInput from "@/components/ChatInput"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { AppSidebar } from "@/components/AppSidebar"
import { Menu, Sparkles, PanelLeftClose, PanelLeft } from "lucide-react"

export default function Home() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return

    const chatId = Date.now().toString()
    sessionStorage.setItem(`chat-${chatId}-initial`, content.trim())
    router.push(`/chat/${chatId}`)
  }

  const examples = [
    "Portfolio website with dark mode",
    "Landing page for a SaaS product",
    "Blog with article cards",
    "Restaurant menu website",
  ]

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Mobile Header with Menu */}
      <header className="flex h-12 items-center border-b px-3 lg:hidden">
        <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="sm">
              <Menu className="h-4 w-4" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-0">
            <AppSidebar onClose={() => setIsMobileMenuOpen(false)} />
          </SheetContent>
        </Sheet>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Desktop Sidebar */}
        {isSidebarOpen && (
          <aside className="hidden w-64 border-r lg:block">
            <AppSidebar onClose={() => setIsSidebarOpen(false)} />
          </aside>
        )}

        {/* Main Content */}
        <div className="flex flex-1 flex-col">
          {/* Desktop Sidebar Toggle */}
          {!isSidebarOpen && (
            <div className="hidden lg:block border-b">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setIsSidebarOpen(true)}
                className="m-2"
              >
                <PanelLeft className="h-4 w-4" />
              </Button>
            </div>
          )}
          <div className="flex-1 flex flex-col items-center justify-center px-4 py-8">
            <div className="w-full max-w-2xl space-y-8">
              <div className="text-center space-y-4">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-blue-500/10 to-cyan-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm font-medium mb-2">
                  <Sparkles className="h-4 w-4" />
                  <span>AI-Powered Website Builder</span>
                </div>
                <h1 className="text-5xl font-bold tracking-tight bg-gradient-to-r from-blue-600 to-cyan-600 dark:from-blue-400 dark:to-cyan-400 bg-clip-text text-transparent">
                  Build beautiful websites
                </h1>
                <p className="text-xl text-muted-foreground">
                  Describe your vision, watch it come to life
                </p>
              </div>

              <div className="space-y-4">
                <p className="text-sm text-muted-foreground text-center font-medium">Try an example</p>
                <div className="flex flex-wrap gap-3 justify-center">
                  {examples.map((example, idx) => (
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

          <div className="border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
          </div>
        </div>
      </div>
    </div>
  )
}
