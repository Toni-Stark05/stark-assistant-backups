#!/usr/bin/env python3
"""Notify about CloudCode quota refresh every 5 hours starting 2026-03-02 18:00 Minsk."""
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

TARGET = 'telegram:2139518623'
ANCHOR_LOCAL = datetime(2026, 3, 3, 16, 0, tzinfo=timezone(timedelta(hours=3)))
ANCHOR_UTC = ANCHOR_LOCAL.astimezone(timezone.utc)
INTERVAL = 5 * 3600  # seconds
STATE_PATH = Path('memory/cloudcode_limit_state.json')
TOLERANCE = 90  # seconds

def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {'last_slot': -1}

def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2))

def send_message(text: str):
    subprocess.run([
        'openclaw', 'message', 'send',
        '--target', TARGET,
        '--message', text
    ], check=True)

def main():
    state = load_state()
    now = datetime.now(timezone.utc)
    elapsed = (now - ANCHOR_UTC).total_seconds()
    if elapsed < -TOLERANCE:
        return  # ещё не время старта
    slot = int(round(elapsed / INTERVAL))
    target_time = ANCHOR_UTC + timedelta(seconds=slot * INTERVAL)
    if abs((now - target_time).total_seconds()) > TOLERANCE:
        return  # не наш слот
    if slot <= state.get('last_slot', -1):
        return  # уже отправлено

    next_time = target_time + timedelta(seconds=INTERVAL)
    text = (
        f"CloudCode: лимиты обновились (слот {slot}).\n"
        f"Текущее обновление: {target_time.astimezone(timezone(timedelta(hours=3))).strftime('%d.%m %H:%M')} (Минск).\n"
        f"Следующее ожидается около {next_time.astimezone(timezone(timedelta(hours=3))).strftime('%d.%m %H:%M')}"
    )
    send_message(text)
    state['last_slot'] = slot
    state['last_sent'] = now.isoformat()
    save_state(state)

if __name__ == '__main__':
    main()
