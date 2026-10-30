// One surface: this canvas is both the visible preview and captureStream source.
export type BroadcastState = {
  state: string;
  mode?: string;
  evidence?: string;
  text?: string;
  warning?: string;
  reason?: string;
  remaining_seconds?: number;
  deadline?: number;
  render_id?: string;
  delivery_id?: string;
  presentation_id?: string;
  chosen_by_chat?: boolean;
  outcome?: string;
  challenge?: {
    title: string;
    description: string;
    difficulty: string;
    duration_seconds: number;
  };
  round?: {
    state: string;
    total_votes: number;
    winner: number | null;
    evidence?: string;
    remaining_seconds: number;
    choices: {
      number: number;
      text: string;
      votes: number;
      percentage: number;
    }[];
  };
};
export const SCENES = [
  "Waiting",
  "Voting",
  "Challenge Active",
  "Challenge Result",
] as const;
export type Scene = (typeof SCENES)[number];

export function sceneFor(state: BroadcastState): Scene {
  if (["voting", "winner", "pending_approval"].includes(state.state))
    return "Voting";
  if (["challenge", "preview"].includes(state.state)) return "Challenge Active";
  if (state.state === "outcome") return "Challenge Result";
  return "Waiting";
}

export function anchorState(
  value: BroadcastState,
  started: number,
): BroadcastState {
  if (!value || typeof value.state !== "string")
    throw new Error("INVALID_PRESENTATION");
  const remaining =
    value.state === "voting"
      ? value.round?.remaining_seconds
      : value.remaining_seconds;
  if (["challenge", "voting", "outcome", "preview"].includes(value.state)) {
    const max =
      value.state === "outcome"
        ? 8
        : value.state === "voting" || value.state === "preview"
          ? 60
          : 120;
    if (!Number.isFinite(remaining) || remaining! <= 0 || remaining! > max)
      throw new Error("INVALID_DEADLINE");
    if (
      value.state === "challenge" &&
      (!value.challenge || !value.render_id || !value.delivery_id)
    )
      throw new Error("INVALID_CHALLENGE");
    value = { ...value, deadline: started + remaining! * 1000 };
  }
  return value;
}

export function atTime(value: BroadcastState, now: number): BroadcastState {
  if (value.deadline !== undefined) {
    if (value.deadline <= now)
      return {
        state: value.state === "challenge" ? "expired" : "waiting",
        mode: value.mode,
        evidence: value.evidence,
      };
    return {
      ...value,
      remaining_seconds: Math.max(0, (value.deadline - now) / 1000),
    };
  }
  return value;
}

const theme = {
  ink: "#f3efff",
  muted: "#b2a7c4",
  violet: "#b69aff",
  mint: "#8fe7c4",
  bg: "#100e19",
};

function box(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  fill: string,
  radius = 20,
) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, radius);
  ctx.fill();
}

function text(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  size: number,
  color = theme.ink,
  weight = 600,
) {
  ctx.fillStyle = color;
  ctx.font = `${weight} ${size}px 'Segoe UI', Arial, sans-serif`;
  ctx.fillText(value, x, y);
}

export function wrapped(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  width: number,
  size: number,
  maxLines: number,
  color = theme.ink,
) {
  ctx.font = `600 ${size}px 'Segoe UI', Arial, sans-serif`;
  // Code-point wrapping works for bounded CJK, emoji, long unbroken words and Latin.
  const lines: string[] = [];
  let line = "";
  for (const char of Array.from(value)) {
    if (char === "\n" || ctx.measureText(line + char).width > width) {
      lines.push(line);
      line = char === "\n" ? "" : char;
    } else line += char;
  }
  if (line) lines.push(line);
  const visible = lines.slice(0, maxLines);
  if (lines.length > maxLines) {
    let last = visible[maxLines - 1];
    while (last && ctx.measureText(last + "…").width > width)
      last = Array.from(last).slice(0, -1).join("");
    visible[maxLines - 1] = last + "…";
  }
  visible.forEach((item, index) =>
    text(ctx, item, x, y + index * size * 1.32, size, color),
  );
}

