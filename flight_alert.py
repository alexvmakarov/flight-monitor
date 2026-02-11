import os
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import requests

ORIGIN = "AMS"
ADULTS = 2
CHILDREN = 1
MAX_PRICE = int(os.getenv("MAX_PRICE_EUR", "700"))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Даты
PERIODS = [
    ("2026-02-21", "2026-03-01"),
    ("2026-07-04", "2026-08-16"),
    ("2026-10-18", "2026-10-26"),
]

# Направления по сезону
WINTER = ["AYT","HRG","LCA"]
SUMMER = ["ALC","AGP","FAO","HER","RHO","AYT"]
AUTUMN = ["FAO","ALC","AGP","LCA","AYT"]

MAX_FLIGHT_HOURS = 5
BAG_ESTIMATE_ONEWAY = 35  # если багаж не включен

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })

def generate_date_pairs(start, end):
    start = datetime.fromisoformat(start)
    end = datetime.fromisoformat(end)
    pairs = []
    d = start
    while d <= end:
        for stay in range(5, 12):
            ret = d + timedelta(days=stay)
            if ret <= end:
                pairs.append((d.strftime("%Y-%m-%d"), ret.strftime("%Y-%m-%d")))
        d += timedelta(days=3)
    return pairs[:40]

def destinations_for_month(month):
    if month in (7,8):
        return SUMMER
    if month == 2:
        return WINTER
    if month == 10:
        return AUTUMN
    return SUMMER

async def search_kayak(origin, dest, depart, ret):
    url = f"https://www.kayak.com/flights/{origin}-{dest}/{depart}/{ret}?sort=price_a&fs=stops=0"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(10000)

        prices = await page.query_selector_all("span")
        cheapest = None

        for el in prices:
            text = await el.inner_text()
            if text and text.startswith("€"):
                try:
                    value = int(text.replace("€","").replace(",",""))
                    if not cheapest or value < cheapest:
                        cheapest = value
                except:
                    pass

        await browser.close()
        return cheapest

async def main():
    found = []

    for start, end in PERIODS:
        month = int(start.split("-")[1])
        destinations = destinations_for_month(month)
        date_pairs = generate_date_pairs(start, end)

        for dest in destinations:
            for depart, ret in date_pairs:
                price = await search_kayak(ORIGIN, dest, depart, ret)
                if not price:
                    continue

                # добавляем багаж если нужно (эвристика)
                total_estimated = price + BAG_ESTIMATE_ONEWAY*2*(ADULTS+CHILDREN)

                if total_estimated <= MAX_PRICE:
                    found.append(f"{dest} {depart}-{ret} €{total_estimated}")

    if found:
        msg = "✈️ <b>Найдены варианты до €{}</b>\n\n".format(MAX_PRICE)
        msg += "\n".join(found)
        send_telegram(msg)

asyncio.run(main())
