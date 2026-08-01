"""
Toys"R"Us Malaysia - Beyblade availability tracker.

Fetches the Beyblade category page(s), extracts each product's name, URL,
price and availability, compares against the last saved state, and sends
a Telegram message for any product that flipped from unavailable -> available.

Designed to run unattended on a schedule (see .github/workflows/check.yml).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CATEGORY_URL = "https://www.toysrus.com.my/beyblade/"
STATE_FILE = Path(__file__).parent / "state.json"
PAGE_SIZE = 48          # matches the site's default page size
MAX_PAGES = 10          # safety cap (88 products / 48 per page = 2 pages today)
REQUEST_DELAY = 1.5     # seconds between page requests, be polite

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-MY,en;q=0.9",
}

PRODUCT_URL_RE = re.compile(r"-\d{7,}\.html$")
PRICE_RE = re.compile(r"RM\s?[\d,]+\.\d{2}")


def fetch_page(start: int) -> str:
    """Fetch one page of the category listing."""
    resp = requests.get(
        CATEGORY_URL,
        params={"start": start, "sz": PAGE_SIZE},
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.text


def find_tile_container(link_tag):
    """
    Walk up the DOM from a product link until we find an ancestor whose
    text contains both a price and a name (i.e. the product tile).
    Works regardless of the theme's actual CSS class names.
    """
    node = link_tag
    for _ in range(6):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        if PRICE_RE.search(text):
            return node
    return link_tag.parent  # fallback


def parse_products(html: str) -> dict:
    """
    Returns {product_url: {"name": ..., "price": ..., "available": bool}}
    """
    soup = BeautifulSoup(html, "html.parser")
    products = {}

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not PRODUCT_URL_RE.search(href):
            continue
        url = href if href.startswith("http") else "https://www.toysrus.com.my" + href
        if url in products:
            continue

        tile = find_tile_container(link)
        tile_text = tile.get_text(" ", strip=True)

        # Name: prefer the link's own text, fall back to image alt text
        name = link.get_text(strip=True)
        if not name:
            img = link.find("img")
            if img and img.get("alt"):
                name = img["alt"].strip()
        if not name:
            continue  # can't identify this product, skip

        price_match = PRICE_RE.search(tile_text)
        price = price_match.group(0) if price_match else None

        # "unavailable" is the confirmed out-of-stock marker on this site.
        # Its absence near the tile is treated as in-stock.
        is_unavailable = bool(re.search(r"\bunavailable\b", tile_text, re.IGNORECASE))

        products[url] = {
            "name": name,
            "price": price,
            "available": not is_unavailable,
        }

    return products


def fetch_all_products() -> dict:
    all_products = {}
    for page in range(MAX_PAGES):
        start = page * PAGE_SIZE
        html = fetch_page(start)
        page_products = parse_products(html)

        new_count = sum(1 for u in page_products if u not in all_products)
        all_products.update(page_products)

        if new_count == 0:
            break  # no new products on this page, we've reached the end
        time.sleep(REQUEST_DELAY)

    return all_products


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured, skipping notification. Message was:")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=15,
    )
    if not resp.ok:
        print(f"Telegram send failed: {resp.status_code} {resp.text}", file=sys.stderr)


def main():
    print(f"Fetching {CATEGORY_URL} ...")
    current = fetch_all_products()
    print(f"Found {len(current)} products.")

    if not current:
        print("No products parsed — the site's markup may have changed. Exiting without touching state.")
        sys.exit(1)

    previous = load_state()
    newly_available = []

    for url, info in current.items():
        was_available = previous.get(url, {}).get("available")
        if info["available"] and was_available is False:
            newly_available.append((url, info))

    if newly_available:
        for url, info in newly_available:
            msg = (
                f"🔴🔵 <b>Beyblade back in stock!</b>\n\n"
                f"<b>{info['name']}</b>\n"
                f"{info['price'] or ''}\n"
                f"{url}"
            )
            send_telegram(msg)
            print(f"NOTIFIED: {info['name']}")
    else:
        print("No new availability.")

    save_state(current)


if __name__ == "__main__":
    main()
