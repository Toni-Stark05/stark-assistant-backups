#!/usr/bin/env python3
"""Quick Gmail inbox check via IMAP (lists newest unread messages)."""
import email
import imaplib
from pathlib import Path
from typing import List

CREDS_PATH = Path('secrets/gmail_credentials.env')
MAX_RESULTS = 10

def load_creds():
    creds = {}
    for line in CREDS_PATH.read_text().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            creds[k.strip()] = v.strip()
    return creds

def format_header(value: str) -> str:
    if not value:
        return ''
    headers = email.header.decode_header(value)
    decoded = []
    for text, charset in headers:
        if isinstance(text, bytes):
            decoded.append(text.decode(charset or 'utf-8', errors='replace'))
        else:
            decoded.append(text)
    return ''.join(decoded)

def fetch_unread(mail: imaplib.IMAP4_SSL) -> List[str]:
    status, data = mail.search(None, 'UNSEEN')
    if status != 'OK':
        return []
    ids = data[0].split()
    return ids[-MAX_RESULTS:]

def main():
    creds = load_creds()
    mail = imaplib.IMAP4_SSL(creds['IMAP_HOST'])
    mail.login(creds['EMAIL'], creds['APP_PASSWORD'])
    mail.select('INBOX')
    ids = fetch_unread(mail)
    if not ids:
        print('No unread messages.')
    else:
        print(f"Unread messages (showing up to {MAX_RESULTS}):")
        for msg_id in ids:
            status, data = mail.fetch(msg_id, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])')
            if status != 'OK':
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)
            subj = format_header(msg['Subject'])
            frm = format_header(msg['From'])
            date = format_header(msg['Date'])
            print(f"- {subj} | {frm} | {date}")
    mail.logout()

if __name__ == '__main__':
    main()
