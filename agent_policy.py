"""Shared agent policy and non-blocking session-context hooks."""
import json
from pathlib import Path
import shlex
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent


def policy(plugin=ROOT, python="python3"):
    command = shlex.join([python, str(plugin / "operator_todos.py")])
    return (ROOT / "agent-policy.md").read_text() + f"""
CLI fallback (JSON through stdin, no shell interpolation):
`{command} post - --source SOURCE`
SOURCE is codex, claude, or hermes. Use the same fields as operator_post. To read
a response: `{command} get -` with {{"id":"REQUEST_ID"}} on stdin.
To acknowledge: `{command} ack -` with id and response_id on stdin.
For Codex, omitted session_id defaults to the actual CODEX_THREAD_ID environment
variable. A missing session ID remains missing; do not guess one.
"""


def hook(source, payload):
    event = payload.get("hook_event_name", "")
    if event not in ("SessionStart", "UserPromptSubmit"):
        return None
    from operator_todos import Store
    store = Store()
    store.record_connection(source, "policy", "session hook")
    context = policy()
    session = payload.get("session_id")
    if isinstance(session, str) and session and len(session) <= 200:
        context += "\nActual session ID supplied by the app: " + json.dumps(session) + ".\n"
        pending = [x["id"] for x in store.snapshot()["items"]
                   if x["source"] == source and x.get("session_id") == session
                   and x["status"] in ("open", "answered")]
        if pending:
            context += "Existing requests for this session; read these before reposting: " + json.dumps(pending) + ".\n"
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}


if __name__ == "__main__":
    # Hooks never block a turn, read the transcript, or manufacture requests.
    try:
        source = sys.argv[sys.argv.index("--source") + 1]
        result = hook(source, json.load(sys.stdin))
        if result:
            print(json.dumps(result))
    except Exception:
        pass
