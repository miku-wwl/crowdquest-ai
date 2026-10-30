import { useEffect, useRef, useState } from "react";
import {
  anchorState,
  drawBroadcast,
  SCENES,
  sceneFor,
  atTime,
  type BroadcastState,
  type Scene,
} from "./studio-canvas";
import {
  CanvasRecorder,
  MAX_SECONDS,
  supportedCodec,
  validFilename,
  type RecorderSnapshot,
} from "./studio-recorder";
import "./studio.css";

type Me = { authenticated: boolean; configured?: boolean; csrf?: string };
type SystemStatus = {
  backend: string;
  eventsub: string;
  worker: string;
  challenge_state: string | null;
  last_outcome: { kind: string; presentation: string } | null;
  evidence: string;
  obs_required: boolean;
};
const initial: BroadcastState = { state: "connecting" };
const initialRecorder: RecorderSnapshot = {
  state: "Idle",
  seconds: 0,
  error: "",
  recordings: [],
};
function filename() {
  return `crowdquest-${new Date()
    .toISOString()
    .replace(/[^0-9]/g, "")
    .slice(0, 14)}-${crypto.randomUUID().slice(0, 8)}.webm`;
}

async function request(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    signal: options.signal
      ? AbortSignal.any([options.signal, AbortSignal.timeout(5000)])
      : AbortSignal.timeout(5000),
  });
  if (!response.ok)
    throw new Error(
      response.status === 401
        ? "OWNER_SIGN_IN_REQUIRED"
        : response.status === 409
          ? "ACK_REJECTED"
          : "BROADCAST_CONNECTION_UNAVAILABLE",
    );
  return response.json();
}

