import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { VotingPanel, VoteBars, type VoteRound } from "./voting";
import { OutcomeDisplay, VotingDisplay } from "./broadcast";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
const candidates = [
  {
    id: "a",
    suggestion: "Use only basic attacks",
    event_time: 1,
    state: "candidate",
    source: "synthetic",
  },
  {
    id: "b",
    suggestion: "<img src=x onerror=alert(1)> Survive without healing",
    event_time: 2,
    state: "candidate",
    source: "synthetic",
  },
  {
    id: "c",
    suggestion: "Third idea",
    event_time: 3,
    state: "candidate",
    source: "synthetic",
  },
];
const choices = candidates.slice(0, 2).map((c, index) => ({
  number: index + 1,
  candidate_id: c.id,
  text: c.suggestion,
  votes: index ? 1 : 2,
  percentage: index ? 33.3 : 66.7,
}));
const example: VoteRound = {
  id: "round",
  state: "Draft",
  version: 1,
  choices,
  remaining_seconds: 15,
  total_votes: 3,
  winner: null,
  plan_bound: false,
};

it("shortlists exactly two and creates only a Draft with no approval request", async () => {
  let round: VoteRound | null = null;
  const posts: { path: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        posts.push({ path, body: JSON.parse(options.body as string) });
        round = example;
      }
      return new Response(JSON.stringify({ round }));
    }),
  );
  const { container } = render(
    <VotingPanel
      candidates={candidates}
      csrf="fixture-csrf"
      onReview={vi.fn()}
    />,
  );
  const create = await screen.findByRole("button", {
    name: "Create voting round",
  });
  await waitFor(() => expect(create).toBeDisabled());
  fireEvent.click(
    screen.getByRole("checkbox", {
      name: "Shortlist " + candidates[0].suggestion,
    }),
  );
  fireEvent.click(
    screen.getByRole("checkbox", {
      name: "Shortlist " + candidates[1].suggestion,
    }),
  );
  expect(
    screen.getByRole("checkbox", { name: "Shortlist Third idea" }),
  ).toBeDisabled();
  await waitFor(() => expect(create).toBeEnabled());
  fireEvent.click(create);
  expect(
    await screen.findByRole("button", { name: "Start voting" }),
  ).toBeEnabled();
  expect(posts).toHaveLength(1);
  expect(posts[0].path).toBe("/api/phase4/rounds");
  expect(posts[0].body.candidate_ids).toEqual(["a", "b"]);
  expect(posts[0].body).not.toHaveProperty("deadline");
  expect(container.querySelector("img")).toBeNull();
});

it("requires explicit tie choice before offering winner planning", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({ round: { ...example, state: "Closed" } }),
        ),
    ),
  );
  render(
    <VotingPanel candidates={candidates} csrf="fixture" onReview={vi.fn()} />,
  );
  expect(
    await screen.findByRole("button", { name: "Choose candidate 1 as winner" }),
  ).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Choose candidate 2 as winner" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Generate winning Plan" }),
  ).toBeNull();
});

it("generates only the bound winner and navigates to its review", async () => {
  const review = vi.fn(),
    posts: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        posts.push(path);
        return new Response(JSON.stringify({ candidate_id: "b" }));
      }
      return new Response(
        JSON.stringify({ round: { ...example, state: "Closed", winner: 2 } }),
      );
    }),
  );
  render(
    <VotingPanel candidates={candidates} csrf="fixture" onReview={review} />,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Generate winning Plan" }),
  );
  await waitFor(() => expect(review).toHaveBeenCalledWith("b"));
  expect(posts).toEqual(["/api/phase4/rounds/round/plan"]);
});

it("fails closed and does not repeat a rejected mutation", async () => {
  let posts = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_path: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        posts++;
        return new Response("{}", { status: 409 });
      }
      return new Response(JSON.stringify({ round: example }));
    }),
  );
  render(
    <VotingPanel candidates={candidates} csrf="fixture" onReview={vi.fn()} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Start voting" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("round changed");
  expect(posts).toBe(1);
});

it("shows persisted vote values as accessible meters and escaped text", () => {
  const { container } = render(<VoteBars round={example} />);
  expect(
    screen.getByRole("meter", { name: "Candidate 1 vote share" }),
  ).toHaveAttribute("value", "66.7");
  expect(screen.getByText(candidates[1].suggestion)).toBeVisible();
  expect(container.querySelector("img")).toBeNull();
});

it("shows voting instructions, countdown and streamer review boundary", () => {
  render(
    <VotingDisplay
      round={{ ...example, state: "Open" }}
      state="voting"
      remaining={12.1}
    />,
  );
  expect(screen.getByLabelText("Voting time remaining")).toHaveTextContent(
    "13",
  );
  expect(screen.getAllByText("!vote 1").length).toBeGreaterThan(0);
});

it.each(["Completed", "Failed", "Skipped"])(
  "labels %s as owner reported gameplay",
  (kind) => {
    render(<OutcomeDisplay kind={kind} />);
    expect(screen.getByText("STREAMER-REPORTED RESULT")).toBeVisible();
    expect(
      screen.getByText(kind + " · Reported by the streamer"),
    ).toBeVisible();
  },
);
