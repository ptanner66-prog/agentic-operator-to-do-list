#!/usr/bin/env python3
"""Install the Omarchy plugin and explicitly connect or disconnect local agents."""
import argparse
import contextlib
import contextvars
import copy
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib

sys.dont_write_bytecode = True
from agent_policy import policy

SOURCE = Path(__file__).resolve().parent
ID = json.loads((SOURCE / 'manifest.json').read_text())['id']
USER_DIR = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(USER_DIR / '.config')))
CODEX_DIR = Path(os.environ.get('CODEX_HOME', str(USER_DIR / '.codex')))
HERMES_DIR = Path(os.environ.get('HERMES_HOME', str(USER_DIR / '.hermes')))
DEST = CONFIG / 'omarchy/plugins' / ID
POLICY_DIR = CONFIG / 'omarchy/operator-todos'
PYTHON = '/usr/bin/python3' if Path('/usr/bin/python3').exists() else sys.executable
MARKER_START = '<!-- operator-todos:start -->'
MARKER_END = '<!-- operator-todos:end -->'
SOURCES = ('codex', 'claude', 'hermes')
STAGED_WRITES = contextvars.ContextVar('operator_todos_setup_writes', default=None)
SETUP_MESSAGE = ('Instructions are installed for future sessions. Reconnect MCP tools or restart the app after active work. '
                 'Codex session hooks also require the app’s normal hook review before they run. '
                 'Claude Code hooks refresh the policy each turn; regular Claude Chat gets it through MCP. '
                 'Idle Claude and Hermes conversations need to resume or read the saved reply.')


def backup(path):
    if path.exists():
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        shutil.copy2(path, path.with_name(path.name + '.operator-todos-backup-' + stamp))


def write(path, text):
    staged = STAGED_WRITES.get()
    if staged is not None:
        staged[path] = text
        return
    if path.exists() and path.read_text() == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.operator-todos-', delete=False) as tmp:
        tmp.write(text)
        temp_path = Path(tmp.name)
    try:
        temp_path.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o600)
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


@contextlib.contextmanager
def setup_transaction():
    """Validate every setup edit before writing, and roll back a failed commit."""
    staged = {}
    token = STAGED_WRITES.set(staged)
    try:
        yield
    finally:
        STAGED_WRITES.reset(token)
    originals = {p: (p.read_bytes(), p.stat().st_mode & 0o777) if p.exists() else None for p in staged}
    changed = []
    try:
        for path, text in staged.items():
            write(path, text)
            changed.append(path)
    except Exception:
        for path in reversed(changed):
            old = originals[path]
            if old is None:
                path.unlink(missing_ok=True)
            else:
                with tempfile.NamedTemporaryFile('wb', dir=path.parent, prefix='.operator-todos-rollback-', delete=False) as tmp:
                    tmp.write(old[0])
                    restored = Path(tmp.name)
                try:
                    restored.chmod(old[1])
                    restored.replace(path)
                finally:
                    restored.unlink(missing_ok=True)
        raise


def json_file(path):
    data = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError(f'Expected a JSON object in {path}')
    return data


