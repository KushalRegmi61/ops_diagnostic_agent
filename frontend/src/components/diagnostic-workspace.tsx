"use client";

/**
 * First interactive workspace for Plan 3.
 *
 * It connects directly to the FastAPI backend and keeps the three core flows
 * visible: evidence upload, run execution, and cited blueprint review.
 */

import {
  AlertCircle,
  CheckCircle2,
  Database,
  FileText,
  Loader2,
  Play,
  Upload,
} from "lucide-react";
import { ChangeEvent, useMemo, useState } from "react";

import {
  API_BASE_URL,
  ApiError,
  Blueprint,
  BlueprintClaim,
  FileRef,
  RunResponse,
  createRun,
  getBlueprint,
  uploadEvidenceFile,
} from "@/lib/api";

type WorkStatus = "idle" | "uploading" | "running" | "complete" | "error";

type TimelineStep = {
  label: string;
  state: "done" | "active" | "waiting";
};

/** Format bytes into compact file sizes for the upload queue. */
function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

/** Return a concise error message for UI feedback. */
function toMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Unexpected frontend error.";
}

/** Choose timeline states from the current local workflow status. */
function timelineFor(status: WorkStatus, files: FileRef[], run: RunResponse | null): TimelineStep[] {
  return [
    {
      label: "Parse files",
      state: files.length > 0 ? "done" : status === "uploading" ? "active" : "waiting",
    },
    {
      label: "Run agents",
      state: run ? (status === "running" ? "active" : "done") : "waiting",
    },
    {
      label: "Review citations",
      state: status === "complete" ? "done" : run && status !== "error" ? "active" : "waiting",
    },
    {
      label: "Blueprint",
      state: status === "complete" ? "done" : "waiting",
    },
  ];
}