export function BroadcastStudio() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const live = useRef<BroadcastState>(initial);
  const layoutRef = useRef<Scene | "Live">("Live");
  const recorder = useRef<CanvasRecorder | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [presentation, setPresentation] = useState(initial);
  const [layout, setLayout] = useState<Scene | "Live">("Live");
  const [resolution, setResolution] = useState("1920x1080");
  const [recording, setRecording] = useState(initialRecorder);
  const [outputName, setOutputName] = useState(filename);
  const [error, setError] = useState("");
  const [drawn, setDrawn] = useState(false);
  const [deliveryStatus, setDeliveryStatus] = useState("Connecting");
  // A document owns one identity. Errors, visibility and layout do not rotate it.
  const [view] = useState(() => crypto.randomUUID());
  const invalidateDelivery = useRef<() => void>(() => {});
  const [now, setNow] = useState(performance.now());
  const downloaded = useRef(new Set<string>());
  const supported = supportedCodec();
  const [width, height] = resolution.split("x").map(Number);
  live.current = presentation;
  layoutRef.current = layout;

  useEffect(() => {
    const controller = new CanvasRecorder((value) => {
      setRecording(value);
      if (["Ready", "Interrupted"].includes(value.state))
        setOutputName(filename());
      if (controller.active)
        sessionStorage.setItem("cq_recording_interrupted", "1");
      else sessionStorage.removeItem("cq_recording_interrupted");
    });
    recorder.current = controller;
    if (sessionStorage.getItem("cq_recording_interrupted")) {
      setError(
        "The previous page closed during recording. Unfinalized browser memory cannot be recovered. No recording was restarted.",
      );
      sessionStorage.removeItem("cq_recording_interrupted");
    }
    const unload = (event: BeforeUnloadEvent) => {
      if (
        controller.active ||
        controller.snapshot.recordings.some(
          (item) => !downloaded.current.has(item.url),
        )
      ) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    const visibility = () => {
      if (document.hidden) controller.interrupt();
    };
    const pagehide = () => {
      controller.interrupt();
    };
    window.addEventListener("beforeunload", unload);
    window.addEventListener("pagehide", pagehide);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      controller.dispose();
      window.removeEventListener("beforeunload", unload);
      window.removeEventListener("pagehide", pagehide);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);

  useEffect(() => {
    let active = true,
      working = false,
      connected = false,
      pageActive = true,
      epoch = 0;
    let csrf = "";
    let acknowledgedRender = "";
    let controller: AbortController | null = null;
    let pendingAck: {
      value: BroadcastState;
      until: number;
      attempts: number;
    } | null = null;
    const attempted = new Set<string>();
    const eligible = () =>
      active &&
      pageActive &&
      !document.hidden &&
      layoutRef.current === "Live" &&
      !!canvas.current;
    const show = (value: BroadcastState) => {
      live.current = value;
      setPresentation(value);
    };
    const suspended = () =>
      document.hidden
        ? "Studio hidden — delivery paused"
        : "Layout preview — delivery paused";
    function invalidate() {
      epoch++;
      controller?.abort();
      pendingAck = null;
      acknowledgedRender = "";
      show({ state: "waiting" });
      setDeliveryStatus(suspended());
    }
    invalidateDelivery.current = invalidate;
    async function painted(signal: AbortSignal) {
      await new Promise<void>((resolve, reject) => {
        let first = 0,
          second = 0;
        const abort = () => {
          cancelAnimationFrame(first);
          cancelAnimationFrame(second);
          signal.removeEventListener("abort", abort);
          reject(new Error("PRESENTATION_INTERRUPTED"));
        };
        if (signal.aborted) return abort();
        signal.addEventListener("abort", abort, { once: true });
        first = requestAnimationFrame(() => {
          second = requestAnimationFrame(() => {
            signal.removeEventListener("abort", abort);
            resolve();
          });
        });
      });
    }
    async function acknowledge(signal: AbortSignal, version: number) {
      const pending = pendingAck;
      if (!pending || !eligible() || epoch !== version) return;
      if (performance.now() >= pending.until || pending.attempts >= 3) {
        pendingAck = null;
        show({ state: "unknown" });
        setDeliveryStatus("ACK unconfirmed — no replay");
        return;
      }
      pending.attempts++;
      setDeliveryStatus("ACK pending");
      await request("/api/studio/ack", {
        method: "POST",
        signal,
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrf,
          "X-Overlay-View": view,
        },
        body: JSON.stringify({
          render_id: pending.value.render_id,
          delivery_id: pending.value.delivery_id,
        }),
      });
      if (!eligible() || epoch !== version) return;
      pendingAck = null;
      acknowledgedRender = pending.value.render_id!;
      setDeliveryStatus("Browser ACK verified");
    }
    async function poll() {
      if (working || !active || !connected) return;
      working = true;
      const version = epoch;
      controller = new AbortController();
      const signal = AbortSignal.any([
        controller.signal,
        AbortSignal.timeout(5000),
      ]);
      try {
        const status: SystemStatus = await request("/api/studio/status", {
          signal,
        });
        if (!active || epoch !== version) return;
        setSystem(status);
        if (!eligible()) {
          setDeliveryStatus(suspended());
          return;
        }
        // Retrying this exact ACK confirms existing visible evidence. It does
        // not fetch, repaint or execute a delivery again.
        if (pendingAck) {
          await acknowledge(signal, version);
          return;
        }
        let started = performance.now();
        let value: BroadcastState = await request("/api/studio/current", {
          signal,
          headers: { "X-Overlay-View": view },
        });
        if (!eligible() || epoch !== version) return;
        if (["delivery_pending", "outcome_pending"].includes(value.state)) {
          const id = value.render_id || value.presentation_id!;
          if (attempted.has(id)) {
            setDeliveryStatus("Delivery already claimed — no replay");
            return;
          }
          // Mark BEFORE POST. A lost response must never trigger another claim.
          attempted.add(id);
          setDeliveryStatus("Delivery pending");
          started = performance.now();
          value = await request("/api/studio/claim", {
            method: "POST",
            signal,
            headers: {
              "Content-Type": "application/json",
              "X-CSRF-Token": csrf,
              "X-Overlay-View": view,
            },
            body: JSON.stringify({ presentation_id: id }),
          });
          if (!eligible() || epoch !== version) return;
        } else if (["claimed", "outcome_claimed"].includes(value.state)) {
          // Continuation is local only: a GET never redelivers the payload.
          if (
            (live.current.render_id || live.current.presentation_id) !==
            (value.render_id || value.presentation_id)
          ) {
            show({ state: "waiting" });
            setDeliveryStatus("Delivery already claimed — no replay");
          } else if (value.state === "claimed")
            setDeliveryStatus("Browser ACK verified");
          return;
        }
        const anchored = anchorState(
          { ...value, evidence: status.evidence },
          started,
        );
        if (atTime(anchored, performance.now()).state !== anchored.state) {
          show({ state: "expired" });
          setDeliveryStatus("Expired render — no replay");
          return;
        }
        if (value.state === "challenge") {
          try {
            drawBroadcast(canvas.current!, anchored, performance.now());
          } catch {
            throw new Error("RENDER_FAILED");
          }
          show(anchored);
          await painted(signal);
          if (
            !eligible() ||
            epoch !== version ||
            atTime(anchored, performance.now()).state !== "challenge"
          )
            return;
          pendingAck = {
            value,
            until: Math.min(started + 4500, anchored.deadline!),
            attempts: 0,
          };
          await acknowledge(signal, version);
        } else {
          show(anchored);
          setDeliveryStatus(
            (value.reason === "NO_REPLAY"
              ? "Delivery already claimed — no replay"
              : value.reason === "ACK_PENDING"
                ? "Delivery already claimed — ACK pending"
                : value.reason) ||
              (value.state === "unknown"
                ? "Delivery unknown — no replay"
                : value.state === "expired"
                  ? "Expired render — no replay"
                  : "Waiting for delivery"),
          );
        }
      } catch (error) {
        if (active && epoch === version) {
          const reason = error instanceof Error ? error.message : "";
          if (reason === "ACK_REJECTED") {
            pendingAck = null;
            show({ state: "unknown" });
            setDeliveryStatus("ACK rejected — no replay");
          } else if (reason === "RENDER_FAILED") {
            pendingAck = null;
            show({ state: "unknown" });
            setDeliveryStatus("Rendering failed — no replay");
          } else if (pendingAck) {
            setDeliveryStatus("ACK unconfirmed — checking same receipt");
          } else {
            setSystem(null);
            // An acknowledged, continuously visible local presentation can
            // keep counting down through status outages. Never refetch it.
            if (
              !acknowledgedRender ||
              live.current.render_id !== acknowledgedRender
            )
              show({ state: "disconnected" });
            setDeliveryStatus(
              "Backend unavailable; claimed deliveries are not retried",
            );
          }
        }
      } finally {
        working = false;
        controller = null;
        if (active && epoch !== version && eligible())
          queueMicrotask(() => void poll());
      }
    }
    const visibility = () => {
      invalidate();
      if (eligible()) void poll();
    };
    const pagehide = () => {
      pageActive = false;
      invalidate();
    };
    const pageshow = () => {
      pageActive = true;
      visibility();
    };
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", pagehide);
    window.addEventListener("pageshow", pageshow);
    void (async () => {
      try {
        const identity: Me = await request("/api/me");
        if (!active) return;
        setMe(identity);
        if (!identity.authenticated) return;
        csrf = identity.csrf!;
        await request("/api/studio/connect", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        });
        if (!active) return;
        connected = true;
        await poll();
      } catch {
        if (active)
          setError(
            "Studio could not establish its local owner session. Refresh after signing in.",
          );
      }
    })();
    const timer = setInterval(() => {
      if (connected) void poll();
    }, 1000);
    return () => {
      active = false;
      controller?.abort();
      clearInterval(timer);
      invalidateDelivery.current = () => {};
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", pagehide);
      window.removeEventListener("pageshow", pageshow);
    };
  }, []);

  useEffect(() => {
    let animation = 0,
      previous = 0,
      failed = false;
    function frame(time: number) {
      if (failed) return;
      if (canvas.current && time - previous >= 1000 / 30) {
        try {
          drawBroadcast(canvas.current, live.current, time, layoutRef.current);
          previous = time - ((time - previous) % (1000 / 30));
          setDrawn(true);
        } catch {
          failed = true;
          setDrawn(false);
          setError("Canvas rendering is unavailable. Recording is disabled.");
          return;
        }
      }
      animation = requestAnimationFrame(frame);
    }
    animation = requestAnimationFrame(frame);
    const clock = setInterval(() => setNow(performance.now()), 250);
    return () => {
      cancelAnimationFrame(animation);
      clearInterval(clock);
    };
  }, [resolution]);

  const state = atTime(presentation, now);
  const active = ["Starting", "Recording", "Stopping", "Finalizing"].includes(
    recording.state,
  );
  const scene = sceneFor(state);
  return (
    <div className="shell studio-shell">
      <header>
        <a className="brand" href="/">
          <span className="brand-mark">CQ</span>CrowdQuest{" "}
          <span className="brand-ai">AI</span>
        </a>
        <span className="phase">BROADCAST STUDIO</span>
        <span className={`connection ${system ? "live" : ""}`}>
          <i />
          {system ? "Backend connected" : "Disconnected"}
        </span>
      </header>
      <main>
        <div className="hero">
          <div>
            <p className="eyebrow">YOUR CHAT. ONE BROADCAST SURFACE.</p>
            <h1>Make the moment yours.</h1>
            <p className="lede">
              Follow current activity and record locally, right in your browser.
            </p>
          </div>
          <a href="/">Open director dashboard ↗</a>
        </div>
        {error && (
          <div className="studio-error" role="alert">
            {error}
          </div>
        )}
        {!me ? (
          <p>Checking local owner session…</p>
        ) : !me.authenticated ? (
          <section className="studio-panel">
            <h2>Sign in as the channel owner</h2>
            <p>
              The Studio uses your existing local owner session. Chat reading
              remains the only Twitch permission.
            </p>
            <a href="/auth/twitch/start">Connect Twitch →</a>
          </section>
        ) : (
          <>
            <div className="studio-status" aria-label="System status">
              <span>
                Delivery <b role="status">{deliveryStatus}</b>
              </span>
              <span>
                Backend <b>{system ? "Connected" : "Unavailable"}</b>
              </span>
              <span>
                EventSub <b>{system?.eventsub || "Unknown"}</b>
              </span>
              <span>
                Worker <b>{system?.worker || "Unknown"}</b>
              </span>
              <span>
                Challenge <b>{system?.challenge_state || "Waiting"}</b>
              </span>
              <span>
                Recorder <b>{recording.state}</b>
              </span>
            </div>
            <div className="studio-workspace">
              <section className="studio-stage">
                <div className="studio-stage-heading">
                  <span className="eyebrow">
                    {layout === "Live"
                      ? "CURRENT PRESENTATION"
                      : "LOCAL LAYOUT PREVIEW"}{" "}
                    · {layout === "Live" ? scene : layout}
                  </span>
                  <button
                    onClick={() => {
                      void canvas.current
                        ?.requestFullscreen()
                        .catch(() =>
                          setError(
                            "Fullscreen was not granted. Use the embedded preview.",
                          ),
                        );
                    }}
                  >
                    Full-screen preview
                  </button>
                </div>
                <canvas
                  ref={canvas}
                  width={width}
                  height={height}
                  aria-label="Broadcast output"
                  role="img"
                />
                <div className="studio-stage-caption">
                  <span>
                    {width} × {height} · 30 FPS target · Silent video
                  </span>
                  <span>
                    {system?.evidence === "SYNTHETIC_TEST"
                      ? "SYNTHETIC TEST DATA"
                      : "Server-authoritative state"}
                  </span>
                </div>
                <p className="studio-live-description" aria-live="polite">
                  Current scene: {scene}.{" "}
                  {state.round
                    ? `${state.round.state}; ${state.round.total_votes} votes; ${state.round.choices.map((item) => `Candidate ${item.number}: ${item.votes}`).join("; ")}; ${Math.ceil(state.remaining_seconds || 0)} seconds; winner ${state.round.winner ?? "undecided"}.`
                    : state.challenge
                      ? `${state.challenge.title}. ${state.challenge.description}. ${Math.ceil(state.remaining_seconds || 0)} seconds.`
                      : state.outcome
                        ? `${state.outcome}, reported by the streamer.`
                        : state.state === "expired"
                          ? "Challenge expired."
                          : "No active presentation."}
                </p>
              </section>
              <aside>
                <section className="studio-panel">
                  <p className="eyebrow">SCENES</p>
                  <h2>Follow the moment.</h2>
                  <div className="studio-scenes">
                    {(["Live", ...SCENES] as const).map((item) => (
                      <button
                        key={item}
                        aria-pressed={layout === item}
                        disabled={active}
                        onClick={() => {
                          layoutRef.current = item;
                          invalidateDelivery.current();
                          setLayout(item);
                        }}
                      >
                        {item === "Live" ? "Follow current state" : item}
                      </button>
                    ))}
                  </div>
                  <p>
                    Layout previews show matching current content only. They
                    never create votes or challenges. Recording follows current
                    activity.
                  </p>
                  {system?.last_outcome && (
                    <p>
                      Last persisted outcome: <b>{system.last_outcome.kind}</b>{" "}
                      · {system.last_outcome.presentation}. Historical results
                      are not replayed.
                    </p>
                  )}
                </section>
                <section className="studio-panel">
                  <p className="eyebrow">LOCAL RECORDING</p>
                  <h2>Keep a real moment.</h2>
                  <label htmlFor="studio-resolution">
                    Recording resolution
                  </label>
                  <select
                    id="studio-resolution"
                    value={resolution}
                    disabled={active}
                    onChange={(event) => {
                      invalidateDelivery.current();
                      setResolution(event.target.value);
                    }}
                  >
                    <option value="1920x1080">1920 × 1080</option>
                    <option value="1280x720">1280 × 720</option>
                  </select>
                  <label htmlFor="studio-filename">Output filename</label>
                  <input
                    id="studio-filename"
                    value={outputName}
                    maxLength={85}
                    disabled={active}
                    onChange={(event) => setOutputName(event.target.value)}
                  />
                  <output aria-label="Recording state">
                    {recording.state} · {recording.seconds.toFixed(1)}s
                  </output>
                  <div className="studio-record-buttons">
                    <button
                      className="primary"
                      disabled={
                        !system ||
                        !drawn ||
                        !supported ||
                        !validFilename(outputName) ||
                        layout !== "Live" ||
                        active ||
                        !recorder.current?.canStart
                      }
                      onClick={() => {
                        if (canvas.current)
                          recorder.current?.start(canvas.current, outputName);
                      }}
                    >
                      Start Recording
                    </button>
                    <button
                      disabled={
                        !["Starting", "Recording"].includes(recording.state)
                      }
                      onClick={() => recorder.current?.stop()}
                    >
                      Stop Recording
                    </button>
                  </div>
                  {recording.error && (
                    <p role="alert" className="studio-error">
                      {recording.error}
                    </p>
                  )}
                  {!supported && (
                    <p role="alert">
                      This browser has no supported Canvas/WebM recorder. The
                      presentation remains available.
                    </p>
                  )}
                  <p>
                    Up to {MAX_SECONDS} seconds / 64 MiB per file; three files
                    per page. Keep this tab visible. No microphone or system
                    audio.
                  </p>
                  <p>
                    Files stay in browser memory. Download before closing or
                    refreshing; your browser chooses the local Downloads folder.
                  </p>
                  <div className="studio-downloads">
                    {recording.recordings.map((item) => (
                      <article key={item.url}>
                        <strong>
                          {item.verified
                            ? item.interrupted
                              ? "Recovered partial recording"
                              : "Finalized · playback verified"
                            : "Unverified recording"}
                        </strong>
                        <p>
                          {item.width} × {item.height} ·{" "}
                          {item.seconds.toFixed(1)}s captured ·{" "}
                          {(item.bytes / 1048576).toFixed(2)} MiB · WebM
                        </p>
                        <a
                          href={item.url}
                          download={item.filename}
                          onClick={() => downloaded.current.add(item.url)}
                        >
                          Download {item.filename}
                        </a>
                        <video
                          controls
                          muted
                          playsInline
                          src={item.url}
                          aria-label={`Playback ${item.filename}`}
                        />
                      </article>
                    ))}
                  </div>
                </section>
              </aside>
            </div>
          </>
        )}
        <footer>
          OBS-free · Display and recording only · Approval, Admission,
          Authorization and Execute remain separate.
        </footer>
      </main>
    </div>
  );
}
