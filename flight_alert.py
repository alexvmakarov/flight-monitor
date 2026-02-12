import os
import requests
import time
import random
from datetime import datetime, timedelta

# ------------------- НАСТРОЙКИ -------------------
ORIGIN = "AMS"
ADULTS = 2
CHILDREN = 1
MAX_DURATION_HOURS = 8
BAG_ESTIMATE_ONEWAY = 35

AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAX_PRICE = float(os.getenv("MAX_PRICE_EUR"))

# ------------------- AIRLINE MAP -------------------
AIRLINE_MAP = {
    "KL": "KLM",
    "LH": "Lufthansa",
    "AF": "Air France",
    "RY": "Ryanair",
    "FR": "Ryanair",
    "W6": "Wizz Air",
    "EZ": "EasyJet",
    "BA": "British Airways",
    "SN": "Brussels Airlines",
    "IB": "Iberia",
    # можно добавлять по необходимости
}

# ------------------- СЕЗОНЫ -------------------
WINTER = ["AYT", "DLM", "HRG", "SSH"]
SUMMER = [
    "ALC","AGP","PMI","IBZ","TFS",
    "FAO","LIS",
    "NAP","BRI","PSR","CAG",
    "HER","RHO","CFU","SKG",
    "AYT","DLM",
    "HRG","SSH"
]
AUTUMN = ["ALC","AGP","PMI","IBZ","FAO","HER","RHO","AYT","DLM","HRG","SSH"]

IATA_MAP = {
    "ALC": "Alicante, Spain",
    "AGP": "Malaga, Spain",
    "PMI": "Palma de Mallorca, Spain",
    "IBZ": "Ibiza, Spain",
    "TFS": "Tenerife South, Spain",
    "FAO": "Faro, Portugal",
    "LIS": "Lisbon, Portugal",
    "NAP": "Naples, Italy",
    "BRI": "Bari, Italy",
    "PSR": "Olbia (Sardinia), Italy",
    "CAG": "Cagliari (Sardinia), Italy",
    "HER": "Heraklion, Greece",
    "RHO": "Rhodes, Greece",
    "CFU": "Corfu, Greece",
    "SKG": "Thessaloniki, Greece",
    "AYT": "Antalya, Turkey",
    "DLM": "Dalaman, Turkey",
    "HRG": "Hurghada, Egypt",
    "SSH": "Sharm El Sheikh, Egypt"
}

# ------------------- Периоды каникул -------------------
PERIODS = [
    ("2026-02-21", "2026-03-01"),
    ("2026-07-04", "2026-08-16"),
    ("2026-10-18", "2026-10-26")
]

# ------------------- TELEGRAM -------------------
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })

# ------------------- Amadeus API -------------------
def get_access_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_API_KEY,
        "client_secret": AMADEUS_API_SECRET
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def duration_under_limit(duration_iso):
    if duration_iso.startswith("PT"):
        h = 0
        m = 0
        if "H" in duration_iso:
            h = int(duration_iso.split("H")[0].replace("PT",""))
        if "M" in duration_iso:
            m = int(duration_iso.split("H")[1].replace("M","")) if "H" in duration_iso else int(duration_iso.replace("PT","").replace("M",""))
        return h + m/60 <= MAX_DURATION_HOURS
    return True

def google_flights_link(origin, dest, depart, ret):
    return f"https://www.google.com/flights?hl=en#flt={origin}.{dest}.{depart}*{dest}.{origin}.{ret}"

def destinations_for_month(month):
    if month in (7,8):
        return SUMMER
    if month == 2:
        return WINTER
    if month == 10:
        return AUTUMN
    return SUMMER

def generate_date_pairs(start, end):
    start = datetime.fromisoformat(start)
    end = datetime.fromisoformat(end)
    pairs = []
    d = start

    # меньше пар для длинных летних каникул
    max_pairs = 6 if start.month in (7,8) else 12

    while d <= end and len(pairs) < max_pairs:
        for stay in range(5, 12):
            ret = d + timedelta(days=stay)
            if ret <= end:
                pairs.append((d.strftime("%Y-%m-%d"), ret.strftime("%Y-%m-%d")))
                if len(pairs) >= max_pairs:
                    break
        d += timedelta(days=3)
    return pairs

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
        "max": 5
    }
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

# ------------------- MAIN -------------------
def main():
    token = get_access_token()
    now = datetime.now()
    found = []

    for start, end in PERIODS:
        start_date = datetime.fromisoformat(start)
        if (start_date - now).days > 200:
            continue

        month = int(start.split("-")[1])
        destinations = destinations_for_month(month)
        date_pairs = generate_date_pairs(start, end)

        for dest in destinations:
            for depart, ret in date_pairs:
                # задержка 2–5 секунд
                time.sleep(random.randint(2,5))

                try:
                    data = search_flights(token, ORIGIN, dest, depart, ret)
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        print(f"Too many requests, sleeping 10 секунд...")
                        time.sleep(10)
                        data = search_flights(token, ORIGIN, dest, depart, ret)
                    else:
                        print(f"Error {dest} {depart}-{ret}: {e}")
                        continue

                offers = data.get("data", [])
                for offer in offers:
                    total_price = float(offer["price"]["total"])
                    # добавляем багаж
                    total_price += BAG_ESTIMATE_ONEWAY*2*(ADULTS+CHILDREN)

                    if total_price > MAX_PRICE:
                        continue

                    itineraries = offer.get("itineraries", [])
                    if not itineraries:
                        continue

                    outbound = itineraries[0].get("segments", [])[0]
                    duration = itineraries[0].get("duration", "PT0H")
                    if not duration_under_limit(duration):
                        continue

                    airline_code = outbound.get("carrierCode", "??")
                    airline = AIRLINE_MAP.get(airline_code, airline_code)
                    city_country = IATA_MAP.get(dest, dest)
                    link = google_flights_link(ORIGIN, dest, depart, ret)

                    found.append({
                        "city": city_country,
                        "iata": dest,
                        "depart": depart,
                        "return": ret,
                        "price": total_price,
                        "airline": airline,
                        "dep_time": outbound.get("departure", {}).get("at", "N/A"),
                        "link": link
                    })

    if found:
        found.sort(key=lambda x: x["price"])
        msg = "✈️ <b>Найдены варианты</b>\n\n"
        for f in found:
            msg += f"{f['city']} ({f['iata']})\n"
            msg += f"{ORIGIN} → {f['iata']}\n"
            msg += f"{f['depart']} – {f['return']}\n"
            msg += f"{f['airline']} {f['dep_time']}\n"
            msg += f"{f['price']} €\n"
            msg += f"Google Flights: {f['link']}\n\n"

        send_telegram(msg)

if __name__ == "__main__":
    main()
