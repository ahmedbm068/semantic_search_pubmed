import os, sys, json, argparse, glob, time
import numpy as np
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import faiss

def read_txt(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            t = line.strip()
            if t:
                yield t

def read_jsonl(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except:
                continue
            for k in ["text","passage","content","abstract","document","body"]:
                if k in obj and isinstance(obj[k], str) and obj[k].strip():
                    yield obj[k].strip()
                    break

def load_corpus(patterns):
    texts = []
    for pat in patterns:
        for p in glob.glob(pat):
            ext = os.path.splitext(p)[1].lower()
            if ext == ".txt":
                texts.extend(list(read_txt(p)))
            elif ext in [".jsonl", ".json"]:
                texts.extend(list(read_jsonl(p)))
    return texts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-path", default="models/biomed-miniLM")
    ap.add_argument("--input", nargs="+", default=["data/raw/train.txt"])
    ap.add_argument("--output-dir", default="data/cache")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--normalize", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    texts = load_corpus(args.input)
    if len(texts) == 0:
        print("No texts found.", file=sys.stderr)
        sys.exit(1)

    model = SentenceTransformer(args.model_path)
    batches = []
    for i in tqdm(range(0, len(texts), args.batch_size)):
        batch = texts[i:i+args.batch_size]
        e = model.encode(batch, convert_to_numpy=True, batch_size=args.batch_size, show_progress_bar=False, normalize_embeddings=args.normalize)
        batches.append(e)
    X = np.concatenate(batches, axis=0)

    if not args.normalize:
        faiss.normalize_L2(X)

    d = X.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(X)

    emb_path = os.path.join(args.output_dir, "embeddings.npy")
    idx_path = os.path.join(args.output_dir, "faiss.index")
    corp_path = os.path.join(args.output_dir, "corpus.jsonl")
    meta_path = os.path.join(args.output_dir, "index_meta.json")

    np.save(emb_path, X)
    faiss.write_index(index, idx_path)
    with open(corp_path, "w", encoding="utf-8") as f:
        for i, t in enumerate(texts):
            f.write(json.dumps({"id": i, "text": t}, ensure_ascii=False) + "\n")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"model_path": args.model_path, "dim": int(d), "size": int(len(texts)), "similarity": "cosine", "normalized": True, "created_at": int(time.time())}, f)

    print("saved", idx_path)
    print("saved", emb_path)
    print("saved", corp_path)
    print("saved", meta_path)

if __name__ == "__main__":
    main()