def write_json(path, data):
    write(path, json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def strip_instruction(text):
    pattern = re.escape(MARKER_START) + r'[\s\S]*?' + re.escape(MARKER_END)
    return re.sub(pattern, '', text).rstrip()


def instructions(path, remove=False):
    if remove and not path.exists():
        return
    old = strip_instruction(path.read_text() if path.exists() else '')
    addition = '' if remove else (f'{MARKER_START}\n' + policy(DEST, PYTHON)
        + f'\nShared policy maintained by Agentic Operator To Do List: {POLICY_DIR / "AGENTS.md"}.\n{MARKER_END}\n')
    result = old + ('\n\n' if old and addition else '\n' if old else '') + addition
    write(path, result)


def owns_server(entry):
    return isinstance(entry, dict) and any(Path(str(arg)).name == 'operator_todos.py' and
        Path(str(arg)).parent.name in (ID, 'local.operator-todos') for arg in entry.get('args', []))


def set_server(data, key, source, remove=False, code=False):
    servers = data.setdefault('mcpServers', {})
    old = servers.get(key)
    if old and not owns_server(old):
        raise ValueError(f'An unrelated MCP server named {key} already exists; no overwrite performed')
    if remove:
        servers.pop(key, None)
    else:
        entry = dict(old or {})
        entry.update(command=PYTHON, args=[str(DEST / 'operator_todos.py'), 'mcp', '--source', source])
        if code:
            entry['type'] = 'stdio'
        servers[key] = entry


def hook_command(source):
    return shlex.join([PYTHON, str(DEST / 'agent_policy.py'), '--source', source])


def owns_hook(hook):
    try:
        return any(Path(a).name == 'agent_policy.py' and Path(a).parent.name in (ID, 'local.operator-todos')
                   for a in shlex.split(hook.get('command', '')))
    except ValueError:
        return False


def configure_hooks(data, source, remove=False):
    hooks = data.setdefault('hooks', {})
    for event in ('SessionStart', 'UserPromptSubmit'):
        groups = []
        for group in hooks.get(event, []):
            kept = [h for h in group.get('hooks', []) if not owns_hook(h)]
            if kept:
                groups.append({**group, 'hooks': kept})
        if not remove:
            groups.append({'hooks': [{'type': 'command', 'command': hook_command(source), 'timeout': 5}]})
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)


def codex_instruction_path():
    override = CODEX_DIR / 'AGENTS.override.md'
    return override if override.exists() and override.read_text().strip() else CODEX_DIR / 'AGENTS.md'


def strip_codex_server(text):
    # Parse header paths with tomllib to support quoted keys and indentation.
    # The semantic guard below rejects unusual syntax if a boundary was ambiguous.
    headers = list(re.finditer(r'(?m)^[ \t]*\[[^\n]+', text))
    for index in range(len(headers) - 1, -1, -1):
        header = headers[index]
        try:
            data = tomllib.loads(header.group() + '\n__operator_todos_header_probe__ = true\n')
            keys = []
            while isinstance(data, dict) and len(data) == 1:
                key, data = next(iter(data.items()))
                keys.append(key)
            owned = keys[:2] == ['mcp_servers', 'operator_todos']
        except tomllib.TOMLDecodeError:
            owned = False
        if owned:
            end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
            text = text[:header.start()] + text[end:]
    return re.sub(r'(?m)^# Operator To-dos integration\n', '', text).rstrip()


def unrelated_codex_settings(data):
    data = copy.deepcopy(data)
    servers = data.get('mcp_servers')
    if isinstance(servers, dict):
        servers.pop('operator_todos', None)
        if not servers:
            data.pop('mcp_servers')
    return data


def connect_codex(remove=False):
    path = CODEX_DIR / 'config.toml'
    old = path.read_text() if path.exists() else ''
    data = tomllib.loads(old)
    entry = data.get('mcp_servers', {}).get('operator_todos')
    if entry and not owns_server(entry):
        raise ValueError('An unrelated MCP server named operator_todos already exists')
    # Preserve all unrelated tables and comments. Server subtables belong to this server.
    result = strip_codex_server(old)
    if not remove:
        result += ('\n\n# Operator To-dos integration\n[mcp_servers.operator_todos]\n'
            f'command = {json.dumps(PYTHON)}\n'
            f'args = {json.dumps([str(DEST / "operator_todos.py"), "mcp", "--source", "codex"])}\n'
            'tool_timeout_sec = 65\n')
    result = result.rstrip() + '\n'
    parsed = tomllib.loads(result)
    if unrelated_codex_settings(data) != unrelated_codex_settings(parsed):
        raise ValueError('Cannot safely update this TOML layout; original Codex settings were retained')
    hook_path = CODEX_DIR / 'hooks.json'
    hooks = json_file(hook_path)
    configure_hooks(hooks, 'codex', remove)
    write(path, result)
    write_json(hook_path, hooks)
    instructions(codex_instruction_path(), remove)
    # Clean our previous inactive block when a real global override takes precedence.
    for candidate in (CODEX_DIR / 'AGENTS.md', CODEX_DIR / 'AGENTS.override.md'):
        if candidate != codex_instruction_path() and candidate.exists():
            if MARKER_START in candidate.read_text():
                instructions(candidate, True)


