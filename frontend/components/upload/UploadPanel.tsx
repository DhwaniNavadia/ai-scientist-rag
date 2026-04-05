"use client";

import { useCallback, useEffect, useState } from "react";
import { Upload, FileText, AlertCircle, X, Crown } from "lucide-react";
import { cn } from "@/lib/utils";
import { uploadPaper, listUploaded, deleteUploaded } from "@/lib/api";
import { useApp } from "@/contexts/AppContext";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";

interface UploadPanelProps {
  onUploaded?: (paperId: string) => void;
}

export function UploadPanel({ onUploaded }: UploadPanelProps) {
  const { demoMode, setPapers, papers, setCurrentPaper, currentPaper } = useApp();
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<string[]>([]);

  // Fetch list of uploaded papers on mount
  useEffect(() => {
    if (demoMode) return;
    listUploaded()
      .then(setUploaded)
      .catch(() => {});
  }, [demoMode]);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.endsWith(".pdf")) {
        setError("Only PDF files are supported.");
        return;
      }
      setError(null);
      setSuccess(null);
      setUploading(true);
      try {
        const result = await uploadPaper(file);
        setSuccess(`Uploaded: ${result.filename}`);
        if (!papers.includes(result.paper_id)) {
          setPapers([...papers, result.paper_id]);
        }
        if (!uploaded.includes(result.paper_id)) {
          setUploaded((prev) => [...prev, result.paper_id]);
        }
        // Auto-select first uploaded as primary
        if (!currentPaper) {
          setCurrentPaper(result.paper_id);
        }
        onUploaded?.(result.paper_id);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Upload failed.");
      } finally {
        setUploading(false);
      }
    },
    [papers, setPapers, setCurrentPaper, currentPaper, onUploaded, uploaded]
  );

  const handleMultipleFiles = useCallback(
    async (files: FileList) => {
      for (const file of Array.from(files)) {
        await handleFile(file);
      }
    },
    [handleFile]
  );

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (files && files.length > 0) handleMultipleFiles(files);
    e.target.value = "";
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) handleMultipleFiles(files);
  }

  async function handleRemove(id: string) {
    try {
      await deleteUploaded(id);
      setUploaded((prev) => prev.filter((p) => p !== id));
      setPapers(papers.filter((p) => p !== id));
      if (currentPaper === id) {
        const remaining = uploaded.filter((p) => p !== id);
        setCurrentPaper(remaining[0] ?? null);
      }
    } catch {
      // ignore
    }
  }

  if (demoMode) {
    return (
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-6 text-center dark:border-amber-700 dark:bg-amber-950/30">
        <AlertCircle className="mx-auto mb-2 h-8 w-8 text-amber-500" />
        <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
          Demo mode is active. Upload is disabled.
        </p>
        <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
          Toggle off demo mode from the sidebar to upload real papers.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <label
        htmlFor="pdf-upload"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col cursor-pointer items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 transition-colors",
          dragging
            ? "border-primary bg-primary/5"
            : "border-border bg-muted/40 hover:border-primary/50 hover:bg-muted/70",
          uploading && "pointer-events-none opacity-50"
        )}
      >
        {uploading ? (
          <>
            <LoadingSpinner size="lg" />
            <p className="text-sm text-muted-foreground">Uploading…</p>
          </>
        ) : (
          <>
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Upload className="h-6 w-6 text-primary" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-foreground">
                Drag & drop PDF(s), or click to browse
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Upload up to 3 papers — the first is primary, extras enable cross-paper analysis
              </p>
            </div>
          </>
        )}
        <input
          id="pdf-upload"
          type="file"
          accept=".pdf"
          multiple
          className="sr-only"
          onChange={onInputChange}
        />
      </label>

      {/* Uploaded papers list */}
      {uploaded.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Uploaded Papers ({uploaded.length}/3)
          </p>
          <ul className="space-y-1.5">
            {uploaded.map((id, idx) => (
              <li
                key={id}
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                  currentPaper === id
                    ? "border-primary/40 bg-primary/5"
                    : "border-border bg-background"
                )}
              >
                <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                <button
                  onClick={() => setCurrentPaper(id)}
                  className="flex-1 text-left font-medium text-foreground hover:underline truncate"
                >
                  {id}
                </button>
                {idx === 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    <Crown className="h-3 w-3" /> Primary
                  </span>
                )}
                {idx > 0 && (
                  <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
                    Paper {idx + 1}
                  </span>
                )}
                <button
                  onClick={() => handleRemove(id)}
                  className="rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                  title="Remove"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
          {uploaded.length >= 2 && (
            <p className="text-xs text-green-600 dark:text-green-400">
              ✓ Cross-paper analysis available — run Full Pipeline or Tier 2 to compare papers
            </p>
          )}
          {uploaded.length === 1 && (
            <p className="text-xs text-muted-foreground">
              Upload 1–2 more papers to enable cross-paper analysis
            </p>
          )}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 rounded-md border border-green-400/40 bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-950/30 dark:text-green-400">
          <FileText className="h-4 w-4 shrink-0" />
          {success}
        </div>
      )}
    </div>
  );
}
