"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface JsonViewerProps {
  data: unknown;
  initialDepth?: number;
  className?: string;
}

export function JsonViewer({ data, initialDepth = 1, className }: JsonViewerProps) {
  return (
    <div
      className={cn(
        "rounded-md bg-muted/50 p-3 text-xs font-mono overflow-auto",
        className
      )}
    >
      <JsonNode value={data} depth={0} initialDepth={initialDepth} />
    </div>
  );
}

function JsonNode({
  value,
  depth,
  initialDepth,
}: {
  value: unknown;
  depth: number;
  initialDepth: number;
}) {
  const [open, setOpen] = useState(depth < initialDepth);

  if (value === null) return <span className="text-muted-foreground">null</span>;
  if (typeof value === "boolean")
    return <span className="text-sky-500">{value.toString()}</span>;
  if (typeof value === "number")
    return <span className="text-orange-400">{value}</span>;
  if (typeof value === "string")
    return <span className="text-green-500">"{value}"</span>;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground">[]</span>;
    return (
      <span>
        <button
          onClick={() => setOpen((o) => !o)}
          className="inline-flex items-center gap-0.5 hover:opacity-70"
        >
          {open ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground" />
          )}
          <span className="text-muted-foreground">Array[{value.length}]</span>
        </button>
        {open && (
          <div className="ml-4 border-l border-border pl-2 mt-0.5 space-y-0.5">
            {value.map((item, i) => (
              <div key={i} className="flex gap-1">
                <span className="text-muted-foreground">{i}:</span>
                <JsonNode value={item} depth={depth + 1} initialDepth={initialDepth} />
              </div>
            ))}
          </div>
        )}
      </span>
    );
  }

  if (typeof value === "object") {
    const keys = Object.keys(value as object);
    if (keys.length === 0) return <span className="text-muted-foreground">{"{}"}</span>;
    return (
      <span>
        <button
          onClick={() => setOpen((o) => !o)}
          className="inline-flex items-center gap-0.5 hover:opacity-70"
        >
          {open ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground" />
          )}
          <span className="text-muted-foreground">Object{`{${keys.length}}`}</span>
        </button>
        {open && (
          <div className="ml-4 border-l border-border pl-2 mt-0.5 space-y-0.5">
            {keys.map((k) => (
              <div key={k} className="flex gap-1 flex-wrap">
                <span className="text-violet-400">"{k}"</span>
                <span className="text-muted-foreground">:</span>
                <JsonNode
                  value={(value as Record<string, unknown>)[k]}
                  depth={depth + 1}
                  initialDepth={initialDepth}
                />
              </div>
            ))}
          </div>
        )}
      </span>
    );
  }

  return <span>{String(value)}</span>;
}
