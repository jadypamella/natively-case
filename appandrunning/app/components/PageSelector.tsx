"use client";

import { useState } from "react";
import { ChevronDown, FileText, Hash } from "lucide-react";
import { Button } from "./ui/button";

interface Section {
    id: string;
    text: string;
    tag?: string;
}

interface PageInfo {
    path: string;
    title: string;
    sections: Section[];
}

interface PageSelectorProps {
    pages: PageInfo[];
    currentPath: string;
    onNavigate: (path: string, hash?: string) => void;
}

export default function PageSelector({ pages, currentPath, onNavigate }: PageSelectorProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [expandedPage, setExpandedPage] = useState<string | null>(null);

    if (pages.length === 0) return null;

    const currentPage = pages.find(p => p.path === currentPath) || pages[0];

    return (
        <div className="relative">
            {/* Trigger Button */}
            <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsOpen(!isOpen)}
                className="gap-2 max-w-[200px]"
            >
                <FileText className="h-4 w-4 shrink-0" />
                <span className="truncate">{currentPage?.title || "Select Page"}</span>
                <ChevronDown className={`h-4 w-4 shrink-0 transition-transform ${isOpen ? "rotate-180" : ""}`} />
            </Button>

            {/* Dropdown */}
            {isOpen && (
                <div className="absolute top-full left-0 mt-1 w-64 bg-white dark:bg-gray-900 border rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
                    {pages.map((page) => (
                        <div key={page.path} className="border-b last:border-b-0">
                            {/* Page Item */}
                            <button
                                onClick={() => {
                                    onNavigate(page.path);
                                    if (page.sections.length === 0) setIsOpen(false);
                                    else setExpandedPage(expandedPage === page.path ? null : page.path);
                                }}
                                className={`w-full px-3 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center gap-2 ${currentPath === page.path ? "bg-blue-50 dark:bg-blue-900/20" : ""
                                    }`}
                            >
                                <FileText className="h-4 w-4 text-gray-400" />
                                <span className="flex-1 truncate">{page.title}</span>
                                {page.sections.length > 0 && (
                                    <ChevronDown className={`h-3 w-3 text-gray-400 transition-transform ${expandedPage === page.path ? "rotate-180" : ""
                                        }`} />
                                )}
                            </button>

                            {/* Sections */}
                            {expandedPage === page.path && page.sections.length > 0 && (
                                <div className="bg-gray-50 dark:bg-gray-800/50">
                                    {page.sections.map((section) => (
                                        <button
                                            key={section.id}
                                            onClick={() => {
                                                onNavigate(page.path, section.id);
                                                setIsOpen(false);
                                            }}
                                            className="w-full px-6 py-1.5 text-left text-xs hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 text-gray-600 dark:text-gray-400"
                                        >
                                            <Hash className="h-3 w-3" />
                                            <span className="truncate">{section.text}</span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
