# Release review · 0.2.2

## Merge-review follow-up

The review of PR #1 at `0a1ce6b` reproduced two remaining functional defects:
omitted session IDs bypassed MCP read/wait routing checks, and answers saved for
over 15 minutes were marked stale immediately after their first delivery.
All three conversation-bound MCP tools now require a matching session ID. A
dedicated delivery timestamp starts the acknowledgement window after each
hand-over or send, including retries; moving a task does not restart that timer.
The session IDs are caller-supplied routing checks, not an authentication boundary.

Generic MCP test clients now discard an ambient `CODEX_THREAD_ID`, while explicit
binding tests can still supply one. Disconnect coverage works with and without
optional PyYAML. The expanded suite has 46 tests. On the hosted Python 3.12.14
review environment, 44 passed, including all 15 blocker regressions. The two
unchanged child-process presence tests failed: a separate process probe confirmed
that this environment retained a readable procfs identity after the child exited
and was reaped. These failures are reported rather than skipped or weakened.
The earlier Omarchy-host results below are author-recorded evidence. Native UI,
fresh-install, and live desktop checks were not repeated in this environment.

## Independent review and 0.2.2 fixes

An independent adversarial review of commit `986b76b` (0.2.1) on 2026-09-13
re-ran the 31 Python tests, the 22 native checks, and the clean-install check,
all passing, and then found five beta blockers by targeted reproduction. 0.2.2
fixes each one, with regression tests in `tests/test_blockers.py`:

1. **Uninstall lock-out.** `omarchy plugin remove` never runs plugin code, so the
   `UserPromptSubmit` hook pointed at a missing script; Python exits 2 and Claude
   Code blocks and erases every prompt (reproduced with `claude -p`). Hooks now run
   `~/.config/omarchy/operator-todos/session-hook.py`, outside the plugin folder,
   which exits 0 silently when the plugin is absent. Agents gained per-app
   **Disconnect** and **Disconnect all apps**; disconnecting no longer creates files
   for apps that were never configured.
2. **Stranded answers.** `operator_wait` ignored `notifications/cancelled` and
   marked delivery `received` before the result was written; the Codex dispatcher
   only pushes `saved` replies. A cancelled wait now ends without a result and
   clears its lease, receipt is recorded only after the result is written, and
   an operator can **Retry delivery**. Unacknowledged hand-overs older than
   15 minutes raise attention, and the failure reason is shown in the row.
3. **Caller-controlled routing.** Any process could post `--source codex` with
   another thread's ID, and a title with newlines could forge a `Response:` line
   in the delivered turn. Titles, options, and IDs are now single-line without
   control characters, the delivered turn states the operator's response first
   and quotes the agent's title last, the row shows the target conversation, and
   the Codex CLI refuses a `session_id` that differs from `CODEX_THREAD_ID`.
4. **Wrong-session acknowledgement.** Any session of the same source could
   acknowledge another session's answer. `operator_get`, `operator_wait`, and
   `operator_ack` now take the caller's `session_id`; a mismatch is refused and
   all three require it when the request names a conversation.
5. **Silent key reuse.** A changed decision posted under an old key returned the
   old approval with no signal. While open, a changed repost returns the stored
   request with `mismatch: true`; once reviewed, it is refused.

The native smoke test grew from 22 to 30 checks: it now posts an agent request
into its isolated database, approves it, lets the Codex adapter fail closed
against an empty `CODEX_HOME`, and checks the kept reason, the attention dot,
and **Retry delivery**.

Also from the review, without a code change: the operator boundary is policy
plus each app's own permission prompts, not the absence of an approval tool; the
0.2.1 live Codex test used the earlier message text, so the desktop IPC path
should be re-run before any stable claim; Claude Chat and Hermes have not been
exercised live on the recorded host. The remaining review items are optional
follow-ups.

## 0.2.1 review

