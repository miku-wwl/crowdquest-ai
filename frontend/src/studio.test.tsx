import { afterEach, beforeEach, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { anchorState, atTime, drawBroadcast, sceneFor } from "./studio-canvas";
import {
  CanvasRecorder,
  supportedCodec,
  validFilename,
} from "./studio-recorder";
import { BroadcastStudio } from "./studio";

vi.mock("./studio-webm", () => ({
  finalizeWebm: async (blob: Blob) => blob,
}));

let instance: MockRecorder;
let supported: string[];
let track: { stop: ReturnType<typeof vi.fn>; onended: null | (() => void) };
let context: CanvasRenderingContext2D;
class MockRecorder {
  static isTypeSupported = (value: string) => supported.includes(value);
  state = "inactive";
  mimeType = "video/webm;codecs=vp8";
  onstart: null | (() => void) = null;
  onstop: null | (() => void) = null;
  onerror: null | (() => void) = null;
  ondataavailable: null | ((event: { data: Blob }) => void) = null;
  start = vi.fn(() => {
    this.state = "recording";
    this.onstart?.();
  });
  stop = vi.fn(() => {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["synthetic-media"]) });
    queueMicrotask(() => this.onstop?.());
  });
  constructor() {
    instance = this;
  }
}

beforeEach(() => {
  Object.defineProperty(document, "hidden", {
    configurable: true,
    value: false,
  });
  supported = ["video/webm;codecs=vp8", "video/webm"];
  vi.stubGlobal("MediaRecorder", MockRecorder);
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:synthetic-video"),
    revokeObjectURL: vi.fn(),
  });
  track = { stop: vi.fn(), onended: null };
  Object.defineProperty(HTMLCanvasElement.prototype, "captureStream", {
    configurable: true,
    writable: true,
    value: vi.fn(
      () =>
        ({
          getTracks: () => [track],
          getVideoTracks: () => [track],
          getAudioTracks: () => [],
        }) as unknown as MediaStream,
    ),
  });
  context = {
    save: vi.fn(),
    restore: vi.fn(),
    scale: vi.fn(),
    fillRect: vi.fn(),
    beginPath: vi.fn(),
    roundRect: vi.fn(),
    fill: vi.fn(),
    fillText: vi.fn(),
    measureText: vi.fn((value: string) => ({
      width: Array.from(value).length * 16,
    })),
    createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
  } as unknown as CanvasRenderingContext2D;
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context);
});

// Deterministic visibility tests, not evidence of native Chromium tab visibility.
const payload = {
  state: "challenge",
  render_id: "render-fixture",
  delivery_id: "delivery-fixture",
  remaining_seconds: 30,
  challenge: {
    title: "Fixture challenge",
    description: "Synthetic only",
    duration_seconds: 30,
    difficulty: "Medium",
  },
};
function visibility(hidden: boolean) {
  act(() => {
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: hidden,
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
}
function fixture(
  options: {
    status?: () => Promise<Response>;
    peek?: () => Promise<Response>;
    claim?: () => Promise<Response>;
    ack?: () => Promise<Response>;
  } = {},
) {
  let claimed = false;
  const calls: { path: string; view?: string }[] = [];
  const fetcher = vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({
      path,
      view: (init?.headers as Record<string, string>)?.["X-Overlay-View"],
    });
    let value: unknown = {};
    if (path === "/api/me") value = { authenticated: true, csrf: "synthetic" };
    if (path === "/api/studio/status" && options.status)
      return options.status();
    if (path === "/api/studio/status")
      value = { evidence: "SYNTHETIC_TEST", worker: "ready" };
    if (path === "/api/studio/current") {
      if (options.peek) return options.peek();
      value = claimed
        ? { state: "claimed", render_id: payload.render_id }
        : { state: "delivery_pending", render_id: payload.render_id };
    }
    if (path === "/api/studio/claim") {
      claimed = true;
      if (options.claim) return options.claim();
      value = payload;
    }
    if (path === "/api/studio/ack" && options.ack) return options.ack();
    return new Response(JSON.stringify(value));
  });
  vi.stubGlobal("fetch", fetcher);
  return {
    calls,
    fetcher,
    count: (path: string) => calls.filter((c) => c.path === path).length,
  };
}
async function connected() {
  await screen.findByText("Backend connected");
}

