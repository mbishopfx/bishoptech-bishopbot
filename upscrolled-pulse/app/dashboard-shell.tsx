"use client";

import { startTransition, useEffect, useEffectEvent, useState } from "react";

type Overview = {
  brand: string;
  paths: Record<string, string>;
  queue: {
    name: string;
    pending_count: number;
    pending_jobs: string[];
  };
  sessions: {
    total: number;
    active: number;
    waiting: number;
    attention: number;
    completed: number;
  };
  memory: {
    resources_count: number;
    notes_count: number;
    db_path: string;
    vibes_path: string;
  };
  recent_sessions: SessionSummary[];
};

type SessionSummary = {
  session_id: string;
  runtime: string;
  launch_mode: string | null;
  user_id: string | null;
  status: string;
  original_request: string | null;
  refined_request: string | null;
  final_summary: string | null;
  started_at: string;
  updated_at: string;
  completed_at: string | null;
  response_target: string | null;
};

type SessionDetail = SessionSummary & {
  plan_text: string | null;
  state: Record<string, string>;
  output_tail: string;
  log_path: string;
  log_excerpt: string;
};

type ResourceRow = {
  category: string;
  key: string;
  path: string;
  description: string;
};

type NoteRow = {
  kind: string;
  title: string;
  content: string;
  session_id?: string | null;
  updated_at: string;
};

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function statusTone(status: string) {
  switch (status) {
    case "completed":
      return "bg-emerald-500/12 text-emerald-200 ring-1 ring-emerald-500/25";
    case "attention_needed":
      return "bg-amber-500/12 text-amber-100 ring-1 ring-amber-500/25";
    case "waiting_for_input":
      return "bg-sky-500/12 text-sky-100 ring-1 ring-sky-500/25";
    case "running":
    case "booting":
    case "settled":
      return "bg-zinc-100/8 text-zinc-100 ring-1 ring-white/10";
    default:
      return "bg-zinc-100/6 text-zinc-300 ring-1 ring-white/8";
  }
}

const runtimeModeOptions = [
  { label: "Default routing", value: "" },
  { label: "Gemini YOLO", value: "--yolo" },
  { label: "Codex full-auto", value: "runtime:codex --full-auto" },
  { label: "Codex YOLO shell", value: "runtime:codex --yolo" },
  { label: "Force Gemini", value: "runtime:gemini" },
];

