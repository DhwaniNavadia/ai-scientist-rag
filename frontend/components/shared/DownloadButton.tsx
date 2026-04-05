"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { cn } from "@/lib/utils";
import { LoadingSpinner } from "./LoadingSpinner";

interface DownloadButtonProps {
  label?: string;
  href?: string;
  onClick?: () => Promise<void> | void;
  variant?: "default" | "outline";
  className?: string;
}

export function DownloadButton({
  label = "Download",
  href,
  onClick,
  variant = "outline",
  className,
}: DownloadButtonProps) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (href) {
      // Use fetch + blob to download without navigating away from the page
      setLoading(true);
      try {
        const res = await fetch(href);
        if (!res.ok) throw new Error(`Download failed: ${res.status}`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        // Extract filename from Content-Disposition or use a default
        const disposition = res.headers.get("content-disposition");
        const match = disposition?.match(/filename="?(.+?)"?$/);
        a.download = match?.[1] ?? "download.json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch {
        // Fallback: open in new tab
        window.open(href, "_blank");
      } finally {
        setLoading(false);
      }
      return;
    }
    if (onClick) {
      setLoading(true);
      try {
        await onClick();
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50",
        variant === "outline"
          ? "border border-input bg-background text-foreground hover:bg-accent"
          : "bg-primary text-primary-foreground hover:bg-primary/90",
        className
      )}
    >
      {loading ? (
        <LoadingSpinner size="sm" />
      ) : (
        <Download className="h-3.5 w-3.5" />
      )}
      {label}
    </button>
  );
}
