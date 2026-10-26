import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { ReviewPanel } from "./review";
import { Overlay } from "./ui";

const candidate = {
  id: "candidate-fixture",
  suggestion: "Survive without healing",
  event_time: 1800000000,
  state: "candidate",
  source: "synthetic",
};
const challenge = {
  title: "<img src=x onerror=alert(1)>",
  description: "A bounded game challenge",
  duration_seconds: 60,
  difficulty: "Medium",
};
const run = {
  run_id: "run-fixture",
  version: 4,
  state: "AwaitingApproval",
  plan: { steps: [{ arguments: challenge }] },
};
const pending = {
  action_id: "action-fixture",
  version: 1,
  state: "Pending",
  admission: null as { state: string; receipt_hash: string } | null,
  rendering: { state: "Waiting", acknowledgements: 0 },
};
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function workflow(initialAction: typeof pending | null = null) {
  const posts: { path: string; body: Record<string, unknown> }[] = [];
  let value = {
    status: initialAction ? "READY" : "Candidate",
    run: initialAction
      ? { ...run, state: "Approved", version: 5 }
      : (null as typeof run | null),
    provenance: initialAction
      ? { source: "SYNTHETIC_TEST" }
      : (null as { source: string } | null),
    action: initialAction,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        const body = JSON.parse(options.body as string);
        posts.push({ path, body });
        if (path.endsWith("/generate"))
          value = {
            ...value,
            status: "READY",
            run: { ...run },
            provenance: { source: "SYNTHETIC_TEST" },
          };
        if (path.endsWith("/decision"))
          value = {
            ...value,
            run: {
              ...run,
              state: body.decision === "APPROVE" ? "Approved" : "Rejected",
              version: 5,
            },
          };
        if (path.endsWith("/admit"))
          value = { ...value, action: { ...pending } };
        if (path.endsWith("/authorize"))
          value = {
            ...value,
            action: { ...pending, state: "Authorized", version: 2 },
          };
        if (path.endsWith("/execute"))
          value = {
            ...value,
            action: {
              ...pending,
              state: "Succeeded",
              version: 4,
              admission: { state: "ELIGIBLE", receipt_hash: "abc123def456" },
              rendering: { state: "RENDERED", acknowledgements: 1 },
            },
          };
        if (path.endsWith("/manual"))
          value = {
            ...value,
            run: { ...run, run_id: "fresh-manual-run" },
            provenance: { source: "OFFLINE_MANUAL" },
          };
      }
      return new Response(
        JSON.stringify(path === "/api/phase3/status" ? { audit: [] } : value),
      );
    }),
  );
  return posts;
}

it("requires distinct explicit generation, approval, admission, authorization and execution", async () => {
  const posts = workflow();
  render(<ReviewPanel candidate={candidate} csrf="fixture-csrf" />);
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Generate proposed Plan" }),
    ).toBeEnabled(),
  );
  expect(posts).toHaveLength(0);
  fireEvent.click(
    screen.getByRole("button", { name: "Generate proposed Plan" }),
  );
  expect(await screen.findByText(challenge.title)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Approve this Plan" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Admit approved Action" }),
    ).toBeEnabled(),
  );
  expect(posts).toHaveLength(2);
  expect(posts[1].body).toEqual({ decision: "APPROVE", expected_version: 4 });
  expect(posts.some((p) => p.path.endsWith("/authorize"))).toBe(false);
  fireEvent.click(
    screen.getByRole("button", { name: "Admit approved Action" }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Authorize this Action" }),
    ).toBeEnabled(),
  );
  expect(posts).toHaveLength(3);
  fireEvent.click(
    screen.getByRole("button", { name: "Authorize this Action" }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Execute authorized Action" }),
    ).toBeEnabled(),
  );
  expect(posts).toHaveLength(4);
  fireEvent.click(
    screen.getByRole("button", { name: "Execute authorized Action" }),
  );
  expect(await screen.findByText("Succeeded")).toBeVisible();
  expect(posts.map((p) => p.path.split("/").at(-1))).toEqual([
    "generate",
    "decision",
    "admit",
    "authorize",
    "execute",
  ]);
});

