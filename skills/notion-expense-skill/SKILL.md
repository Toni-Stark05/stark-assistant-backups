---
name: notion-expense
description: "Fast expense logger for Igor's Notion Transactions DB. Turns natural-language expense commands into structured entries via scripts/notion_add_expense.py."
---

# Notion Expense Logger

Use this skill whenever Igor says что-то вроде “запиши расход…”, “добавь в Продукты 25 рублей”, “список трат”, etc., и хочется не засорять основной контекст.

## Когда использовать
- Добавление/фиксация расходов в существующую Notion таблицу `Transactions`.
- Пользователь обычно диктует: описание/контрагента (“поход в Euroopt”), сумму + валюту (“25 рублей”, “20 USD”), категорию (“категория Продукты”, “Кафе и рестораны”), счёт (“наличными”, “с виртуальной карты тг”).
- Если одно из полей не прозвучало, уточни перед записью.

## Процедура
1. **Распарсить** команду вручную / вопросами:
   - `amount` (float), `currency` (BYN|USD|USDT, по умолчанию BYN).
   - `category` (строка из Notion multi-select; можно создавать новую опцию).
   - `direction` (Expense / Income / Transfer) — если пользователь говорит “доход”/“прибавилось” → ставь Income.
   - `description` / `counterparty` (кратко: Euroopt, OpenAI, Notion и т.д.).
   - `account` — основной счёт. Для Expense/Income это счёт, где отражаем движение (расход/доход). Для Transfer это **источник** (“откуда списываем”).
   - `transfer_account` — используется для переводов и показывает приёмник (“куда зачисляем”).
   - `method` (Card/Cash/Transfer/Online — следует из счёта; дефолт Cash).
   - `date` (если не сказано — сегодня в Минске).
2. **Подтверди** вслух: сумму, валюту, категории, счёт(+source), дату и описание. Если всё верно — переходи к записи.
3. **Записать** через CLI скрипт:
   ```bash
   python scripts/notion_add_expense.py \
     --amount <float> \
     --currency <BYN|USD|USDT> \
     --category "<категория>" \
     --direction <Expense|Income|Transfer> \
     --description "<описание/контрагент>" \
     --account "<счёт>" \
     [--transfer-account "<счёт-источник>"] \
     --method <Cash|Card|Transfer|Online> \
     [--date YYYY-MM-DD] [--notes "доп. комментарий"]
   ```
4. Скрипт вернёт JSON `{ "url": "..." }`. Сообщи пользователю, что расход записан, и дай ссылку.

## Примечания
- Секреты (Notion токен) уже лежат в `secrets/notion_token.txt`.
- Категории и счета создаются/берутся динамически — Notion разрешает новые опции.
- Если пользователь попросил “список трат” — лучше перейти на обычный режим (просмотреть таблицу в Notion или выгрузить за период). Этот скилл отвечает именно за быстрый `add`.
- Для повторяющихся формулировок можно предложить шаблоны (например “кафе = Кафе и рестораны + Наличные”).
