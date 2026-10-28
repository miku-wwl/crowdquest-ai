import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { ObsAdmin } from "./obs-admin";

afterEach(() => {
  vi.unstubAllGlobals();
});

function transport(authenticated = true, configured = true) {
  let active = false;
  const posts: string[] = [];
  let fail = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      const operation = path.replace("/api/obs-admin", "");
      if (options?.method === "POST") {
        posts.push(operation);
        expect(options.headers).toMatchObject({
          "X-CSRF-Token": "synthetic-csrf",
        });
        if (fail)
          return new Response(
            JSON.stringify({ detail: "OBS_OUTCOME_UNKNOWN" }),
            { status: 409 },
          );
        if (operation === "/login")
          return new Response(
            JSON.stringify({
              authenticated: true,
              configured,
              csrf: "synthetic-csrf",
            }),
          );
        if (operation === "/record/start") active = true;
        if (operation === "/record/stop") active = false;
        return new Response(JSON.stringify({ ok: true, result: "VERIFIED" }));
      }
      if (operation === "/session")
        return new Response(
          JSON.stringify({ authenticated, configured, csrf: "synthetic-csrf" }),
        );
      return new Response(
        JSON.stringify({
          connected: true,
          revision: "synthetic-revision",
          obs_version: "32.2.2",
          websocket_version: "5.6.3",
          scenes: [
            "CrowdQuest Demo",
            "<img src=x onerror=alert(1)>",
            "Other existing scene",
          ],
          current_scene: "CrowdQuest Demo",
          streaming: false,
          recording: {
            active,
            paused: false,
            elapsed_seconds: 3,
            output_path: active ? null : "C:/synthetic/test.mkv",
          },
          overlay: {
            found: true,
            valid: true,
            enabled: true,
            url: "http://localhost:8000/overlay",
          },
        }),
      );
    }),
  );
  return {
    posts,
    fail: () => {
      fail = true;
    },
  };
}

it("shows actual state and requires explicit commands, never auto-records", async () => {
  const { posts } = transport();
  const { container } = render(<ObsAdmin />);
  await screen.findByText("32.2.2");
  expect(screen.getByText("Connected")).toBeVisible();
  expect(screen.getByRole("button", { name: "Stop Recording" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Switch scene" })).toBeDisabled();
  expect(posts).toEqual([]);
  expect(container.querySelector("img")).toBeNull();
  expect(screen.queryByRole("button", { name: /stream/i })).toBeNull();
  fireEvent.change(screen.getByLabelText("Existing scene"), {
    target: { value: "Other existing scene" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Switch scene" }));
  await waitFor(() => expect(posts).toEqual(["/scene"]));
});

it("prevents double-clicks and confirms start/stop from refreshed status", async () => {
  const { posts } = transport();
  render(<ObsAdmin />);
  const start = await screen.findByRole("button", { name: "Start Recording" });
  await waitFor(() => expect(start).toBeEnabled());
  fireEvent.click(start);
  fireEvent.click(start);
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Stop Recording" }),
    ).toBeEnabled(),
  );
  expect(posts).toEqual(["/record/start"]);
  fireEvent.click(screen.getByRole("button", { name: "Stop Recording" }));
  await waitFor(() => expect(start).toBeEnabled());
  expect(posts).toEqual(["/record/start", "/record/stop"]);
  expect(screen.getByText("C:/synthetic/test.mkv")).toBeVisible();
});

it("stops on uncertain commands without retry or stale enabled controls", async () => {
  const { posts, fail } = transport();
  render(<ObsAdmin />);
  const start = await screen.findByRole("button", { name: "Start Recording" });
  await waitFor(() => expect(start).toBeEnabled());
  fail();
  fireEvent.click(start);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "OBS_OUTCOME_UNKNOWN",
  );
  expect(start).toBeDisabled();
  expect(posts).toEqual(["/record/start"]);
});

it("uses a separate password form with no OBS credential field", async () => {
  const { posts } = transport(false);
  render(<ObsAdmin />);
  const input = await screen.findByLabelText("Admin passphrase");
  expect(input).toHaveAttribute("type", "password");
  expect(screen.queryByLabelText("OBS password")).toBeNull();
  fireEvent.change(input, { target: { value: "synthetic-admin-passphrase" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in locally" }));
  await screen.findByText("OBS Connection");
  expect(posts).toEqual(["/login"]);
});

it("keeps all controls unavailable until private setup", async () => {
  transport(false, false);
  render(<ObsAdmin />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Setup required");
  expect(
    screen.getByRole("button", { name: "Sign in locally" }),
  ).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Start Recording" })).toBeNull();
});
