// Browser-local silent recording. No microphone, display capture, upload or AIG call.
import { finalizeWebm } from "./studio-webm";
export const MAX_SECONDS = 180;
export const MAX_BYTES = 64 * 1024 * 1024;
export const MAX_RECORDINGS = 3;
export const CODECS = [
  "video/webm;codecs=vp8",
  "video/webm;codecs=vp9",
  "video/webm",
];
export type RecordingState =
  | "Idle"
  | "Starting"
  | "Recording"
  | "Stopping"
  | "Finalizing"
  | "Ready"
  | "Interrupted"
  | "Error";
export type Recording = {
  url: string;
  filename: string;
  bytes: number;
  mime: string;
  seconds: number;
  width: number;
  height: number;
  verified: boolean;
  interrupted: boolean;
};
export type RecorderSnapshot = {
  state: RecordingState;
  seconds: number;
  error: string;
  recordings: Recording[];
};

export function validFilename(value: string) {
  return /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}\.webm$/.test(value);
}

export function supportedCodec() {
  if (typeof MediaRecorder === "undefined") return null;
  return CODECS.find((mime) => MediaRecorder.isTypeSupported(mime)) || null;
}

export async function verifyVideo(
  url: string,
  width: number,
  height: number,
  expectedSeconds: number,
): Promise<void> {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "auto";
  try {
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error("PLAYBACK_VERIFICATION_TIMEOUT")),
        10000,
      );
      const finish = (error?: Error) => {
        clearTimeout(timer);
        video.onloadeddata = null;
        video.ontimeupdate = null;
        video.onerror = null;
        if (error) reject(error);
        else resolve();
      };
      video.onerror = () => finish(new Error("VIDEO_DECODE_FAILED"));
      video.onloadeddata = () => {
        if (video.videoWidth !== width || video.videoHeight !== height)
          return finish(new Error("VIDEO_RESOLUTION_MISMATCH"));
        if (
          !Number.isFinite(video.duration) ||
          Math.abs(video.duration - expectedSeconds) > 1
        )
          return finish(new Error("VIDEO_DURATION_INVALID"));
        video.ontimeupdate = () => {
          if (video.currentTime >= 0.1) finish();
        };
        void video
          .play()
          .catch(() => finish(new Error("VIDEO_PLAYBACK_FAILED")));
      };
      video.src = url;
      video.load();
    });
  } finally {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
}

