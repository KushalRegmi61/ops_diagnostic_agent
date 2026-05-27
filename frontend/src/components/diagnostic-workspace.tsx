"use client";

/**
 * Diagnostic workspace — premium light-mode UI with a balanced 3-column layout.
 *
 * Left rail hosts intake + pipeline controls; the center column is the cited
 * blueprint canvas; the right rail surfaces parsed evidence and the live event
 * stream. Claim bodies are rendered as Markdown so the model's `**bold**`,
 * lists, and headings come through cleanly. Citation chips expand inline to
 * round-trip every claim back to its backend-resolved source excerpt.
 */

import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Compass,
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
  ReactNode,
  useEffect,
  useMemo,
  useRef,
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

import { Markdown } from "./markdown";

type WorkStatus = "idle" | "uploading" | "running" | "complete" | "error";

type TimelineStep = {
  label: string;
  hint: string;
  state: "done" | "active" | "waiting";
};

type AccentKey = "indigo" | "teal" | "amber" | "rose";

/** Operator steering text cap — mirrors backend RunContext.user_context max_length. */
const USER_CONTEXT_MAX = 2000;

const TERMINAL_RUN_EVENT_TYPES = new Set(["run_completed", "run_failed"]);

const ACCENTS: Record<
  AccentKey,
  { bg: string; soft: string; text: string; chipBorder: string }
> = {
  indigo: {
    bg: "bg-indigo-50",
    soft: "border-indigo-200",
    text: "text-indigo-700",
    chipBorder: "border-indigo-200",
  },
  teal: {
    bg: "bg-teal-50",
    soft: "border-teal-200",
    text: "text-teal-700",
    chipBorder: "border-teal-200",
  },
  amber: {
    bg: "bg-amber-50",
    soft: "border-amber-200",
    text: "text-amber-700",
    chipBorder: "border-amber-200",
  },
  rose: {
    bg: "bg-rose-50",
    soft: "border-rose-200",
    text: "text-rose-700",
    chipBorder: "border-rose-200",
  },
};

/** Bytes → compact human-readable size for the upload queue. */
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

/** Append a streamed run event and cap history so the rail stays snappy. */
function appendRunEvent(events: RunEvent[], event: RunEvent): RunEvent[] {
  return [...events, event].slice(-80);
}

/** Open a WS to the run, forward events, resolve on terminal event. */
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

/** Compute the 4 pipeline-stage visuals from local state. */
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
      state: hasBlueprint
        ? "done"
        : run && status === "running"
          ? "active"
          : "waiting",
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

/** Inline excerpt chip — collapsed by default, lazy-fetches excerpt on first open. */
function CitationChip({ source }: { source: Source }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Toggle open + lazy-load backend excerpt on first expand. */
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
        className="group inline-flex max-w-full items-center gap-1.5 rounded-full border border-[var(--border)] bg-white px-2.5 py-1 text-[11px] font-medium text-[var(--fg-muted)] transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
        onClick={toggle}
        type="button"
      >
        <FileText aria-hidden="true" className="h-3 w-3 shrink-0" />
        <span className="max-w-[200px] truncate">{source.file_name}</span>
        <span className="rounded-sm bg-[var(--bg-soft)] px-1 font-mono text-[10px] text-[var(--fg-dim)] group-hover:bg-white">
          {locatorLabel(source.locator)}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <div className="fade-up mt-2 rounded-md border border-[var(--border)] bg-[var(--bg-soft)] p-3">
          {loading ? (
            <div className="space-y-2">
              <div className="h-3 w-4/5 rounded bg-white shimmer" />
              <div className="h-3 w-3/5 rounded bg-white shimmer" />
              <div className="h-3 w-2/3 rounded bg-white shimmer" />
            </div>
          ) : error ? (
            <p className="text-xs text-rose-700">{error}</p>
          ) : (
            <div className="flex gap-2.5">
              <Quote
                aria-hidden="true"
                className="h-3.5 w-3.5 shrink-0 text-indigo-500"
              />
              <p className="whitespace-pre-wrap font-mono text-[11.5px] leading-relaxed text-[var(--fg)]">
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
        <h3 className="text-[14px] font-semibold tracking-tight text-[var(--fg-strong)]">
          {title}
        </h3>
      </div>
      <span className="rounded-full border border-[var(--border)] bg-white px-2 py-0.5 font-mono text-[10px] text-[var(--fg-muted)]">
        {count.toString().padStart(2, "0")}
      </span>
    </div>
  );
}

/** A blueprint subsection (steps / systems / metrics / risks). */
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
              <div className="flex-1 min-w-0">
                <Markdown compact source={claim.text} />
              </div>
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

/** Empty-state pipeline-step row. */
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
      <span className="flex h-7 w-7 items-center justify-center rounded-full border border-[var(--border)] bg-white font-mono text-[11px] text-[var(--fg-muted)]">
        {n}
      </span>
      <span className="flex items-center gap-1.5 text-[12.5px] text-[var(--fg-muted)]">
        {icon}
        {label}
      </span>
    </div>
  );
}

