#!/usr/bin/env python3
"""Prepare a Gmail digest of new messages since last run."""
import argparse
import email
import imaplib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

CREDS_PATH = Path('secrets/gmail_credentials.env')
STATE_PATH = Path('memory/gmail_state.json')
TARGET = 'telegram:2139518623'
MAX_ITEMS = 10


def load_creds() -> Dict[str, str]:
    creds = {}
    for line in CREDS_PATH.read_text().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            creds[k.strip()] = v.strip()
    return creds

def load_state() -> Dict[str, int]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {'last_uid': 0}

def save_state(state: Dict[str, int]):
    state['last_run'] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2))


def format_header(value: str) -> str:
    if not value:
        return ''
    decoded = []
    for text, charset in email.header.decode_header(value):
        if isinstance(text, bytes):
            decoded.append(text.decode(charset or 'utf-8', errors='replace'))
        else:
            decoded.append(text)
    return ''.join(decoded)


def fetch_new_uids(mail: imaplib.IMAP4_SSL, last_uid: int) -> List[int]:
    status, data = mail.uid('search', None, 'ALL')
    if status != 'OK' or not data or not data[0]:
        return []
    uids = [int(x) for x in data[0].split()]
    return [uid for uid in uids if uid > last_uid]


def fetch_headers(mail: imaplib.IMAP4_SSL, uids: List[int]) -> List[Tuple[int, str, str, str]]:
    items = []
    for uid in uids:
        status, data = mail.uid('fetch', str(uid), '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])')
        if status != 'OK' or not data or data[0] is None:
            continue
        msg = email.message_from_bytes(data[0][1])
        subj = format_header(msg['Subject']) or 'Без темы'
        frm = format_header(msg['From'])
        date = format_header(msg['Date'])
        items.append((uid, subj, frm, date))
    return items


def render_digest(items: List[Tuple[int, str, str, str]], total_new: int) -> str:
    if not items:
        return 'Gmail digest: новых писем нет.'
    lines = [f"Gmail digest: {len(items)} новых (из {total_new})."]
    for idx, (_, subj, frm, date) in enumerate(items, 1):
        lines.append(f"{idx}. {subj} — {frm} — {date}")
    if total_new > len(items):
        lines.append(f"…и ещё {total_new - len(items)} писем.")
    return '\n'.join(lines)


def send_message(text: str):
    subprocess.run([
        'openclaw', 'message', 'send',
        '--target', TARGET,
        '--message', text
    ], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--send', action='store_true', help='send to chat via openclaw message')
    args = parser.parse_args()

    creds = load_creds()
    state = load_state()
    mail = imaplib.IMAP4_SSL(creds['IMAP_HOST'])
    mail.login(creds['EMAIL'], creds['APP_PASSWORD'])
    mail.select('INBOX')

    new_uids = fetch_new_uids(mail, int(state.get('last_uid', 0)))
    total_new = len(new_uids)
    digest_text = ''
    if total_new:
        trimmed = new_uids[-MAX_ITEMS:]
        headers = fetch_headers(mail, trimmed)
        digest_text = render_digest(headers, total_new)
        state['last_uid'] = max(new_uids)
        save_state(state)
    else:
        digest_text = 'Gmail digest: новых писем нет.'
    mail.logout()

    if args.send:
        send_message(digest_text)
    else:
        print(digest_text)

if __name__ == '__main__':
    main()
