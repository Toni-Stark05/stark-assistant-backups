#!/usr/bin/env python3
"""Refresh the Finance HQ page summary and chart."""
import json
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

NOTION_TOKEN = open('secrets/notion_token.txt').read().strip()
HEADERS = {
    'Authorization': f'Bearer {NOTION_TOKEN}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}
PAGE_ID = '31792ff0-2f2e-81dc-aa8f-d40b7c5e8e7d'
HEADING_ID = '31792ff0-2f2e-81a1-ac7f-c00e1d602fdc'
PARAGRAPH_ID = '31792ff0-2f2e-8166-b92d-f2e0a1912b06'
CALLOUT_ID = '31792ff0-2f2e-8179-8b75-f3c0000e51fe'
TRANSACTIONS_DB = '31792ff0-2f2e-8144-a789-e55b77b7c26b'
ACCOUNTS_DB = '31792ff0-2f2e-811a-8c25-c933535b17a2'

local_tz = timezone(timedelta(hours=3))
today_local = datetime.now(local_tz).date()
start_30 = (today_local - timedelta(days=30)).isoformat()
start_7 = (today_local - timedelta(days=6)).isoformat()


def query_transactions(limit=None, sorts=None, filter_payload=None):
    payload = {}
    if filter_payload:
        payload['filter'] = filter_payload
    if sorts:
        payload['sorts'] = sorts
    if limit:
        payload['page_size'] = limit
    results = []
    while True:
        resp = requests.post(
            f'https://api.notion.com/v1/databases/{TRANSACTIONS_DB}/query',
            headers=HEADERS,
            json=payload
        )
        data = resp.json()
        results.extend(data.get('results', []))
        if not data.get('has_more'):
            break
        payload['start_cursor'] = data['next_cursor']
    return results


def get_accounts_map():
    resp = requests.post(
        f'https://api.notion.com/v1/databases/{ACCOUNTS_DB}/query',
        headers=HEADERS,
        json={'page_size': 100}
    )
    data = resp.json()
    mapping = {}
    for page in data.get('results', []):
        name = ''.join([t['plain_text'] for t in page['properties']['Name']['title']])
        mapping[page['id']] = name
    return mapping

recent = query_transactions(limit=5, sorts=[{'property': 'Date', 'direction': 'descending'}])
last30 = query_transactions(filter_payload={
    'and': [
        {'property': 'Date', 'date': {'on_or_after': start_30}},
        {'property': 'Direction', 'select': {'equals': 'Expense'}}
    ]
})
accounts = get_accounts_map()

last7_totals = defaultdict(float)
today_totals = defaultdict(float)
byn_by_day = defaultdict(float)

for page in last30:
    props = page['properties']
    date_field = props['Date']['date']
    if not date_field or not date_field['start']:
        continue
    d = date_field['start']
    amount = props['Amount']['number'] or 0.0
    currency = props['Currency']['select']['name'] if props['Currency']['select'] else 'BYN'
    if d >= start_7:
        last7_totals[currency] += amount
        if d == today_local.isoformat():
            today_totals[currency] += amount
        if currency == 'BYN':
            byn_by_day[d] += amount
    if d == today_local.isoformat():
        today_totals[currency] += amount


def fmt_money(value):
    return f"{value:,.2f}".replace(',', ' ')

summary_lines = ["Сводка за 7 дней:"]
for currency in sorted(last7_totals.keys()):
    summary_lines.append(f"• {currency}: {fmt_money(last7_totals[currency])}")
if not last7_totals:
    summary_lines.append('• нет расходов')

if today_totals:
    today_line = ', '.join([
        f"{currency} {fmt_money(value)}"
        for currency, value in today_totals.items()
    ])
else:
    today_line = 'нет'
summary_lines.append(f"Сегодня: {today_line}")
summary_lines.append('Последние операции:')

recent_lines = []
for idx, page in enumerate(recent, 1):
    props = page['properties']
    name = ''.join([t['plain_text'] for t in props['Name']['title']])
    date_field = props['Date']['date']
    date_str = date_field['start'] if date_field else today_local.isoformat()
    dt = datetime.fromisoformat(date_str)
    human_date = dt.strftime('%d.%m')
    amount = props['Amount']['number'] or 0.0
    currency = props['Currency']['select']['name'] if props['Currency']['select'] else 'BYN'
    relation = props['Account']['relation']
    account_name = accounts.get(relation[0]['id'], '') if relation else ''
    sign = '-' if props['Direction']['select'] and props['Direction']['select']['name'] == 'Expense' else ''
    recent_lines.append(
        f"{idx}. {human_date} — {name} — {sign}{fmt_money(amount)} {currency}"
        + (f" ({account_name})" if account_name else '')
    )
if not recent_lines:
    recent_lines.append('нет записей')
summary_lines.extend(recent_lines)
summary_text = '\n'.join(summary_lines)

paragraph_text = (
    "Автосводка: суммы за 7 дней, траты сегодня и последние операции. Ниже — базы Accounts/Transactions" )

requests.patch(
    f'https://api.notion.com/v1/blocks/{HEADING_ID}',
    headers=HEADERS,
    json={'heading_1': {'rich_text': [{'type': 'text', 'text': {'content': 'Finance HQ — дэшборд'}}]}}
)
requests.patch(
    f'https://api.notion.com/v1/blocks/{PARAGRAPH_ID}',
    headers=HEADERS,
    json={'paragraph': {'rich_text': [{'type': 'text', 'text': {'content': paragraph_text}}]}}
)
requests.patch(
    f'https://api.notion.com/v1/blocks/{CALLOUT_ID}',
    headers=HEADERS,
    json={'callout': {'rich_text': [{'type': 'text', 'text': {'content': summary_text}}], 'icon': {'type': 'emoji', 'emoji': '📊'}}}
)

children_resp = requests.get(f'https://api.notion.com/v1/blocks/{CALLOUT_ID}/children?page_size=50', headers=HEADERS)
for child in children_resp.json().get('results', []):
    requests.delete(f"https://api.notion.com/v1/blocks/{child['id']}", headers=HEADERS)

# Chart data (BYN)
dates = [today_local - timedelta(days=i) for i in reversed(range(7))]
labels = [d.strftime('%d.%m') for d in dates]
data = [round(byn_by_day.get(d.isoformat(), 0.0), 2) for d in dates]
config = {
    'type': 'bar',
    'data': {
        'labels': labels,
        'datasets': [{
            'label': 'BYN',
            'backgroundColor': '#f97316',
            'data': data
        }]
    },
    'options': {
        'plugins': {
            'legend': {'display': False},
            'title': {'display': True, 'text': 'Расходы BYN (7 дней)'}
        },
        'scales': {'y': {'beginAtZero': True}}
    }
}
chart_url = 'https://quickchart.io/chart?c=' + urllib.parse.quote(json.dumps(config))

requests.post(
    f'https://api.notion.com/v1/blocks/{CALLOUT_ID}/children',
    headers=HEADERS,
    json={'children': [{
        'object': 'block',
        'type': 'image',
        'image': {'type': 'external', 'external': {'url': chart_url}}
    }]}
)
