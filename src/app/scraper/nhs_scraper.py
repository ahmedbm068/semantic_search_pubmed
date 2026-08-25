import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.nhs.uk"
CONDITIONS_URL = f"{BASE_URL}/conditions/"
OUTPUT_PATH = Path(__file__).resolve().parents[3] / "data" / "scraped" / "nhs_conditions.jsonl"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 15


def get_conditions_links() -> list[str]:
    r = requests.get(CONDITIONS_URL, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links: set[str] = set()
    for a in soup.select('a[href^="/conditions/"]'):
        href = a.get("href")
        if not href:
            continue
        href = href.split("#")[0]
        if href in ("/conditions/",):
            continue
        if href.startswith("/"):
            href = BASE_URL + href
        links.add(href)
    links_list = sorted(links)
    print(f"Found {len(links_list)} condition links")
    return links_list


def scrape_condition(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    title_el = soup.select_one("h1")
    main = soup.select_one("main") or soup
    paragraphs: list[str] = []
    for p in main.select("p"):
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)
    body = "\n".join(paragraphs)
    return {
        "url": url,
        "title": title_el.get_text(strip=True) if title_el else "",
        "body": body,
        "source": "nhs_conditions",
    }


def scrape_all(max_items: int | None = None) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    links = get_conditions_links()
    if max_items:
        links = links[:max_items]
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for i, link in enumerate(links, start=1):
            try:
                data = scrape_condition(link)
                if data["body"]:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
                print(f"[{i}/{len(links)}] {data['title']}")
                time.sleep(1)
            except Exception as e:
                print(f"Error scraping {link}: {e}")


if __name__ == "__main__":
    scrape_all(max_items=50)
