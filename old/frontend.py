import streamlit as st
import requests
import re

def highlight_keywords(text, keywords):
    for kw in keywords.split():
        text = re.sub(f"(?i)({kw})", r"**\1**", text)
    return text

st.set_page_config(page_title="Semantic Search PubMed", layout="wide")

st.title("Semantic Search PubMed")
question = st.text_input("Pose ta question :", "")
top_k = st.slider("Nombre de résultats :", 1, 5, 3)

if st.button("Rechercher") and question:
    url = "http://127.0.0.1:8000/search"
    payload = {"question": question, "top_k": top_k}

    with st.spinner("Recherche en cours..."):
        try:
            response = requests.post(url, json=payload)
            data = response.json()
            results = data.get("results", [])

            if results:
                st.success(f"Résultats pour : {question}")
                for i, res in enumerate(results, 1):
                    with st.expander(f"Result {i} (distance: {res['distance']:.4f})"):
                        st.markdown(highlight_keywords(res['text'], question))
            else:
                st.warning("Aucun résultat trouvé.")
        except Exception as e:
            st.error(f"Erreur : {e}")
