from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from corpus import load_corpus
import os
import pickle

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def create_index(corpus):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    embeddings_cache = os.path.join(CACHE_DIR, "embeddings.npy")
    index_cache = os.path.join(CACHE_DIR, "faiss.index")
    
    if os.path.exists(embeddings_cache) and os.path.exists(index_cache):
        embeddings_np = np.load(embeddings_cache)
        index = faiss.read_index(index_cache)
    else:
        embeddings = model.encode(corpus, convert_to_tensor=True)
        embeddings_np = np.array(embeddings.cpu()).astype('float32')
        
        index = faiss.IndexFlatL2(embeddings_np.shape[1])
        index.add(embeddings_np)
        
        np.save(embeddings_cache, embeddings_np)
        faiss.write_index(index, index_cache)
    
    return index, embeddings_np

if __name__ == "__main__":
    corpus = load_corpus()
    index, embeddings = create_index(corpus)
    print("Index created with", len(corpus), "documents")