def connect_claude(remove=False):
    desktop_path = CONFIG / 'Claude/claude_desktop_config.json'
    code_path = USER_DIR / '.claude.json'
    settings_path = USER_DIR / '.claude/settings.json'
    desktop, code, settings = json_file(desktop_path), json_file(code_path), json_file(settings_path)
    # Validate collisions in both surfaces before writing either one.
    set_server(desktop, 'operator-todos', 'claude', remove)
    set_server(code, 'operator-todos', 'claude', remove, code=True)
    configure_hooks(settings, 'claude', remove)
    write_json(desktop_path, desktop)
    write_json(code_path, code)
    write_json(settings_path, settings)
    instructions(USER_DIR / '.claude/CLAUDE.md', remove)


def hermes_profiles():
    return [HERMES_DIR] + sorted(p.parent for p in (HERMES_DIR / 'profiles').glob('*/config.yaml'))


def connect_hermes(remove=False):
    # Hermes already depends on PyYAML. Only this optional adapter requires it.
    import yaml
    prepared = []
    for home in hermes_profiles():
        path = home / 'config.yaml'
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text()) or {}
        servers = data.setdefault('mcp_servers', {})
        old = servers.get('operator-todos')
        if old and not owns_server(old):
            raise ValueError(f'An unrelated operator-todos server exists in Hermes profile {home.name}')
        if remove:
            servers.pop('operator-todos', None)
        else:
            servers['operator-todos'] = {'command': PYTHON,
                'args': [str(DEST / 'operator_todos.py'), 'mcp', '--source', 'hermes']}
        prepared.append((home, path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True)))
    if not prepared and not remove:
        raise ValueError('No local Hermes configuration found. Configure Hermes first, then connect it here.')
    for home, path, text in prepared:
        write(path, text)
        instructions(home / 'SOUL.md', remove)