it("hidden Studio does not acquire until visible, then paints and ACKs exactly once", async () => {
  visibility(true);
  const f = fixture();
  render(<BroadcastStudio />);
  await connected();
  expect(f.count("/api/studio/current")).toBe(0);
  expect(f.count("/api/studio/claim")).toBe(0);
  visibility(false);
  await waitFor(() => expect(f.count("/api/studio/ack")).toBe(1));
  expect(context.fillText).toHaveBeenCalledWith(
    "Fixture challenge",
    expect.any(Number),
    expect.any(Number),
  );
  expect(f.count("/api/studio/claim")).toBe(1);
});

it("hide during non-consuming peek discards its response without a claim", async () => {
  let resolve!: (r: Response) => void;
  const f = fixture({
    peek: () =>
      new Promise((r) => {
        resolve = r;
      }),
  });
  render(<BroadcastStudio />);
  await waitFor(() => expect(f.count("/api/studio/current")).toBe(1), {
    timeout: 2000,
  });
  visibility(true);
  await act(async () =>
    resolve(
      new Response(
        JSON.stringify({
          state: "delivery_pending",
          render_id: payload.render_id,
        }),
      ),
    ),
  );
  expect(f.count("/api/studio/claim")).toBe(0);
  expect(f.count("/api/studio/ack")).toBe(0);
});

it("hide during claim never paints or ACKs a stale response or reclaims", async () => {
  let resolve!: (r: Response) => void;
  const f = fixture({
    claim: () =>
      new Promise((r) => {
        resolve = r;
      }),
  });
  render(<BroadcastStudio />);
  await waitFor(() => expect(f.count("/api/studio/claim")).toBe(1), {
    timeout: 2000,
  });
  visibility(true);
  await act(async () => resolve(new Response(JSON.stringify(payload))));
  visibility(false);
  await waitFor(() => expect(f.count("/api/studio/current")).toBe(2));
  expect(f.count("/api/studio/claim")).toBe(1);
  expect(f.count("/api/studio/ack")).toBe(0);
  expect(context.fillText).not.toHaveBeenCalledWith(
    "Fixture challenge",
    expect.any(Number),
    expect.any(Number),
  );
});

it("transient backend error preserves View ID and resumes ordinary polling", async () => {
  let count = 0;
  const f = fixture({
    peek: async () => {
      if (++count === 1) throw new TypeError("Synthetic offline");
      return new Response(JSON.stringify({ state: "waiting" }));
    },
  });
  render(<BroadcastStudio />);
  await waitFor(() => expect(f.count("/api/studio/current")).toBe(2), {
    timeout: 3000,
  });
  expect(new Set(f.calls.filter((c) => c.view).map((c) => c.view)).size).toBe(
    1,
  );
});

it("keeps an already acknowledged local presentation through a transient status outage", async () => {
  let outage = false;
  const f = fixture({
    status: async () => {
      if (!outage && f.count("/api/studio/ack") > 0) {
        outage = true;
        throw new TypeError("Fixture status outage");
      }
      return new Response(
        JSON.stringify({ evidence: "SYNTHETIC_TEST", worker: "ready" }),
      );
    },
  });
  render(<BroadcastStudio />);
  await screen.findByText("Browser ACK verified", {}, { timeout: 2500 });
  await screen.findByText(
    "Backend unavailable; claimed deliveries are not retried",
    {},
    { timeout: 2500 },
  );
  expect(screen.getByText(/Current scene: Challenge Active/)).toHaveTextContent(
    "Fixture challenge",
  );
  await screen.findByText("Browser ACK verified", {}, { timeout: 2500 });
  expect(f.count("/api/studio/claim")).toBe(1);
  expect(f.count("/api/studio/ack")).toBe(1);
});

