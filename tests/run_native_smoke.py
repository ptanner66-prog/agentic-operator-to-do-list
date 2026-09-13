#!/usr/bin/env python3
"""Test the real QML inside the existing Omarchy shell without opening a window.

Uses an isolated database and a temporary service plugin. No second Quickshell,
physical input, or changes to the user's to-dos. QML aliases expose the production
controls; only the popup's visual opening is disabled for lifecycle checks.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
os.environ['OMARCHY_SHELL_IPC_TIMEOUT'] = '10s'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
ID = 'local.operator-todos-smoke-' + uuid.uuid4().hex[:8]
DEST = CONFIG / 'omarchy/plugins' / ID
if DEST.exists():
    raise SystemExit('Temporary smoke plugin already exists; inspect it before retrying.')
with tempfile.TemporaryDirectory(prefix='operator-todos-smoke-') as temp:
    work = Path(temp)
    result = work / 'result.json'
    try:
        DEST.mkdir(parents=True)
        (DEST / 'manifest.json').write_text(json.dumps(dict(schemaVersion=1, id=ID,
            name='Temporary Operator To-dos test', version='0.0.0', kinds=['service'],
            entryPoints={'service': 'Smoke.qml'})))
        shutil.copy2(ROOT / 'tests/native/Smoke.qml', DEST / 'Smoke.qml')
        shutil.copy2(ROOT / 'ChoiceButton.qml', DEST / 'ChoiceButton.qml')
        qml = (ROOT / 'TodoPanel.qml').read_text().replace('  id: root\n',
            '  id: root\n  property alias testInput: addInput\n  property alias testAdd: addButton\n  property alias testTabs: termTabs\n', 1)
        qml = qml.replace('    open: root.opened\n', '    open: false\n', 1)
        (DEST / 'TodoPanel.qml').write_text(qml)
        (DEST / 'operator_todos.py').write_text('import os,sys,runpy,json\n'
            f'os.environ["OPERATOR_TODOS_DATA"] = {str(work / "data")!r}\n'
            # No Codex IPC endpoint here, so a delivery attempt fails closed without reaching the real app.
            f'os.environ["CODEX_HOME"] = {str(work / "no-codex")!r}\n'
            'if len(sys.argv)>2 and sys.argv[1]=="post" and json.loads(sys.argv[2]).get("title")=="SIMULATE_SAVE_FAILURE":\n'
            '    print(json.dumps({"ok":False,"error":"Simulated storage error"})); sys.exit(1)\n'
            f'sys.path.insert(0, {str(ROOT)!r})\n'
            f'runpy.run_path({str(ROOT / "operator_todos.py")!r},run_name="__main__")\n')
        (DEST / 'record.py').write_text(f'import pathlib,sys\npathlib.Path({str(result)!r}).write_text(sys.argv[1])\n')
        subprocess.run(['omarchy', 'plugin', 'validate', str(DEST)], check=True)
        subprocess.run(['omarchy-shell', 'shell', 'rescanPlugins'], check=True, capture_output=True)
        discovery_deadline = time.monotonic() + 10
        while time.monotonic() < discovery_deadline:
            listing = subprocess.run(['omarchy', 'plugin', 'list', '--json'], capture_output=True, text=True, check=True)
            if any(p['id'] == ID for p in json.loads(listing.stdout)):
                break
            time.sleep(.3)
        enabled = subprocess.run(['omarchy', 'plugin', 'enable', ID], capture_output=True, text=True)
        if enabled.returncode:
            raise RuntimeError(enabled.stdout + enabled.stderr)
        deadline = time.monotonic() + 30
        while not result.exists() and time.monotonic() < deadline:
            time.sleep(.2)
        if not result.exists():
            raise RuntimeError('No native test result; inspect the Omarchy shell log.')
        data = json.loads(result.read_text())
        print(json.dumps(data, indent=2))
        if not data['ok']:
            raise SystemExit(1)
    finally:
        subprocess.run(['omarchy', 'plugin', 'remove', ID, '--yes'], capture_output=True)
        if DEST.exists():
            shutil.rmtree(DEST)
        for saved in DEST.parent.glob('.' + ID + '.bak.*'):
            shutil.rmtree(saved)
