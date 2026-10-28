import { fixWebmDuration } from "@fix-webm-duration/fix";

// Parse metadata only: the duration library cannot delimit unknown-size Clusters.
// Giving it the media tail would nest later Clusters inside a finite first Cluster.
// Preserve that entire tail byte-for-byte and keep the root streaming-sized.
export async function finalizeWebm(
  blob: Blob,
  milliseconds: number,
): Promise<Blob> {
  if (!Number.isFinite(milliseconds) || milliseconds <= 0)
    throw new Error("INVALID_WEBM_DURATION");
  const bytes = new Uint8Array(await blob.slice(0, 1024 * 1024).arrayBuffer());
  function field(at: number, identifier = false) {
    let mask = 0x80,
      length = 1;
    while (length <= 8 && !(bytes[at] & mask)) {
      mask >>= 1;
      length++;
    }
    if (length > (identifier ? 4 : 8) || at + length > bytes.length)
      throw new Error("INVALID_WEBM_HEADER");
    let value = BigInt(identifier ? bytes[at] : bytes[at] & (mask - 1));
    for (let i = 1; i < length; i++)
      value = value * 256n + BigInt(bytes[at + i]);
    return {
      length,
      value,
      unknown: !identifier && value === (1n << BigInt(length * 7)) - 1n,
    };
  }
  const ebml = field(0, true);
  if (ebml.value !== 0x1a45dfa3n) throw new Error("INVALID_WEBM_HEADER");
  const headerSize = field(ebml.length);
  if (headerSize.unknown || headerSize.value > 1024n)
    throw new Error("INVALID_WEBM_HEADER");
  const segmentAt = ebml.length + headerSize.length + Number(headerSize.value);
  const segment = field(segmentAt, true);
  if (segment.value !== 0x18538067n) throw new Error("INVALID_WEBM_SEGMENT");
  const segmentSize = field(segmentAt + segment.length);
  let at = segmentAt + segment.length + segmentSize.length;
  let info = false;
  while (at < bytes.length) {
    const id = field(at, true);
    if (id.value === 0x1f43b675n) {
      if (!info) throw new Error("WEBM_INFO_MISSING");
      const fixed = await fixWebmDuration(blob.slice(0, at), milliseconds, {
        logger: false,
      });
      return new Blob([await streamingSegment(fixed), blob.slice(at)], {
        type: blob.type,
      });
    }
    const size = field(at + id.length);
    if (size.unknown || size.value > BigInt(bytes.length - at))
      throw new Error("INVALID_WEBM_METADATA");
    info ||= id.value === 0x1549a966n;
    at += id.length + size.length + Number(size.value);
  }
  throw new Error("WEBM_CLUSTER_MISSING");
}

export async function streamingSegment(blob: Blob): Promise<Blob> {
  const header = new Uint8Array(await blob.slice(0, 2048).arrayBuffer());
  function size(at: number) {
    let mask = 0x80,
      length = 1;
    while (length <= 8 && !(header[at] & mask)) {
      mask >>= 1;
      length++;
    }
    if (length > 8 || at + length > header.length)
      throw new Error("INVALID_WEBM_HEADER");
    let value = header[at] & (mask - 1);
    for (let i = 1; i < length; i++) value = value * 256 + header[at + i];
    return { length, value };
  }
  if (
    header.length < 16 ||
    ![0x1a, 0x45, 0xdf, 0xa3].every((value, i) => header[i] === value)
  )
    throw new Error("INVALID_WEBM_HEADER");
  const ebml = size(4);
  if (ebml.value > 1024) throw new Error("INVALID_WEBM_HEADER");
  const segment = 4 + ebml.length + ebml.value;
  if (
    ![0x18, 0x53, 0x80, 0x67].every((value, i) => header[segment + i] === value)
  )
    throw new Error("INVALID_WEBM_SEGMENT");
  const at = segment + 4;
  const field = size(at);
  header[at] = (1 << (9 - field.length)) - 1;
  header.fill(0xff, at + 1, at + field.length);
  return new Blob([header, blob.slice(header.length)], { type: blob.type });
}
