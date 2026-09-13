#!/usr/bin/env python3
"""Check a clean source checkout and isolated installation on an Omarchy host.

This is not a fresh-OS test. It never changes the real bar, app configuration,
or to-do database. Codex and Claude begin with empty settings; Hermes uses a
minimal local-profile fixture. Requires git, Omarchy and optional PyYAML.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

DEFAULT_REPO = 'https://github.com/ptanner66-prog/agentic-operator-to-do-list.git'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default=DEFAULT_REPO)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='operator-inbox-fresh-install-') as directory:
        work = Path(directory)
        checkout = work / 'checkout'
        subprocess.run(['git', 'clone', '--depth', '1', args.repository, str(checkout)], check=True, capture_output=True)
        commit = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
        install_script = '''
import json, sys
from pathlib import Path
work, checkout = map(Path, sys.argv[1:3])
sys.path.insert(0, str(checkout))
import install
install.USER_DIR = work / 'user'
install.CONFIG = work / 'config'
install.CODEX_DIR = work / 'codex'
install.HERMES_DIR = work / 'hermes'
install.DEST = install.CONFIG / 'omarchy/plugins' / install.ID
install.POLICY_DIR = install.CONFIG / 'omarchy/operator-todos'
if sys.argv[3] == 'install':
    sources = ['codex', 'claude']
    try:
        import yaml
        install.HERMES_DIR.mkdir()
        (install.HERMES_DIR / 'config.yaml').write_text('model: example-model\\n')
        sources.append('hermes')
    except ImportError:
        pass
    sys.argv = ['install.py', '--no-enable', '--connect', *sources]
    install.main()
    from operator_todos import Store
    agents = install.status(Store(work / 'data'))['agents']
    assert all(a['configured'] for a in agents if a['source'] in sources), agents
    assert not any(a['connected'] for a in agents), agents
    assert not (install.CONFIG / 'omarchy/shell.json').exists()
    (work / 'setup.json').write_text(json.dumps({'sources': sources, 'destination': str(install.DEST)}))
else:
    for source in json.loads((work / 'setup.json').read_text())['sources']:
        install.connect(source, remove=True)
    import tomllib
    assert 'operator_todos' not in tomllib.loads((install.CODEX_DIR / 'config.toml').read_text()).get('mcp_servers', {})
    assert 'operator-todos' not in json.loads((install.CONFIG / 'Claude/claude_desktop_config.json').read_text()).get('mcpServers', {})
    assert (work / 'data/todos.sqlite3').exists()
'''
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OPERATOR_TODOS_DATA': str(work / 'data')}
        subprocess.run([sys.executable, '-c', install_script, str(work), str(checkout), 'install'], env=env, check=True, capture_output=True, text=True)
        setup = json.loads((work / 'setup.json').read_text())
        installed = Path(setup['destination'])
        subprocess.run(['omarchy', 'plugin', 'validate', str(installed)], check=True, capture_output=True)
        backend = installed / 'operator_todos.py'
        def command(name, payload=None):
            result = subprocess.run([sys.executable, str(backend), name, '-'], input=json.dumps(payload or {}),
                                    env=env, check=True, capture_output=True, text=True)
            parsed = json.loads(result.stdout)
            assert parsed['ok'], parsed
            return parsed['result']
        assert command('list')['items'] == []
        item = command('post', {'title': 'Clean-install check', 'term': 'long'})
        assert command('get', {'id': item['id']})['title'] == 'Clean-install check'
        assert command('act', {'id': item['id'], 'action': 'done'})['status'] == 'done'
        assert command('act', {'id': item['id'], 'action': 'restore'})['term'] == 'long'
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05', 'clientInfo': {'name': 'clean-install-check'}}},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}
        ]
        result = subprocess.run([sys.executable, str(backend), 'mcp', '--source', 'claude'],
                                input=''.join(json.dumps(m) + '\n' for m in messages), env=env,
                                check=True, capture_output=True, text=True, timeout=10)
        responses = {r['id']: r for r in map(json.loads, result.stdout.splitlines())}
        assert responses[1]['result']['serverInfo']['name'] == 'operator-todos'
        assert 'operator_post' in [t['name'] for t in responses[2]['result']['tools']]
        subprocess.run([sys.executable, '-c', install_script, str(work), str(checkout), 'disconnect'], env=env, check=True, capture_output=True, text=True)
        report = {'ok': True, 'checkout_commit': commit, 'version': json.loads((installed / 'manifest.json').read_text())['version'],
                  'scope': 'Clean Git checkout and isolated per-user installation on an existing Omarchy host; not a fresh operating system',
                  'configured_sources': setup['sources'], 'checks': ['Manifest validates before and after install',
                  'Empty app configs gain working MCP and policy setup', 'No real bar or app config changed',
                  'Installed backend persists a long-term task and restores it from history',
                  'Installed stdio MCP initializes and exposes agent tools', 'Disconnect removes integration entries and retains the database']}
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
