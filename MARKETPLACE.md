# Marketplace listing draft

**Name:** Agentic Operator To Do List

**Repository:** https://github.com/ptanner66-prog/agentic-operator-to-do-list

**Category:** Productivity

**Suggested tags:** AI agents, MCP, to-do, operator inbox

**License:** MIT

**Status:** Beta 0.2.1

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
resumption uses an internal, version-sensitive desktop interface and still needs
a live end-to-end verification. Idle Claude Chat and Hermes conversations must
resume to read saved replies. Standing instructions guide agents but cannot
guarantee compliance in every conversation.

## Evidence

- `preview.png`: native UI with demo data.
- `docs/demo.mp4` and `docs/demo.gif`: 30-second recording using a scripted MCP
  client and automated UI actions; not proof of idle desktop resumption.
- `REVIEW.md`: tested versions, 31 Python tests, 22 native checks, clean-checkout
  isolated installation, and remaining integration limits.

This is a draft for the Omarchy submission form. It has not been submitted.
