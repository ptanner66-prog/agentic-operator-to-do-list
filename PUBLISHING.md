# Publishing Agentic Operator To Do List

Developed for Omarchy Quattro, following the
[development guide](https://plugins.omarchy.org/develop.html) and
[publishing guide](https://plugins.omarchy.org/publish.html).

The repository root contains the manifest, bar entry point, nested panel,
Python backend, setup tools, README, MIT license, tests, and optional preview.
The panel runs inside the existing shell. It does not start another Quickshell
instance or write into `/usr/share/omarchy`.

## Release validation

The 0.2.2 candidate is labeled **beta**. See `REVIEW.md` and `verification.json`
for the checks completed, the five review blockers fixed in 0.2.2, and the
integration tests still needed before a stable claim.

```sh
omarchy plugin validate .
python3 -m unittest discover -s tests -v
python3 tests/run_native_smoke.py
python3 tests/run_fresh_install.py
```

Also run `qmllint` with the installed shell import path, as described in the
development guide. Some installed Qt metadata describes Omarchy theme objects
and dynamically loaded panels only as `QObject`, producing missing-property
warnings. Investigate syntax, type, and layout errors; check the running shell
log as well as the static report.

Check the bar on each display; open, close, Escape, reopen, disable/re-enable,
and restart the shell. Check that Agents → Disconnect all apps removes every MCP
entry and hook, and that `omarchy plugin remove` afterwards leaves each app usable. Check a fresh installation with no agent configuration,
then use Agents → Connect. Confirm Add, Enter, delete, dismiss, restore, short/long
lists, long context scrolling, and the attention dot. The red dot belongs on the
closed bar icon; green connection dots belong only in Agents. Use temporary data.

Test each connected app separately: have it post one harmless decision with a
real conversation link, answer in the panel, and verify its exact acknowledgement.
Document app versions. The experimental Codex desktop IPC adapter requires its
own end-to-end test; backend tests and a successful MCP handshake do not establish
that idle desktop conversations can resume. Claude Chat and remote Hermes bots
have the limits documented in README.

The live Codex test passed on desktop build `26.901.51231`; its method and limits
are recorded in `docs/live-codex-verification.json`. Repeat it after desktop
updates, and keep the beta designation while compatibility coverage is limited.

## Submit

The public source repository is
[ptanner66-prog/agentic-operator-to-do-list](https://github.com/ptanner66-prog/agentic-operator-to-do-list).
The manifest uses the permanent publisher namespace `portertanner.operator-todos`;
the reserved `omarchy.*` namespace is not used. Submit the repository URL through
the publishing guide's issue form when ready. Maintainers review the listing.
A marketplace listing does not make the plugin a bundled first-party component.

Use `MARKETPLACE.md` as the listing draft. `preview.png` is the native UI preview;
the README includes a 30-second GIF/MP4 demo. The demo uses a scripted MCP client
and automated UI clicks. Keep that distinction and the idle-agent beta limits
visible when sharing it.

The distributable contains no personal to-dos, credentials, app configuration,
machine-specific paths, or database. Do not add any of those to the repository.

## Dependencies and changes on a user's machine

Runtime: Omarchy Quattro, its Qt/Quickshell installation, Python 3.11+.
Optional local Hermes setup: PyYAML. Tests use the same runtime.

Ordinary plugin installation places the bar widget. Connecting an app is an
explicit setup action in the panel or installer. It writes only the documented
per-user MCP, policy and hook settings plus the hook launcher and shared policy
under `~/.config/omarchy/operator-todos/`, with backups; it does not alter app
permission modes, trust hooks automatically, restart apps, or expose a network
service. Disconnect integrations, with **Disconnect all apps** in Agents or
`install.py --disconnect`, before removing the plugin. Saved to-dos are retained
after disable, disconnect, or removal.
