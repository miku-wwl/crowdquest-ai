import { useEffect, useRef, useState } from "react";
import "./obs-admin.css";

type Session = { authenticated: boolean; csrf: string; configured: boolean };
type Status = {
  connected: boolean;
  revision: string;
  obs_version: string;
  websocket_version: string;
  scenes: string[];
  current_scene: string;
  streaming: boolean;
  recording: {
    active: boolean;
    paused: boolean;
    elapsed_seconds: number;
    output_path: string | null;
  };
  overlay: {
    found: boolean;
    valid: boolean;
    enabled: boolean | null;
    url: string | null;
  };
};
const base = "/api/obs-admin";
const messages: Record<string, string> = {
  VERIFIED: "OBS confirmed the requested state.",
  STATE_RECONCILED:
    "The reply was lost. A fresh OBS query confirms the current state; the command was not retried.",
  ALREADY_IN_STATE:
    "OBS is already in that recording state. No command was sent.",
  ALREADY_CURRENT: "That scene is already current. No command was sent.",
  REFRESH_REQUEST_ACKNOWLEDGED:
    "OBS acknowledged the refresh button. Check the actual OBS preview for rendering.",
};
const errors: Record<string, string> = {
  OBS_UNAVAILABLE:
    "Open OBS and check that its WebSocket server is listening on port 4455.",
  OBS_AUTH_FAILED:
    "Correct the OBS password through private terminal setup. Keep authentication enabled.",
  OBS_AUTH_REQUIRED:
    "Personally enable password authentication in OBS WebSocket settings.",
  OBS_STALE:
    "This page state was already used. Refresh status before another operation.",
  OBS_BUSY:
    "Another OBS operation is still running. Wait, then refresh status.",
  OBS_OUTCOME_UNKNOWN:
    "Inspect OBS and refresh status. The command was not retried.",
  ADMIN_LOGIN_FAILED:
    "The Admin passphrase was not accepted. Use your separate local passphrase.",
  ADMIN_AUTH_REQUIRED: "Your local Admin session expired. Sign in again.",
};

class AdminError extends Error {
  constructor(
    message: string,
    readonly unauthorized = false,
  ) {
    super(message);
  }
}

async function api(path: string, options: RequestInit = {}) {
  const response = await fetch(base + path, {
    credentials: "same-origin",
    cache: "no-store",
    signal: AbortSignal.timeout(30000),
    ...options,
  });
  const value = await response.json();
  if (!response.ok) {
    // Show only application-owned errors, never echo arbitrary server payloads.
    const code =
      typeof value.detail === "string" ? value.detail : "REQUEST_REJECTED";
    const safe = /^[A-Z_]{1,64}$/.test(code) ? code : "REQUEST_REJECTED";
    throw new AdminError(safe, response.status === 401);
  }
  return value;
}

