"use client";

import { Sparkles } from "lucide-react";

export default function ThinkingIndicator() {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
        <Sparkles className="h-4 w-4 text-primary animate-pulse" />
      </div>
      <div className="flex items-center gap-2 rounded-lg bg-muted px-4 py-3">
        <div className="flex gap-1">
          <div
            className="h-2 w-2 rounded-full bg-primary/60 animate-bounce"
            style={{ animationDelay: "0ms" }}
          />
          <div
            className="h-2 w-2 rounded-full bg-primary/60 animate-bounce"
            style={{ animationDelay: "150ms" }}
          />
          <div
            className="h-2 w-2 rounded-full bg-primary/60 animate-bounce"
            style={{ animationDelay: "300ms" }}
          />
        </div>
        <span className="text-sm text-muted-foreground ml-2">
          Thinking...
        </span>
      </div>
    </div>
  );
}

