"use client";

/**
 * Diagnostic workspace — premium dark-mode UI.
 *
 * Drives the evidence-upload → run → cited blueprint flow against the FastAPI
 * backend. Designed as a single focused canvas: intake on the left rail, live
 * pipeline + blueprint on the right canvas. Citation chips expand into the
 * backend-resolved excerpt so every claim is one click from its source text.
 */

import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Database,
  FileText,
  Gauge,
  Layers,
  Loader2,
  Play,
  Quote,
  Radio,
  Settings2,
  Sparkles,
  Target,
  Trash2,
  Upload,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import {
  ChangeEvent,
  DragEvent,
  Fragment,
  ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  API_BASE_URL,
  ApiError,
  Blueprint,
  BlueprintClaim,
  FileRef,
  RunEvent,
  RunResponse,
  Source,
  createRun,
  getBlueprint,
  getExcerpt,
  getRun,
  openRunEventSocket,
  uploadEvidenceFile,
} from "@/lib/api";

type WorkStatus = "idle" | "uploading" | "running" | "complete" | "error";

type TimelineStep = {
  label: string;
  hint: string;
  state: "done" | "active" | "waiting";
};

type AccentKey = "violet" | "teal" | "amber" | "rose";

const TERMINAL_RUN_EVENT_TYPES = new Set(["run_completed", "run_failed"]);

const ACCENTS: Record<
  AccentKey,
  { hex: string; bg: string; ring: string; soft: string; text: string }
> = {
  violet: {
    hex: "#7c8cff",
    bg: "bg-[#7c8cff]/12",
    ring: "ring-violet",
    soft: "border-[#7c8cff]/30",
    text: "text-[#a6b1ff]",
  },
  teal: {
    hex: "#4ecdc4",
    bg: "bg-[#4ecdc4]/12",
    ring: "ring-teal",
    soft: "border-[#4ecdc4]/30",
    text: "text-[#7ee0d8]",
  },
  amber: {
    hex: "#ffb86b",
    bg: "bg-[#ffb86b]/12",
    ring: "ring-amber",
    soft: "border-[#ffb86b]/30",
    text: "text-[#ffd29a]",
  },
  rose: {
    hex: "#ff6b80",
    bg: "bg-[#ff6b80]/12",
    ring: "ring-rose",
    soft: "border-[#ff6b80]/30",
    text: "text-[#ff97a7]",
  },
};

/** Bytes → compact human-readable size string for the upload queue. */
function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

/** Render any caught value as a UI-safe error string. */
function toMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Unexpected frontend error.";
}

/** Append a streamed run event and cap the history so the rail stays snappy. */
function appendRunEvent(events: RunEvent[], event: RunEvent): RunEvent[] {
  return [...events, event].slice(-60);
}

/** Open a WS to the run, forward events, resolve on terminal event, reject on failure. */
function waitForRunCompletion(
  runId: string,
  onEvent: (event: RunEvent) => void,
): Promise<RunEvent> {
  return new Promise((resolve, reject) => {
    const socket = openRunEventSocket(runId);
    let settled = false;

    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as RunEvent;
      onEvent(event);
      if (!TERMINAL_RUN_EVENT_TYPES.has(event.type)) return;

      settled = true;
      socket.close();
      if (event.type === "run_failed") {
        reject(new Error(event.message));
      } else {
        resolve(event);
      }
    };

    socket.onerror = () => {
      settled = true;
      reject(new Error("Run event stream disconnected."));
    };

    socket.onclose = () => {
      if (!settled) {
        reject(new Error("Run event stream closed before the run completed."));
      }
    };
  });
}

