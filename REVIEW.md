# Release review · 0.2.1

Reviewed 2026-09-13 against the Omarchy
[development](https://plugins.omarchy.org/develop.html) and
[publishing](https://plugins.omarchy.org/publish.html) guides.

**Verdict: beta candidate.** The native to-do list, setup preservation, and local
MCP response flow passed the automated checks below. Do not describe all idle
desktop conversations as automatically resumable. Codex's private IPC adapter
still needs a live end-to-end delivery and acknowledgement test in a deliberately
created test conversation. Claude Chat and Hermes require an active wait or a
resumed conversation to consume a saved answer.

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

Testing host: Omarchy 4.0.3 / Quattro, Qt 6.11.2, Python 3.14. The supported Python
minimum is 3.11. Hermes setup also needs PyYAML. A fresh-machine install and other
runtime versions have not been verified in this review.

## Before claiming stable desktop integration

1. In each supported app, create one harmless request with a real conversation
   link. Answer from the panel and confirm that exact response ID is acknowledged.
2. Test idle Codex resumption separately and record the desktop build. Current
   adapter assumptions came from build 26.901.51231; no public compatibility
   guarantee exists. An uncertain send stays visible and is not retried.
3. Reconnect MCP tools after this update to start the presence-aware server.
   Review Codex hooks through its native hook review. App-specific instruction
   files and hooks guide agents but cannot guarantee every model follows policy.

Source repository: [ptanner66-prog/agentic-operator-to-do-list](https://github.com/ptanner66-prog/agentic-operator-to-do-list).
No marketplace submission has been made. The permanent third-party ID is
`portertanner.operator-todos`; marketplace
publication is subject to maintainer review and does not imply first-party status.