Reviewed 2026-09-13 against the Omarchy
[development](https://plugins.omarchy.org/develop.html) and
[publishing](https://plugins.omarchy.org/publish.html) guides.

**Verdict: beta candidate with live Codex idle resumption verified.** The native
list, setup preservation, local MCP flow, and one real idle Codex delivery test
passed. The Codex result applies to desktop build `26.901.51231` with a discoverable
conversation owner; its private interface remains version-sensitive. Claude Chat
and Hermes require an active wait or a resumed conversation to consume an answer.

## Fixed during review

- **Connection status:** historical tool/hook receipts could not prove a live
  connection. New per-client sessions renew presence, check process identity,
  expire stale heartbeats, and clear on exit. Only Agents shows green.
- **Attention and labels:** the outside icon shows a red dot only while closed
  and attention is pending. Both term labels omit counts, including populated lists.
- **Codex configuration preservation:** an indented table could be swallowed by
  the former text replacement. Quoted/indented headers are now recognized, and
  parsed unrelated settings must match before any setup files are changed.
  Ambiguous layouts fail without edits.
- **Partial setup:** configuration edits are staged for validation; a failed
  commit restores earlier writes. Existing settings and file modes are retained,
  with backups kept beside changed files.
- **Desktop reply routing:** a missing/empty conversation owner now stops delivery
  before a start-turn request can be sent without a target. Initialization failures
  also close their socket. These paths were tested with mocks, not live messages.

## Completed verification

- 31 Python tests passed: concurrent requests, deduplication, approval scope,
  dismissal/deletion, fresh responses after restore, response delivery, stdio MCP,
  process presence, setup preservation/rollback, and desktop adapter safeguards.
- 22 checks passed using the real QML panel inside the existing Omarchy shell and
  an isolated database. These include Add/Enter, draft retention after a failed
  save, History restoration, count-free tabs, and closed/open attention behavior.
- Native plugin manifest validation passed. The nested panel uses the existing
  shell and forwards its lifecycle; no second Quickshell process is started.
- QML static analysis reports existing dynamic-property, unqualified-access,
  and installed signal-metadata warnings. It is not a warning-free lint result.
- A clean clone of public commit `f71ec15` installed successfully into isolated
  user/config/data directories. Empty Codex/Claude settings and a minimal Hermes
  fixture were connected; installed CLI persistence, MCP initialization, restore,
  disconnect, and database retention checks passed. See `docs/fresh-install.json`.
- The 30-second native UI demo completed an actual MCP post → wait → response →
  exact-response acknowledgement cycle against an isolated database. Its client
  and UI clicks are scripted. This establishes the MCP path, not live LLM or idle
  desktop resumption. Screenshot and recording contain only demo data.
- A separate real Codex task posted a request through the CLI fallback, completed
  its first turn, and was confirmed idle before approval. The native QML Approve
  button was activated programmatically against its isolated database. The normal
  watcher and desktop IPC adapter resumed the same task. It read the response and
  acknowledged the exact response ID in 7.7 seconds, then completed its second
  turn. No wait lease or separate task-message tool resumed it. The temporary task
  was archived after verification. See `docs/live-codex-verification.json`.

A separate reviewer reported 28/31 tests passing in a restricted environment.
All 31 passed again on this Omarchy host. The socket-cleanup unit test now mocks
its endpoint, removing an unnecessary bind permission dependency. The two child
process-presence failures were not reproduced here; those integration tests
depend on Linux procfs accurately exposing child identities and remain enabled.

Testing host: Omarchy 4.0.3-1 / Quattro, Quickshell 0.3.1-1, Qt 6.11.2-3,
Python 3.14.7-1. Installed desktop packages are Codex 26.901.51231-1,
Claude 1.49585.0-1, and Hermes 2026.8.31-3. Installed versions alone do not establish
successful reply delivery in those apps. The supported Python minimum is 3.11;
Hermes setup also needs PyYAML. A fresh operating-system install and other runtime
versions have not been verified in this review.

## Before claiming stable desktop integration

1. Complete equivalent real-app reply tests for Claude and Hermes. Their configured
   settings and scripted MCP checks do not establish every desktop mode's behavior.
2. Repeat the passed idle Codex test after desktop updates and cover additional
   conversation states. Build 26.901.51231 passed with an available owner; no
   public compatibility guarantee exists. Uncertain sends are not retried.
3. Reconnect MCP tools after this update to start the presence-aware server.
   Review Codex hooks through its native hook review. App-specific instruction
   files and hooks guide agents but cannot guarantee every model follows policy.

Source repository: [ptanner66-prog/agentic-operator-to-do-list](https://github.com/ptanner66-prog/agentic-operator-to-do-list).
No marketplace submission has been made. The permanent third-party ID is
`portertanner.operator-todos`; marketplace
publication is subject to maintainer review and does not imply first-party status.