/** Render a group of blueprint claims with citation counts. */
function ClaimList({ title, claims }: { title: string; claims: BlueprintClaim[] }) {
  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      <div className="grid gap-3">
        {claims.map((claim, index) => (
          <article
            className="rounded-md border border-slate-200 bg-white p-4 shadow-sm"
            key={`${title}-${index}`}
          >
            <p className="text-sm leading-6 text-slate-800">{claim.text}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {claim.sources.map((source, sourceIndex) => (
                <span
                  className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600"
                  key={`${source.file_id}-${sourceIndex}`}
                >
                  <FileText aria-hidden="true" className="h-3.5 w-3.5" />
                  {source.file_name}
                </span>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

/** Main client component for the diagnostic frontend shell. */
export function DiagnosticWorkspace() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<FileRef[]>([]);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [status, setStatus] = useState<WorkStatus>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const timeline = useMemo(
    () => timelineFor(status, uploadedFiles, run),
    [status, uploadedFiles, run],
  );

  /** Store the chosen files locally until the user starts the diagnostic run. */
  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFiles(Array.from(event.target.files ?? []));
    setMessage(null);
  }

  /** Upload files sequentially, then start the synchronous backend graph run. */
  async function onStartRun() {
    if (selectedFiles.length === 0) return;

    setStatus("uploading");
    setMessage(null);
    setRun(null);
    setBlueprint(null);

    try {
      const refs: FileRef[] = [];
      for (const file of selectedFiles) {
        refs.push(await uploadEvidenceFile(file));
        setUploadedFiles([...refs]);
      }

      setStatus("running");
      const createdRun = await createRun(refs.map((file) => file.file_id));
      setRun(createdRun);

      const finalBlueprint = await getBlueprint(createdRun.run_id);
      setBlueprint(finalBlueprint);
      setStatus("complete");
    } catch (error) {
      setStatus("error");
      setMessage(toMessage(error));
    }
  }

  const canStart = selectedFiles.length > 0 && status !== "uploading" && status !== "running";

  return (
    <main className="min-h-screen bg-stone-50 text-slate-950">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-teal-700">
              Ops Diagnostic Agent
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950">
              Evidence-to-blueprint workspace
            </h1>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 shadow-sm">
            <Database aria-hidden="true" className="h-4 w-4 text-teal-700" />
            <span>{API_BASE_URL}</span>
          </div>
        </header>

        {message ? (
          <div className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{message}</p>
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
          <section className="space-y-6">
            <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-950">Intake files</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    PDF, DOCX, transcript, table, MBOX, JSON, Markdown, or text.
                  </p>
                </div>
                <Upload aria-hidden="true" className="h-5 w-5 text-teal-700" />
              </div>

              <label className="mt-5 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center transition hover:border-teal-500 hover:bg-teal-50">
                <Upload aria-hidden="true" className="h-7 w-7 text-slate-500" />
                <span className="mt-3 text-sm font-medium text-slate-800">Choose evidence files</span>
                <input className="sr-only" multiple onChange={onFileChange} type="file" />
              </label>

              <div className="mt-4 grid gap-2">
                {selectedFiles.map((file) => (
                  <div
                    className="flex items-center justify-between gap-3 rounded-md border border-slate-200 px-3 py-2 text-sm"
                    key={`${file.name}-${file.lastModified}`}
                  >
                    <span className="min-w-0 truncate font-medium text-slate-700">{file.name}</span>
                    <span className="shrink-0 text-slate-500">{formatBytes(file.size)}</span>
                  </div>
                ))}
              </div>

              <button
                className="mt-5 inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={!canStart}
                onClick={onStartRun}
                type="button"
              >
                {status === "uploading" || status === "running" ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Play aria-hidden="true" className="h-4 w-4" />
                )}
                Start diagnostic run
              </button>
            </div>

            <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-950">Run timeline</h2>
              <div className="mt-4 grid gap-3">
                {timeline.map((step) => (
                  <div className="flex items-center gap-3" key={step.label}>
                    {step.state === "done" ? (
                      <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-teal-700" />
                    ) : step.state === "active" ? (
                      <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin text-amber-600" />
                    ) : (
                      <span className="h-5 w-5 rounded-full border border-slate-300" />
                    )}
                    <span className="text-sm font-medium text-slate-700">{step.label}</span>
                  </div>
                ))}
              </div>

              {run ? (
                <div className="mt-5 rounded-md bg-slate-50 p-3 text-sm text-slate-600">
                  <div className="flex items-center justify-between gap-3">
                    <span>Run</span>
                    <code className="truncate font-mono text-xs text-slate-900">{run.run_id}</code>
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3">
                    <span>Status</span>
                    <span className="font-medium text-slate-900">{run.status}</span>
                  </div>
                </div>
              ) : null}
            </div>
          </section>

          <section className="space-y-6">
            <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-950">Parsed evidence</h2>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {uploadedFiles.length === 0 ? (
                  <p className="text-sm text-slate-500">No parsed files yet.</p>
                ) : (
                  uploadedFiles.map((file) => (
                    <article
                      className="rounded-md border border-slate-200 bg-slate-50 p-4"
                      key={file.file_id}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="truncate text-sm font-semibold text-slate-900">
                            {file.file_name}
                          </h3>
                          <p className="mt-1 text-xs text-slate-500">{file.mime_type}</p>
                        </div>
                        <span className="rounded-md bg-teal-100 px-2 py-1 text-xs font-semibold text-teal-800">
                          {file.parser_status}
                        </span>
                      </div>
                    </article>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold text-slate-950">Blueprint</h2>
                {blueprint ? (
                  <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                    Opportunity {blueprint.opportunity_ref}
                  </span>
                ) : null}
              </div>

              {blueprint ? (
                <div className="mt-5 space-y-6">
                  <article className="rounded-md border border-teal-200 bg-teal-50 p-4">
                    <p className="text-base font-medium leading-7 text-slate-950">
                      {blueprint.summary.text}
                    </p>
                  </article>
                  <ClaimList claims={blueprint.steps} title="Implementation steps" />
                  <ClaimList claims={blueprint.required_systems} title="Required systems" />
                  <ClaimList claims={blueprint.success_metrics} title="Success metrics" />
                  <ClaimList claims={blueprint.risks} title="Risks" />
                </div>
              ) : (
                <div className="mt-5 flex min-h-72 items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
                  <p className="max-w-sm text-sm leading-6 text-slate-500">
                    The generated automation blueprint will appear after the backend run completes.
                  </p>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
