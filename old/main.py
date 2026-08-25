from fastapi import FastAPI
from pydantic import BaseModel
from embeddings import create_index
from corpus import load_corpus
from sentence_transformers import SentenceTransformer
import numpy as np

app = FastAPI(title="Semantic Search PubMed")

class Query(BaseModel):
    question: str
    top_k: int = 5

print("Loading corpus and embeddings...")
corpus = load_corpus()  # uses cached corpus if available
model = SentenceTransformer('all-MiniLM-L6-v2')
index, embeddings_np = create_index(corpus)  # uses cached FAISS index if available
print("Ready!")

@app.post("/search")
def search(query: Query):
    if not query.question.strip():
        return {"results": []}
    
    q_embedding = model.encode([query.question], convert_to_tensor=True).cpu().numpy().astype('float32')
    D, I = index.search(q_embedding, query.top_k)
    
    results = [
        {"text": corpus[i], "distance": float(D[0][j])} 
        for j, i in enumerate(I[0])
    ]
    return {"results": results}