export function ObsAdmin() {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [password, setPassword] = useState("");
  const [scene, setScene] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const inFlight = useRef(false);

  function failed(value: unknown) {
    setStatus(null); // never leave controls enabled on stale/disconnected state
    setError(
      value instanceof AdminError
        ? `${value.message}${errors[value.message] ? ` — ${errors[value.message]}` : ""}`
        : "Connection lost. Refresh status and inspect OBS before another operation. No automatic retry.",
    );
    if (
      value instanceof AdminError &&
      value.unauthorized &&
      value.message !== "ADMIN_LOGIN_FAILED"
    ) {
      setSession(null);
      void api("/session")
        .then(setSession)
        .catch(() => {});
    }
  }

  async function loadStatus() {
    const next: Status = await api("/status");
    setStatus(next);
    setScene((old) => (next.scenes.includes(old) ? old : next.current_scene));
    return next;
  }

  async function perform(operation: () => Promise<void>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (value) {
      failed(value);
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  }

  useEffect(() => {
    let active = true;
    api("/session")
      .then((value: Session) => {
        if (active) setSession(value);
      })
      .catch((value) => {
        if (active) failed(value);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!session?.authenticated) return;
    let active = true;
    async function poll() {
      if (!active || inFlight.current) return;
      inFlight.current = true;
      try {
        const next: Status = await api("/status");
        if (active) {
          setStatus(next);
          setScene((old) =>
            next.scenes.includes(old) ? old : next.current_scene,
          );
          setError("");
        }
      } catch (value) {
        if (active) failed(value);
      } finally {
        inFlight.current = false;
      }
    }
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [session?.authenticated]);

  async function post(path: string, body: object) {
    return api(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session!.csrf,
      },
      body: JSON.stringify(body),
    });
  }

  function command(path: string, extra: object = {}) {
    if (!status || !session?.authenticated) return;
    void perform(async () => {
      setFeedback("");
      const result = await post(path, { revision: status.revision, ...extra });
      setFeedback(
        messages[result.result] || "Operation finished. Check OBS status.",
      );
      await loadStatus();
    });
  }

  const disabled = busy || !status?.connected || status.streaming;
  return (
    <div className="shell obs-admin-shell">
      <header>
        <a className="brand" href="/">
          <span className="brand-mark">CQ</span>CrowdQuest{" "}
          <span className="brand-ai">AI</span>
        </a>
        <span className="phase">LOCAL OBS ADMIN</span>
        <span className={`connection ${status?.connected ? "live" : ""}`}>
          <i />
          {status?.connected ? "Connected" : "Disconnected"}
        </span>
      </header>
      <main>
        <div className="hero">
          <div>
            <p className="eyebrow">YOUR STUDIO. LOCAL CONTROL.</p>
            <h1>A small desk for OBS.</h1>
            <p className="lede">
              Choose a scene, refresh your overlay and record locally.
            </p>
          </div>
          {session?.authenticated && (
            <button
              disabled={busy}
              onClick={() =>
                void perform(async () => {
                  await post("/logout", {});
                  setStatus(null);
                  setSession(await api("/session"));
                  setFeedback("Signed out.");
                })
              }
            >
              Sign out
            </button>
          )}
        </div>
        <p className="obs-note">
          Loopback only · Explicit controls · Recording is processed by OBS
        </p>
        {error && (
          <div className="obs-error" role="alert">
            {error}
            <p>
              Check OBS WebSocket settings, keep authentication enabled, and
              refresh status. Enter passwords only through private setup or the
              local Admin sign-in.
            </p>
          </div>
        )}
        {feedback && (
          <div className="obs-feedback" role="status">
            {feedback}
          </div>
        )}
        {busy && <p role="status">Waiting for OBS…</p>}
        {!session ? (
          <p>Loading local session…</p>
        ) : !session.authenticated ? (
          <section className="obs-panel obs-signin">
            <h2>Local Admin sign-in</h2>
            <p>
              Use your separate Admin passphrase. The OBS WebSocket password
              stays on the backend.
            </p>
            {!session.configured && (
              <p role="alert">
                Setup required: run <code>python -m crowdquest.obs_setup</code>{" "}
                in your private local terminal. Restart only when safe.
              </p>
            )}
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void perform(async () => {
                  try {
                    setSession(await post("/login", { password }));
                  } finally {
                    setPassword("");
                  }
                });
              }}
            >
              <label htmlFor="admin-passphrase">Admin passphrase</label>
              <input
                id="admin-passphrase"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                maxLength={256}
              />
              <button disabled={busy || !password || !session.configured}>
                Sign in locally
              </button>
            </form>
          </section>
        ) : (
          <div className="obs-grid">
            <section className="obs-panel">
              <h2>OBS Connection</h2>
              <dl>
                <dt>OBS version</dt>
                <dd>{status?.obs_version || "—"}</dd>
                <dt>WebSocket version</dt>
                <dd>{status?.websocket_version || "—"}</dd>
                <dt>Current scene</dt>
                <dd>{status?.current_scene || "—"}</dd>
                <dt>Streaming</dt>
                <dd>
                  {status
                    ? status.streaming
                      ? "Active · controls blocked"
                      : "Inactive"
                    : "Unknown"}
                </dd>
              </dl>
              <button
                disabled={busy}
                onClick={() =>
                  void perform(async () => {
                    await loadStatus();
                  })
                }
              >
                Refresh status
              </button>
            </section>
            <section className="obs-panel">
              <h2>Scene Control</h2>
              <label htmlFor="obs-scene">Existing scene</label>
              <select
                id="obs-scene"
                value={scene}
                onChange={(event) => setScene(event.target.value)}
                disabled={disabled}
              >
                {!status && <option value="">Connect to OBS first</option>}
                {status?.scenes.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
              <button
                disabled={disabled || !scene || scene === status?.current_scene}
                onClick={() => command("/scene", { scene })}
              >
                Switch scene
              </button>
              <p>Only existing program scenes can be selected.</p>
            </section>
            <section className="obs-panel">
              <h2>CrowdQuest Overlay</h2>
              <dl>
                <dt>Existing source</dt>
                <dd>
                  {status?.overlay.found ? "CrowdQuest Overlay" : "Not found"}
                </dd>
                <dt>Enabled in current scene</dt>
                <dd>
                  {status?.overlay.enabled == null
                    ? "Not directly present / unknown"
                    : status.overlay.enabled
                      ? "Yes"
                      : "No"}
                </dd>
                <dt>Local URL</dt>
                <dd>{status?.overlay.url || "No validated local URL"}</dd>
              </dl>
              <button
                disabled={disabled || !status?.overlay.valid}
                onClick={() => command("/overlay/refresh")}
              >
                Refresh CrowdQuest overlay
              </button>
              <p>
                Refreshes the existing source. Check its actual OBS preview for
                visibility.
              </p>
            </section>
            <section className="obs-panel">
              <h2>Local Recording</h2>
              <div
                className={`obs-record-state ${status?.recording.active ? "active" : ""}`}
              >
                <strong>
                  {status
                    ? status.recording.active
                      ? status.recording.paused
                        ? "Paused"
                        : "Recording"
                      : "Stopped"
                    : "Unknown"}
                </strong>
                <span>
                  {status
                    ? `${Math.floor(status.recording.elapsed_seconds)} seconds`
                    : "—"}
                </span>
              </div>
              <div className="obs-actions">
                <button
                  disabled={disabled || !!status?.recording.active}
                  onClick={() => command("/record/start")}
                >
                  Start Recording
                </button>
                <button
                  disabled={disabled || !status?.recording.active}
                  onClick={() => command("/record/stop")}
                >
                  Stop Recording
                </button>
              </div>
              <p>
                Output file:{" "}
                <span className="obs-path">
                  {status?.recording.output_path ||
                    "Available after an acknowledged stop in this server session."}
                </span>
              </p>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