/** Pick visual state for each step of the local 4-stage pipeline. */
function timelineFor(
  status: WorkStatus,
  files: FileRef[],
  run: RunResponse | null,
  hasBlueprint: boolean,
): TimelineStep[] {
  return [
    {
      label: "Parse evidence",
      hint: "Files routed through typed parsers",
      state:
        files.length > 0
          ? "done"
          : status === "uploading"
            ? "active"
            : "waiting",
    },
    {
      label: "Per-file agents",
      hint: "ReAct loops extract claims & locators",
      state: run
        ? status === "running"
          ? "active"
          : "done"
        : files.length > 0 && status !== "error"
          ? "active"
          : "waiting",
    },
    {
      label: "Cross-file synthesis",
      hint: "Bottlenecks · ROI · fastest win",
      state: hasBlueprint ? "done" : run && status === "running" ? "active" : "waiting",
    },
    {
      label: "Cited blueprint",
      hint: "Every claim round-trips to source text",
      state: hasBlueprint ? "done" : "waiting",
    },
  ];
}

/** Best-effort short label for any locator object. */
function locatorLabel(locator: Record<string, unknown>): string {
  if ("page" in locator && locator.page != null) return `p.${locator.page}`;
  if ("row" in locator && locator.row != null) return `row ${locator.row}`;
  if ("line" in locator && locator.line != null) return `line ${locator.line}`;
  if ("cue_index" in locator) return `cue ${locator.cue_index}`;
  if ("message_id" in locator) return "message";
  if ("section" in locator && typeof locator.section === "string")
    return locator.section;
  return "source";
}