export function drawBroadcast(
  canvas: HTMLCanvasElement,
  original: BroadcastState,
  now: number,
  layout: Scene | "Live" = "Live",
) {
  const ctx = canvas.getContext("2d", { alpha: false });
  if (!ctx) throw new Error("CANVAS_UNAVAILABLE");
  const state = atTime(original, now);
  const scene = layout === "Live" ? sceneFor(state) : layout;
  const isLayout = layout !== "Live";
  ctx.save();
  ctx.scale(canvas.width / 1280, canvas.height / 720);
  ctx.fillStyle = theme.bg;
  ctx.fillRect(0, 0, 1280, 720);
  const gradient = ctx.createRadialGradient(1120, 20, 0, 1120, 20, 920);
  gradient.addColorStop(0, "#352153");
  gradient.addColorStop(1, theme.bg);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 1280, 720);
  box(ctx, 48, 38, 44, 44, theme.violet, 12);
  text(ctx, "CQ", 56, 67, 22, "#211433", 800);
  text(ctx, "CrowdQuest AI", 108, 69, 27);
  text(ctx, "YOUR CHAT BECOMES THE GAME DIRECTOR", 110, 94, 11, theme.muted);
  text(ctx, scene.toUpperCase(), 930, 70, 17, theme.violet);
  const synthetic =
    state.evidence === "SYNTHETIC_TEST" ||
    state.round?.evidence === "SYNTHETIC_TEST";
  text(
    ctx,
    synthetic
      ? "SYNTHETIC TEST • ISOLATED APPLICATION STATE"
      : "AUTHORITATIVE CROWDQUEST STATE • LOCAL PRESENTATION",
    48,
    138,
    12,
    synthetic ? "#ffd891" : theme.muted,
  );
  if (isLayout)
    text(
      ctx,
      "LAYOUT PREVIEW • DOES NOT CHANGE CURRENT STATE",
      48,
      164,
      12,
      "#ffd891",
    );
  const show = !isLayout || sceneFor(state) === scene;
  if (show && scene === "Voting" && state.round) {
    const round = state.round;
    text(
      ctx,
      state.state === "voting"
        ? "Chat, make the call."
        : state.state === "pending_approval"
          ? "Your pick is in review."
          : round.winner
            ? "Chat has spoken."
            : "It’s a tie. Streamer decides.",
      48,
      218,
      43,
    );
    if (state.state === "voting")
      text(
        ctx,
        `${Math.ceil(state.remaining_seconds || 0)} SEC`,
        1050,
        215,
        32,
        theme.mint,
      );
    for (const [index, choice] of round.choices.slice(0, 2).entries()) {
      const y = 248 + index * 158;
      box(
        ctx,
        48,
        y,
        1184,
        142,
        round.winner === choice.number ? "#302443" : "#1b1827",
      );
      text(
        ctx,
        `${choice.number.toString().padStart(2, "0")}`,
        72,
        y + 42,
        25,
        theme.violet,
      );
      wrapped(
        ctx,
        choice.text,
        132,
        y + 26,
        900,
        Array.from(choice.text).length > 100 ? 16 : 24,
        Array.from(choice.text).length > 100 ? 5 : 3,
      );
      text(ctx, `${choice.votes} votes`, 1070, y + 46, 20, theme.mint);
      box(ctx, 132, y + 119, 1016, 6, "#3c334b", 3);
      if (choice.percentage > 0)
        box(
          ctx,
          132,
          y + 119,
          (1016 * Math.max(0, Math.min(100, choice.percentage))) / 100,
          6,
          theme.violet,
          3,
        );
    }
    text(
      ctx,
      state.state === "voting"
        ? "TWITCH CHAT  !vote 1  /  !vote 2  •  ONE VOTE PER VIEWER"
        : `${round.state.toUpperCase()}  •  ${round.total_votes} votes  •  ${round.winner ? `Winner: ${round.winner}` : "No automatic winner"}`,
      48,
      612,
      17,
      theme.muted,
    );
    text(
      ctx,
      "STREAMER REVIEW AND INDEPENDENT AUTHORIZATION STILL REQUIRED",
      48,
      644,
      12,
      theme.violet,
    );
  } else if (
    show &&
    scene === "Challenge Active" &&
    (state.challenge || state.text)
  ) {
    const challenge = state.challenge;
    text(
      ctx,
      challenge
        ? "APPROVED CHALLENGE • AIG SUCCEEDED • WORKER DELIVERED"
        : "DEVELOPMENT PREVIEW • NOT APPROVED / NOT EXECUTED",
      48,
      216,
      15,
      theme.mint,
    );
    if (state.chosen_by_chat) {
      box(ctx, 48, 242, 212, 34, "#244135", 10);
      text(ctx, "CHOSEN BY CHAT", 68, 266, 16, theme.mint);
    }
    wrapped(ctx, challenge?.title || state.text || "", 48, 330, 1010, 34, 3);
    if (challenge)
      wrapped(ctx, challenge.description, 48, 450, 960, 22, 6, theme.muted);
    text(
      ctx,
      `${Math.ceil(state.remaining_seconds || 0)}`,
      1090,
      355,
      80,
      theme.mint,
    );
    text(ctx, "SECONDS LEFT", 1070, 394, 14, theme.muted);
    text(
      ctx,
      challenge
        ? `${challenge.difficulty} • Display only; no gameplay automation`
        : state.warning || "DEVELOPMENT PREVIEW • NOT APPROVED / NOT EXECUTED",
      48,
      630,
      16,
      theme.violet,
    );
  } else if (show && scene === "Challenge Result" && state.outcome) {
    const kind = state.outcome;
    text(ctx, "STREAMER-REPORTED RESULT", 48, 236, 17, theme.violet);
    wrapped(
      ctx,
      kind === "Completed"
        ? "Challenge complete."
        : kind === "Failed"
          ? "That was a tough one."
          : "On to the next idea.",
      48,
      350,
      1150,
      68,
      2,
    );
    text(ctx, `${kind} • Reported by the streamer`, 48, 483, 30, theme.mint);
    text(ctx, "Ready for what chat dreams up next.", 48, 557, 22, theme.muted);
  } else {
    text(
      ctx,
      isLayout && scene !== "Waiting"
        ? `${scene} layout`
        : state.state === "disconnected"
          ? "Connection interrupted."
          : state.state === "expired"
            ? "Challenge expired."
            : "Ready for your next idea.",
      48,
      334,
      58,
    );
    wrapped(
      ctx,
      isLayout && scene !== "Waiting"
        ? "No current content matches. This view cannot create votes, challenges or results."
        : state.state === "disconnected"
          ? "The current presentation has ended. Reconnect to the backend safely."
          : "Chat proposes. The streamer chooses. Every action stays behind its safety gates.",
      48,
      410,
      1000,
      27,
      3,
      theme.muted,
    );
  }
  ctx.fillStyle = "#352b43";
  ctx.fillRect(48, 674, 1184, 1);
  text(ctx, "CROWD-POWERED. STREAMER-CONTROLLED.", 48, 704, 12, theme.muted);
  text(
    ctx,
    "LOCAL BROWSER BROADCAST • NO OBS REQUIRED",
    885,
    704,
    11,
    theme.violet,
  );
  ctx.restore();
}
