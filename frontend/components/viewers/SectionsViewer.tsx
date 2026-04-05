"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";

interface SectionsViewerProps {
  sections: Record<string, string>;
  paperTitle?: string;
}

export function SectionsViewer({ sections, paperTitle }: SectionsViewerProps) {
  const keys = Object.keys(sections);
  const [openSections, setOpenSections] = useState<Set<string>>(
    new Set(keys.length > 0 ? [keys[0]] : [])
  );

  function toggle(key: string) {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (keys.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <BookOpen className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No sections found for this paper.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {paperTitle && (
        <h2 className="text-lg font-semibold text-foreground mb-4">{paperTitle}</h2>
      )}
      {keys.map((key) => {
        const isOpen = openSections.has(key);
        const text = sections[key] ?? "";
        const wordCount = text.split(/\s+/).filter(Boolean).length;
        return (
          <div
            key={key}
            className="rounded-lg border border-border bg-card overflow-hidden"
          >
            <button
              onClick={() => toggle(key)}
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-accent/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                {isOpen ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="font-medium text-sm text-foreground">{key}</span>
              </div>
              <span className="text-xs text-muted-foreground">{wordCount} words</span>
            </button>
            {isOpen && (
              <div className="px-4 pb-4 pt-1">
                <div className="border-t border-border pt-3">
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
                    {text}
                  </p>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
