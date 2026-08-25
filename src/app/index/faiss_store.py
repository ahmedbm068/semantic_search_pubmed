import faiss, numpy as np, pickle

class FaissStore:
    def __init__(self, index_path, emb_path, corpus_path):
        self.index_path=index_path
        self.emb_path=emb_path
        self.corpus_path=corpus_path
        self.index=None
        self.emb=None
        self.corpus=None

    def load(self):
        self.index=faiss.read_index(self.index_path)
        self.emb=np.load(self.emb_path)
        with open(self.corpus_path,"rb") as f:
            self.corpus=pickle.load(f)

    def search(self, q_emb, k):
        D,I=self.index.search(q_emb.astype("float32"), k)
        return D[0], I[0]
