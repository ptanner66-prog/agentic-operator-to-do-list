# Agentic Operator To Do List

Use Agentic Operator To Do List in Omarchy whenever the user explicitly asks
you to add a to-do, or an IMPORTANT operator decision blocks authorized work:
direction, scope, cost, external commitments, or a consequential blocker.
Handle routine authorized work yourself. Do not fill the list with progress
reports, finished work, speculative suggestions, or routine permission prompts.

Before ending a turn needing the operator, call `operator_post`. Give the user
enough information to decide without reopening the conversation: what is ready,
what needs deciding, your recommendation, and what each answer will do. Include
concrete costs or affected resources when relevant. Use `approval`, `choice`, or
`reply` for a decision and `task` for a to-do. Set `important: true` or
`explicitly_requested: true`. Short term is for current work; long term is for
future work. Include the real project, `session_id`, and conversation link when
available. Never invent an identifier or link. Reuse `request_key` for the same
decision so retries cannot create duplicates or change an already reviewed action.

At the start of a later turn, check `operator_list` for your session and read any
responses with `operator_get`. Use `operator_wait` when you can wait for an answer
now. Acknowledge the exact `response_id` with `operator_ack`, passing your own
`session_id`, then continue within its scope. An unchecked, dismissed, deleted, or
rejected item is NOT approval. If `operator_post` returns `mismatch: true`, the
operator reviews the stored text, not yours; a changed decision needs a new key.
Never use the UI's `act` command or manufacture your own operator response.
Do not recreate dismissed/deleted requests unless the user asks or circumstances
materially change. Native application permission requirements still apply.

Only claim the request was saved after a successful tool result. If tools are
unavailable, use the local CLI described below. If saving fails, tell the user in
the conversation instead of silently losing their decision.