it("non-Live preview does not consume an available delivery", async () => {
  let resolve!: (r: Response) => void;
  const f = fixture({
    peek: () =>
      new Promise((r) => {
        resolve = r;
      }),
  });
  render(<BroadcastStudio />);
  await waitFor(() => expect(f.count("/api/studio/current")).toBe(1), {
    timeout: 2000,
  });
  fireEvent.click(screen.getByRole("button", { name: /^Voting$/ }));
  await act(async () =>
    resolve(
      new Response(
        JSON.stringify({
          state: "delivery_pending",
          render_id: payload.render_id,
        }),
      ),
    ),
  );
  expect(f.count("/api/studio/claim")).toBe(0);
  expect(f.count("/api/studio/ack")).toBe(0);
});

it("retries only the same ACK after response loss, without another claim", async () => {
  let count = 0;
  const f = fixture({
    ack: async () => {
      if (++count === 1) throw new TypeError("Synthetic lost ACK response");
      return new Response("{}");
    },
  });
  render(<BroadcastStudio />);
  await screen.findByText("Browser ACK verified", {}, { timeout: 3500 });
  expect(f.count("/api/studio/claim")).toBe(1);
  expect(f.count("/api/studio/ack")).toBe(2);
  expect(new Set(f.calls.filter((c) => c.view).map((c) => c.view)).size).toBe(
    1,
  );
});

it("rejected ACK is never reported as verified or followed by another claim", async () => {
  const f = fixture({ ack: async () => new Response("{}", { status: 409 }) });
  render(<BroadcastStudio />);
  await screen.findByText("ACK rejected — no replay", {}, { timeout: 2500 });
  expect(f.count("/api/studio/claim")).toBe(1);
  expect(screen.queryByText("Browser ACK verified")).toBeNull();
});

it("hide between draw and paint fences the ACK", async () => {
  vi.stubGlobal(
    "requestAnimationFrame",
    vi.fn(() => 1),
  );
  const f = fixture();
  render(<BroadcastStudio />);
  await waitFor(
    () =>
      expect(context.fillText).toHaveBeenCalledWith(
        "Fixture challenge",
        expect.any(Number),
        expect.any(Number),
      ),
    { timeout: 2000 },
  );
  visibility(true);
  expect(f.count("/api/studio/ack")).toBe(0);
  visibility(false);
  await screen.findByText("Delivery already claimed — no replay");
  expect(f.count("/api/studio/claim")).toBe(1);
});

it("a Canvas draw failure cannot generate a positive ACK", async () => {
  vi.mocked(context.fillText).mockImplementation((text) => {
    if (text === "Fixture challenge") throw new Error("Fixture draw failure");
  });
  const f = fixture();
  render(<BroadcastStudio />);
  await screen.findByText(
    "Rendering failed — no replay",
    {},
    { timeout: 2500 },
  );
  expect(f.count("/api/studio/ack")).toBe(0);
});

it("a slow claim response past the conservative deadline is never painted or ACKed", async () => {
  const f = fixture({
    claim: async () => {
      await new Promise((resolve) => setTimeout(resolve, 80));
      return new Response(
        JSON.stringify({ ...payload, remaining_seconds: 0.001 }),
      );
    },
  });
  render(<BroadcastStudio />);
  await screen.findByText("Expired render — no replay", {}, { timeout: 2500 });
  expect(f.count("/api/studio/ack")).toBe(0);
  expect(context.fillText).not.toHaveBeenCalledWith(
    "Fixture challenge",
    expect.any(Number),
    expect.any(Number),
  );
});