export class CanvasRecorder {
  snapshot: RecorderSnapshot = {
    state: "Idle",
    seconds: 0,
    error: "",
    recordings: [],
  };
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];
  private bytes = 0;
  private started = Number.NaN;
  private tick: ReturnType<typeof setInterval> | null = null;
  private watchdog: ReturnType<typeof setTimeout> | null = null;
  private interrupted = false;
  private filename = "";
  private width = 0;
  private height = 0;
  private disposed = false;

  constructor(
    private changed: (value: RecorderSnapshot) => void,
    private verify = verifyVideo,
  ) {}

  get active() {
    return ["Starting", "Recording", "Stopping", "Finalizing"].includes(
      this.snapshot.state,
    );
  }
  get canStart() {
    return (
      !this.active &&
      !this.recorder &&
      !this.disposed &&
      this.snapshot.recordings.length < MAX_RECORDINGS
    );
  }

  private publish(state: RecordingState, error = "") {
    this.snapshot = { ...this.snapshot, state, error };
    if (!this.disposed) this.changed(this.snapshot);
  }

  private clearTimers() {
    if (this.tick) clearInterval(this.tick);
    if (this.watchdog) clearTimeout(this.watchdog);
    this.tick = null;
    this.watchdog = null;
  }

  private releaseTracks() {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }

  start(canvas: HTMLCanvasElement, filename: string) {
    if (!this.canStart) return false;
    if (!validFilename(filename)) {
      this.publish("Error", "INVALID_FILENAME");
      return false;
    }
    if (this.snapshot.recordings.some((item) => item.filename === filename)) {
      this.publish("Error", "DUPLICATE_FILENAME");
      return false;
    }
    if (this.snapshot.recordings.length >= MAX_RECORDINGS) {
      this.publish(
        "Error",
        "SESSION_RECORDING_LIMIT: download your files; a page reload clears browser memory.",
      );
      return false;
    }
    const mime = supportedCodec();
    if (!mime || typeof canvas.captureStream !== "function") {
      this.publish("Error", "CANVAS_RECORDING_UNSUPPORTED");
      return false;
    }
    this.publish("Starting");
    this.filename = filename;
    this.width = canvas.width;
    this.height = canvas.height;
    this.bytes = 0;
    this.chunks = [];
    this.interrupted = false;
    this.started = Number.NaN;
    this.snapshot = { ...this.snapshot, seconds: 0 };
    try {
      this.stream = canvas.captureStream(30);
      if (
        this.stream.getAudioTracks().length ||
        this.stream.getVideoTracks().length !== 1
      )
        throw new Error("INVALID_CANVAS_STREAM");
      const recorder = new MediaRecorder(this.stream, {
        mimeType: mime,
        videoBitsPerSecond: 2400000,
      });
      this.recorder = recorder;
      recorder.onstart = () => {
        if (this.recorder !== recorder) return;
        if (this.snapshot.state !== "Starting") return;
        this.started = performance.now();
        this.publish("Recording");
        this.tick = setInterval(() => {
          this.snapshot = {
            ...this.snapshot,
            seconds: (performance.now() - this.started) / 1000,
          };
          if (!this.disposed) this.changed(this.snapshot);
          if (this.snapshot.seconds >= MAX_SECONDS) this.stop();
        }, 200);
      };
      recorder.ondataavailable = (event) => {
        if (this.recorder !== recorder) return;
        if (event.data.size === 0) return;
        if (this.bytes + event.data.size > MAX_BYTES) {
          this.interrupted = true;
          this.stop();
          return;
        }
        this.bytes += event.data.size;
        this.chunks.push(event.data);
      };
      recorder.onerror = () => {
        if (this.recorder !== recorder) return;
        this.interrupted = true;
        if (recorder.state !== "inactive") this.stop();
        else {
          this.clearTimers();
          this.releaseTracks();
          this.publish("Stopping", "MEDIA_RECORDER_FAILED");
          this.watchdog = setTimeout(
            () => this.publish("Error", "RECORDING_ERROR_FINALIZATION_TIMEOUT"),
            10000,
          );
        }
      };
      recorder.onstop = () => {
        if (this.recorder === recorder)
          void this.finalize(recorder.mimeType || mime);
      };
      this.stream.getVideoTracks()[0].onended = () => {
        if (["Starting", "Recording"].includes(this.snapshot.state))
          this.interrupt();
      };
      recorder.start(1000);
      this.watchdog = setTimeout(() => {
        if (this.snapshot.state === "Starting") {
          this.interrupt();
          this.publish("Error", "RECORDING_START_TIMEOUT");
        }
      }, 8000);
      return true;
    } catch {
      this.clearTimers();
      this.releaseTracks();
      this.recorder = null;
      this.publish("Error", "RECORDING_START_FAILED: no automatic retry.");
      return false;
    }
  }

  stop() {
    if (
      !["Starting", "Recording"].includes(this.snapshot.state) ||
      !this.recorder
    )
      return false;
    this.clearTimers();
    this.snapshot = {
      ...this.snapshot,
      seconds: Number.isFinite(this.started)
        ? (performance.now() - this.started) / 1000
        : 0,
    };
    this.publish("Stopping");
    try {
      this.recorder.stop();
      this.watchdog = setTimeout(() => {
        this.releaseTracks();
        this.publish(
          "Error",
          "RECORDING_STOP_TIMEOUT: an unfinalized recording cannot be exported.",
        );
      }, 10000);
      return true;
    } catch {
      this.releaseTracks();
      this.publish(
        "Error",
        "RECORDING_STOP_FAILED: inspect the page; no automatic retry.",
      );
      return false;
    }
  }

  interrupt() {
    this.interrupted = true;
    return this.stop();
  }

  private async finalize(mime: string) {
    this.clearTimers();
    this.releaseTracks();
    let blob = new Blob(this.chunks, { type: mime });
    this.chunks = [];
    this.recorder = null;
    if (
      !blob.size ||
      !mime.startsWith("video/webm") ||
      this.snapshot.seconds < 0.2
    ) {
      this.publish("Error", "EMPTY_OR_UNSUPPORTED_VIDEO");
      return;
    }
    this.publish("Finalizing");
    // Native Chrome WebM often lacks Duration. This adds metadata, never alters frames.
    let url: string;
    try {
      blob = await finalizeWebm(blob, this.snapshot.seconds * 1000);
      url = URL.createObjectURL(blob);
    } catch {
      this.publish("Error", "VIDEO_CONTAINER_FINALIZATION_FAILED");
      return;
    }
    try {
      await this.verify(url, this.width, this.height, this.snapshot.seconds);
      const recording: Recording = {
        url,
        filename: this.filename,
        bytes: blob.size,
        mime,
        seconds: this.snapshot.seconds,
        width: this.width,
        height: this.height,
        verified: true,
        interrupted: this.interrupted,
      };
      this.snapshot = {
        ...this.snapshot,
        recordings: [...this.snapshot.recordings, recording],
      };
      this.publish(
        this.interrupted ? "Interrupted" : "Ready",
        this.interrupted
          ? "Recording was interrupted; the recovered file decodes, but its coverage is partial."
          : "",
      );
    } catch {
      // Keep even a failed file available, clearly unverified; never call it success.
      const recording: Recording = {
        url,
        filename: this.filename,
        bytes: blob.size,
        mime,
        seconds: this.snapshot.seconds,
        width: this.width,
        height: this.height,
        verified: false,
        interrupted: true,
      };
      this.snapshot = {
        ...this.snapshot,
        recordings: [...this.snapshot.recordings, recording],
      };
      this.publish(
        "Error",
        "VIDEO_VERIFICATION_FAILED: export is retained for inspection, not accepted as a playable recording.",
      );
    }
  }

  dispose() {
    this.disposed = true;
    if (["Starting", "Recording"].includes(this.snapshot.state))
      this.interrupt();
    this.clearTimers();
    this.releaseTracks();
    // Blob URLs live until page teardown. No file on disk is ever removed.
  }
}
