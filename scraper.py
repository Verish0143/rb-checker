
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import re
import time

URL = "https://www.lineage2.cz/vault/global/rb-checker"
HISTORY_FILE = "rb_history.json"

# Bez User-Agentu se requests hlásí jako "python-requests" a web ho může odmítat.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) "
        "Gecko/20100101 Firefox/140.0"
    )
}

# Pauzy mezi opakováními (s), když web vrátí 5xx nebo neodpoví.
RETRY_DELAYS = [10, 30, 60]


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def fetch():
    # Web občas vrací 503. Zkusíme to znovu, a když nevyjde ani poslední
    # pokus, vrátíme None - další běh za 20 minut to dožene.
    for attempt, delay in enumerate([0] + RETRY_DELAYS, start=1):
        if delay:
            time.sleep(delay)

        try:
            response = requests.get(URL, headers=HEADERS, timeout=30)
        except (requests.ConnectionError, requests.Timeout) as e:
            print(f"Pokus {attempt}: web neodpověděl ({e})")
            continue

        if response.status_code >= 500:
            print(f"Pokus {attempt}: HTTP {response.status_code}")
            continue

        # 4xx neopakujeme, to je chyba, kterou je potřeba vidět.
        response.raise_for_status()
        return response.text

    return None


def scrape():
    html = fetch()

    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")

    rows = soup.find_all("tr")
    current = {}

    for r in rows:
        cells = r.find_all("td")

        if len(cells) >= 3:
            link = cells[0].find(
                "a",
                href=re.compile(r"/vault/detail/npc/(\d+)")
            )

            if not link:
                continue

            match = re.search(
                r"/vault/detail/npc/(\d+)",
                link["href"]
            )

            if not match:
                continue

            npc_id = match.group(1)
            name = link.get_text(strip=True)
            level = cells[1].get_text(strip=True)
            alive = cells[2].get_text(strip=True)

            current[npc_id] = {
                "name": name,
                "level": level,
                "state": alive
            }

    return current


def main():
    history = load_history()
    current = scrape()

    if current is None:
        # ::warning:: ukáže výpadek v GitHub Actions jako žlutou poznámku,
        # běh ale skončí úspěšně a historie zůstane beze změny.
        print("::warning::Web lineage2.cz je nedostupný, běh přeskočen.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Spočítáme výskyty jednotlivých jmen v aktuálním seznamu.
    name_counts = {}

    for info in current.values():
        name = info["name"]
        name_counts[name] = name_counts.get(name, 0) + 1

    # Migrace staré historie:
    # Jednoznačná jména převedeme na NPC ID a zachováme timestampy.
    # Duplicitní jména nelze bezpečně rozdělit, proto začnou nově.

    for npc_id, info in current.items():
        name = info["name"]

        if npc_id not in history and name in history:
            if name_counts[name] == 1:
                history[npc_id] = history.pop(name)

                # Doplníme jméno do starších záznamů.
                for record in history[npc_id]:
                    record["name"] = name

    # Odstraníme staré textové klíče.
    # Všechny aktuální záznamy už budou identifikovány NPC ID.
    history = {
        key: value
        for key, value in history.items()
        if str(key).isdigit()
    }

    # Zpracování aktuálního stavu bossů.
    for npc_id, info in current.items():
        name = info["name"]
        level = info["level"]
        state = info["state"]

        if npc_id not in history:
            history[npc_id] = []

        # Doplníme jméno i do případných existujících záznamů.
        for record in history[npc_id]:
            record["name"] = name

        # Nový záznam vytvoříme pouze při změně stavu.
        if (
            not history[npc_id]
            or history[npc_id][-1]["state"] != state
        ):
            history[npc_id].append({
                "name": name,
                "level": level,
                "state": state,
                "timestamp": timestamp
            })

    save_history(history)

    print("========== RB CHECKER ==========")
    print("Načteno bossů:", len(current))
    print("Uloženo NPC ID:", len(history))
    print("Dokončeno.")


if __name__ == "__main__":
    main()