/** Inline excerpt fetcher — collapsed by default, hits backend on expand. */
function CitationChip({ source }: { source: Source }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Toggle open + lazy-load the excerpt on first expand. */
  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && text == null && !loading) {
      setLoading(true);
      setError(null);
      try {
        const body = await getExcerpt(source);
        setText(body);
      } catch (err) {
        setError(toMessage(err));
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <div className="w-full">
      <button
        aria-expanded={open}
        className="group inline-flex max-w-full items-center gap-1.5 rounded-full border border-[var(--border-strong)] bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-[var(--fg-muted)] transition hover:border-[#7c8cff]/50 hover:bg-[#7c8cff]/10 hover:text-[#cdd4ff]"
        onClick={toggle}
        type="button"
      >
        <FileText aria-hidden="true" className="h-3 w-3 shrink-0" />
        <span className="max-w-[180px] truncate">{source.file_name}</span>
        <span className="rounded-sm bg-white/5 px-1 font-mono text-[10px] text-[var(--fg-dim)] group-hover:text-[var(--fg-muted)]">
          {locatorLabel(source.locator)}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <div className="fade-up mt-2 rounded-md border border-[var(--border)] bg-black/40 p-3">
          {loading ? (
            <div className="space-y-2">
              <div className="h-3 w-4/5 rounded bg-white/5 shimmer" />
              <div className="h-3 w-3/5 rounded bg-white/5 shimmer" />
              <div className="h-3 w-2/3 rounded bg-white/5 shimmer" />
            </div>
          ) : error ? (
            <p className="text-xs text-[#ff97a7]">{error}</p>
          ) : (
            <div className="flex gap-2.5">
              <Quote
                aria-hidden="true"
                className="h-3.5 w-3.5 shrink-0 text-[#7c8cff]"
              />
              <p className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-[var(--fg-muted)]">
                {text}
              </p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

/** Section header used inside each colored blueprint card. */
function SectionHeader({
  icon,
  title,
  count,
  accent,
}: {
  icon: ReactNode;
  title: string;
  count: number;
  accent: AccentKey;
}) {
  const a = ACCENTS[accent];
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2.5">
        <span
          className={`flex h-7 w-7 items-center justify-center rounded-md ${a.bg} ${a.text}`}
        >
          {icon}
        </span>
        <h3 className="text-sm font-semibold tracking-wide text-[var(--fg)]">
          {title}
        </h3>
      </div>
      <span className="rounded-full border border-[var(--border-strong)] bg-white/[0.03] px-2 py-0.5 font-mono text-[10px] text-[var(--fg-muted)]">
        {count.toString().padStart(2, "0")}
      </span>
    </div>
  );
}

/** Render the list of claims for a blueprint subsection, with citations. */
function ClaimList({
  title,
  claims,
  icon,
  accent,
}: {
  title: string;
  claims: BlueprintClaim[];
  icon: ReactNode;
  accent: AccentKey;
}) {
  return (
    <section className="space-y-3">
      <SectionHeader
        accent={accent}
        count={claims.length}
        icon={icon}
        title={title}
      />
      <div className="grid gap-2.5">
        {claims.map((claim, index) => (
          <article
            className="card group p-4 hover:bg-[var(--bg-card-hover)]"
            key={`${title}-${index}`}
          >
            <div className="flex gap-3">
              <span
                aria-hidden="true"
                className={`mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md font-mono text-[10px] font-bold ${ACCENTS[accent].bg} ${ACCENTS[accent].text}`}
              >
                {index + 1}
              </span>
              <p className="flex-1 text-[13.5px] leading-6 text-[var(--fg)]">
                {claim.text}
              </p>
            </div>
            {claim.sources.length > 0 ? (
              <div className="mt-3 grid gap-2 pl-8">
                {claim.sources.map((source, sourceIndex) => (
                  <CitationChip
                    key={`${source.file_id}-${sourceIndex}`}
                    source={source}
                  />
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

/** Small step number for the empty-state hero. */
function HeroStep({
  n,
  label,
  icon,
}: {
  n: number;
  label: string;
  icon: ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-7 w-7 items-center justify-center rounded-full border border-[var(--border-strong)] bg-white/[0.03] font-mono text-[11px] text-[var(--fg-muted)]">
        {n}
      </span>
      <span className="flex items-center gap-1.5 text-[12px] text-[var(--fg-muted)]">
        {icon}
        {label}
      </span>
    </div>
  );
}

/** Choose an emoji-free icon + color per event level / terminal type. */
function eventVisual(event: RunEvent): { icon: ReactNode; tone: string } {
  if (event.level === "error" || event.type === "run_failed") {
    return {
      icon: <AlertCircle aria-hidden="true" className="h-3.5 w-3.5" />,
      tone: "text-[#ff97a7]",
    };
  }
  if (event.level === "warning") {
    return {
      icon: <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />,
      tone: "text-[#ffd29a]",
    };
  }
  if (event.type === "run_completed") {
    return {
      icon: <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />,
      tone: "text-[#7ee0d8]",
    };
  }
  return {
    icon: <CircleDot aria-hidden="true" className="h-3.5 w-3.5" />,
    tone: "text-[var(--fg-dim)]",
  };
}

/** Pretty short timestamp, e.g. "14:02:31". */
function shortTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour12: false });
}

/** Main client component for the diagnostic workspace shell. */
export function DiagnosticWorkspace() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<FileRef[]>([]);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [status, setStatus] = useState<WorkStatus>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [runEvents, setRunEvents] = useState<RunEvent[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);

  /** Live elapsed-time counter while a run is in flight. */
  useEffect(() => {
    if (status !== "uploading" && status !== "running") return;
    if (runStartedAt == null) return;
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - runStartedAt) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [status, runStartedAt]);

  const timeline = useMemo(
    () => timelineFor(status, uploadedFiles, run, blueprint != null),
    [status, uploadedFiles, run, blueprint],
  );

  const totalClaims = useMemo(() => {
    if (!blueprint) return 0;
    return (
      blueprint.steps.length +
      blueprint.required_systems.length +
      blueprint.success_metrics.length +
      blueprint.risks.length +
      1
    );
  }, [blueprint]);

  const totalCitations = useMemo(() => {
    if (!blueprint) return 0;
    const count = (cs: BlueprintClaim[]) =>
      cs.reduce((acc, c) => acc + c.sources.length, 0);
    return (
      blueprint.summary.sources.length +
      count(blueprint.steps) +
      count(blueprint.required_systems) +
      count(blueprint.success_metrics) +
      count(blueprint.risks)
    );
  }, [blueprint]);

  /** Merge newly chosen files into the queue (de-dup by name+size+mtime). */
  function addFiles(incoming: File[]) {
    setSelectedFiles((prev) => {
      const key = (f: File) => `${f.name}-${f.size}-${f.lastModified}`;
      const seen = new Set(prev.map(key));
      return [...prev, ...incoming.filter((f) => !seen.has(key(f)))];
    });
    setMessage(null);
  }

  /** Read files from the native input element. */
  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  /** Allow dropping anywhere inside the dropzone wrapper. */
  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragOver(false);
    addFiles(Array.from(event.dataTransfer.files));
  }

  /** Remove a single queued file before upload. */
  function removeFile(file: File) {
    setSelectedFiles((prev) =>
      prev.filter(
        (f) =>
          !(
            f.name === file.name &&
            f.size === file.size &&
            f.lastModified === file.lastModified
          ),
      ),
    );
  }

  /** Upload queued files, kick off the run, stream events, fetch blueprint. */
  async function onStartRun() {
    if (selectedFiles.length === 0) return;

    setStatus("uploading");
    setMessage(null);
    setRun(null);
    setBlueprint(null);
    setRunEvents([]);
    setRunStartedAt(Date.now());
    setElapsed(0);

    try {
      const refs: FileRef[] = [];
      for (const file of selectedFiles) {
        refs.push(await uploadEvidenceFile(file));
        setUploadedFiles([...refs]);
      }

      setStatus("running");
      const createdRun = await createRun(refs.map((f) => f.file_id));
      setRun(createdRun);

      await waitForRunCompletion(createdRun.run_id, (event) => {
        setRunEvents((current) => appendRunEvent(current, event));
      });
      const latestRun = await getRun(createdRun.run_id);
      setRun(latestRun);

      const finalBlueprint = await getBlueprint(createdRun.run_id);
      setBlueprint(finalBlueprint);
      setStatus("complete");
    } catch (error) {
      setStatus("error");
      setMessage(toMessage(error));
    }
  }

  /** Reset the entire workspace back to the empty state. */
  function resetAll() {
    setSelectedFiles([]);
    setUploadedFiles([]);
    setRun(null);
    setBlueprint(null);
    setStatus("idle");
    setMessage(null);
    setRunEvents([]);
    setRunStartedAt(null);
    setElapsed(0);
  }

  const canStart =
    selectedFiles.length > 0 && status !== "uploading" && status !== "running";
  const isWorking = status === "uploading" || status === "running";

  return (
    <main className="relative z-10 min-h-screen text-[var(--fg)]">
      {/* Top bar */}
      <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--bg-base)]/70 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1400px] items-center justify-between gap-4 px-6 py-3.5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[#7c8cff] to-[#4ecdc4] shadow-[0_8px_24px_-12px_rgba(124,140,255,0.6)]">
              <Sparkles aria-hidden="true" className="h-4.5 w-4.5 text-[#0a0c14]" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-[15px] font-semibold tracking-tight text-[var(--fg)]">
                Ops Diagnostic Agent
              </span>
              <span className="text-[11px] uppercase tracking-[0.18em] text-[var(--fg-dim)]">
                Evidence → Cited Blueprint
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="chip">
              <Database aria-hidden="true" className="h-3 w-3" />
              <span className="font-mono">{API_BASE_URL}</span>
            </span>
            <span
              className={`chip ${
                isWorking
                  ? "border-[#7c8cff]/40 text-[#a6b1ff]"
                  : status === "complete"
                    ? "border-[#4ecdc4]/40 text-[#7ee0d8]"
                    : status === "error"
                      ? "border-[#ff6b80]/40 text-[#ff97a7]"
                      : ""
              }`}
            >
              <span
                className={`pulse-dot inline-block h-1.5 w-1.5 rounded-full ${
                  isWorking
                    ? "bg-[#7c8cff] text-[#7c8cff]"
                    : status === "complete"
                      ? "bg-[#4ecdc4] text-[#4ecdc4]"
                      : status === "error"
                        ? "bg-[#ff6b80] text-[#ff6b80]"
                        : "bg-[var(--fg-dim)] text-transparent"
                }`}
              />
              {isWorking
                ? "Running"
                : status === "complete"
                  ? "Complete"
                  : status === "error"
                    ? "Failed"
                    : "Idle"}
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6 px-6 py-8">
        {message ? (
          <div className="fade-up flex items-start gap-3 rounded-lg border border-[#ff6b80]/40 bg-[#ff6b80]/[0.08] px-4 py-3 text-sm text-[#ffb3bf]">
            <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            <p className="flex-1">{message}</p>
            <button
              aria-label="Dismiss"
              className="text-[#ffb3bf]/80 hover:text-white"
              onClick={() => setMessage(null)}
              type="button"
            >
              <X aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[400px_1fr]">
          {/* LEFT RAIL */}
          <aside className="flex flex-col gap-5">
            {/* Intake */}
            <div className="card p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[#7c8cff]/15 text-[#a6b1ff]">
                    <Upload aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <h2 className="text-[15px] font-semibold tracking-tight">
                    Intake evidence
                  </h2>
                </div>
                {selectedFiles.length > 0 ? (
                  <span className="chip">{selectedFiles.length} queued</span>
                ) : null}
              </div>
              <p className="mt-1.5 text-[12.5px] text-[var(--fg-muted)]">
                PDF, DOCX, transcripts, CSV, XLSX, MBOX, JSON, MD, or TXT.
              </p>

              <label
                className={`mt-4 flex min-h-[148px] cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-6 text-center transition ${
                  dragOver
                    ? "border-[#7c8cff] bg-[#7c8cff]/10"
                    : "border-[var(--border-strong)] bg-white/[0.015] hover:border-[#7c8cff]/50 hover:bg-[#7c8cff]/[0.04]"
                }`}
                onDragLeave={() => setDragOver(false)}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDrop={onDrop}
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#7c8cff]/15 text-[#a6b1ff]">
                  <Upload aria-hidden="true" className="h-5 w-5" />
                </span>
                <span className="text-[13px] font-medium text-[var(--fg)]">
                  Drop files or click to browse
                </span>
                <span className="text-[11px] text-[var(--fg-dim)]">
                  Multi-select supported
                </span>
                <input
                  className="sr-only"
                  multiple
                  onChange={onFileChange}
                  type="file"
                />
              </label>

              {selectedFiles.length > 0 ? (
                <ul className="mt-3 grid gap-1.5">
                  {selectedFiles.map((file) => (
                    <li
                      className="flex items-center gap-2.5 rounded-md border border-[var(--border)] bg-white/[0.02] px-2.5 py-2"
                      key={`${file.name}-${file.lastModified}`}
                    >
                      <FileText
                        aria-hidden="true"
                        className="h-3.5 w-3.5 shrink-0 text-[var(--fg-dim)]"
                      />
                      <span className="min-w-0 flex-1 truncate text-[12.5px] text-[var(--fg)]">
                        {file.name}
                      </span>
                      <span className="shrink-0 font-mono text-[10.5px] text-[var(--fg-dim)]">
                        {formatBytes(file.size)}
                      </span>
                      <button
                        aria-label={`Remove ${file.name}`}
                        className="rounded p-0.5 text-[var(--fg-dim)] hover:bg-white/5 hover:text-[#ff97a7]"
                        disabled={isWorking}
                        onClick={() => removeFile(file)}
                        type="button"
                      >
                        <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}

              <div className="mt-5 flex gap-2">
                <button
                  className="btn-primary inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg px-4 text-[13.5px]"
                  disabled={!canStart}
                  onClick={onStartRun}
                  type="button"
                >
                  {isWorking ? (
                    <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play aria-hidden="true" className="h-4 w-4" />
                  )}
                  {isWorking ? "Running…" : "Start diagnostic"}
                </button>
                {status === "complete" || status === "error" ? (
                  <button
                    aria-label="Reset workspace"
                    className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--border-strong)] bg-white/[0.02] text-[var(--fg-muted)] transition hover:border-[var(--border-strong)] hover:bg-white/5 hover:text-[var(--fg)]"
                    onClick={resetAll}
                    type="button"
                  >
                    <Trash2 aria-hidden="true" className="h-4 w-4" />
                  </button>
                ) : null}
              </div>
            </div>

            {/* Pipeline */}
            <div className="card p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[#4ecdc4]/15 text-[#7ee0d8]">
                    <Workflow aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <h2 className="text-[15px] font-semibold tracking-tight">
                    Pipeline
                  </h2>
                </div>
                {isWorking ? (
                  <span className="chip border-[#7c8cff]/30 text-[#a6b1ff]">
                    <Loader2 aria-hidden="true" className="h-3 w-3 animate-spin" />
                    {Math.floor(elapsed / 60)}:
                    {String(elapsed % 60).padStart(2, "0")}
                  </span>
                ) : null}
              </div>

              <ol className="mt-4 grid gap-2.5">
                {timeline.map((step, idx) => (
                  <li
                    className="relative flex items-start gap-3 rounded-md border border-transparent px-2 py-2 transition"
                    key={step.label}
                  >
                    <span
                      className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                        step.state === "done"
                          ? "bg-[#4ecdc4]/20 text-[#7ee0d8]"
                          : step.state === "active"
                            ? "bg-[#7c8cff]/20 text-[#a6b1ff]"
                            : "border border-[var(--border-strong)] text-[var(--fg-dim)]"
                      }`}
                    >
                      {step.state === "done" ? (
                        <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
                      ) : step.state === "active" ? (
                        <Loader2 aria-hidden="true" className="h-3 w-3 animate-spin" />
                      ) : (
                        idx + 1
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-[13px] font-medium ${
                          step.state === "waiting"
                            ? "text-[var(--fg-muted)]"
                            : "text-[var(--fg)]"
                        }`}
                      >
                        {step.label}
                      </p>
                      <p className="mt-0.5 text-[11.5px] text-[var(--fg-dim)]">
                        {step.hint}
                      </p>
                      {step.state === "active" ? (
                        <div className="mt-2 h-[2px] w-full overflow-hidden rounded bg-white/5">
                          <div className="h-full w-1/3 rounded shimmer" />
                        </div>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ol>

              {run ? (
                <div className="mt-4 grid gap-1.5 rounded-md border border-[var(--border)] bg-black/30 p-3 font-mono text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--fg-dim)]">run_id</span>
                    <span className="truncate text-[var(--fg)]">{run.run_id}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--fg-dim)]">status</span>
                    <span className="text-[var(--fg)]">{run.status}</span>
                  </div>
                  {run.langfuse_trace_id ? (
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--fg-dim)]">trace</span>
                      <span className="truncate text-[var(--fg)]">
                        {run.langfuse_trace_id}
                      </span>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            {/* Live events */}
            <div className="card p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[#ffb86b]/15 text-[#ffd29a]">
                    <Radio aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <h2 className="text-[15px] font-semibold tracking-tight">
                    Live events
                  </h2>
                </div>
                <span className="chip">
                  <Activity aria-hidden="true" className="h-3 w-3" />
                  {runEvents.length}
                </span>
              </div>

              <div
                aria-live="polite"
                className="mt-3 max-h-[360px] space-y-1.5 overflow-y-auto pr-1"
              >
                {runEvents.length === 0 ? (
                  <p className="rounded-md border border-dashed border-[var(--border-strong)] bg-white/[0.015] p-4 text-center text-[12px] text-[var(--fg-dim)]">
                    Run updates will stream here in real time.
                  </p>
                ) : (
                  [...runEvents].reverse().map((event) => {
                    const v = eventVisual(event);
                    return (
                      <div
                        className="fade-up flex items-start gap-2.5 rounded-md border border-[var(--border)] bg-white/[0.015] px-2.5 py-2 text-[12px]"
                        key={`${event.run_id}-${event.seq}`}
                      >
                        <span className={`mt-0.5 ${v.tone}`}>{v.icon}</span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[var(--fg)]">{event.message}</p>
                          <div className="mt-0.5 flex items-center gap-2 font-mono text-[10px] text-[var(--fg-dim)]">
                            <span>{shortTime(event.timestamp)}</span>
                            <span>·</span>
                            <span className="truncate">{event.stage}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </aside>

          {/* RIGHT CANVAS */}
          <section className="flex flex-col gap-6">
            {/* Parsed evidence row */}
            {uploadedFiles.length > 0 ? (
              <div className="fade-up card p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[#7c8cff]/15 text-[#a6b1ff]">
                      <Layers aria-hidden="true" className="h-4 w-4" />
                    </span>
                    <h2 className="text-[15px] font-semibold tracking-tight">
                      Parsed evidence
                    </h2>
                  </div>
                  <span className="chip">
                    {uploadedFiles.length} file{uploadedFiles.length === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="mt-4 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
                  {uploadedFiles.map((file) => (
                    <article
                      className="group flex items-start gap-3 rounded-md border border-[var(--border)] bg-white/[0.02] p-3 transition hover:border-[var(--border-strong)] hover:bg-white/[0.04]"
                      key={file.file_id}
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[#4ecdc4]/12 text-[#7ee0d8]">
                        <FileText aria-hidden="true" className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium text-[var(--fg)]">
                          {file.file_name}
                        </p>
                        <p className="mt-0.5 truncate font-mono text-[10.5px] text-[var(--fg-dim)]">
                          {file.mime_type}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                          file.parser_status === "ok"
                            ? "border-[#4ecdc4]/30 bg-[#4ecdc4]/10 text-[#7ee0d8]"
                            : file.parser_status === "error"
                              ? "border-[#ff6b80]/30 bg-[#ff6b80]/10 text-[#ff97a7]"
                              : "border-[var(--border-strong)] bg-white/[0.03] text-[var(--fg-muted)]"
                        }`}
                      >
                        {file.parser_status}
                      </span>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Blueprint */}
            <div className="card overflow-hidden p-0">
              {blueprint ? (
                <div className="fade-up">
                  {/* Blueprint hero */}
                  <div className="relative border-b border-[var(--border)] bg-gradient-to-br from-[#7c8cff]/[0.08] via-transparent to-[#4ecdc4]/[0.06] p-6">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-[#7c8cff] to-[#4ecdc4] shadow-[0_8px_24px_-12px_rgba(124,140,255,0.6)]">
                          <Zap aria-hidden="true" className="h-5 w-5 text-[#0a0c14]" />
                        </span>
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--fg-dim)]">
                            Automation Blueprint
                          </p>
                          <h2 className="mt-0.5 text-[18px] font-semibold tracking-tight text-[var(--fg)]">
                            Opportunity #{blueprint.opportunity_ref}
                          </h2>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="chip border-[#7c8cff]/30 text-[#a6b1ff]">
                          <Target aria-hidden="true" className="h-3 w-3" />
                          {totalClaims} claims
                        </span>
                        <span className="chip border-[#4ecdc4]/30 text-[#7ee0d8]">
                          <Quote aria-hidden="true" className="h-3 w-3" />
                          {totalCitations} citations
                        </span>
                        <span className="chip border-[#ffb86b]/30 text-[#ffd29a]">
                          <Gauge aria-hidden="true" className="h-3 w-3" />
                          {uploadedFiles.length} source{uploadedFiles.length === 1 ? "" : "s"}
                        </span>
                      </div>
                    </div>

                    <p className="mt-5 text-[15px] leading-7 text-[var(--fg)]">
                      {blueprint.summary.text}
                    </p>
                    {blueprint.summary.sources.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {blueprint.summary.sources.map((source, idx) => (
                          <CitationChip
                            key={`summary-${idx}`}
                            source={source}
                          />
                        ))}
                      </div>
                    ) : null}
                  </div>

                  {/* Bento grid of sections */}
                  <div className="grid gap-5 p-6 lg:grid-cols-2">
                    <ClaimList
                      accent="violet"
                      claims={blueprint.steps}
                      icon={<ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />}
                      title="Implementation steps"
                    />
                    <ClaimList
                      accent="teal"
                      claims={blueprint.required_systems}
                      icon={<Settings2 aria-hidden="true" className="h-3.5 w-3.5" />}
                      title="Required systems"
                    />
                    <ClaimList
                      accent="amber"
                      claims={blueprint.success_metrics}
                      icon={<Gauge aria-hidden="true" className="h-3.5 w-3.5" />}
                      title="Success metrics"
                    />
                    <ClaimList
                      accent="rose"
                      claims={blueprint.risks}
                      icon={<AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />}
                      title="Risks"
                    />
                  </div>
                </div>
              ) : (
                <div className="flex min-h-[520px] flex-col items-center justify-center gap-6 p-10 text-center">
                  <div className="relative">
                    <div className="absolute inset-0 -z-10 rounded-full bg-gradient-to-br from-[#7c8cff]/20 to-[#4ecdc4]/20 blur-2xl" />
                    <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-[var(--border-strong)] bg-gradient-to-br from-[#11141b] to-[#0d0f14]">
                      {isWorking ? (
                        <Loader2
                          aria-hidden="true"
                          className="h-8 w-8 animate-spin text-[#a6b1ff]"
                        />
                      ) : (
                        <Sparkles
                          aria-hidden="true"
                          className="h-8 w-8 text-[#a6b1ff]"
                        />
                      )}
                    </div>
                  </div>

                  <div className="max-w-md space-y-2">
                    <h3 className="text-[18px] font-semibold tracking-tight">
                      {isWorking
                        ? "Synthesizing your blueprint…"
                        : "Your cited blueprint will land here"}
                    </h3>
                    <p className="text-[13.5px] leading-6 text-[var(--fg-muted)]">
                      Upload operational evidence — meeting transcripts, ops docs,
                      CSV extracts, MBOX threads — and the agent will produce a
                      step-by-step automation plan where every claim round-trips
                      to its source.
                    </p>
                  </div>

                  <div className="grid w-full max-w-sm gap-3 text-left">
                    <HeroStep
                      icon={<Upload aria-hidden="true" className="h-3.5 w-3.5" />}
                      label="Drop multi-format evidence"
                      n={1}
                    />
                    <HeroStep
                      icon={<Workflow aria-hidden="true" className="h-3.5 w-3.5" />}
                      label="Per-file ReAct agents in parallel"
                      n={2}
                    />
                    <HeroStep
                      icon={<Sparkles aria-hidden="true" className="h-3.5 w-3.5" />}
                      label="Cross-file synthesis & ROI scoring"
                      n={3}
                    />
                    <HeroStep
                      icon={<Quote aria-hidden="true" className="h-3.5 w-3.5" />}
                      label="Cited blueprint — every claim sourced"
                      n={4}
                    />
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>

        <footer className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] pt-5 text-[11px] text-[var(--fg-dim)]">
          <span>
            Built with FastAPI · LangGraph · Redis Stack · Ollama / OpenAI / Groq
          </span>
          <span className="font-mono">
            v0.1 · {new Date().getFullYear()}
          </span>
        </footer>
      </div>
    </main>
  );
}

/* Keep Fragment imported for future composition; export nothing else. */
export { Fragment };
