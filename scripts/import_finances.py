#!/usr/bin/env python3
"""Import CSV transactions into Notion Accounts & Transactions databases."""
import csv
import datetime
from collections import OrderedDict

import requests
from dateutil import parser

TOKEN_PATH = "secrets/notion_token.txt"
ACCOUNTS_DB_ID = "31792ff0-2f2e-811a-8c25-c933535b17a2"
TRANSACTIONS_DB_ID = "31792ff0-2f2e-8144-a789-e55b77b7c26b"
NOTION_VERSION = "2022-06-28"

CSV_PATH = "./media/inbound/file_7---f536d445-b0cd-43c5-a789-61c00a4c5440.csv"

def parse_number(val: str) -> float:
    if val is None:
        return 0.0
    val = val.strip().replace(",", ".")
    if not val:
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0

def clean_text(val: str) -> str:
    if val is None:
        return ""
    return val.strip().replace("\"\"", "\"")

def sanitize_category(name: str) -> str:
    if not name:
        return "Без категории"
    return name.replace(",", " / ").strip()

def guess_account_type(name: str) -> str:
    lower = name.lower()
    if "налич" in lower:
        return "Cash"
    if "карта" in lower or "card" in lower:
        return "Card"
    if "банк" in lower:
        return "Checking"
    if any(token in lower for token in ("usdt", "xaut", "a98")):
        return "Crypto"
    if "монет" in lower:
        return "Wallet"
    if "телефон" in lower or "долг" in lower:
        return "Other"
    return "Other"

def guess_method(name: str, direction: str) -> str:
    lower = name.lower()
    if direction == "Transfer":
        return "Transfer"
    if "налич" in lower:
        return "Cash"
    if "карта" in lower:
        return "Card"
    if "банк" in lower:
        return "Transfer"
    if any(token in lower for token in ("usdt", "xaut")):
        return "Online"
    return "Other"

def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def load_rows(path: str):
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            if any(row.values()):
                rows.append(row)
    return rows

def collect_accounts(rows):
    info = OrderedDict()
    for row in rows:
        for prefix in ("outcome", "income"):
            acc = clean_text(row.get(f"{prefix}AccountName", ""))
            cur = clean_text(row.get(f"{prefix}CurrencyShortTitle", ""))
            if not acc:
                continue
            slot = info.setdefault(acc, {"currency": None})
            if cur and not slot.get("currency"):
                slot["currency"] = cur
    return info

def fetch_account_map(headers_dict):
    account_map = {}
    start_cursor = None
    while True:
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{ACCOUNTS_DB_ID}/query",
            headers=headers_dict,
            json=payload,
            timeout=60,
        )
        data = resp.json()
        for page in data.get("results", []):
            title = page["properties"]["Name"]["title"]
            if title:
                name = title[0]["plain_text"]
                account_map[name] = page["id"]
        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")
    return account_map

def ensure_accounts(headers_dict, candidates, existing):
    for name, info in candidates.items():
        if not name or name in existing:
            continue
        payload = {
            "parent": {"database_id": ACCOUNTS_DB_ID},
            "properties": {
                "Name": {"title": [{"type": "text", "text": {"content": name}}]},
                "Institution": {"rich_text": [{"type": "text", "text": {"content": name}}]},
                "Type": {"select": {"name": guess_account_type(name)}},
                "Currency": {"select": {"name": info.get("currency") or "BYN"}},
                "Status": {"select": {"name": "Active"}},
                "Balance": {"number": 0},
                "Notes": {"rich_text": [{"type": "text", "text": {"content": "Импортировано автоматически"}}]},
            },
        }
        resp = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers_dict,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        existing[name] = resp.json().get("id")


def build_transactions(rows):
    parsed = []
    for row in rows:
        date_str = clean_text(row.get("date", ""))
        dt = None
        if date_str:
            try:
                dt = parser.parse(date_str)
            except Exception:
                dt = None
        parsed.append((dt or datetime.datetime.min, date_str, row))
    parsed.sort(key=lambda x: x[0])
    return parsed

