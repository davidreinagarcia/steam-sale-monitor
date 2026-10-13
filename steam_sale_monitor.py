#!/usr/bin/env python3
"""Telegram alert when a Steam game goes on sale.

Games are listed in steam_games.json next to this script. Telegram credentials
(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) come from the environment or a .env file
next to this script. Intended to run from cron every few hours.

    python3 steam_sale_monitor.py            # check and notify
    python3 steam_sale_monitor.py --dry-run  # check, print instead of sending
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV_FILE = BASE / ".env"
STATE_FILE = BASE / "state" / "steam_sale_monitor.json"
DEFAULT_GAMES_FILE = BASE / "steam_games.json"
COUNTRY = os.environ.get("STEAM_COUNTRY", "es")

API = "https://store.steampowered.com/api/appdetails"


def log(msg):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def load_env_file():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def send_telegram(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15)


def fetch_price(appid):
    query = urllib.parse.urlencode({"appids": appid, "cc": COUNTRY, "filters": "price_overview"})
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": "steam-sale-monitor"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)
    entry = payload.get(str(appid), {})
    if not entry.get("success"):
        return None
    data = entry.get("data")
    if not isinstance(data, dict):
        return None
    return data.get("price_overview")


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--games", type=Path, default=DEFAULT_GAMES_FILE)
    args = parser.parse_args()

    load_env_file()
    games = load_json(args.games, [])
    if not games:
        log(f"No games configured in {args.games}")
        return 0

    state = {} if args.dry_run else load_json(STATE_FILE, {})
    failures = 0

    for game in games:
        appid, name = game["appid"], game["name"]
        min_discount = max(int(game.get("min_discount", 1)), 1)
        try:
            price = fetch_price(appid)
        except Exception as exc:
            log(f"{name} ({appid}): request failed: {exc}")
            failures += 1
            continue
        if price is None:
            log(f"{name} ({appid}): no price data")
            continue

        discount = price.get("discount_percent", 0)
        final_cents = price["final"]
        if discount < min_discount:
            state.pop(str(appid), None)
            log(f"{name}: {price['final_formatted']}, no sale")
            continue

        last_cents = state.get(str(appid), {}).get("final")
        if last_cents is not None and final_cents >= last_cents:
            log(f"{name}: {discount}% off at {price['final_formatted']}, already notified")
            continue

        msg = (
            f"{name} esta de rebajas en Steam: -{discount}%\n"
            f"{price['final_formatted']} (antes {price['initial_formatted']})\n"
            f"https://store.steampowered.com/app/{appid}"
        )
        if args.dry_run:
            log(f"DRY RUN would send:\n{msg}")
        else:
            try:
                send_telegram(msg)
            except Exception as exc:
                log(f"{name}: Telegram failed: {exc}")
                failures += 1
                continue
            state[str(appid)] = {"final": final_cents, "notified_at": datetime.now().isoformat(timespec="seconds")}
            log(f"{name}: notified, -{discount}% at {price['final_formatted']}")

    if not args.dry_run:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