/** Choose icon + tone class per event level / terminal type. */
function eventVisual(event: RunEvent): { icon: ReactNode; tone: string } {
  if (event.level === "error" || event.type === "run_failed") {
    return {
      icon: <AlertCircle aria-hidden="true" className="h-3.5 w-3.5" />,
      tone: "text-rose-600",
    };
  }
  if (event.level === "warning") {
    return {
      icon: <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />,
      tone: "text-amber-600",
    };
  }
  if (event.type === "run_completed") {
    return {
      icon: <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />,
      tone: "text-teal-600",
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
  const [userContext, setUserContext] = useState("");
  const [submittedContext, setSubmittedContext] = useState<string | null>(null);
  const steeringRef = useRef<HTMLTextAreaElement | null>(null);

  /** Auto-grow the steering textarea like Claude/ChatGPT's composer. */
  useEffect(() => {
    const el = steeringRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 360)}px`;
  }, [userContext]);

  /** Tick a live elapsed-time counter while a run is in flight. */
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

  /** Merge newly-chosen files into the queue (de-dup by name+size+mtime). */
  function addFiles(incoming: File[]) {
    setSelectedFiles((prev) => {
      const key = (f: File) => `${f.name}-${f.size}-${f.lastModified}`;
      const seen = new Set(prev.map(key));
      return [...prev, ...incoming.filter((f) => !seen.has(key(f)))];
    });
    setMessage(null);
  }

  /** Native input change handler. */
  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  /** Drop zone handler. */
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

  /** Upload queued files, kick off the run, stream events, then fetch blueprint. */
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
      const trimmedContext = userContext.trim();
      setSubmittedContext(trimmedContext ? trimmedContext : null);
      const createdRun = await createRun(
        refs.map((f) => f.file_id),
        trimmedContext || null,
      );
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
    setUserContext("");
    setSubmittedContext(null);
  }

  const canStart =
    selectedFiles.length > 0 && status !== "uploading" && status !== "running";
  const isWorking = status === "uploading" || status === "running";
  const showHero =
    status === "idle" &&
    uploadedFiles.length === 0 &&
    run == null &&
    blueprint == null;
  const contextCharCount = userContext.length;
  const overLimit = contextCharCount > USER_CONTEXT_MAX;

  return (
    <main className="relative z-10 min-h-screen text-[var(--fg)]">
      {/* Top bar */}
      <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--bg-base)]/80 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1800px] items-center justify-between gap-4 px-6 py-3.5 xl:px-10">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-teal-400 shadow-[0_8px_24px_-12px_rgba(79,70,229,0.5)]">
              <Sparkles aria-hidden="true" className="h-4.5 w-4.5 text-white" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-[15px] font-semibold tracking-tight text-[var(--fg-strong)]">
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
                  ? "border-indigo-300 text-indigo-700"
                  : status === "complete"
                    ? "border-teal-300 text-teal-700"
                    : status === "error"
                      ? "border-rose-300 text-rose-700"
                      : ""
              }`}
            >
              <span
                className={`pulse-dot inline-block h-1.5 w-1.5 rounded-full ${
                  isWorking
                    ? "bg-indigo-500 text-indigo-500"
                    : status === "complete"
                      ? "bg-teal-500 text-teal-500"
                      : status === "error"
                        ? "bg-rose-500 text-rose-500"
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

      <div className="mx-auto flex w-full max-w-[1800px] flex-col gap-6 px-6 py-8 xl:px-10">
        {message ? (
          <div className="fade-up flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            <AlertCircle
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0"
            />
            <p className="flex-1">{message}</p>
            <button
              aria-label="Dismiss"
              className="text-rose-700/80 hover:text-rose-900"
              onClick={() => setMessage(null)}
              type="button"
            >
              <X aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        ) : null}

        {showHero ? (
          /* IDLE — file-first composer hero, centered like a native AI input
             but with files as the primary surface and steering text as a
             secondary, clearly-optional aid. */
          <section className="grid min-h-[calc(100vh-180px)] w-full gap-8 lg:grid-cols-[240px_minmax(0,1fr)]">
            {/* Left nav — pipeline overview */}
            <aside className="lg:sticky lg:top-[88px] lg:self-start">
              <p className="mb-3 px-1 text-[10.5px] font-semibold uppercase tracking-[0.18em] text-[var(--fg-dim)]">
                Pipeline
              </p>
              <ol className="grid gap-2">
                {[
                  { n: 1, label: "Parse", hint: "Typed parsers per file", icon: <FileText className="h-3.5 w-3.5" /> },
                  { n: 2, label: "Per-file agents", hint: "Parallel ReAct loops", icon: <Workflow className="h-3.5 w-3.5" /> },
                  { n: 3, label: "Synthesis", hint: "Cross-file bottlenecks", icon: <Sparkles className="h-3.5 w-3.5" /> },
                  { n: 4, label: "Cited blueprint", hint: "Every claim sourced", icon: <Quote className="h-3.5 w-3.5" /> },
                ].map((s) => (
                  <li
                    className="flex items-start gap-2.5 rounded-lg border border-[var(--border)] bg-white px-3 py-2.5"
                    key={s.n}
                  >
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--bg-soft)] font-mono text-[10px] text-[var(--fg-muted)]">
                      {s.n}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-[var(--fg-strong)]">
                        {s.icon}
                        {s.label}
                      </p>
                      <p className="mt-0.5 text-[11px] text-[var(--fg-dim)]">
                        {s.hint}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </aside>

            {/* Main composer column — fills all remaining width */}
            <div className="flex w-full min-w-0 flex-col">
            <div className="mb-7 flex flex-col items-center text-center">
              <span className="chip mb-4 border-indigo-200 text-indigo-700">
                <Sparkles aria-hidden="true" className="h-3 w-3" />
                File-first diagnostic · not a chatbot
              </span>
              <h1 className="text-balance text-[28px] font-semibold tracking-tight text-[var(--fg-strong)] lg:text-[34px]">
                Diagnose your operation from the evidence.
              </h1>
              <p className="mt-3 max-w-2xl text-[15px] leading-7 text-slate-700">
                Drop the artifacts your team already produces: transcripts,
                docs, CSVs, MBOX threads, and get a cited automation
                blueprint. Every claim round-trips to a real excerpt.
              </p>
            </div>

            <div className="flex w-full flex-1 flex-col overflow-hidden">
              {/* Primary surface — drop zone (fills available height, no card chrome) */}
              <label
                className={`group relative flex flex-1 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl px-6 py-12 text-center transition ${
                  dragOver
                    ? "bg-indigo-50/60"
                    : "bg-transparent hover:bg-indigo-50/30"
                }`}
                onDragLeave={() => setDragOver(false)}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDrop={onDrop}
              >
                <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white shadow-[0_8px_24px_-12px_rgba(79,70,229,0.4)] ring-1 ring-indigo-100">
                  <Upload aria-hidden="true" className="h-6 w-6 text-indigo-600" />
                </span>
                <div className="space-y-1">
                  <p className="text-[15px] font-semibold tracking-tight text-[var(--fg-strong)]">
                    Drop evidence files or click to browse
                  </p>
                  <p className="text-[12px] text-[var(--fg-dim)]">
                    PDF · DOCX · transcripts (VTT/SRT) · CSV · XLSX · MBOX · JSON · MD · TXT
                  </p>
                </div>
                <input
                  className="sr-only"
                  multiple
                  onChange={onFileChange}
                  type="file"
                />

                {selectedFiles.length > 0 ? (
                  <ul
                    className="mt-3 grid w-full max-w-xl gap-1.5"
                    onClick={(e) => e.preventDefault()}
                  >
                    {selectedFiles.map((file) => (
                      <li
                        className="flex w-full min-w-0 items-center gap-2 overflow-hidden rounded-md border border-[var(--border)] bg-white py-1.5 pl-2.5 pr-1.5 text-left"
                        key={`${file.name}-${file.lastModified}`}
                      >
                        <FileText
                          aria-hidden="true"
                          className="h-3.5 w-3.5 shrink-0 text-[var(--fg-dim)]"
                        />
                        <span className="min-w-0 flex-1 truncate text-[12.5px] text-[var(--fg-strong)]">
                          {file.name}
                        </span>
                        <span className="shrink-0 whitespace-nowrap font-mono text-[10.5px] text-[var(--fg-dim)]">
                          {formatBytes(file.size)}
                        </span>
                        <button
                          aria-label={`Remove ${file.name}`}
                          className="ml-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded text-[var(--fg-dim)] transition hover:bg-rose-50 hover:text-rose-600"
                          onClick={(e) => {
                            e.preventDefault();
                            removeFile(file);
                          }}
                          type="button"
                        >
                          <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </label>

              {/* Secondary surface — steering text (clearly optional, flush) */}
              <div className="mt-6">
                <div className="mb-2 flex items-center justify-between">
                  <label
                    className="flex items-center gap-2 text-[12.5px] font-semibold tracking-tight text-[var(--fg-strong)]"
                    htmlFor="user-context"
                  >
                    <Compass
                      aria-hidden="true"
                      className="h-3.5 w-3.5 text-teal-600"
                    />
                    Steering
                    <span className="rounded-full bg-[var(--bg-soft)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--fg-dim)]">
                      optional
                    </span>
                  </label>
                  <span
                    className={`font-mono text-[10.5px] ${
                      overLimit ? "text-rose-600" : "text-[var(--fg-dim)]"
                    }`}
                  >
                    {contextCharCount} / {USER_CONTEXT_MAX}
                  </span>
                </div>
                <textarea
                  className={`block w-full resize-none overflow-y-auto rounded-lg border bg-[var(--bg-soft)]/40 px-4 py-3 text-[15.5px] leading-7 text-[var(--fg-strong)] placeholder:text-[var(--fg-dim)] focus:outline-none focus:ring-2 focus:ring-indigo-300/60 ${
                    overLimit ? "border-rose-300" : "border-[var(--border)]"
                  }`}
                  id="user-context"
                  maxLength={USER_CONTEXT_MAX}
                  onChange={(e) => setUserContext(e.target.value)}
                  placeholder="e.g. We're a 5-person ops team. Focus on customer onboarding, ignore billing. Bias the diagnosis toward fastest wins under 2 weeks."
                  ref={steeringRef}
                  rows={2}
                  style={{ minHeight: 64 }}
                  value={userContext}
                />
                <p className="mt-1.5 text-[11.5px] text-[var(--fg-dim)]">
                  Steering biases the diagnosis order; it is never cited as
                  evidence. Files are the source of truth.
                </p>

                <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-4">
                  <p className="text-[11.5px] text-[var(--fg-dim)]">
                    {selectedFiles.length === 0
                      ? "Add at least one evidence file to begin."
                      : `${selectedFiles.length} file${selectedFiles.length === 1 ? "" : "s"} ready · ${userContext.trim() ? "steered" : "no steering"}`}
                  </p>
                  <button
                    className="btn-primary inline-flex h-11 items-center justify-center gap-2 rounded-lg px-5 text-[13.5px]"
                    disabled={!canStart || overLimit}
                    onClick={onStartRun}
                    type="button"
                  >
                    {isWorking ? (
                      <Loader2
                        aria-hidden="true"
                        className="h-4 w-4 animate-spin"
                      />
                    ) : (
                      <Play aria-hidden="true" className="h-4 w-4" />
                    )}
                    Run diagnostic
                  </button>
                </div>
              </div>
            </div>

            </div>
          </section>
        ) : (
          /* ACTIVE — 3-column workspace: left rail | center blueprint | right rail */
          <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_320px]">
          {/* LEFT RAIL */}
          <aside className="flex flex-col gap-5 lg:sticky lg:top-[88px] lg:self-start">
            {/* Intake */}
            <div className="card p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-50 text-indigo-700">
                    <Upload aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <h2 className="text-[15px] font-semibold tracking-tight text-[var(--fg-strong)]">
                    Intake
                  </h2>
                </div>
                {selectedFiles.length > 0 ? (
                  <span className="chip">{selectedFiles.length} queued</span>
                ) : null}
              </div>
              <p className="mt-1.5 text-[12.5px] text-[var(--fg-muted)]">
                PDF · DOCX · transcripts · CSV · XLSX · MBOX · JSON · MD · TXT
              </p>

              <label
                className={`mt-4 flex min-h-[140px] cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-6 text-center transition ${
                  dragOver
                    ? "border-indigo-400 bg-indigo-50"
                    : "border-[var(--border-strong)] bg-[var(--bg-soft)]/40 hover:border-indigo-300 hover:bg-indigo-50/60"
                }`}
                onDragLeave={() => setDragOver(false)}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDrop={onDrop}
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
                  <Upload aria-hidden="true" className="h-5 w-5" />
                </span>
                <span className="text-[13px] font-medium text-[var(--fg-strong)]">
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
                <ul className="mt-3 grid w-full gap-1.5">
                  {selectedFiles.map((file) => (
                    <li
                      className="flex w-full min-w-0 items-center gap-2 overflow-hidden rounded-md border border-[var(--border)] bg-[var(--bg-soft)]/40 py-1.5 pl-2.5 pr-1.5"
                      key={`${file.name}-${file.lastModified}`}
                    >
                      <FileText
                        aria-hidden="true"
                        className="h-3.5 w-3.5 shrink-0 text-[var(--fg-dim)]"
                      />
                      <span className="min-w-0 flex-1 truncate text-[12.5px] text-[var(--fg-strong)]">
                        {file.name}
                      </span>
                      <span className="shrink-0 whitespace-nowrap font-mono text-[10.5px] text-[var(--fg-dim)]">
                        {formatBytes(file.size)}
                      </span>
                      <button
                        aria-label={`Remove ${file.name}`}
                        className="ml-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded text-[var(--fg-dim)] transition hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-40"
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
                    <Loader2
                      aria-hidden="true"
                      className="h-4 w-4 animate-spin"
                    />
                  ) : (
                    <Play aria-hidden="true" className="h-4 w-4" />
                  )}
                  {isWorking ? "Running…" : "Start diagnostic"}
                </button>
                {status === "complete" || status === "error" ? (
                  <button
                    aria-label="Reset workspace"
                    className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--border)] bg-white text-[var(--fg-muted)] transition hover:border-[var(--border-strong)] hover:text-[var(--fg-strong)]"
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
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-50 text-teal-700">
                    <Workflow aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <h2 className="text-[15px] font-semibold tracking-tight text-[var(--fg-strong)]">
                    Pipeline
                  </h2>
                </div>
                {isWorking ? (
                  <span className="chip border-indigo-300 text-indigo-700">
                    <Loader2
                      aria-hidden="true"
                      className="h-3 w-3 animate-spin"
                    />
                    {Math.floor(elapsed / 60)}:
                    {String(elapsed % 60).padStart(2, "0")}
                  </span>
                ) : null}
              </div>

              <ol className="mt-4 grid gap-2.5">
                {timeline.map((step, idx) => (
                  <li
                    className="relative flex items-start gap-3 rounded-md px-1 py-1.5"
                    key={step.label}
                  >
                    <span
                      className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                        step.state === "done"
                          ? "bg-teal-100 text-teal-700"
                          : step.state === "active"
                            ? "bg-indigo-100 text-indigo-700"
                            : "border border-[var(--border)] bg-white text-[var(--fg-dim)]"
                      }`}
                    >
                      {step.state === "done" ? (
                        <CheckCircle2
                          aria-hidden="true"
                          className="h-3.5 w-3.5"
                        />
                      ) : step.state === "active" ? (
                        <Loader2
                          aria-hidden="true"
                          className="h-3 w-3 animate-spin"
                        />
                      ) : (
                        idx + 1
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-[13px] font-medium ${
                          step.state === "waiting"
                            ? "text-[var(--fg-muted)]"
                            : "text-[var(--fg-strong)]"
                        }`}
                      >
                        {step.label}
                      </p>
                      <p className="mt-0.5 text-[11.5px] text-[var(--fg-dim)]">
                        {step.hint}
                      </p>
                      {step.state === "active" ? (
                        <div className="mt-2 h-[2px] w-full overflow-hidden rounded bg-indigo-100">
                          <div className="h-full w-1/3 rounded shimmer" />
                        </div>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ol>

              {run ? (
                <div className="mt-4 grid gap-1.5 rounded-md border border-[var(--border)] bg-[var(--bg-soft)] p-3 font-mono text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--fg-dim)]">run_id</span>
                    <span className="truncate text-[var(--fg-strong)]">
                      {run.run_id}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--fg-dim)]">status</span>
                    <span className="text-[var(--fg-strong)]">
                      {run.status}
                    </span>
                  </div>
                  {run.langfuse_trace_id ? (
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--fg-dim)]">trace</span>
                      <span className="truncate text-[var(--fg-strong)]">
                        {run.langfuse_trace_id}
                      </span>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </aside>

          {/* CENTER — BLUEPRINT */}
          <section className="min-w-0">
            <div className="card overflow-hidden p-0">
              {blueprint ? (
                <div className="fade-up">
                  {/* Blueprint hero */}
                  <div className="relative border-b border-[var(--border)] bg-gradient-to-br from-indigo-50 via-white to-teal-50 p-6 lg:p-8">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-teal-400 shadow-[0_10px_24px_-10px_rgba(79,70,229,0.55)]">
                          <Zap
                            aria-hidden="true"
                            className="h-5 w-5 text-white"
                          />
                        </span>
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--fg-dim)]">
                            Automation Blueprint
                          </p>
                          <h2 className="mt-0.5 text-[20px] font-semibold tracking-tight text-[var(--fg-strong)]">
                            Opportunity #{blueprint.opportunity_ref}
                          </h2>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="chip border-indigo-200 text-indigo-700">
                          <Target aria-hidden="true" className="h-3 w-3" />
                          {totalClaims} claims
                        </span>
                        <span className="chip border-teal-200 text-teal-700">
                          <Quote aria-hidden="true" className="h-3 w-3" />
                          {totalCitations} citations
                        </span>
                        <span className="chip border-amber-200 text-amber-700">
                          <Gauge aria-hidden="true" className="h-3 w-3" />
                          {uploadedFiles.length} source
                          {uploadedFiles.length === 1 ? "" : "s"}
                        </span>
                      </div>
                    </div>

                    <div className="mt-6 rounded-lg border border-[var(--border)] bg-white/70 p-5 backdrop-blur">
                      <Markdown source={blueprint.summary.text} />
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
                  </div>

                  {/* Bento grid of sections */}
                  <div className="grid gap-6 p-6 lg:grid-cols-2 lg:p-8">
                    <ClaimList
                      accent="indigo"
                      claims={blueprint.steps}
                      icon={
                        <ArrowRight
                          aria-hidden="true"
                          className="h-3.5 w-3.5"
                        />
                      }
                      title="Implementation steps"
                    />
                    <ClaimList
                      accent="teal"
                      claims={blueprint.required_systems}
                      icon={
                        <Settings2 aria-hidden="true" className="h-3.5 w-3.5" />
                      }
                      title="Required systems"
                    />
                    <ClaimList
                      accent="amber"
                      claims={blueprint.success_metrics}
                      icon={
                        <Gauge aria-hidden="true" className="h-3.5 w-3.5" />
                      }
                      title="Success metrics"
                    />
                    <ClaimList
                      accent="rose"
                      claims={blueprint.risks}
                      icon={
                        <AlertTriangle
                          aria-hidden="true"
                          className="h-3.5 w-3.5"
                        />
                      }
                      title="Risks"
                    />
                  </div>
                </div>
              ) : (
                <div className="flex min-h-[420px] flex-col items-center justify-center gap-6 p-8 text-center">
                  <div className="relative">
                    <div className="absolute inset-0 -z-10 rounded-full bg-gradient-to-br from-indigo-200/60 to-teal-200/60 blur-2xl" />
                    <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-[var(--border)] bg-white">
                      {isWorking ? (
                        <Loader2
                          aria-hidden="true"
                          className="h-8 w-8 animate-spin text-indigo-600"
                        />
                      ) : (
                        <Sparkles
                          aria-hidden="true"
                          className="h-8 w-8 text-indigo-600"
                        />
                      )}
                    </div>
                  </div>

                  <div className="max-w-md space-y-2">
                    <h3 className="text-[20px] font-semibold tracking-tight text-[var(--fg-strong)]">
                      {isWorking
                        ? "Synthesizing your blueprint…"
                        : "Your cited blueprint will land here"}
                    </h3>
                    <p className="text-[14px] leading-7 text-[var(--fg-muted)]">
                      Upload operational evidence: meeting transcripts, ops
                      docs, CSV extracts, MBOX threads, and the agent produces a
                      step-by-step automation plan where every claim round-trips
                      to its source.
                    </p>
                  </div>

                  <div className="grid w-full max-w-sm gap-3 text-left">
                    <HeroStep
                      icon={
                        <Upload aria-hidden="true" className="h-3.5 w-3.5" />
                      }
                      label="Drop multi-format evidence"
                      n={1}
                    />
                    <HeroStep
                      icon={
                        <Workflow aria-hidden="true" className="h-3.5 w-3.5" />
                      }
                      label="Per-file ReAct agents in parallel"
                      n={2}
                    />
                    <HeroStep
                      icon={
                        <Sparkles aria-hidden="true" className="h-3.5 w-3.5" />
                      }
                      label="Cross-file synthesis & ROI scoring"
                      n={3}
                    />
                    <HeroStep
                      icon={
                        <Quote aria-hidden="true" className="h-3.5 w-3.5" />
                      }
                      label="Cited blueprint · every claim sourced"
                      n={4}
                    />
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* RIGHT RAIL — joins center column on lg, becomes a sidebar on xl. */}
          <aside className="grid gap-5 lg:grid-cols-2 lg:col-span-2 xl:col-span-1 xl:grid-cols-1 xl:sticky xl:top-[88px] xl:self-start">
            {/* Operator steering (read-only echo of submitted user_context) */}
            {submittedContext ? (
              <div className="card p-5 lg:col-span-2 xl:col-span-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-50 text-teal-700">
                      <Compass aria-hidden="true" className="h-4 w-4" />
                    </span>
                    <h2 className="text-[15px] font-semibold tracking-tight text-[var(--fg-strong)]">
                      Steering
                    </h2>
                  </div>
                  <span className="chip border-teal-200 text-teal-700">
                    applied
                  </span>
                </div>
                <p className="mt-3 whitespace-pre-wrap rounded-md border border-[var(--border)] bg-[var(--bg-soft)]/60 p-3 text-[12.5px] leading-6 text-[var(--fg-strong)]">
                  {submittedContext}
                </p>
                <p className="mt-2 text-[11px] text-[var(--fg-dim)]">
                  Biases ranking and synthesis. Never cited as a source.
                </p>
              </div>
            ) : null}

            {/* Parsed evidence */}
            <div className="card p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-50 text-indigo-700">
                    <Layers aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <h2 className="text-[15px] font-semibold tracking-tight text-[var(--fg-strong)]">
                    Parsed evidence
                  </h2>
                </div>
                <span className="chip">
                  {uploadedFiles.length} file
                  {uploadedFiles.length === 1 ? "" : "s"}
                </span>
              </div>

              {uploadedFiles.length === 0 ? (
                <p className="mt-4 rounded-md border border-dashed border-[var(--border-strong)] bg-[var(--bg-soft)]/40 p-4 text-center text-[12px] text-[var(--fg-dim)]">
                  Parsed file metadata appears here once uploads complete.
                </p>
              ) : (
                <ul className="mt-4 grid max-h-[280px] gap-2 overflow-y-auto pr-1">
                  {uploadedFiles.map((file) => (
                    <li
                      className="flex w-full min-w-0 items-start gap-2.5 overflow-hidden rounded-md border border-[var(--border)] bg-white p-2.5"
                      key={file.file_id}
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-teal-50 text-teal-700">
                        <FileText aria-hidden="true" className="h-3.5 w-3.5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12.5px] font-medium text-[var(--fg-strong)]">
                          {file.file_name}
                        </p>
                        <p className="mt-0.5 truncate font-mono text-[10.5px] text-[var(--fg-dim)]">
                          {file.mime_type}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                          file.parser_status === "ok"
                            ? "border-teal-200 bg-teal-50 text-teal-700"
                            : file.parser_status === "error"
                              ? "border-rose-200 bg-rose-50 text-rose-700"
                              : "border-[var(--border)] bg-[var(--bg-soft)] text-[var(--fg-muted)]"
                        }`}
                      >
                        {file.parser_status}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Live events */}
            <div className="card p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-amber-50 text-amber-700">
                    <Radio aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <h2 className="text-[15px] font-semibold tracking-tight text-[var(--fg-strong)]">
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
                className="mt-3 max-h-[480px] space-y-1.5 overflow-y-auto pr-1"
              >
                {runEvents.length === 0 ? (
                  <p className="rounded-md border border-dashed border-[var(--border-strong)] bg-[var(--bg-soft)]/40 p-4 text-center text-[12px] text-[var(--fg-dim)]">
                    Run updates will stream here in real time.
                  </p>
                ) : (
                  [...runEvents].reverse().map((event) => {
                    const v = eventVisual(event);
                    return (
                      <div
                        className="fade-up flex items-start gap-2.5 rounded-md border border-[var(--border)] bg-white px-2.5 py-2 text-[12px]"
                        key={`${event.run_id}-${event.seq}`}
                      >
                        <span className={`mt-0.5 ${v.tone}`}>{v.icon}</span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[var(--fg-strong)]">
                            {event.message}
                          </p>
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
          </div>
        )}

        <footer className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] pt-5 text-[11px] text-[var(--fg-dim)]">
          <span>
            Built with FastAPI · LangGraph · Redis Stack · Ollama / OpenAI /
            Groq
          </span>
          <span className="font-mono">v0.2 · {new Date().getFullYear()}</span>
        </footer>
      </div>
    </main>
  );
}
