# Phase 4.5.6 — Dashboard History Cleanup

Status note dated 2026-10-30. This record supplements, and does not rewrite, earlier
acceptance reports.

## Delivery and qualification

- Feature source commit: `ad28c815258cd86d0a1dbe99b328a00b2696cada`.
- Push to `main` and feature-commit CI: [run 40976755384](https://github.com/miku-wwl/crowdquest-ai/actions/runs/40976755384), conclusion **success**.
- The owner-provided local delivery report listed 290 backend tests and 63 frontend
  tests. These remain attributed reported counts, not a fresh test run or counts
  independently extracted from GitHub logs during this documentation pass.
- **ISOLATED_QUALIFICATION=PASS:** synthetic Dashboard reset/browser coverage and
  the Studio ACK browser suite are qualified by the feature commit CI. This does not
  prove real Twitch-to-Studio acceptance. The native background-tab retest for Phase
  4.5.5 remains PARTIAL/pending.
- **LOCAL_ACTIVATION_EVIDENCE=PARTIAL:** the supplied screenshot shows the clean view;
  read-only SQLite confirms persistent watermarks/history. The owner's login/click
  sequence is not independently verified.

## Display-only mechanism

The consumer intake database adds `dashboard_sessions` with a per-channel generation,
`candidate_after` and `round_after` rowid watermarks, and `cleared_at`. Clear Demo
History requires the authenticated channel owner, same-origin request and CSRF token.
It refuses while a Draft/Open round, model generation/edit, nonterminal Action, eligible
job without a terminal render record, or active render is present. The route fails
closed on storage errors.

A clear advances display watermarks; it does not delete or change candidate, vote,
Plan, Action, approval/authorization, admission receipt, render, ACK, UNKNOWN, or
EventSub deduplication records. Dashboard candidate selection and current-round
selection honor those watermarks, so old suggestions cannot be reselected into a new
Plan through the current demo view. New candidates written after the watermark appear
normally. The chosen generation/watermarks persist across refresh.

## Screenshot and read-only activation evidence

The cleared view is evidenced for the local profile on 2026-10-30. The screenshot
shows the post-clear display, but does not independently establish the owner's login
or the button click. Evidence is attributed as follows:

- `USER_PROVIDED_SCREENSHOT`: the Dashboard showed “Previous demo records are hidden,”
  no current round, Inbox count 0, and the waiting state for two new suggestions.
- `AGENT_READ_ONLY_SQLITE`: `dashboard_sessions` generation 1; zero candidates and
  voting rounds above the stored display watermarks; all 9 earlier candidate rows and
  4 earlier voting-round rows remained stored; SQLite `integrity_check` passed.
- The screenshot showed EventSub listening, 0 notifications and 0 newly stored events.
  No new real Twitch suggestion/vote/Plan/Action-to-Studio end-to-end retest was
  performed in this documentation pass: `NEW_REAL_TWITCH_E2E=NOT_RUN`.

The screenshot is user-supplied visual evidence and is not copied to an invented
repository path. Read-only database evidence confirms persistence; neither source
independently verifies the login and click sequence or proves a new post-clear Twitch
event. `OWNER_LOGIN_AND_CLEAR_CLICK=NOT_INDEPENDENTLY_VERIFIED`; the clean view itself
is screenshot-evidenced and watermark persistence is database-verified. The earlier
Phase 4 overall result remains PARTIAL.

## Safety and remaining limits

The deployed build retains the existing Phase 4.5.5 peek/claim/ACK protocol. Historical
UNKNOWN and EXPIRED records remain terminal; this feature does not reset them or replay
an Action. AIG `Succeeded`/admission receipt, worker delivery, browser ACK, visible
Canvas and the owner's truthful external challenge outcome remain distinct evidence.

`PRODUCTION_DATA_DELETED=NO`, `REAL_ACTION_EXECUTED=NO`,
`REAL_TWITCH_MESSAGE_SENT_BY_AGENT=NO`, `SERVICE_RESTARTED_DURING_THIS_DOC_PASS=NO`.
The real post-clear Twitch suggestion/vote-to-Studio flow and Phase 4.5.5 native
background-tab behavior remain pending separate live acceptance.
