"use client";

import { useState } from "react";
import { PageStructure } from "../lib/api-client";
import { Button } from "./ui/button";
import { ChevronDown, FileText, Hash } from "lucide-react";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
} from "./ui/dropdown-menu";

interface PageSelectorProps {
    pages: PageStructure | null;
    devUrl: string;
    onNavigate: (url: string) => void;
}

export default function PageSelector({ pages, devUrl, onNavigate }: PageSelectorProps) {
    const [selectedPage, setSelectedPage] = useState<string | null>(null);

    if (!pages || pages.total_pages === 0) {
        return (
            <Button variant="ghost" size="sm" disabled className="gap-2">
                <FileText className="h-4 w-4" />
                No pages
            </Button>
        );
    }

    const handlePageSelect = (url: string, title: string) => {
        const fullUrl = devUrl + url;
        setSelectedPage(title);
        onNavigate(fullUrl);
    };

    const handleSectionSelect = (pageUrl: string, sectionId: string) => {
        const fullUrl = `${devUrl}${pageUrl}#${sectionId}`;
        onNavigate(fullUrl);
    };

    const displayText = selectedPage || `${pages.total_pages} page${pages.total_pages > 1 ? 's' : ''}`;

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                    <FileText className="h-4 w-4" />
                    {displayText}
                    <ChevronDown className="h-4 w-4" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-64">
                <DropdownMenuLabel>Pages ({pages.total_pages})</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {pages.pages.map((page) => {
                    if (page.sections.length === 0) {
                        return (
                            <DropdownMenuItem
                                key={page.path}
                                onClick={() => handlePageSelect(page.url, page.title)}
                                className="cursor-pointer"
                            >
                                <FileText className="mr-2 h-4 w-4" />
                                <span className="truncate">{page.title}</span>
                            </DropdownMenuItem>
                        );
                    }

                    return (
                        <DropdownMenuSub key={page.path}>
                            <DropdownMenuSubTrigger className="cursor-pointer">
                                <FileText className="mr-2 h-4 w-4" />
                                <span className="truncate">{page.title}</span>
                            </DropdownMenuSubTrigger>
                            <DropdownMenuSubContent className="w-56">
                                <DropdownMenuItem
                                    onClick={() => handlePageSelect(page.url, page.title)}
                                    className="cursor-pointer font-medium"
                                >
                                    <FileText className="mr-2 h-4 w-4" />
                                    View full page
                                </DropdownMenuItem>
                                {page.sections.length > 0 && <DropdownMenuSeparator />}
                                {page.sections.map((section) => (
                                    <DropdownMenuItem
                                        key={section.id}
                                        onClick={() => handleSectionSelect(page.url, section.id)}
                                        className="cursor-pointer"
                                    >
                                        <Hash className="mr-2 h-4 w-4 text-muted-foreground" />
                                        <span className="truncate text-sm">{section.name}</span>
                                    </DropdownMenuItem>
                                ))}
                            </DropdownMenuSubContent>
                        </DropdownMenuSub>
                    );
                })}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
