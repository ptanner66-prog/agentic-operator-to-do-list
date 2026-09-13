import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install
from agent_policy import hook
from operator_todos import Store


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        values = {'USER_DIR': self.root, 'CONFIG': self.root / 'config',
                  'CODEX_DIR': self.root / 'codex', 'HERMES_DIR': self.root / 'hermes',
                  'DEST': self.root / 'config/omarchy/plugins' / install.ID,
                  'POLICY_DIR': self.root / 'config/omarchy/operator-todos'}
        for name, value in values.items():
            patch = mock.patch.object(install, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def put(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_codex_global_override_and_idempotent_hooks(self):
        self.put(install.CODEX_DIR / 'config.toml', '# Keep this\nmodel = "user-model"\n[mcp_servers.other]\ncommand="existing"\nargs=["one", "two"]\n')
        self.put(install.CODEX_DIR / 'AGENTS.override.md', 'User instructions.\n')
        self.put(install.CODEX_DIR / 'hooks.json', json.dumps({'hooks': {'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': 'existing-hook'}]}]}}))
        install.connect('codex')
        install.connect('codex')
        config = tomllib.loads((install.CODEX_DIR / 'config.toml').read_text())
        self.assertEqual(config['mcp_servers']['other']['args'], ['one', 'two'])
        self.assertEqual(config['model'], 'user-model')
        instructions = (install.CODEX_DIR / 'AGENTS.override.md').read_text()
        self.assertTrue(instructions.startswith('User instructions.'))
        self.assertEqual(instructions.count(install.MARKER_START), 1)
        hooks = json.loads((install.CODEX_DIR / 'hooks.json').read_text())['hooks']
        self.assertEqual(len(hooks['UserPromptSubmit']), 2)
        self.assertEqual(len(hooks['SessionStart']), 1)
        install.connect('codex', remove=True)
        config = tomllib.loads((install.CODEX_DIR / 'config.toml').read_text())
        self.assertNotIn('operator_todos', config['mcp_servers'])
        self.assertEqual((install.CODEX_DIR / 'AGENTS.override.md').read_text(), 'User instructions.\n')
        self.assertEqual(json.loads((install.CODEX_DIR / 'hooks.json').read_text())['hooks']['UserPromptSubmit'][0]['hooks'][0]['command'], 'existing-hook')

    def test_claude_preserves_settings_and_disconnects_only_this_plugin(self):
        settings = install.USER_DIR / '.claude/settings.json'
        self.put(settings, json.dumps({'theme': 'dark', 'hooks': {'Stop': [{'hooks': [{'command': 'keep-hook'}]}]}}))
        self.put(install.USER_DIR / '.claude/CLAUDE.md', 'Keep my workflow.\n')
        install.connect('claude')
        install.connect('claude')
        data = json.loads(settings.read_text())
        self.assertEqual(data['theme'], 'dark')
        self.assertEqual(len(data['hooks']['UserPromptSubmit']), 1)
        install.connect('claude', remove=True)
        data = json.loads(settings.read_text())
        self.assertEqual(list(data['hooks']), ['Stop'])
        self.assertEqual((install.USER_DIR / '.claude/CLAUDE.md').read_text(), 'Keep my workflow.\n')

    def test_unrelated_server_collision_does_not_overwrite_config(self):
        path = install.CONFIG / 'Claude/claude_desktop_config.json'
        original = json.dumps({'mcpServers': {'operator-todos': {'command': 'something-else'}}})
        self.put(path, original)
        with self.assertRaises(ValueError):
            install.connect('claude')
        self.assertEqual(path.read_text(), original)
        self.assertFalse((install.USER_DIR / '.claude.json').exists())

    def test_hermes_profiles_preserve_identity_and_other_servers(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('Optional Hermes adapter requires PyYAML')
        for home in [install.HERMES_DIR, install.HERMES_DIR / 'profiles/example']:
            self.put(home / 'config.yaml', 'model: keep-model\nmcp_servers:\n  existing:\n    command: keep-command\n')
            self.put(home / 'SOUL.md', 'Existing identity.\n')
        install.connect('hermes')
        install.connect('hermes')
        for home in install.hermes_profiles():
            config = yaml.safe_load((home / 'config.yaml').read_text())
            self.assertEqual(config['model'], 'keep-model')
            self.assertEqual(config['mcp_servers']['existing']['command'], 'keep-command')
            self.assertEqual((home / 'SOUL.md').read_text().count(install.MARKER_START), 1)
        install.connect('hermes', remove=True)
        self.assertEqual((install.HERMES_DIR / 'SOUL.md').read_text(), 'Existing identity.\n')

    def test_hook_supplies_policy_and_real_session_without_creating_tasks(self):
        with mock.patch.dict(os.environ, {'OPERATOR_TODOS_DATA': str(self.root / 'data')}):
            result = hook('codex', {'hook_event_name': 'UserPromptSubmit', 'session_id': 'real-test-session', 'prompt': 'secret prompt must not be stored'})
            context = result['hookSpecificOutput']['additionalContext']
            self.assertIn('real-test-session', context)
            self.assertIn('operator_post', context)
            self.assertNotIn('secret prompt', context)
            store = Store()
            self.assertEqual(store.snapshot()['items'], [])
            self.assertEqual(store.connections()[0]['mode'], 'policy')

    def test_configuration_is_not_reported_as_a_live_connection(self):
        install.connect('codex')
        status = install.status(Store(self.root / 'data'))
        codex = status['agents'][0]
        self.assertTrue(codex['configured'])
        self.assertFalse(codex['connected'])
        self.assertIn('No app connection seen', codex['detail'])

    def test_codex_quoted_and_indented_tables_preserve_other_settings(self):
        path = install.CODEX_DIR / 'config.toml'
        self.put(path, 'model="keep-model"\n  [mcp_servers."operator_todos"]\ncommand="python3"\nargs=[\n'
                 + json.dumps(str(install.DEST / 'operator_todos.py')) + ',\n"mcp"\n]\n'
                 + '  [mcp_servers.other]\ncommand="keep-command"\n')
        install.connect('codex')
        install.connect('codex')
        config = tomllib.loads(path.read_text())
        self.assertEqual(config['mcp_servers']['other']['command'], 'keep-command')
        self.assertEqual(config['model'], 'keep-model')
        install.connect('codex', remove=True)
        self.assertEqual(tomllib.loads(path.read_text())['mcp_servers'], {'other': {'command': 'keep-command'}})

    def test_ambiguous_multiline_toml_fails_without_changing_files(self):
        path = install.CODEX_DIR / 'config.toml'
        original = 'notes="""\n[mcp_servers.operator_todos]\nthis is text, not a table\n"""\nmodel="keep"\n'
        self.put(path, original)
        self.put(install.POLICY_DIR / 'AGENTS.md', 'Old shared policy')
        with self.assertRaises(ValueError):
            install.connect('codex')
        self.assertEqual(path.read_text(), original)
        self.assertEqual((install.POLICY_DIR / 'AGENTS.md').read_text(), 'Old shared policy')
        self.assertFalse((install.CODEX_DIR / 'hooks.json').exists())

    def test_failed_setup_commit_restores_previous_files(self):
        path = install.CODEX_DIR / 'config.toml'
        self.put(path, 'model="keep"\n')
        path.chmod(0o640)
        original_write = install.write
        def failing_write(target, value):
            if install.STAGED_WRITES.get() is None and target.name == 'hooks.json':
                raise OSError('Simulated write failure')
            return original_write(target, value)
        with mock.patch.object(install, 'write', side_effect=failing_write):
            with self.assertRaises(OSError):
                install.connect('codex')
        self.assertEqual(path.read_text(), 'model="keep"\n')
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertFalse((install.POLICY_DIR / 'AGENTS.md').exists())
        self.assertFalse((install.CODEX_DIR / 'AGENTS.md').exists())

    def test_development_id_migration_preserves_placement_and_other_widgets(self):
        old = install.CONFIG / 'omarchy/plugins/local.operator-todos'
        self.put(old / 'manifest.json', json.dumps({'id': 'local.operator-todos', 'name': 'Operator To-dos'}))
        self.put(old / 'keep.txt', 'Saved plugin source')
        path = install.CONFIG / 'omarchy/shell.json'
        self.put(path, json.dumps({'bar': {'layout': {'right': [{'id': 'other'}, {'id': 'local.operator-todos', 'settings': {'custom': 2}}]}}}))
        with mock.patch.dict(os.environ, {'OPERATOR_TODOS_DATA': str(self.root / 'data')}):
            install.migrate_legacy()
        layout = json.loads(path.read_text())['bar']['layout']['right']
        self.assertEqual(layout, [{'id': 'other'}, {'id': install.ID, 'settings': {'custom': 2}}])
        self.assertFalse(old.exists())
        self.assertEqual(next(install.POLICY_DIR.glob('legacy-plugin-*/keep.txt')).read_text(), 'Saved plugin source')


if __name__ == '__main__':
    unittest.main()
