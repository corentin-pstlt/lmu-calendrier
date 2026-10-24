import json
import csv
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.racecontrol.gg/events"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
}
OUT_DIR = Path("docs")
OUT_DIR.mkdir(exist_ok=True)


def get_soup():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def extract_embedded_json(soup):
    """
    RaceControl est une application web : les données sont souvent
    embarquées dans un script JSON (Next.js / framework similaire).
    On cherche les blocs JSON contenant des événements.
    """
    candidates = []

    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if "LMU" not in text and "Le Mans Ultimate" not in text:
            continue

        # Recherche simple de tableaux JSON d'événements
        for match in re.finditer(r"\[(?:[^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\]", text):
            snippet = match.group(0)
            if any(key in snippet for key in ('"title"', '"name"', '"startDate"', '"event"')):
                try:
                    data = json.loads(snippet)
                except json.JSONDecodeError:
                    continue

                if isinstance(data, list):
                    candidates.extend(data)
                elif isinstance(data, dict):
                    candidates.append(data)

    return candidates


def extract_visible_events(soup):
    """
    Solution de secours : extraction du texte visible des cartes d'événements.
    """
    events = []
    seen = set()

    for card in soup.select("a[href*='/events/']"):
        title_el = card.find(string=re.compile(r"\S"))
        text = " | ".join(x.strip() for x in card.stripped_strings if x.strip())

        if not text or text in seen:
            continue
        seen.add(text)

        href = card.get("href", "")
        event_id = None
        m = re.search(r"/events/(\d+)", href)
        if m:
            event_id = int(m.group(1))

        events.append({
            "id": event_id,
            "title": title_el.strip() if title_el else None,
            "url": f"https://www.racecontrol.gg{href}" if href.startswith("/") else href,
            "raw_text": text,
            "source": "racecontrol.gg",
            "retrieved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        })

    return events


def save_json(events, filename="lmu_events.json"):
    path = OUT_DIR / filename
    path.write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def save_csv(events, filename="lmu_events.csv"):
    path = OUT_DIR / filename

    fields = [
        "id", "title", "url", "raw_text", "source", "retrieved_at"
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(events)

    return path


def main():
    soup = get_soup()

    events = extract_embedded_json(soup)

    if not events:
        print("Aucun JSON exploitable trouvé : extraction du HTML visible.")
        events = extract_visible_events(soup)

    if not events:
        raise SystemExit("Aucun événement récupéré. La structure du site a probablement changé.")

    json_path = save_json(events)
    csv_path = save_csv(events)

    print(f"{len(events)} événements récupérés.")
    print(f"JSON : {json_path}")
    print(f"CSV  : {csv_path}")


if __name__ == "__main__":
    main()