export function DashboardShell() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [resources, setResources] = useState<ResourceRow[]>([]);
  const [notes, setNotes] = useState<NoteRow[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [composerCommand, setComposerCommand] = useState("/cli");
  const [composerMode, setComposerMode] = useState("");
  const [composerText, setComposerText] = useState("");
  const [sessionInput, setSessionInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>("");
  const [lastAction, setLastAction] = useState<string>("");

  const loadBase = useEffectEvent(async () => {
    try {
      const [overviewPayload, sessionsPayload, resourcesPayload, notesPayload] = await Promise.all([
        fetchJson<Overview>("/api/dashboard/overview"),
        fetchJson<{ sessions: SessionSummary[] }>("/api/dashboard/sessions"),
        fetchJson<{ resources: ResourceRow[] }>("/api/dashboard/resources"),
        fetchJson<{ notes: NoteRow[] }>("/api/dashboard/notes"),
      ]);

      setError("");
      setOverview(overviewPayload);
      setSessions(sessionsPayload.sessions);
      setResources(resourcesPayload.resources);
      setNotes(notesPayload.notes);

      if (!selectedSessionId && sessionsPayload.sessions[0]?.session_id) {
        setSelectedSessionId(sessionsPayload.sessions[0].session_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data.");
    }
  });

  const loadSession = useEffectEvent(async (sessionId: string) => {
    if (!sessionId) {
      setSelectedSession(null);
      return;
    }
    try {
      const payload = await fetchJson<SessionDetail>(`/api/dashboard/sessions/${sessionId}`);
      setError("");
      setSelectedSession(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session.");
    }
  });

  useEffect(() => {
    startTransition(() => {
      void loadBase();
    });
  }, [loadBase]);

  useEffect(() => {
    startTransition(() => {
      void loadSession(selectedSessionId);
    });
  }, [loadSession, selectedSessionId]);

  useEffect(() => {
    const id = window.setInterval(() => {
      startTransition(() => {
        void loadBase();
        if (selectedSessionId) {
          void loadSession(selectedSessionId);
        }
      });
    }, 5000);
    return () => window.clearInterval(id);
  }, [loadBase, loadSession, selectedSessionId]);

  const selectedSessionSummary = sessions.find((session) => session.session_id === selectedSessionId) ?? null;

  async function handleTriggerCommand() {
    if (!composerText.trim()) {
      setError("Enter a command to run.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const payload = await fetchJson<{ job_id: string; input_text: string }>("/api/dashboard/commands", {
        method: "POST",
        body: JSON.stringify({
          command: composerCommand,
          runtime_mode: composerMode,
          text: composerText.trim(),
        }),
      });
      setLastAction(`Queued ${composerCommand} as job ${payload.job_id}`);
      setComposerText("");
      startTransition(() => {
        void loadBase();
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to queue command.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSendSessionInput() {
    if (!selectedSessionId || !sessionInput.trim()) {
      setError("Select a session and enter input.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const payload = await fetchJson<{ job_id: string }>("/api/dashboard/sessions/" + selectedSessionId + "/input", {
        method: "POST",
        body: JSON.stringify({ text: sessionInput.trim() }),
      });
      setLastAction(`Queued session input as job ${payload.job_id}`);
      setSessionInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send input.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.07),_transparent_22%),linear-gradient(135deg,_#131416_0%,_#1b1d21_45%,_#111214_100%)] text-zinc-100">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-6 py-6 lg:px-8">
        <header className="grid gap-4 rounded-[28px] border border-white/10 bg-black/25 p-6 shadow-[0_24px_80px_rgba(0,0,0,0.45)] backdrop-blur md:grid-cols-[1.5fr_1fr]">
          <div>
            <div className="mb-3 flex items-center gap-3">
              <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.8)]" />
              <span className="text-xs uppercase tracking-[0.35em] text-zinc-400">Bishop command center</span>
            </div>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-[-0.05em] text-white sm:text-5xl">
              A lean operator console for local-first agent work.
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-zinc-400 sm:text-base">
              Trigger the same worker flow as Slack, watch live sessions, inspect durable memory, and steer active terminals
              without bouncing between tools.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {[
              { label: "Active sessions", value: overview?.sessions.active ?? 0 },
              { label: "Waiting on input", value: overview?.sessions.waiting ?? 0 },
              { label: "Queued jobs", value: overview?.queue.pending_count ?? 0 },
              { label: "Memory notes", value: overview?.memory.notes_count ?? 0 },
            ].map((card) => (
              <div key={card.label} className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                <div className="text-xs uppercase tracking-[0.22em] text-zinc-500">{card.label}</div>
                <div className="mt-2 text-3xl font-semibold tracking-[-0.06em] text-white">{card.value}</div>
              </div>
            ))}
          </div>
        </header>

        {error ? (
          <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {error}
          </div>
        ) : null}
        {lastAction ? (
          <div className="mt-4 rounded-2xl border border-emerald-400/15 bg-emerald-500/8 px-4 py-3 text-sm text-emerald-100">
            {lastAction}
          </div>
        ) : null}

        <section className="mt-6 grid flex-1 gap-6 xl:grid-cols-[420px_minmax(0,1fr)_380px]">
          <div className="space-y-6">
            <div className="rounded-[24px] border border-white/8 bg-zinc-950/55 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold tracking-[-0.03em] text-white">Command composer</h2>
                  <p className="mt-1 text-sm text-zinc-500">Queue the same `/cli` and `/codex` flows the Slack bot uses.</p>
                </div>
                <span className="rounded-full bg-zinc-100/6 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-zinc-400">
                  RQ-backed
                </span>
              </div>

              <div className="grid gap-3">
                <div className="grid grid-cols-2 gap-3">
                  <label className="grid gap-2 text-sm text-zinc-400">
                    Command
                    <select
                      value={composerCommand}
                      onChange={(event) => setComposerCommand(event.target.value)}
                      className="rounded-2xl border border-white/10 bg-zinc-900 px-4 py-3 text-sm text-white outline-none transition focus:border-zinc-300"
                    >
                      <option value="/cli">/cli</option>
                      <option value="/codex">/codex</option>
                    </select>
                  </label>

                  <label className="grid gap-2 text-sm text-zinc-400">
                    Runtime mode
                    <select
                      value={composerMode}
                      onChange={(event) => setComposerMode(event.target.value)}
                      className="rounded-2xl border border-white/10 bg-zinc-900 px-4 py-3 text-sm text-white outline-none transition focus:border-zinc-300"
                    >
                      {runtimeModeOptions.map((option) => (
                        <option key={option.value || "default"} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <label className="grid gap-2 text-sm text-zinc-400">
                  Instruction
                  <textarea
                    value={composerText}
                    onChange={(event) => setComposerText(event.target.value)}
                    placeholder="Inspect the repo, reconcile the listener state, and summarize the blockers."
                    className="min-h-40 rounded-[22px] border border-white/10 bg-zinc-900 px-4 py-4 text-sm leading-7 text-white outline-none transition placeholder:text-zinc-500 focus:border-zinc-300"
                  />
                </label>

                <button
                  type="button"
                  onClick={handleTriggerCommand}
                  disabled={busy}
                  className="inline-flex items-center justify-center rounded-2xl bg-zinc-100 px-4 py-3 text-sm font-medium text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {busy ? "Queueing..." : "Trigger worker"}
                </button>
              </div>
            </div>

            <div className="rounded-[24px] border border-white/8 bg-zinc-950/55 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold tracking-[-0.03em] text-white">System index</h2>
                  <p className="mt-1 text-sm text-zinc-500">Live paths and durable resources the operator prompt can use.</p>
                </div>
                <span className="rounded-full bg-white/6 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-zinc-400">
                  {resources.length} resources
                </span>
              </div>
              <div className="space-y-3">
                {resources.slice(0, 8).map((resource) => (
                  <div key={resource.key} className="rounded-2xl border border-white/6 bg-white/[0.02] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-white">{resource.key}</div>
                      <span className="rounded-full bg-zinc-100/6 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-zinc-400">
                        {resource.category}
                      </span>
                    </div>
                    <p className="mt-2 break-all text-xs leading-6 text-zinc-500">{resource.path}</p>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">{resource.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid min-h-[70vh] gap-6 lg:grid-rows-[minmax(0,300px)_minmax(0,1fr)]">
            <div className="rounded-[24px] border border-white/8 bg-zinc-950/55 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold tracking-[-0.03em] text-white">Session rail</h2>
                  <p className="mt-1 text-sm text-zinc-500">Recent sessions from the durable SQLite lifecycle store.</p>
                </div>
                <span className="rounded-full bg-white/6 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-zinc-400">
                  {sessions.length} visible
                </span>
              </div>

              <div className="grid gap-3 overflow-y-auto pr-1">
                {sessions.map((session) => (
                  <button
                    type="button"
                    key={session.session_id}
                    onClick={() => setSelectedSessionId(session.session_id)}
                    className={`rounded-[22px] border p-4 text-left transition ${
                      session.session_id === selectedSessionId
                        ? "border-zinc-200/35 bg-white/[0.06]"
                        : "border-white/6 bg-white/[0.02] hover:border-white/12 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-white">
                        {session.runtime?.toUpperCase() || "AGENT"} · {session.session_id}
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.22em] ${statusTone(session.status)}`}>
                        {session.status.replaceAll("_", " ")}
                      </span>
                    </div>
                    <p className="mt-3 line-clamp-2 text-sm leading-6 text-zinc-300">
                      {session.original_request || session.refined_request || "No prompt recorded."}
                    </p>
                    <div className="mt-3 flex items-center justify-between text-xs text-zinc-500">
                      <span>{session.launch_mode || "default"}</span>
                      <span>{new Date(session.updated_at).toLocaleString()}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-[24px] border border-white/8 bg-zinc-950/55 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold tracking-[-0.03em] text-white">Inspector</h2>
                  <p className="mt-1 text-sm text-zinc-500">Session details, live tail, and the same follow-up input path Slack threads use.</p>
                </div>
                {selectedSessionSummary ? (
                  <span className={`rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.22em] ${statusTone(selectedSessionSummary.status)}`}>
                    {selectedSessionSummary.status.replaceAll("_", " ")}
                  </span>
                ) : null}
              </div>

              {selectedSession ? (
                <div className="grid gap-5">
                  <div className="grid gap-3 rounded-[22px] border border-white/6 bg-white/[0.02] p-4 md:grid-cols-2">
                    <div>
                      <div className="text-xs uppercase tracking-[0.22em] text-zinc-500">Original request</div>
                      <div className="mt-2 text-sm leading-6 text-zinc-200">{selectedSession.original_request || "No request captured."}</div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.22em] text-zinc-500">Final summary</div>
                      <div className="mt-2 text-sm leading-6 text-zinc-200">{selectedSession.final_summary || "Still in progress."}</div>
                    </div>
                  </div>

                  <div className="grid gap-4 xl:grid-cols-2">
                    <div className="rounded-[22px] border border-white/6 bg-zinc-900/80 p-4">
                      <div className="mb-3 text-xs uppercase tracking-[0.22em] text-zinc-500">Output tail</div>
                      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-6 text-zinc-200">
                        {selectedSession.output_tail || "(No output yet)"}
                      </pre>
                    </div>
                    <div className="rounded-[22px] border border-white/6 bg-zinc-900/80 p-4">
                      <div className="mb-3 text-xs uppercase tracking-[0.22em] text-zinc-500">Session log excerpt</div>
                      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-6 text-zinc-300">
                        {selectedSession.log_excerpt || "(No log excerpt yet)"}
                      </pre>
                    </div>
                  </div>

                  <div className="rounded-[22px] border border-white/6 bg-white/[0.02] p-4">
                    <div className="mb-3 text-xs uppercase tracking-[0.22em] text-zinc-500">Send input to active session</div>
                    <div className="flex flex-col gap-3 sm:flex-row">
                      <textarea
                        value={sessionInput}
                        onChange={(event) => setSessionInput(event.target.value)}
                        placeholder="Continue with the OpenClaw memory path and summarize the cron jobs."
                        className="min-h-24 flex-1 rounded-2xl border border-white/10 bg-zinc-900 px-4 py-3 text-sm leading-6 text-white outline-none transition placeholder:text-zinc-500 focus:border-zinc-300"
                      />
                      <button
                        type="button"
                        onClick={handleSendSessionInput}
                        disabled={busy || !selectedSessionId}
                        className="rounded-2xl bg-white px-5 py-3 text-sm font-medium text-zinc-950 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        Send to worker
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-[22px] border border-dashed border-white/10 px-6 py-12 text-center text-sm text-zinc-500">
                  Select a session to inspect output, logs, and interactive input controls.
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-[24px] border border-white/8 bg-zinc-950/55 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold tracking-[-0.03em] text-white">Durable memory</h2>
                  <p className="mt-1 text-sm text-zinc-500">Recent reusable notes and the backing SQLite location.</p>
                </div>
                <span className="rounded-full bg-white/6 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-zinc-400">
                  SQLite
                </span>
              </div>
              <div className="rounded-2xl border border-white/6 bg-white/[0.02] p-4">
                <div className="text-xs uppercase tracking-[0.22em] text-zinc-500">Memory DB</div>
                <div className="mt-2 break-all font-mono text-xs leading-6 text-zinc-300">{overview?.memory.db_path}</div>
                <div className="mt-4 text-xs uppercase tracking-[0.22em] text-zinc-500">Vibes file</div>
                <div className="mt-2 break-all font-mono text-xs leading-6 text-zinc-300">{overview?.memory.vibes_path}</div>
              </div>

              <div className="mt-4 space-y-3">
                {notes.map((note) => (
                  <div key={`${note.updated_at}-${note.title}`} className="rounded-2xl border border-white/6 bg-white/[0.02] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-white">{note.title}</div>
                      <span className="rounded-full bg-zinc-100/6 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-zinc-400">
                        {note.kind}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-300">{note.content}</p>
                    <div className="mt-3 text-xs text-zinc-500">{new Date(note.updated_at).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[24px] border border-white/8 bg-zinc-950/55 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold tracking-[-0.03em] text-white">Paths and storage</h2>
                  <p className="mt-1 text-sm text-zinc-500">Where BISHOP reads durable state across agents and sessions.</p>
                </div>
                <span className="rounded-full bg-white/6 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-zinc-400">
                  local-first
                </span>
              </div>
              <div className="space-y-3">
                {Object.entries(overview?.paths ?? {}).map(([key, value]) => (
                  <div key={key} className="rounded-2xl border border-white/6 bg-white/[0.02] p-4">
                    <div className="text-xs uppercase tracking-[0.22em] text-zinc-500">{key.replaceAll("_", " ")}</div>
                    <div className="mt-2 break-all font-mono text-xs leading-6 text-zinc-300">{value}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