def connect(source, remove=False):
    if source not in SOURCES:
        raise ValueError('Choose codex, claude, or hermes')
    POLICY_DIR.mkdir(parents=True, exist_ok=True)
    with (POLICY_DIR / '.setup.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with setup_transaction():
            if not remove:
                write(POLICY_DIR / 'AGENTS.md', policy(DEST, PYTHON))
            {'codex': connect_codex, 'claude': connect_claude, 'hermes': connect_hermes}[source](remove)


def has_policy(path):
    return path.exists() and MARKER_START in path.read_text()


def status(store):
    seen = store.connections()
    live = {a['source']: a['clients'] for a in store.live_agents()}
    agents = []
    for source, name in [('codex', 'Codex'), ('claude', 'Claude'), ('hermes', 'Hermes')]:
        try:
            if source == 'codex':
                path = CODEX_DIR / 'config.toml'
                config = tomllib.loads(path.read_text()) if path.exists() else {}
                configured = owns_server(config.get('mcp_servers', {}).get('operator_todos')) and has_policy(codex_instruction_path())
            elif source == 'claude':
                configured = (owns_server(json_file(CONFIG / 'Claude/claude_desktop_config.json').get('mcpServers', {}).get('operator-todos'))
                    and owns_server(json_file(USER_DIR / '.claude.json').get('mcpServers', {}).get('operator-todos'))
                    and has_policy(USER_DIR / '.claude/CLAUDE.md'))
            else:
                profiles = [p for p in hermes_profiles() if (p / 'config.yaml').exists()]
                configured = False
                if profiles:
                    import yaml
                    configured = all(has_policy(p / 'SOUL.md') and owns_server(
                        (yaml.safe_load((p / 'config.yaml').read_text()) or {}).get('mcp_servers', {}).get('operator-todos')) for p in profiles)
            detail = 'Standing instructions and connection configured.' if configured else 'Connect to install standing instructions and agent tools.'
            receipts = [r for r in seen if r['source'] == source]
            if receipts:
                latest = max(receipts, key=lambda r: r['seen'])
                when = datetime.datetime.fromtimestamp(latest['seen']).strftime('%b %d %H:%M')
                detail += f' Last {"tool connection" if latest["mode"] == "mcp" else "policy hook"} seen {when}.'
            elif configured:
                detail += ' No app connection seen yet; reconnect its tools.'
            if source == 'codex':
                if not any(r['mode'] == 'policy' for r in receipts):
                    detail += ' Session hooks need Codex hook review; global instructions are already installed.' if configured else ''
            elif source == 'claude':
                detail += ' Idle Chat replies stay saved until you reopen the chat.'
            elif source == 'hermes':
                detail += ' Local profiles only; remote bots require their own connection.'
        except Exception as exc:
            configured, detail = False, f'Setup needs attention: {exc}'
        agents.append(dict(source=source, name=name, configured=configured,
                           connected=source in live, clients=live.get(source, 0), detail=detail))
    return {'agents': agents}


def migrate_legacy():
    """Retire the development ID while retaining placement, data, and integrations."""
    legacy_id = 'local.operator-todos'
    legacy = CONFIG / 'omarchy/plugins' / legacy_id
    if ID == legacy_id or not (legacy / 'manifest.json').exists():
        return
    manifest = json_file(legacy / 'manifest.json')
    if manifest.get('id') != legacy_id or manifest.get('name') != 'Operator To-dos':
        raise ValueError('An unrelated plugin occupies the development ID')
    from operator_todos import Store
    configured = [a['source'] for a in status(Store())['agents'] if a['configured']]
    for source in configured:
        connect(source)
    config_path = CONFIG / 'omarchy/shell.json'
    def replace(value):
        if isinstance(value, dict):
            return {ID if k == legacy_id else k: replace(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v) for v in value]
        return ID if value == legacy_id else value
    if config_path.exists():
        write_json(config_path, replace(json_file(config_path)))
    saved = POLICY_DIR / ('legacy-plugin-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(saved))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--connect', nargs='*', choices=SOURCES, default=[])
    p.add_argument('--disconnect', nargs='*', choices=SOURCES, default=[])
    p.add_argument('--no-enable', action='store_true')
    p.add_argument('--status', action='store_true')
    args = p.parse_args()
    if args.status:
        from operator_todos import Store
        print(json.dumps(status(Store()), indent=2))
        return
    if args.disconnect:
        for app in args.disconnect:
            connect(app, remove=True)
        print('Disconnected: ' + ', '.join(args.disconnect) + '. Saved to-dos are retained.')
        return
    subprocess.run(['omarchy', 'plugin', 'validate', str(SOURCE)], check=True)
    if DEST.exists() and DEST.resolve() != SOURCE:
        current = json.loads((DEST / 'manifest.json').read_text())
        if current.get('id') != ID:
            raise ValueError('Destination contains another plugin')
    if DEST.resolve() != SOURCE:
        shutil.copytree(SOURCE, DEST, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('__pycache__', '.git', 'tests', '*.sqlite*'))
    migrate_legacy()
    for app in args.connect:
        connect(app)
    if not args.no_enable:
        backup(CONFIG / 'omarchy/shell.json')
        subprocess.run(['omarchy', 'bar', 'put', ID, '--section', 'right', '--index', '0'], check=True,
            env={**os.environ, 'OMARCHY_SHELL_IPC_TIMEOUT': '10s'})
    print('Installed ' + str(DEST))
    if args.connect:
        print(SETUP_MESSAGE)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
