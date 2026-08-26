import os
import re
import time

import requests
import streamlit as st

st.set_page_config(page_title="Semantic Search", page_icon="🔎", layout="wide")
API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

def ping():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        return r.ok and r.json().get("ok") is True
    except Exception:
        return False

def highlight(text, query):
    terms = [t for t in re.split(r"\W+", query) if len(t) > 2]
    for t in sorted(set(terms), key=len, reverse=True):
        text = re.sub(rf"(?i)({re.escape(t)})", r"**\1**", text)
    return text

def normalize(resp_json):
    if isinstance(resp_json, list):
        return resp_json
    for key in ("results", "hits", "data"):
        if key in resp_json and isinstance(resp_json[key], list):
            return resp_json[key]
    return []

with st.sidebar:
    st.markdown("### API")
    st.write(API_BASE)
    st.success("API OK") if ping() else st.error("API DOWN")
    k = st.slider("Top K", 1, 50, 10, 1)
    min_score = st.slider("Min score", 0.0, 1.0, 0.0, 0.01)
    st.caption("Change API via env: API_BASE_URL")

st.title("🔎 Semantic Search")
q = st.text_input("Query", "diabetes")
do = st.button("Search", type="primary")

if do and q.strip():
    t0 = time.time()
    try:
        r = requests.post(
            f"{API_BASE}/v1/search",
            json={"query": q, "k": k, "min_score": min_score},
            timeout=60
        )
        elapsed = (time.time() - t0) * 1000
        if r.ok:
            hits = normalize(r.json())
            st.caption(f"Latency: {elapsed:.1f} ms • {len(hits)} results")
            if not hits:
                st.info("No results.")
            for i, h in enumerate(hits, 1):
                text = h.get("text") or h.get("chunk") or h.get("content") or ""
                score = h.get("score") or h.get("similarity") or h.get("distance") or 0.0
                meta = h.get("meta") or {}

                display_score = float(score)

                col1, col2 = st.columns([1, 5])
                with col1:
                    st.markdown(f"**#{i}**")
                with col2:
                    st.markdown(f"**Score:** {display_score:.3f}")

                st.markdown(highlight(text, q))
                if meta:
                    st.json(meta, expanded=False)
                st.divider()
        else:
            st.error(f"{r.status_code} {r.text}")
    except Exception as e:
        st.error(str(e))
