import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { vi, beforeEach, afterEach } from "vitest";
import { CandidateList, Dashboard, Overlay, WARNING } from "./ui";

const suggestion = '<img src=x onerror="window.pwned=1"> Survive 60 seconds';
const candidates = [
  {
    id: "candidate-1",
    suggestion,
    event_time: 1800000000,
    state: "candidate",
    source: "synthetic",
  },
];
let posts: { path: string; body?: string }[];
beforeEach(() => {
  posts = [];
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function transport(authenticated = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        posts.push({ path, body: options.body as string });
        return new Response(JSON.stringify({ ok: true }));
      }
      const result =
        path === "/api/me"
          ? {
              authenticated,
              login: "fixture_owner",
              csrf: "synthetic-csrf",
              connection: "connected",
            }
          : path === "/api/candidates"
            ? {
                session: {
                  generation: 0,
                  candidate_after: 0,
                  round_after: 0,
                  cleared_at: null,
                },
                candidates,
              }
            : { pending: ["ABCDEF1234567890"], ready: 1 };
      return new Response(JSON.stringify(result));
    }),
  );
}

it("renders candidate text literally and requires explicit selection", () => {
  const select = vi.fn();
  const { container } = render(
    <CandidateList candidates={candidates} selected="" onSelect={select} />,
  );
  expect(screen.getByText(suggestion)).toBeVisible();
  expect(container.querySelector("img")).toBeNull();
  expect(select).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("radio"));
  expect(select).toHaveBeenCalledWith("candidate-1");
});

it("shows connection and manual preview without auto-publishing", async () => {
  transport();
  render(<Dashboard />);
  await screen.findByText("@fixture_owner");
  expect(screen.getByText("connected")).toBeVisible();
  expect(screen.getByText("DIRECTOR DASHBOARD")).toBeVisible();
  expect(screen.getByText("Broadcast Studio")).toBeVisible();
  expect(screen.getByText("MANUAL PREVIEW")).toBeVisible();
  await screen.findByRole("radio");
  const preview = screen.getByRole("button", { name: "Preview selected →" });
  expect(preview).toBeDisabled();
  expect(posts).toHaveLength(0);
  fireEvent.click(screen.getByRole("radio"));
  expect(preview).toBeEnabled();
  expect(posts).toHaveLength(0);
  fireEvent.click(preview);
  await waitFor(() =>
    expect(posts).toEqual([
      {
        path: "/api/preview",
        body: JSON.stringify({ candidate_id: "candidate-1" }),
      },
    ]),
  );
  expect(screen.getByText(WARNING)).toBeVisible();
});

it("offers only sign-in for unauthenticated state", async () => {
  transport(false);
  render(<Dashboard />);
  expect(
    await screen.findByRole("link", { name: "Connect Twitch →" }),
  ).toHaveAttribute("href", "/auth/twitch/start");
  expect(screen.queryByRole("radio")).toBeNull();
});

it("confirms a persistent demo-history reset and waits for new suggestions", async () => {
  let generation = 0;
  let visible = candidates;
  const confirmation = vi.fn(() => true);
  vi.stubGlobal("confirm", confirmation);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        posts.push({ path, body: options.body as string });
        generation++;
        visible = [];
        return new Response(
          JSON.stringify({
            session: {
              generation,
              candidate_after: 1,
              round_after: 0,
              cleared_at: 1800000000,
            },
          }),
        );
      }
      const result =
        path === "/api/me"
          ? {
              authenticated: true,
              login: "fixture_owner",
              csrf: "synthetic-csrf",
              connection: "connected",
              workflow: "production",
              features: ["crowd_voting"],
            }
          : path === "/api/candidates"
            ? {
                session: {
                  generation,
                  candidate_after: generation ? 1 : 0,
                  round_after: generation ? 1 : 0,
                  cleared_at: generation ? 1800000000 : null,
                },
                candidates: visible,
              }
            : path === "/api/phase4/voting"
              ? { round: null }
              : { pending: [], ready: 0 };
      return new Response(JSON.stringify(result));
    }),
  );
  render(<Dashboard />);
  await screen.findByRole("radio");
  fireEvent.click(
    screen.getByRole("button", { name: "Hide Earlier Activity" }),
  );
  await waitFor(() => expect(screen.queryByRole("radio")).toBeNull());
  expect(confirmation).toHaveBeenCalledWith(
    "Hide earlier suggestions and voting rounds from this view? Historical records and audit evidence will be preserved.",
  );
  expect(posts).toContainEqual({
    path: "/api/demo/session/clear",
    body: "{}",
  });
  expect(
    await screen.findByText(
      "Waiting for 2 new suggestions before a fresh vote can start.",
    ),
  ).toBeVisible();
  expect(
    screen.getByText(
      "Earlier activity is hidden. New suggestions will appear here.",
    ),
  ).toBeVisible();
  expect(
    screen
      .getByText(
        "Earlier activity is hidden. New suggestions will appear here.",
      )
      .closest('[role="status"]'),
  ).toHaveClass("notice-compact");
});

it("renders network errors without candidate controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new Error("synthetic failure")),
  );
  render(<Dashboard />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Connection lost");
  expect(screen.queryByRole("radio")).toBeNull();
});

it("renders a server rejection after a manual action", async () => {
  transport();
  render(<Dashboard />);
  fireEvent.click(await screen.findByRole("radio"));
  const previous = globalThis.fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) =>
      options?.method === "POST"
        ? new Response("{}", { status: 403 })
        : previous(path, options),
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Preview selected →" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Request rejected",
  );
});

it("renders overlay untrusted text with the warning and synthetic attribution", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            state: "preview",
            text: suggestion,
            expires_at: Date.now() / 1000 + 60,
            remaining_seconds: 60,
            source: "synthetic",
          }),
        ),
    ),
  );
  const { container } = render(<Overlay />);
  expect(await screen.findByText(suggestion)).toBeVisible();
  expect(screen.getByText(WARNING)).toBeVisible();
  expect(screen.getByText("SYNTHETIC TEST DATA")).toBeVisible();
  expect(container.querySelector("img")).toBeNull();
});

it("clears overlay into disconnected state when polling fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<Overlay />);
  expect(await screen.findByText("Connection lost")).toBeVisible();
  expect(screen.queryByText(suggestion)).toBeNull();
});

it.each(["remaining", "legacy_date"])(
  "expires by monotonic time despite client clock jumps (%s)",
  async (protocol) => {
    vi.useFakeTimers({
      toFake: [
        "setTimeout",
        "clearTimeout",
        "setInterval",
        "clearInterval",
        "Date",
        "performance",
      ],
    });
    const serverEpoch = 1800000000;
    vi.setSystemTime((serverEpoch + 86400) * 1000);
    let requests = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        if (++requests > 1) return new Promise<Response>(() => {});
        return new Response(
          JSON.stringify({
            state: "preview",
            text: "Monotonic preview",
            source: "synthetic",
            expires_at: serverEpoch + 2,
            ...(protocol === "remaining" ? { remaining_seconds: 2 } : {}),
          }),
          { headers: { Date: new Date(serverEpoch * 1000).toUTCString() } },
        );
      }),
    );
    render(<Overlay />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText("Monotonic preview")).toBeVisible();
    vi.setSystemTime((serverEpoch - 86400) * 1000);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2250);
    });
    expect(screen.queryByText("Monotonic preview")).toBeNull();
    expect(screen.getByText("Ready for your next idea")).toBeVisible();
  },
);