it("serializes slow polls and cleans up after pagehide", async () => {
  const f = fixture({ peek: () => new Promise(() => {}) });
  render(<BroadcastStudio />);
  await waitFor(() => expect(f.count("/api/studio/current")).toBe(1), {
    timeout: 2000,
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
  });
  expect(f.count("/api/studio/current")).toBe(1);
  act(() => window.dispatchEvent(new Event("pagehide")));
  expect(f.count("/api/studio/claim")).toBe(0);
  expect(f.count("/api/studio/ack")).toBe(0);
});

it("unmount cancels outstanding work and a new document gets a new View ID", async () => {
  let resolve!: (r: Response) => void;
  const f = fixture({
    claim: () =>
      new Promise((r) => {
        resolve = r;
      }),
  });
  const first = render(<BroadcastStudio />);
  await waitFor(() => expect(f.count("/api/studio/claim")).toBe(1), {
    timeout: 2000,
  });
  first.unmount();
  await act(async () => resolve(new Response(JSON.stringify(payload))));
  expect(f.count("/api/studio/ack")).toBe(0);
  render(<BroadcastStudio />);
  await waitFor(() => expect(f.count("/api/studio/current")).toBe(2), {
    timeout: 2000,
  });
  expect(new Set(f.calls.filter((c) => c.view).map((c) => c.view)).size).toBe(
    2,
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("detects a supported WebM fallback and rejects paths or disguised containers", () => {
  supported = ["video/webm"];
  expect(supportedCodec()).toBe("video/webm");
  supported = [];
  expect(supportedCodec()).toBeNull();
  for (const value of [
    "../test.webm",
    "C:\\secret.webm",
    "test.mp4",
    "test.webm.exe",
    "/tmp/test.webm",
    "secret?.webm",
  ])
    expect(validFilename(value)).toBe(false);
  expect(validFilename("crowdquest-20261028-a1b2.webm")).toBe(true);
});

it("anchors server deadlines to request start and clears content at expiry", () => {
  const value = anchorState(
    {
      state: "challenge",
      remaining_seconds: 15,
      challenge: {
        title: "Bounded",
        description: "Test",
        difficulty: "Medium",
        duration_seconds: 15,
      },
      render_id: "render",
      delivery_id: "delivery",
    },
    1000,
  );
  expect(atTime(value, 16000)).toMatchObject({ state: "expired" });
  expect(atTime(value, 16000).challenge).toBeUndefined();
  expect(() =>
    anchorState({ state: "outcome", remaining_seconds: 9 }, 0),
  ).toThrow();
  expect(() =>
    anchorState({ state: "challenge", remaining_seconds: Number.NaN }, 0),
  ).toThrow();
});

it.each([
  ["waiting", "Waiting"],
  ["expired", "Waiting"],
  ["voting", "Voting"],
  ["winner", "Voting"],
  ["challenge", "Challenge Active"],
  ["outcome", "Challenge Result"],
])("maps %s to the authoritative %s scene", (state, scene) => {
  expect(sceneFor({ state })).toBe(scene);
});

it.each(["Completed", "Failed", "Skipped"])(
  "draws actual persisted %s on the captured surface",
  (outcome) => {
    const canvas = document.createElement("canvas");
    canvas.width = 1920;
    canvas.height = 1080;
    drawBroadcast(
      canvas,
      { state: "outcome", outcome, evidence: "SYNTHETIC_TEST" },
      0,
    );
    expect(context.fillText).toHaveBeenCalledWith(
      `${outcome} • Reported by the streamer`,
      48,
      483,
    );
    expect(context.fillText).toHaveBeenCalledWith(
      "SYNTHETIC TEST • ISOLATED APPLICATION STATE",
      48,
      138,
    );
  },
);

it("draws exact authoritative totals without generating or counting votes", () => {
  const canvas = document.createElement("canvas");
  drawBroadcast(
    canvas,
    {
      state: "winner",
      round: {
        state: "Closed",
        remaining_seconds: 0,
        total_votes: 3,
        winner: 1,
        choices: [
          { number: 1, text: "First", votes: 2, percentage: 66.7 },
          { number: 2, text: "Second", votes: 1, percentage: 33.3 },
        ],
      },
    },
    0,
  );
  expect(context.fillText).toHaveBeenCalledWith("2 votes", 1070, 294);
  expect(context.fillText).toHaveBeenCalledWith(
    "CLOSED  •  3 votes  •  Winner: 1",
    48,
    612,
  );
});

it("prevents duplicate sessions and verifies a finalized Blob before success", async () => {
  vi.useFakeTimers();
  const verify = vi.fn(async () => {});
  const recorder = new CanvasRecorder(vi.fn(), verify);
  const canvas = document.createElement("canvas");
  canvas.width = 1920;
  canvas.height = 1080;
  expect(recorder.start(canvas, "test.webm")).toBe(true);
  expect(recorder.start(canvas, "second.webm")).toBe(false);
  expect(instance.start).toHaveBeenCalledOnce();
  await vi.advanceTimersByTimeAsync(2000);
  expect(recorder.stop()).toBe(true);
  expect(recorder.stop()).toBe(false);
  await vi.advanceTimersByTimeAsync(0);
  expect(verify).toHaveBeenCalledWith("blob:synthetic-video", 1920, 1080, 2);
  expect(recorder.snapshot.state).toBe("Ready");
  expect(recorder.snapshot.recordings[0]).toMatchObject({
    seconds: 2,
    verified: true,
    interrupted: false,
  });
  expect(track.stop).toHaveBeenCalled();
  recorder.dispose();
});

it("does not label an interrupted or undecodable output as a successful recording", async () => {
  vi.useFakeTimers();
  const recorder = new CanvasRecorder(vi.fn(), async () => {
    throw new Error("decode failure");
  });
  recorder.start(document.createElement("canvas"), "partial.webm");
  await vi.advanceTimersByTimeAsync(1000);
  recorder.interrupt();
  await vi.advanceTimersByTimeAsync(0);
  expect(recorder.snapshot.state).toBe("Error");
  expect(recorder.snapshot.recordings[0]).toMatchObject({
    verified: false,
    interrupted: true,
  });
  recorder.dispose();
});

it("handles start/stop exceptions without automatic retry or overlapping recorders", () => {
  const recorder = new CanvasRecorder(vi.fn(), async () => {});
  recorder.start(document.createElement("canvas"), "stopfail.webm");
  instance.stop.mockImplementation(() => {
    throw new Error("Synthetic stop failure");
  });
  expect(recorder.stop()).toBe(false);
  expect(recorder.start(document.createElement("canvas"), "other.webm")).toBe(
    false,
  );
  expect(instance.start).toHaveBeenCalledOnce();
  recorder.dispose();
});

it("never calls recording or AIG endpoints and disables fake-layout recording", async () => {
  const posts: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      if (options?.method === "POST") posts.push(path);
      const value =
        path === "/api/me"
          ? { authenticated: true, csrf: "synthetic-csrf" }
          : path === "/api/studio/status"
            ? {
                backend: "connected",
                eventsub: "listening",
                worker: "ready",
                challenge_state: "WAITING",
                last_outcome: null,
                evidence: "SYNTHETIC_TEST",
                obs_required: false,
              }
            : { state: "waiting" };
      return new Response(JSON.stringify(value));
    }),
  );
  render(<BroadcastStudio />);
  await screen.findByText("Backend connected");
  expect(screen.getByRole("img", { name: "Broadcast output" })).toHaveAttribute(
    "width",
    "1920",
  );
  fireEvent.click(screen.getByRole("button", { name: "Challenge Active" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Start Recording" }),
    ).toBeDisabled(),
  );
  expect(posts).toEqual(["/api/studio/connect"]);
  expect(posts.some((path) => path.includes("execute"))).toBe(false);
});
