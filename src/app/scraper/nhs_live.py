import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.nhs.uk"
SEARCH_URL = BASE_URL + "/search?query={query}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PubMedSemantic/1.0; +http://localhost)"
}
TIMEOUT = 10


def _normalize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _overlap_score(query: str, text: str) -> float:
    q_tokens = set(_normalize(query))
    t_tokens = set(_normalize(text))
    if not q_tokens or not t_tokens:
        return 0.0
    return len(q_tokens & t_tokens) / float(len(q_tokens))


def _extract_conditions_url(href: str) -> str | None:
    """
    NHS search results often use a /search/click?...&url=%2Fconditions%2F... link.
    This function normalises any href that ultimately points to a /conditions/... page.
    """
    if not href:
        return None

    # If it's a search click link, pull the real /conditions/... URL from the query string
    if "/search/click" in href and "url=" in href:
        try:
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            url_param = qs.get("url", [None])[0]
            if url_param:
                # IMPORTANT: decode %2Fconditions%2Fcancer%2F -> /conditions/cancer/
                href = unquote(url_param)
        except Exception:
            pass

    # Now check if it actually points to a conditions page
    if "/conditions/" not in href:
        return None

    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return BASE_URL + href
    return None


def find_condition_urls(query: str, limit: int = 3) -> list[str]:
    try:
        url = SEARCH_URL.format(query=quote_plus(query))
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    urls: list[str] = []
    q_tokens = set(_normalize(query))

    # Look at all links and extract those that ultimately point to /conditions/... pages.
    for a in soup.find_all("a", href=True):
        raw_href = a.get("href") or ""
        href = _extract_conditions_url(raw_href)
        if not href:
            continue

        title_text = a.get_text(" ", strip=True).lower()
        if q_tokens and not any(t in title_text for t in q_tokens):
            # skip obviously unrelated condition links
            continue

        if href not in urls:
            urls.append(href)
        if len(urls) >= limit:
            break

    return urls


def scrape_condition_page(url: str) -> dict[str, Any] | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    title_el = soup.select_one("h1")
    main = soup.select_one("main") or soup

    paragraphs: list[str] = []
    for p in main.select("p"):
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)

    if not paragraphs:
        return None

    body = "\n".join(paragraphs)

    return {
        "url": url,
        "title": title_el.get_text(strip=True) if title_el else "",
        "body": body,
        "paragraphs": paragraphs,
        "source": "nhs_live",
    }


def fetch_nhs_for_query(query: str) -> dict[str, Any] | None:
    urls = find_condition_urls(query, limit=1)
    if not urls:
        return None
    return scrape_condition_page(urls[0])


def fetch_nhs_chunks_for_query(query: str, k: int = 10) -> list[dict[str, Any]]:
    """
    Return up to k best-scoring NHS snippets (paragraphs) for a query.
    Each result looks like a normal search hit: {text, title, url, score, id, source, meta}.
    """
    urls = find_condition_urls(query, limit=5)
    results: list[dict[str, Any]] = []

    for url in urls:
        article = scrape_condition_page(url)
        if not article:
            continue

        title = article.get("title", "")
        paragraphs: list[str] = article.get("paragraphs", []) or []

        for idx, para in enumerate(paragraphs):
            if not para:
                continue

            score = _overlap_score(query, f"{title} {para}")

            results.append(
                {
                    "text": para,
                    "title": title,
                    "url": article["url"],
                    "score": score,
                    "id": f"{article['url']}#p{idx}",
                    "source": "NHS",
                    "meta": {
                        "title": title,
                        "url": article["url"],
                        "source": "NHS",
                    },
                }
            )

    results.sort(key=lambda x: x["score"], reverse=True)
    if k <= 0:
        return results
    return results[:k]
