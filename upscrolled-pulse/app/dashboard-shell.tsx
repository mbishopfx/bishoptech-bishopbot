"use client";

import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

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

type ViewKey = "launch" | "sessions" | "memory" | "paths";

const runtimeModeOptions = [
  { label: "Default", value: "" },
  { label: "Gemini YOLO", value: "--yolo" },
  { label: "Codex auto", value: "runtime:codex --full-auto" },
  { label: "Codex shell", value: "runtime:codex --yolo" },
  { label: "Gemini forced", value: "runtime:gemini" },
];

const navItems: Array<{ key: ViewKey; label: string; glyph: string }> = [
  { key: "launch", label: "Launch", glyph: ">" },
  { key: "sessions", label: "Sessions", glyph: "#" },
  { key: "memory", label: "Memory", glyph: "*" },
  { key: "paths", label: "Paths", glyph: "/" },
];

const asciiFrames = [
  String.raw`▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒
░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░
▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒
~~::==--~~::==--~~::==--~~::==--~~::=`,
  String.raw`░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░
▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒
░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░
=--~~::==--~~::==--~~::==--~~::==--~`,
  String.raw`▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░
░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒░░▒▒░░▒
▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░░▒░▒▒░
::==--~~::==--~~::==--~~::==--~~::==`,
];

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "now";
  }
  return new Date(value).toLocaleString();
}

function statusTone(status: string) {
  switch (status) {
    case "completed":
      return "text-emerald-200 bg-emerald-400/10 ring-1 ring-emerald-300/20";
    case "attention_needed":
      return "text-amber-100 bg-amber-400/10 ring-1 ring-amber-300/20";
    case "waiting_for_input":
      return "text-sky-100 bg-sky-400/10 ring-1 ring-sky-300/20";
    case "running":
    case "booting":
    case "settled":
      return "text-zinc-100 bg-white/7 ring-1 ring-white/8";
    default:
      return "text-zinc-300 bg-white/5 ring-1 ring-white/6";
  }
}

function trimError(text: string) {
  return text.length > 180 ? `${text.slice(0, 177)}...` : text;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 4500);
  try {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
      signal: controller.signal,
    });

    const bodyText = await response.text();
    let payload: unknown = {};
    if (bodyText) {
      try {
        payload = JSON.parse(bodyText);
      } catch {
        payload = { error: bodyText };
      }
    }
    if (!response.ok) {
      const errorPayload = payload as { error?: string; detail?: string };
      throw new Error(errorPayload.error || errorPayload.detail || `Request failed: ${response.status}`);
    }
    return payload as T;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function AsciiBackdrop() {
  const [frameIndex, setFrameIndex] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setFrameIndex((value) => (value + 1) % asciiFrames.length);
    }, 240);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_12%,rgba(255,255,255,0.15),transparent_0%,transparent_30%),radial-gradient(circle_at_78%_18%,rgba(255,255,255,0.07),transparent_0%,transparent_26%),linear-gradient(150deg,rgba(255,255,255,0.03),transparent_35%,transparent_70%,rgba(255,255,255,0.02))]" />
      <pre className="ascii-rain absolute -top-10 right-[-8%] select-none text-[10px] leading-4 text-white/10 sm:text-xs">
        {asciiFrames[frameIndex]}
      </pre>
      <pre className="ascii-rain absolute bottom-[-4%] left-[8%] select-none text-[10px] leading-4 text-white/8 sm:text-xs">
        {asciiFrames[(frameIndex + 1) % asciiFrames.length]}
      </pre>
    </div>
  );
}

