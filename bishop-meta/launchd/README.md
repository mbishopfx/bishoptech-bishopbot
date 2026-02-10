# launchd (Local Worker)

This makes the BishopBot local worker run automatically on macOS login.

## Install

- Run: `./bishop-meta/launchd/install.sh`

## Uninstall

- Run: `./bishop-meta/launchd/uninstall.sh`

## Logs

- `/Users/matthewbishop/BishopBot/logs/launchd-local-worker.out.log`
- `/Users/matthewbishop/BishopBot/logs/launchd-local-worker.err.log`

## macOS Permissions

The worker uses AppleScript/System Events to control Terminal.
If sessions fail to type or return, ensure macOS Privacy permissions are granted:

- System Settings -> Privacy & Security
- Accessibility: allow the controlling process (often `Terminal`, `osascript`, and/or your Python runtime)
- Automation: allow controlling Terminal and System Events if prompted
