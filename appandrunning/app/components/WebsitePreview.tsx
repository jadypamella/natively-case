"use client";

import { useState, useEffect } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { RefreshCw, ExternalLink } from "lucide-react";
import PageSelector from "./PageSelector";

interface PageInfo {
  path: string;
  title: string;
  sections: { id: string; text: string; tag?: string }[];
}

interface WebsitePreviewProps {
  devUrl: string;
  refreshTrigger?: number;
  pages?: PageInfo[];
}

export default function WebsitePreview({ devUrl, refreshTrigger, pages = [] }: WebsitePreviewProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [currentPath, setCurrentPath] = useState("index.html");

  // Refresh when external trigger changes
  useEffect(() => {
    if (refreshTrigger !== undefined && refreshTrigger > 0) {
      console.log('[WebsitePreview] External refresh trigger received:', refreshTrigger);
      setRefreshKey((prev) => prev + 1);
    }
  }, [refreshTrigger]);

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const handleNavigate = (path: string, hash?: string) => {
    setCurrentPath(path);
    setRefreshKey(prev => prev + 1);
  };

  // Build the full URL
  const currentUrl = devUrl.replace(/\/$/, "") + "/" + currentPath;

  return (
    <Card className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3 bg-muted/30">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="2" y="3" width="20" height="14" rx="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
          </div>
          <div>
            <div className="text-sm font-bold">
              Live Preview
            </div>
            <div className="text-xs font-medium text-muted-foreground">
              Your website is running
            </div>
          </div>
        </div>
        {pages.length > 1 && (
          <PageSelector
            pages={pages}
            currentPath={currentPath}
            onNavigate={handleNavigate}
          />
        )}
        <div className="flex items-center gap-2">
          <Button
            onClick={handleRefresh}
            variant="ghost"
            size="sm"
            className="gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button
            asChild
            size="sm"
            className="gap-2"
          >
            <a
              href={devUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="h-4 w-4" />
              Open
            </a>
          </Button>
        </div>
      </div>

      {/* Browser-like URL bar */}
      {isExpanded && (
        <>
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 flex items-center gap-2">
            <div className="flex gap-1.5">
              <div className="h-3 w-3 rounded-full bg-red-500" />
              <div className="h-3 w-3 rounded-full bg-yellow-500" />
              <div className="h-3 w-3 rounded-full bg-green-500" />
            </div>
            <div className="ml-4 text-xs text-gray-600 font-mono truncate flex-1">
              {devUrl}
            </div>
          </div>

          {/* Iframe preview */}
          <div className="flex-1 relative bg-white">
            <iframe
              key={refreshKey}
              src={currentUrl}
              className="absolute inset-0 w-full h-full border-0"
              title="Website Preview"
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
            />
          </div>
        </>
      )}
    </Card>
  );
}

