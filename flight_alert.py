import os
import requests
from datetime import datetime, timedelta
import isodate

API_KEY = os.getenv("AMADEUS_API_KEY")
API_SECRET = os.getenv("AMADEUS_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAX_PRICE = int(os.getenv("MAX_PRICE_EUR", "700"))

ORIGIN = "AMS"
ADULTS = 2
CHILDREN = 1
MAX_DURATION_HOURS = 6

PERIODS = [
    ("2026-02-21", "2026-03-01"),
    ("2026-07-04", "2026-08-16"),
    ("2026-10-18", "2026-10-26"),
]

WINTER = ["AYT","HRG","LCA"]
SUMMER = ["ALC","AGP","FAO","HER","RHO","AYT"]
AUTUMN = ["FAO","ALC","AGP","LCA","AYT"]

IATA_MAP = {
    "AYT": "Antalya, Turkey",
    "HRG": "Hurghada, Egypt",
    "LCA": "Larnaca, Cyprus",
    "ALC": "Alicante, Spain",
    "AGP": "Malaga, Spain",
    "FAO": "Faro, Portugal",
    "HER": "Heraklion, Greece",
    "RHO": "Rhodes, Greece"
}

AIRLINE_MAP = {
    "KL": "KLM",
    "VY": "Vueling",
    "HV": "Transavia",
    "U2": "easyJet",
    "FR": "Ryanair"
}

def get_access_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": API_SECRET
    }
    r = requests.post(url, data=data, timeout=20)
    return r.json()["access_token"]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }, timeout=20)

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
    return pairs[:6]

def destinations_for_month(month):
    if month in (7,8):
        return SUMMER
    if month == 2:
        return WINTER
    if month == 10:
        return AUTUMN
    return SUMMER

def duration_under_limit(duration_iso):
    duration = isodate.parse_duration(duration_iso)
    hours = duration.total_seconds() / 3600
    return hours <= MAX_DURATION_HOURS

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
    r = requests.get(url, headers=headers, params=params, timeout=20)
    data = r.json()

    if "data" not in data or not data["data"]:
        return None

    valid_offers = []

    for offer in data["data"]:
        outbound = offer["itineraries"][0]
        inbound = offer["itineraries"][1]

        if not duration_under_limit(outbound["duration"]):
            continue
        if not duration_under_limit(inbound["duration"]):
            continue

        price = float(offer["price"]["total"])
        segment = outbound["segments"][0]

        valid_offers.append({
            "price": price,
            "airline": segment["carrierCode"],
            "departure_time": segment["departure"]["at"]
        })

    if not valid_offers:
        return None

    return min(valid_offers, key=lambda x: x["price"])

def google_flights_link(origin, dest, depart, ret):
    return f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{depart}%20through%20{ret}"

def main():
    token = get_access_token()
    found = []

    for start, end in PERIODS:
        month = int(start.split("-")[1])
        destinations = destinations_for_month(month)
        date_pairs = generate_date_pairs(start, end)

        for dest in destinations:
            for depart, ret in date_pairs:
                result = search_flights(token, ORIGIN, dest, depart, ret)
                if not result:
                    continue

                if result["price"] <= MAX_PRICE:
                    city = IATA_MAP.get(dest, dest)
                    airline = AIRLINE_MAP.get(result["airline"], result["airline"])

                    dep_date = datetime.fromisoformat(depart).strftime("%d %b")
                    ret_date = datetime.fromisoformat(ret).strftime("%d %b")
                    dep_time = result["departure_time"][11:16]

                    link = google_flights_link(ORIGIN, dest, depart, ret)

                    found.append(
                        f"<b>{city} ({dest})</b>\n"
                        f"{ORIGIN} → {dest}\n"
                        f"{dep_date} – {ret_date}\n"
                        f"{airline} {dep_time}\n"
                        f"€{int(result['price'])}\n"
                        f"<a href='{link}'>Google Flights</a>\n"
                    )

    if found:
        msg = f"✈️ <b>Варианты до €{MAX_PRICE}</b>\n\n"
        msg += "\n".join(found[:5])
        send_telegram(msg)

if __name__ == "__main__":
    main()
