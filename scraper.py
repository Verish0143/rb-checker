import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os

URL = "https://www.lineage2.cz/vault/global/rb-checker"
HISTORY_FILE = "rb_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def scrape():
    html = requests.get(URL).text
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.find_all("tr")
    current = {}
    for r in rows:
        cells = r.find_all("td")
        if len(cells) >= 3:
            name = cells[0].get_text(strip=True)
            level = cells[1].get_text(strip=True)
            alive = cells[2].get_text(strip=True)

            key = name  # boss name jako hlavní klíč
            current[key] = {
                "level": level,
                "state": alive
            }

    return current

def main():
    history = load_history()
    current = scrape()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for boss, info in current.items():
        level = info["level"]
        state = info["state"]

        if boss not in history:
            history[boss] = []

        # pokud se stav změnil, uložíme nový záznam
        if not history[boss] or history[boss][-1]["state"] != state:
            history[boss].append({
                "level": level,
                "state": state,
                "timestamp": timestamp
            })

    save_history(history)

if __name__ == "__main__":
    main()
