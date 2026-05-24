/**
 * Typed browser client for the FastAPI backend.
 *
 * These types mirror backend/app/schemas.py closely enough for the frontend
 * workflow: upload files, start diagnostic runs, fetch blueprints, and resolve
 * citations through the excerpt endpoint.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export type ParserStatus = "ok" | "error" | "pending";

export type FileRef = {
  file_id: string;
  file_name: string;
  mime_type: string;
  blob_path: string;
  parser_status: ParserStatus;
};

export type RunResponse = {
  run_id: string;
  status: string;
  langfuse_trace_id: string | null;
};

export type Source = {
  file_id: string;
  file_name: string;
  type:
    | "pdf"
    | "docx"
    | "md"
    | "txt"
    | "transcript_vtt"
    | "transcript_srt"
    | "csv"
    | "xlsx"
    | "mbox"
    | "json";
  locator: Record<string, unknown>;
};

export type BlueprintClaim = {
  text: string;
  sources: Source[];
};

export type Blueprint = {
  opportunity_ref: number;
  summary: BlueprintClaim;
  steps: BlueprintClaim[];
  required_systems: BlueprintClaim[];
  success_metrics: BlueprintClaim[];
  risks: BlueprintClaim[];
};

export class ApiError extends Error {
  status: number;

  /** Preserve the backend HTTP status alongside the readable error message. */
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Parse FastAPI error responses without assuming every failure is JSON. */
async function errorMessage(response: Response): Promise<string> {
  const fallback = `${response.status} ${response.statusText}`.trim();

  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

/** Fetch JSON from the backend and normalize non-2xx responses into ApiError. */
async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }

  return (await response.json()) as T;
}

/** Upload one evidence file and return the parsed file reference. */
export async function uploadEvidenceFile(file: File): Promise<FileRef> {
  const formData = new FormData();
  formData.append("file", file);

  return requestJson<FileRef>("/api/files", {
    method: "POST",
    body: formData,
  });
}

/** Start a diagnostic run for uploaded file ids. */
export async function createRun(fileIds: string[]): Promise<RunResponse> {
  return requestJson<RunResponse>("/api/runs", {
    method: "POST",
    body: JSON.stringify({ file_ids: fileIds }),
  });
}

/** Fetch a run by id. */
export async function getRun(runId: string): Promise<RunResponse> {
  return requestJson<RunResponse>(`/api/runs/${runId}`);
}

/** Fetch the final automation blueprint for a completed run. */
export async function getBlueprint(runId: string): Promise<Blueprint> {
  return requestJson<Blueprint>(`/api/runs/${runId}/blueprint`);
}

/** Resolve a citation locator to backend parser excerpt text. */
export async function getExcerpt(source: Source): Promise<string> {
  const response = await requestJson<{ text: string }>(`/api/files/${source.file_id}/excerpt`, {
    method: "POST",
    body: JSON.stringify({ locator: source.locator }),
  });

  return response.text;
}

export { API_BASE_URL };
