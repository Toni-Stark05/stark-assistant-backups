# Stark Assistant Backups

This repository stores configuration, memory, and scripts for Stark's OpenClaw workspace.

## Contents
- `AGENTS.md`, `SOUL.md`, `USER.md`, etc. — personality + user context
- `memory/` — daily notes / long-term context
- `scripts/` — automation scripts (importers, backups, etc.)
- `.gitignore` excludes `secrets/` (tokens), `.openclaw/` runtime state, and Python caches.

## Restore Procedure
1. Provision a new OpenClaw agent host.
2. Clone this repository into `/root/.openclaw/workspace` (or desired workspace path).
3. Recreate `secrets/` manually (Notion tokens, GitHub PATs, etc.) — they are never pushed to GitHub.
4. Install required tools (pip, faster-whisper, etc.) via the scripts/notes in this repo.
5. Restart the agent: `openclaw agent restart` (or re-run the model session) to pick up the restored files.

## Backup Automation
Backups run nightly at 00:00 Minsk time (UTC+3).
- Command commits any changes with message `backup: YYYY-MM-DD`.
- The commit is pushed to `github.com/Toni-Stark05/stark-assistant-backups`.
- Manual backup script: `python3 scripts/import_finances.py` handles Notion imports; add similar scripts for other data if needed.

## Manual Backup
Run: `./scripts/backup.sh` (planned) or `git commit -am "manual backup" && git push`.
