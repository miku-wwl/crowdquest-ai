# Phase 4 competitive upgrade

Date: 2026-10-27, Pacific/Auckland. Baseline:
`369ec862465705225f8781dd867ecd23fdf90028` (clean checkout).

Positioning: **CrowdQuest AI — Your Chat Becomes the Game Director.**
Viewers propose; the community chooses; the local model structures; the streamer
reviews and independently authorizes; AIG admits one effect; OBS presents it.

## Reviewed implementation decisions

1. Keep voting in the existing consumer intake SQLite database. Validate EventSub
   before parsing `!vote 1`/`!vote 2`; transact delivery/message dedup, round eligibility,
   one keyed pseudonym per voter/round and vote insertion together. Tallies are derived
   from committed votes, never client counters. Preserve legacy quest parsing/limits.
2. Persist Draft/Open/Closed/Cancelled rounds, frozen pairs of candidates, optimistic
   versions, command identities, bounded server-created deadlines and explicit tie
   selection. One unfinished round per channel. Deadline expiry is materialized under
   the same write lock as voting. Restart never extends an Open round.
3. Bind the selected winner to its immutable candidate and model Run in consumer
   provenance. No vote path calls Approval, admission, Authorization or Execute.
   Add the audience badge from this trusted mapping, outside AIG arguments/schema.
4. Add immutable owner-reported outcomes to the consumer rendering ledger, linked to
   a durable successful Action, receipt and acknowledged render. Outcomes do not alter
   AIG results. Present each outcome briefly with a durable per-overlay issue marker;
   reload/restart never rearms the presentation or repeats the challenge.
5. Retain existing owner/CSRF/Origin and overlay pairing boundaries. The overlay polls
   read-only voting/presentation data through its existing credential; no voter IDs,
   runtime credentials, raw chat or private paths are returned.
6. Keep the exact installed AIG v0.3.0 pin, public API, single trusted tool, four separate
   human operations and five-second budget. No core extension or new tool is needed.
7. Use a trusted `frontend_directory` composition parameter for test builds. The default
   remains the existing dist directory; tests select an isolated build. Do not rebuild
   the dist consumed by the real PID 20136 or start/restart any real process.

## Baseline evidence

Before edits: 163 Python tests and 16 frontend tests passed (exit 0). Installed public
API/provenance, offline lock and dependency compatibility passed. Real listener was
observed at 127.0.0.1:8000, PID 20136; it was not modified. The checkout was clean.
The prior real Phase 3 session is recorded separately from new synthetic qualification.

## Qualification boundary

Phase 4 live Twitch/voting/outcome/OBS acceptance is NOT_RUN until separately authorized.
All development and destructive/fault tests use isolated temporary state. See the
acceptance report and live runbook for measured results and remaining gates.
