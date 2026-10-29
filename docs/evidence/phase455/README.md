# Phase 4.5.5 evidence

All new media and execution evidence is **SYNTHETIC_TEST_ONLY**. No production SQLite,
real chat history, OAuth/capability/session credentials or private file hashes are included.

- `baseline-comparison.json`: expected failures against original source; direct hidden
  polling and View ID failures distinguished from new-protocol compatibility failures.
- `dependency.json`: installed pin/API/RECORD and original instruction prefix verification;
  its Phase 0 scope is dependency verification only, not runtime or live acceptance.
- `delivery-qualification.json`: actual Chromium with two pages, explicit visibility
  override when native hidden state is unavailable, actual ACK and durable observation.
  The native two-tab qualification is PARTIAL even though deterministic protocol checks pass.
- `recording.json`, `synthetic-video-decode.txt`: final Canvas/WebM playback, dimensions,
  duration, hash and full FFmpeg decode evidence (exported log trailing whitespace normalized). The 8.2 MB WebM remains local at
  `.artifacts/phase455/final-studio-verified/` and is excluded from Git/review ZIP.
- `synthetic-visible-challenge.png`: supplementary Canvas frame, not a substitute for
  ACK evidence or evidence of OBS rendering. The four scene preview frames remain in
  the local artifact directory with the WebM, keeping Git and the review package small.
- `preservation.json`: sanitized read-only checkpoint. A normal live Worker heartbeat
  changes render.sqlite3; no test/repair production write or whole-interval byte identity
  is claimed. Historical files and live frontend/dist are preserved.
- `test-summary.json`: executed local commands, exit codes, counts, security scope and
  explicit remaining gaps. Exact commit and completed CI are in the owner's review package.

Historical Phase 4.5.4 evidence is outside this directory and was not edited.
