// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { finalizeWebm, streamingSegment } from "./studio-webm";

afterEach(() => vi.unstubAllGlobals());

it("preserves encoded payload and VINT width while normalizing the streaming root", async () => {
  // A tiny EBML envelope fixture, not claimed as a decodable video.
  const bytes = new Uint8Array([
    0x1a, 0x45, 0xdf, 0xa3, 0x81, 0x00, 0x18, 0x53, 0x80, 0x67, 0x40, 0x08,
    0x1f, 0x43, 0xb6, 0x75, 0xff, 0x01, 0x02, 0x03,
  ]);
  const result = new Uint8Array(
    await (
      await streamingSegment(new Blob([bytes], { type: "video/webm" }))
    ).arrayBuffer(),
  );
  expect(result.length).toBe(bytes.length);
  expect([...result.slice(0, 10)]).toEqual([...bytes.slice(0, 10)]);
  expect([...result.slice(10, 12)]).toEqual([0x7f, 0xff]);
  expect([...result.slice(12)]).toEqual([...bytes.slice(12)]);
});

it("fails closed on malformed or unbounded EBML headers", async () => {
  await expect(streamingSegment(new Blob(["not a video"]))).rejects.toThrow();
  await expect(
    streamingSegment(
      new Blob([
        new Uint8Array([
          0x1a, 0x45, 0xdf, 0xa3, 0x00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        ]),
      ]),
    ),
  ).rejects.toThrow();
});

it("adds duration without parsing or rewriting streaming media Clusters", async () => {
  // Node has no FileReader; use its Blob reader. Real Chromium covers the native API.
  vi.stubGlobal(
    "FileReader",
    class {
      result: ArrayBuffer | null = null;
      onloadend: (() => void) | null = null;
      async readAsArrayBuffer(blob: Blob) {
        this.result = await blob.arrayBuffer();
        this.onloadend?.();
      }
    },
  );
  // Structurally valid metadata, deliberately opaque media bytes: not a video.
  const metadata = new Uint8Array([
    0x1a, 0x45, 0xdf, 0xa3, 0x80, 0x18, 0x53, 0x80, 0x67, 0x01, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0x15, 0x49, 0xa9, 0x66, 0x87, 0x2a, 0xd7,
    0xb1, 0x83, 0x0f, 0x42, 0x40,
  ]);
  const media = new Uint8Array([
    0x1f, 0x43, 0xb6, 0x75, 0x01, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xa3, 0x81, 0x42, 0x1f, 0x43, 0xb6, 0x75, 0x01, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xa3, 0x81, 0x43,
  ]);
  const result = new Uint8Array(
    await (
      await finalizeWebm(
        new Blob([metadata, media], { type: "video/webm" }),
        32000,
      )
    ).arrayBuffer(),
  );
  expect([...result.slice(-media.length)]).toEqual([...media]);
  expect(result.length).toBeGreaterThan(metadata.length + media.length);
  await expect(
    finalizeWebm(new Blob([metadata, media]), NaN),
  ).rejects.toThrow();
  await expect(finalizeWebm(new Blob([metadata]), 1000)).rejects.toThrow();
});