export function DashboardShell() {
  const bootstrappedRef = useRef(false);
  const pollLockRef = useRef(false);
  const [view, setView] = useState<ViewKey>("launch");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [resources, setResources] = useState<ResourceRow[]>([]);
  const [notes, setNotes] = useState<NoteRow[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [composerCommand, setComposerCommand] = useState("/cli");
  const [composerMode, setComposerMode] = useState("");
  const [composerText, setComposerText] = useState("");
  const [sessionInput, setSessionInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState("");
  const [connectionIssue, setConnectionIssue] = useState("");
  const [lastSyncedAt, setLastSyncedAt] = useState<string>("");

  const loadReferenceData = useEffectEvent(async () => {
    const [resourcesResult, notesResult] = await Promise.allSettled([
      fetchJson<{ resources: ResourceRow[] }>("/api/dashboard/resources"),
      fetchJson<{ notes: NoteRow[] }>("/api/dashboard/notes"),
    ]);

    if (resourcesResult.status === "fulfilled") {
      setResources(resourcesResult.value.resources);
    }
    if (notesResult.status === "fulfilled") {
      setNotes(notesResult.value.notes);
    }
  });

  const loadLiveData = useEffectEvent(async (silent = false) => {
    const [overviewResult, sessionsResult] = await Promise.allSettled([
      fetchJson<Overview>("/api/dashboard/overview"),
      fetchJson<{ sessions: SessionSummary[] }>("/api/dashboard/sessions"),
    ]);

    const overviewOk = overviewResult.status === "fulfilled";
    const sessionsOk = sessionsResult.status === "fulfilled";

    if (overviewOk) {
      setOverview(overviewResult.value);
    }
    if (sessionsOk) {
      setSessions(sessionsResult.value.sessions);
      if (!selectedSessionId && sessionsResult.value.sessions[0]?.session_id) {
        setSelectedSessionId(sessionsResult.value.sessions[0].session_id);
      }
    }

    if (overviewOk || sessionsOk) {
      setConnectionIssue("");
      setLastSyncedAt(new Date().toLocaleTimeString());
      return sessionsOk ? sessionsResult.value.sessions : sessions;
    }

    const message =
      overviewResult.status === "rejected"
        ? overviewResult.reason instanceof Error
          ? overviewResult.reason.message
          : "Dashboard backend is unavailable."
        : sessionsResult.status === "rejected" && sessionsResult.reason instanceof Error
          ? sessionsResult.reason.message
          : "Dashboard backend is unavailable.";

    if (!silent || (!overview && sessions.length === 0)) {
      setConnectionIssue(trimError(message));
    }
    return sessions;
  });

  const loadSelectedSession = useEffectEvent(async (sessionId: string, silent = false) => {
    if (!sessionId) {
      setSelectedSession(null);
      return;
    }

    try {
      const payload = await fetchJson<SessionDetail>(`/api/dashboard/sessions/${sessionId}`);
      setSelectedSession(payload);
      if (!silent) {
        setConnectionIssue("");
      }
    } catch (error) {
      if (!silent) {
        setConnectionIssue(error instanceof Error ? trimError(error.message) : "Failed to load session.");
      }
    }
  });

  useEffect(() => {
    if (bootstrappedRef.current) {
      return;
    }
    bootstrappedRef.current = true;
    startTransition(() => {
      void loadLiveData(false);
      void loadReferenceData();
    });
  }, [loadLiveData, loadReferenceData]);

  useEffect(() => {
    startTransition(() => {
      void loadSelectedSession(selectedSessionId, false);
    });
  }, [loadSelectedSession, selectedSessionId]);

  useEffect(() => {
    let tick = 0;
    const id = window.setInterval(() => {
      if (document.visibilityState === "hidden" || pollLockRef.current) {
        return;
      }
      pollLockRef.current = true;
      tick += 1;
      startTransition(() => {
        void Promise.all([
          loadLiveData(true),
          view === "sessions" && selectedSessionId ? loadSelectedSession(selectedSessionId, true) : Promise.resolve(),
          (view === "memory" || view === "paths") && tick % 6 === 0 ? loadReferenceData() : Promise.resolve(),
        ]).finally(() => {
          pollLockRef.current = false;
        });
      });
    }, view === "sessions" ? 9000 : 18000);
    return () => {
      window.clearInterval(id);
      pollLockRef.current = false;
    };
  }, [loadLiveData, loadReferenceData, loadSelectedSession, selectedSessionId, view]);

  const selectedSessionSummary = sessions.find((session) => session.session_id === selectedSessionId) ?? null;

  async function handleTriggerCommand() {
    if (!composerText.trim()) {
      setBanner("Enter a command before launching.");
      return;
    }

    setBusy(true);
    try {
      const payload = await fetchJson<{ job_id: string }>("/api/dashboard/commands", {
        method: "POST",
        body: JSON.stringify({
          command: composerCommand,
          runtime_mode: composerMode,
          text: composerText.trim(),
        }),
      });
      setBanner(`Queued ${composerCommand} as ${payload.job_id}`);
      setConnectionIssue("");
      setComposerText("");
      setView("sessions");
      window.setTimeout(() => {
        startTransition(() => {
          void (async () => {
            const latestSessions = await loadLiveData(true);
            const nextSession =
              latestSessions?.find((session) => session.user_id === "dashboard") ?? latestSessions?.[0] ?? null;
            if (nextSession?.session_id) {
              setSelectedSessionId(nextSession.session_id);
              await loadSelectedSession(nextSession.session_id, true);
            }
          })();
        });
      }, 700);
    } catch (error) {
      setConnectionIssue(error instanceof Error ? trimError(error.message) : "Failed to queue command.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSendSessionInput() {
    if (!selectedSessionId || !sessionInput.trim()) {
      setBanner("Pick a session and write the follow-up first.");
      return;
    }

    setBusy(true);
    try {
      const payload = await fetchJson<{ job_id: string }>(`/api/dashboard/sessions/${selectedSessionId}/input`, {
        method: "POST",
        body: JSON.stringify({ text: sessionInput.trim() }),
      });
      setBanner(`Queued follow-up as ${payload.job_id}`);
      setConnectionIssue("");
      setSessionInput("");
      startTransition(() => void loadSelectedSession(selectedSessionId, true));
    } catch (error) {
      setConnectionIssue(error instanceof Error ? trimError(error.message) : "Failed to send follow-up.");
    } finally {
      setBusy(false);
    }
  }

  const stats = [
    { label: "active", value: overview?.sessions.active ?? 0 },
    { label: "waiting", value: overview?.sessions.waiting ?? 0 },
    { label: "queue", value: overview?.queue.pending_count ?? 0 },
    { label: "notes", value: overview?.memory.notes_count ?? 0 },
  ];

  return (
    <main className="relative min-h-screen overflow-hidden bg-[linear-gradient(145deg,#101113_0%,#17191d_46%,#0b0c0e_100%)] text-zinc-100">
      <AsciiBackdrop />
      <div className="relative flex min-h-screen">
        <aside className="hidden w-20 shrink-0 border-r border-white/7 bg-black/20 backdrop-blur md:flex md:flex-col md:items-center md:justify-between md:py-8">
          <div className="space-y-6">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] text-lg tracking-[0.3em] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
              B
            </div>
            <nav className="space-y-3">
              {navItems.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setView(item.key)}
                  className={`group flex w-16 flex-col items-center gap-2 rounded-2xl px-2 py-3 text-[11px] uppercase tracking-[0.22em] transition ${
                    view === item.key ? "bg-white/[0.08] text-white" : "text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-200"
                  }`}
                >
                  <span className="text-sm">{item.glyph}</span>
                  <span>{item.label}</span>
                </button>
              ))}
            </nav>
          </div>

          <div className="operator-pill rotate-180 [writing-mode:vertical-rl]">liquid metal local-first</div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-white/7 bg-black/18 px-5 py-4 backdrop-blur sm:px-7">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-2">
                <div className="operator-pill">{overview?.brand ?? "BISHOP"} / command center</div>
                <div className="flex flex-wrap gap-2 text-xs uppercase tracking-[0.24em] text-zinc-500">
                  {stats.map((stat) => (
                    <div key={stat.label} className="rounded-full border border-white/7 bg-white/[0.03] px-3 py-2 text-zinc-200">
                      {stat.label} <span className="ml-2 text-white">{stat.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.2em] text-zinc-500">
                <span className="rounded-full border border-white/7 bg-white/[0.03] px-3 py-2">
                  sync {lastSyncedAt || "pending"}
                </span>
                <span className="rounded-full border border-white/7 bg-white/[0.03] px-3 py-2">
                  api {connectionIssue ? "degraded" : "stable"}
                </span>
              </div>
            </div>
            <div className="mt-4 flex gap-2 overflow-x-auto md:hidden">
              {navItems.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setView(item.key)}
                  className={`rounded-full border px-3 py-2 text-[11px] uppercase tracking-[0.22em] transition ${
                    view === item.key ? "border-white/14 bg-white/[0.08] text-white" : "border-white/7 bg-white/[0.03] text-zinc-400"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </header>

          {connectionIssue ? (
            <div className="mx-5 mt-4 rounded-2xl border border-amber-300/12 bg-amber-400/8 px-4 py-3 text-sm text-amber-50 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] sm:mx-7">
              {connectionIssue}. Holding the last good state.
            </div>
          ) : null}
          {banner ? (
            <div className="mx-5 mt-4 rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3 text-sm text-zinc-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] sm:mx-7">
              {banner}
            </div>
          ) : null}

          <div className="flex min-h-0 flex-1 flex-col gap-5 px-5 py-5 sm:px-7 lg:flex-row">
            <section className="panel-stage min-h-[72vh] flex-1 rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-5 shadow-[0_30px_80px_rgba(0,0,0,0.45)] backdrop-blur">
              {view === "launch" ? (
                <div className="view-stage grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
                  <div className="space-y-4">
                    <div className="operator-block">
                      <div className="operator-label">launch</div>
                      <div className="operator-copy">Same queue. Same worker. Same runtime flow as Slack.</div>
                    </div>

                    <div className="rounded-[24px] border border-white/8 bg-black/18 p-4">
                      <div className="grid gap-3 md:grid-cols-2">
                        <label className="grid gap-2 text-sm text-zinc-400">
                          Command
                          <select
                            value={composerCommand}
                            onChange={(event) => setComposerCommand(event.target.value)}
                            className="rounded-2xl border border-white/10 bg-zinc-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-zinc-300"
                          >
                            <option value="/cli">/cli</option>
                            <option value="/codex">/codex</option>
                          </select>
                        </label>
                        <label className="grid gap-2 text-sm text-zinc-400">
                          Mode
                          <select
                            value={composerMode}
                            onChange={(event) => setComposerMode(event.target.value)}
                            className="rounded-2xl border border-white/10 bg-zinc-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-zinc-300"
                          >
                            {runtimeModeOptions.map((option) => (
                              <option key={option.label} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <label className="mt-3 grid gap-2 text-sm text-zinc-400">
                        Instruction
                        <textarea
                          value={composerText}
                          onChange={(event) => setComposerText(event.target.value)}
                          placeholder="Use openbrowser to inspect the issue, then summarize the blockers."
                          className="min-h-48 rounded-[22px] border border-white/10 bg-zinc-950/80 px-4 py-4 font-mono text-sm leading-7 text-white outline-none transition placeholder:text-zinc-500 focus:border-zinc-300"
                        />
                      </label>

                      <div className="mt-3 flex items-center justify-between gap-3">
                        <div className="text-xs uppercase tracking-[0.22em] text-zinc-500">
                          prompt now routes through vibes-full.md
                        </div>
                        <button
                          type="button"
                          onClick={handleTriggerCommand}
                          disabled={busy}
                          className="rounded-2xl border border-white/12 bg-white px-5 py-3 text-sm font-medium text-zinc-950 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {busy ? "Queueing" : "Trigger"}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="operator-block">
                      <div className="operator-label">queue</div>
                      <div className="operator-copy">Recent sessions and the current worker backlog.</div>
                    </div>
                    <div className="grid gap-3">
                      {overview?.recent_sessions.slice(0, 5).map((session) => (
                        <button
                          key={session.session_id}
                          type="button"
                          onClick={() => {
                            setSelectedSessionId(session.session_id);
                            setView("sessions");
                          }}
                          className="rounded-[22px] border border-white/7 bg-white/[0.03] px-4 py-4 text-left transition hover:border-white/14 hover:bg-white/[0.05]"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="text-sm font-medium text-white">
                              {session.runtime.toUpperCase()} · {session.session_id}
                            </div>
                            <span className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.22em] ${statusTone(session.status)}`}>
                              {session.status.replaceAll("_", " ")}
                            </span>
                          </div>
                          <div className="mt-3 text-sm leading-6 text-zinc-300">
                            {session.original_request || session.refined_request || "No request captured."}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}

              {view === "sessions" ? (
                <div className="view-stage grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
                  <div className="space-y-3">
                    {sessions.map((session) => (
                      <button
                        key={session.session_id}
                        type="button"
                        onClick={() => setSelectedSessionId(session.session_id)}
                        className={`w-full rounded-[22px] border px-4 py-4 text-left transition ${
                          selectedSessionId === session.session_id
                            ? "border-white/20 bg-white/[0.08]"
                            : "border-white/7 bg-white/[0.03] hover:border-white/14 hover:bg-white/[0.05]"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium text-white">{session.session_id}</span>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.22em] ${statusTone(session.status)}`}>
                            {session.status.replaceAll("_", " ")}
                          </span>
                        </div>
                        <div className="mt-2 text-xs uppercase tracking-[0.2em] text-zinc-500">
                          {session.runtime} / {session.launch_mode || "default"}
                        </div>
                        <div className="mt-3 line-clamp-2 text-sm leading-6 text-zinc-300">
                          {session.original_request || session.refined_request || "No request captured."}
                        </div>
                      </button>
                    ))}
                  </div>

                  <div className="space-y-4">
                    <div className="operator-block">
                      <div className="operator-label">session</div>
                      <div className="operator-copy">
                        {selectedSessionSummary
                          ? `${selectedSessionSummary.runtime.toUpperCase()} · ${selectedSessionSummary.session_id}`
                          : "Pick a session from the rail."}
                      </div>
                    </div>

                    {selectedSession ? (
                      <>
                        <div className="grid gap-4 md:grid-cols-2">
                          <div className="rounded-[22px] border border-white/7 bg-black/16 p-4">
                            <div className="operator-label">request</div>
                            <div className="mt-3 text-sm leading-6 text-zinc-200">
                              {selectedSession.original_request || selectedSession.refined_request || "No request captured."}
                            </div>
                          </div>
                          <div className="rounded-[22px] border border-white/7 bg-black/16 p-4">
                            <div className="operator-label">summary</div>
                            <div className="mt-3 text-sm leading-6 text-zinc-200">
                              {selectedSession.final_summary || "Still running."}
                            </div>
                          </div>
                        </div>

                        <div className="grid gap-4 xl:grid-cols-2">
                          <div className="rounded-[22px] border border-white/7 bg-zinc-950/85 p-4">
                            <div className="operator-label">live tail</div>
                            <pre className="mt-3 max-h-[24rem] overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-6 text-zinc-200">
                              {selectedSession.output_tail || "(No output yet)"}
                            </pre>
                          </div>
                          <div className="rounded-[22px] border border-white/7 bg-zinc-950/85 p-4">
                            <div className="operator-label">log excerpt</div>
                            <pre className="mt-3 max-h-[24rem] overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-6 text-zinc-300">
                              {selectedSession.log_excerpt || "(No log excerpt yet)"}
                            </pre>
                          </div>
                        </div>

                        <div className="rounded-[22px] border border-white/7 bg-black/16 p-4">
                          <div className="operator-label">follow-up</div>
                          <div className="mt-3 flex flex-col gap-3 lg:flex-row">
                            <textarea
                              value={sessionInput}
                              onChange={(event) => setSessionInput(event.target.value)}
                              placeholder="Continue with the OpenClaw memory path and summarize what changed."
                              className="min-h-24 flex-1 rounded-2xl border border-white/10 bg-zinc-950/80 px-4 py-3 text-sm leading-6 text-white outline-none transition placeholder:text-zinc-500 focus:border-zinc-300"
                            />
                            <button
                              type="button"
                              onClick={handleSendSessionInput}
                              disabled={busy || !selectedSessionId}
                              className="rounded-2xl border border-white/12 bg-white px-5 py-3 text-sm font-medium text-zinc-950 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              Send
                            </button>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="rounded-[22px] border border-dashed border-white/10 px-6 py-12 text-center text-sm text-zinc-500">
                        No session selected.
                      </div>
                    )}
                  </div>
                </div>
              ) : null}

              {view === "memory" ? (
                <div className="view-stage grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
                  <div className="rounded-[22px] border border-white/7 bg-black/16 p-4">
                    <div className="operator-label">memory</div>
                    <div className="mt-3 space-y-3">
                      <div className="rounded-2xl border border-white/7 bg-white/[0.03] px-4 py-3">
                        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">db</div>
                        <div className="mt-2 break-all font-mono text-xs leading-6 text-zinc-200">{overview?.memory.db_path}</div>
                      </div>
                      <div className="rounded-2xl border border-white/7 bg-white/[0.03] px-4 py-3">
                        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">vibes</div>
                        <div className="mt-2 break-all font-mono text-xs leading-6 text-zinc-200">{overview?.memory.vibes_path}</div>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {notes.map((note) => (
                      <div key={`${note.updated_at}-${note.title}`} className="rounded-[22px] border border-white/7 bg-black/16 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-medium text-white">{note.title}</div>
                          <span className="rounded-full bg-white/7 px-2 py-1 text-[10px] uppercase tracking-[0.22em] text-zinc-300">
                            {note.kind}
                          </span>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-zinc-300">{note.content}</p>
                        <div className="mt-3 text-xs uppercase tracking-[0.2em] text-zinc-500">{formatTimestamp(note.updated_at)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {view === "paths" ? (
                <div className="view-stage grid gap-3 xl:grid-cols-2">
                  {resources.map((resource) => (
                    <div key={resource.key} className="rounded-[22px] border border-white/7 bg-black/16 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-medium text-white">{resource.key}</div>
                        <span className="rounded-full bg-white/7 px-2 py-1 text-[10px] uppercase tracking-[0.22em] text-zinc-300">
                          {resource.category}
                        </span>
                      </div>
                      <div className="mt-3 break-all font-mono text-xs leading-6 text-zinc-300">{resource.path}</div>
                      <div className="mt-3 text-sm leading-6 text-zinc-400">{resource.description}</div>
                    </div>
                  ))}
                </div>
              ) : null}
            </section>

            <aside className="panel-stage w-full shrink-0 space-y-4 rounded-[28px] border border-white/8 bg-black/16 p-5 shadow-[0_24px_70px_rgba(0,0,0,0.32)] backdrop-blur lg:w-[23rem]">
              <div className="operator-block">
                <div className="operator-label">status</div>
                <div className="operator-copy">Live state, queue pressure, and current selection.</div>
              </div>

              <div className="grid gap-3">
                {stats.map((stat) => (
                  <div key={stat.label} className="rounded-[22px] border border-white/7 bg-white/[0.03] px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.22em] text-zinc-500">{stat.label}</div>
                    <div className="mt-2 text-3xl font-semibold tracking-[-0.06em] text-white">{stat.value}</div>
                  </div>
                ))}
              </div>

              <div className="rounded-[22px] border border-white/7 bg-black/16 p-4">
                <div className="operator-label">selected</div>
                {selectedSessionSummary ? (
                  <div className="mt-3 space-y-3 text-sm leading-6 text-zinc-300">
                    <div className="flex items-center justify-between gap-3">
                      <span>{selectedSessionSummary.session_id}</span>
                      <span className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.22em] ${statusTone(selectedSessionSummary.status)}`}>
                        {selectedSessionSummary.status.replaceAll("_", " ")}
                      </span>
                    </div>
                    <div>{selectedSessionSummary.runtime.toUpperCase()} / {selectedSessionSummary.launch_mode || "default"}</div>
                    <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">{formatTimestamp(selectedSessionSummary.updated_at)}</div>
                  </div>
                ) : (
                  <div className="mt-3 text-sm text-zinc-500">No active selection.</div>
                )}
              </div>

              <div className="rounded-[22px] border border-white/7 bg-black/16 p-4">
                <div className="operator-label">paths</div>
                <div className="mt-3 space-y-3">
                  {Object.entries(overview?.paths ?? {})
                    .slice(0, 4)
                    .map(([key, value]) => (
                      <div key={key}>
                        <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">{key.replaceAll("_", " ")}</div>
                        <div className="mt-1 break-all font-mono text-xs leading-5 text-zinc-300">{value}</div>
                      </div>
                    ))}
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </main>
  );
}