def create_transactions(headers_dict, account_map, parsed_rows):
    for _, date_str, row in parsed_rows:
        outcome = parse_number(row.get("outcome"))
        income = parse_number(row.get("income"))
        outcome_acc = clean_text(row.get("outcomeAccountName", ""))
        income_acc = clean_text(row.get("incomeAccountName", ""))
        outcome_cur = clean_text(row.get("outcomeCurrencyShortTitle", "")) or None
        income_cur = clean_text(row.get("incomeCurrencyShortTitle", "")) or None
        category = sanitize_category(clean_text(row.get("categoryName", "")))
        payee = clean_text(row.get("payee", ""))
        comment = clean_text(row.get("comment", ""))
        created = clean_text(row.get("createdDate", ""))
        changed = clean_text(row.get("changedDate", ""))

        direction = "Expense"
        amount = outcome if outcome > 0 else income
        currency = outcome_cur if outcome > 0 else income_cur
        primary_account = outcome_acc if outcome > 0 else income_acc
        transfer_account = None

        if outcome > 0 and income > 0:
            direction = "Transfer"
            amount = outcome or income
            currency = outcome_cur or income_cur
            primary_account = outcome_acc or income_acc
            if outcome_acc and income_acc and outcome_acc != income_acc:
                transfer_account = income_acc
        elif income > 0 and outcome == 0:
            direction = "Income"
            primary_account = income_acc
            currency = income_cur
        else:
            direction = "Expense"
            primary_account = outcome_acc
            currency = outcome_cur

        if not primary_account or primary_account not in account_map:
            continue

        title_parts = [part for part in (category, payee) if part]
        if not title_parts:
            title_parts.append(primary_account)
        title = " — ".join(title_parts)[:200]

        notes = []
        if comment:
            notes.append(comment)
        if direction == "Transfer" and income_acc:
            notes.append(f"→ {income_acc} ({income or 0} {income_cur or ''})")
        if created or changed:
            notes.append(f"Создано: {created}, обновлено: {changed}")
        notes_text = "\n".join([n for n in notes if n.strip()])

        properties = {
            "Name": {"title": [{"type": "text", "text": {"content": title}}]},
            "Amount": {"number": round(amount, 2)},
            "Direction": {"select": {"name": direction}},
            "Category": {"multi_select": [{"name": category}]},
            "Account": {"relation": [{"id": account_map[primary_account]}]},
            "Currency": {"select": {"name": currency or "BYN"}},
            "Status": {"select": {"name": "Cleared"}},
            "Method": {"select": {"name": guess_method(primary_account, direction)}},
        }
        if date_str:
            properties["Date"] = {"date": {"start": date_str}}
        if transfer_account and transfer_account in account_map:
            properties["Transfer Account"] = {"relation": [{"id": account_map[transfer_account]}]}
        if payee:
            properties["Counterparty"] = {"rich_text": [{"type": "text", "text": {"content": payee}}]}
        if notes_text:
            properties["Notes"] = {"rich_text": [{"type": "text", "text": {"content": notes_text}}]}

        resp = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers_dict,
            json={"parent": {"database_id": TRANSACTIONS_DB_ID}, "properties": properties},
            timeout=60,
        )
        resp.raise_for_status()

def main():
    token = open(TOKEN_PATH).read().strip()
    headers_dict = notion_headers(token)
    rows = load_rows(CSV_PATH)
    account_candidates = collect_accounts(rows)
    account_map = fetch_account_map(headers_dict)
    ensure_accounts(headers_dict, account_candidates, account_map)
    account_map = fetch_account_map(headers_dict)
    parsed_rows = build_transactions(rows)
    create_transactions(headers_dict, account_map, parsed_rows)

if __name__ == "__main__":
    main()
