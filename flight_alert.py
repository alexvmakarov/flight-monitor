import os
import requests
from datetime import datetime, timedelta

API_KEY = os.getenv("AMADEUS_API_KEY")
API_SECRET = os.getenv("AMADEUS_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAX_PRICE = int(os.getenv("MAX_PRICE_EUR", "700"))

ORIGIN = "AMS"
ADULTS = 2
CHILDREN = 1

PERIODS = [
    ("2026-02-21", "2026-03-01"),
    ("2026-07-04", "2026-08-16"),
    ("2026-10-18", "2026-10-26"),
]

WINTER = ["AYT","HRG","LCA"]
SUMMER = ["ALC","AGP","FAO","HER","RHO","AYT"]
AUTUMN = ["FAO","ALC","AGP","LCA","AYT"]

def get_access_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": API_SECRET
    }
    r = requests.post(url, data=data)
    return r.json()["access_token"]

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
        ret = d + timedelta(days=7)
        if ret <= end:
            pairs.append((d.strftime("%Y-%m-%d"), ret.strftime("%Y-%m-%d")))
        d += timedelta(days=7)
    return pairs[:8]

def destinations_for_month(month):
    if month in (7,8):
        return SUMMER
    if month == 2:
        return WINTER
    if month == 10:
        return AUTUMN
    return SUMMER

def search_flights(token, origin, dest, depart, ret):
    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": dest,
        "departureDate": depart,
        "returnDate": ret,
        "adults": ADULTS,
        "children": CHILDREN,
        "nonStop": "true",
        "currencyCode": "EUR",
        "max": 5
    }
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, params=params)
    data = r.json()

    if "data" not in data:
        return None

    cheapest = None
    for offer in data["data"]:
        price = float(offer["price"]["total"])
        if not cheapest or price < cheapest:
            cheapest = price

    return cheapest

def main():
    token = get_access_token()
    found = []

    for start, end in PERIODS:
        month = int(start.split("-")[1])
        destinations = destinations_for_month(month)
        date_pairs = generate_date_pairs(start, end)

        for dest in destinations:
            for depart, ret in date_pairs:
                price = search_flights(token, ORIGIN, dest, depart, ret)
                if not price:
                    continue

                if price <= MAX_PRICE:
                    found.append(f"{dest} {depart}-{ret} €{int(price)}")

    if found:
        msg = f"✈️ <b>Варианты до €{MAX_PRICE}</b>\n\n"
        msg += "\n".join(found)
        send_telegram(msg)

if __name__ == "__main__":
    main()
