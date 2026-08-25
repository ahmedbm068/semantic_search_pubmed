from .nhs_live import fetch_nhs_for_query
from .nhs_summarizer import summarize_nhs_body

def search_nhs_with_summary(query: str) -> dict | None:
    article = fetch_nhs_for_query(query)
    if not article:
        return None
    body = article.get("body") or ""
    title = article.get("title") or ""
    summary = summarize_nhs_body(body, title=title)
    return {
        "id": article["url"],
        "title": title,
        "url": article["url"],
        "summary": summary,
        "source": "NHS",
    }