it("shows unknown as terminal without retry or replacement controls", async () => {
  workflow({ ...pending, state: "Unknown", version: 4 });
  render(<ReviewPanel candidate={candidate} csrf="fixture" />);
  expect(await screen.findByText(/stopped permanently/)).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Execute authorized Action" }),
  ).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Edit a manual draft" }),
  ).toBeNull();
});

it("renders exact fields as text and manual edits create a fresh review", async () => {
  const posts = workflow();
  const { container } = render(
    <ReviewPanel candidate={candidate} csrf="fixture" />,
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Generate proposed Plan" }),
    ).toBeEnabled(),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Generate proposed Plan" }),
  );
  expect(await screen.findByText(challenge.title)).toBeVisible();
  expect(container.querySelector("img")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Edit a manual draft" }));
  fireEvent.change(screen.getByLabelText("Title"), {
    target: { value: "Reviewed edit" },
  });
  fireEvent.change(screen.getByLabelText("Description", { exact: true }), {
    target: { value: "Explicit description" },
  });
  fireEvent.change(screen.getByLabelText("Difficulty", { exact: true }), {
    target: { value: "Hard" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create manual Plan" }));
  expect(
    await screen.findByText("OFFLINE_MANUAL", { exact: true }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Approve this Plan" }),
  ).toBeEnabled();
  expect(posts.at(-1)?.body).toMatchObject({
    expected_version: 4,
    challenge: {
      title: "Reviewed edit",
      description: "Explicit description",
      difficulty: "Hard",
    },
  });
  expect(posts.filter((p) => p.path.endsWith("/generate"))).toHaveLength(1);
});

it("surfaces stale rejection without combining or retrying operations", async () => {
  const posts = workflow();
  render(<ReviewPanel candidate={candidate} csrf="fixture" />);
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Generate proposed Plan" }),
    ).toBeEnabled(),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Generate proposed Plan" }),
  );
  await screen.findByRole("button", { name: "Approve this Plan" });
  const original = globalThis.fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) =>
      options?.method === "POST"
        ? new Response("{}", { status: 409 })
        : original(path, options),
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Approve this Plan" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("state changed");
  expect(posts).toHaveLength(1);
});

it("pauses controls while current state is unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<ReviewPanel candidate={candidate} csrf="fixture" />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Actions are paused",
  );
  expect(
    screen.getByRole("button", { name: "Generate proposed Plan" }),
  ).toBeDisabled();
});

it("acknowledges production display once and escapes model text", async () => {
  const posts: string[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    cb(0);
    return 1;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        posts.push(path);
        return new Response('{"ok":true}');
      }
      return new Response(
        JSON.stringify({
          mode: "production",
          state: "challenge",
          render_id: "fixture-render",
          delivery_id: "fixture-delivery",
          challenge,
          remaining_seconds: 60,
        }),
      );
    }),
  );
  const { container } = render(<Overlay />);
  expect(await screen.findByText(challenge.title)).toBeVisible();
  await waitFor(() => expect(posts).toEqual(["/api/overlay/ack"]));
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByLabelText("Time remaining")).toBeVisible();
});

it("production countdown expires with wall-clock jumps and no fresh response", async () => {
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
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    cb(0);
    return 1;
  });
  vi.setSystemTime(1800000000000);
  let gets = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_path: string, options?: RequestInit) => {
      if (options?.method === "POST") return new Response('{"ok":true}');
      if (++gets > 1) return new Promise<Response>(() => {});
      return new Response(
        JSON.stringify({
          mode: "production",
          state: "challenge",
          render_id: "fixture-render",
          delivery_id: "fixture-delivery",
          challenge: { ...challenge, duration_seconds: 15 },
          remaining_seconds: 15,
        }),
      );
    }),
  );
  render(<Overlay />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(screen.getByText(challenge.title)).toBeVisible();
  vi.setSystemTime(1700000000000);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(15250);
  });
  expect(screen.queryByText(challenge.title)).toBeNull();
  expect(screen.getByText("Challenge expired")).toBeVisible();
});
