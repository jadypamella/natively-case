"use client"

import { MessageSquare, Settings, Sparkles, X } from "lucide-react"
import { Button } from "./ui/button"
import { Separator } from "./ui/separator"
import Link from "next/link"

interface AppSidebarProps {
  onClose?: () => void
}

export function AppSidebar({ onClose }: AppSidebarProps) {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="px-3 py-2">
        <div className="flex items-center justify-between px-2">
          <Link 
            href="/" 
            className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity"
            onClick={onClose}
          >
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-bold">App & Running</h2>
          </Link>
          {onClose && (
            <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <Separator />

      <div className="flex-1 px-3">
        <div className="space-y-1">
          <Button
            variant="ghost"
            className="w-full justify-start"
            size="sm"
          >
            <MessageSquare className="mr-2 h-4 w-4" />
            Chats
          </Button>
        </div>
      </div>

      <div className="px-3 pb-4">
        <Separator className="mb-3" />
        <Button
          variant="ghost"
          className="w-full justify-start"
          size="sm"
        >
          <Settings className="mr-2 h-4 w-4" />
          Settings
        </Button>
      </div>
    </div>
  )
}

