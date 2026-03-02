#!/usr/bin/env python3
"""Add an expense row into the Notion Transactions database."""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

NOTION_TOKEN = Path('secrets/notion_token.txt').read_text().strip()
HEADERS = {
    'Authorization': f'Bearer {NOTION_TOKEN}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}
TRANSACTIONS_DB = '31792ff0-2f2e-8144-a789-e55b77b7c26b'
ACCOUNTS_DB = '31792ff0-2f2e-811a-8c25-c933535b17a2'

def get_account_id(name: str) -> str:
    payload = {
        'query': name,
        'filter': {'value': 'page', 'property': 'object'}
    }
    resp = requests.post('https://api.notion.com/v1/search', headers=HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()
    for result in data.get('results', []):
        props = result.get('properties', {})
        title_parts = props.get('Name', {}).get('title', [])
        title = ''.join([part['plain_text'] for part in title_parts]) if title_parts else ''
        if title.strip() == name.strip():
            return result['id']
    raise SystemExit(f'Account "{name}" not found in Notion (search)')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--amount', type=float, required=True)
    parser.add_argument('--currency', default='BYN')
    parser.add_argument('--category', required=True)
    parser.add_argument('--description', required=True, help='Short name / counterparty / memo')
    parser.add_argument('--account', default='Наличные')
    parser.add_argument('--transfer-account', default=None, help='Source account for transfers (sets Transfer Account relation)')
    parser.add_argument('--direction', default='Expense', choices=['Expense', 'Income', 'Transfer'])
    parser.add_argument('--method', default='Cash')
    parser.add_argument('--date', default=None, help='ISO date YYYY-MM-DD (default: today Minsk time)')
    parser.add_argument('--notes', default='')
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now(timezone(timedelta(hours=3))).date().isoformat()

    page_payload = {
        'parent': {'database_id': TRANSACTIONS_DB},
        'properties': {
            'Name': {'title': [{'type': 'text', 'text': {'content': f"{args.category} — {args.description}"}}]},
            'Date': {'date': {'start': date_str}},
            'Amount': {'number': round(args.amount, 2)},
            'Direction': {'select': {'name': args.direction}},
            'Category': {'multi_select': [{'name': args.category}]},
            'Account': {'relation': [{'id': get_account_id(args.account)}]},
            'Currency': {'select': {'name': args.currency}},
            'Status': {'select': {'name': 'Cleared'}},
            'Method': {'select': {'name': args.method}},
            'Counterparty': {'rich_text': [{'type': 'text', 'text': {'content': args.description}}]}
        }
    }
    if args.transfer_account:
        page_payload['properties']['Transfer Account'] = {'relation': [{'id': get_account_id(args.transfer_account)}]}
    if args.notes:
        page_payload['properties']['Notes'] = {'rich_text': [{'type': 'text', 'text': {'content': args.notes}}]}

    resp = requests.post('https://api.notion.com/v1/pages', headers=HEADERS, json=page_payload)
    resp.raise_for_status()
    data = resp.json()
    output = {
        'id': data['id'],
        'url': data['url']
    }
    print(json.dumps(output))

if __name__ == '__main__':
    main()
