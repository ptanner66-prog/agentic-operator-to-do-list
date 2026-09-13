# Marketplace listing draft

**Name:** Agentic Operator To Do List

**Repository:** https://github.com/ptanner66-prog/agentic-operator-to-do-list

**Category:** Productivity

**Suggested tags:** AI agents, MCP, to-do, operator inbox

**License:** MIT

**Status:** Beta 0.2.2

## Description

Your agents' decision inbox, in the Omarchy bar. Collect important decisions
from Codex, Claude, and Hermes with enough context to answer quickly: what needs
deciding, the agent's recommendation, and the consequences. Approve, reject,
choose an option, or reply without hunting through conversations. Keep your own
short-term and long-term to-dos alongside agent requests.

A red dot on the closed bar icon means something needs you. Green dots in Agents
show live MCP connections. Requests are stored locally in SQLite, duplicate
requests are suppressed, and agents acknowledge exact response IDs.

**Beta limits:** a waiting MCP client can receive your reply directly. Idle Codex
resumption passed a real delivery/acknowledgement test on desktop build
26.901.51231 with 0.2.1, but uses an internal, version-sensitive interface. It
requires a discoverable conversation owner. Idle Claude Chat and Hermes
conversations must resume to read saved replies. Standing instructions guide agents
but cannot guarantee compliance in every conversation; the operator boundary is
policy plus each app's own permission prompts. Disconnect apps from the Agents view
before removing the plugin. An independent review on 2026-09-13 found five beta
blockers, fixed in 0.2.2 with regression tests.

## Evidence

- `preview.png`: native UI with demo data.
- `docs/demo.mp4` and `docs/demo.gif`: 30-second recording using a scripted MCP
  client and automated UI actions; not proof of idle desktop resumption.
- `REVIEW.md`: the independent review, the 0.2.2 fixes, tested versions,
  42 Python tests, 30 native checks, clean-checkout isolated installation, and
  remaining integration limits.
- `docs/live-codex-verification.json`: real idle-task resumption and exact-response
  acknowledgement on the recorded Codex build.

This is a draft for the Omarchy submission form. It has not been submitted.
