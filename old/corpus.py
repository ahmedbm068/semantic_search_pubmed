from datasets import load_dataset
import re
import os
import pickle

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def preprocess(text):
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^a-z0-9.,;!? ]', '', text)
    return text

def load_corpus(n_docs=None):
    cache_path = os.path.join(CACHE_DIR, "corpus.pkl")
    
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            corpus = pickle.load(f)
    else:
        dataset = load_dataset("armanc/pubmed-rct20k", split="train")
        corpus = [preprocess(item["text"]) for item in dataset]  # "text" is the field in this dataset
        with open(cache_path, "wb") as f:
            pickle.dump(corpus, f)

    if n_docs:
        corpus = corpus[:n_docs]
    return corpus

if __name__ == "__main__":
    docs = load_corpus(n_docs=5)
    for doc in docs:
        print(doc)
