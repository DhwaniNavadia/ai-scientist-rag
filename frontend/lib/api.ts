import type {
  EvaluationReport,
  FinalReport,
  PipelineStatus,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Generic fetch helper ────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
    });
  } catch (err) {
    throw new Error(`Network error reaching ${url}: ${String(err)}`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore JSON parse failure on error body
    }
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

// ── Upload ──────────────────────────────────────────────────────────────────

export async function uploadPaper(
  file: File
): Promise<{ paper_id: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${BASE}/api/upload`, { method: "POST", body: form });
  } catch (err) {
    throw new Error(`Network error uploading file: ${String(err)}`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore
    }
    throw new Error(`Upload failed (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function listUploaded(): Promise<string[]> {
  const data = await apiFetch<{ uploaded: string[] }>("/api/uploaded");
  return data.uploaded;
}

export async function deleteUploaded(paperId: string): Promise<void> {
  await apiFetch(`/api/uploaded/${encodeURIComponent(paperId)}`, {
    method: "DELETE",
  });
}

// ── Pipeline control ────────────────────────────────────────────────────────

export async function runPipeline(
  paperId: string,
  mode: "run" | "eval" | "full" | "tier1" | "tier2",
  tier?: "tier1" | "tier2"
): Promise<{ job_id: string; status: string }> {
  return apiFetch("/api/pipeline/run", {
    method: "POST",
    body: JSON.stringify({ paper_id: paperId, mode, tier: tier ?? null }),
  });
}

export async function getPipelineStatus(paperId: string): Promise<PipelineStatus> {
  return apiFetch(`/api/pipeline/status/${encodeURIComponent(paperId)}`);
}

// ── Fetch outputs ───────────────────────────────────────────────────────────

export async function getFinalReport(paperId: string): Promise<FinalReport> {
  return apiFetch(`/api/outputs/${encodeURIComponent(paperId)}/final_report`);
}

export async function getEvaluationReport(
  paperId: string
): Promise<EvaluationReport> {
  return apiFetch(`/api/outputs/${encodeURIComponent(paperId)}/evaluation_report`);
}

export async function listPapers(): Promise<string[]> {
  const data = await apiFetch<{ papers: string[] }>("/api/outputs/papers");
  return data.papers;
}

export async function getCrossPaperData(
  paperId: string
): Promise<{ cross_claims: unknown[]; contradictions: unknown[] }> {
  return apiFetch(`/api/outputs/${encodeURIComponent(paperId)}/cross_paper`);
}

// ── Download ────────────────────────────────────────────────────────────────

export function getDownloadUrl(
  paperId: string,
  fileType: string
): string {
  return `${BASE}/api/outputs/${encodeURIComponent(paperId)}/download/${fileType}`;
}
