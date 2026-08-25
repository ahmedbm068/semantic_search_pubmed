import os, json, random, re, pandas as pd, numpy as np

random.seed(42)
np.random.seed(42)

def split_sentences(t):
    t=re.sub(r"\s+"," ",str(t)).strip()
    s=re.split(r"(?<=[.!?])\s+", t)
    return [x for x in s if len(x.split())>5]

def main(src_csv, out_train, out_val, max_per_doc=5):
    df=pd.read_csv(src_csv)
    df=df[df["text"].astype(str).str.strip()!=""]
    rows=[]
    for _,r in df.iterrows():
        sents=split_sentences(r["text"])
        if not sents: 
            continue
        picks=random.sample(sents, min(len(sents), max_per_doc))
        for q in picks:
            rows.append({"query": q, "doc": r["text"]})
    random.shuffle(rows)
    n=int(0.9*len(rows))
    os.makedirs(os.path.dirname(out_train), exist_ok=True)
    with open(out_train,"w",encoding="utf-8") as f:
        for x in rows[:n]:
            f.write(json.dumps(x, ensure_ascii=False)+"\n")
    with open(out_val,"w",encoding="utf-8") as f:
        for x in rows[n:]:
            f.write(json.dumps(x, ensure_ascii=False)+"\n")
    print(len(rows), "pairs", "train", n, "val", len(rows)-n)

if __name__=="__main__":
    import sys
    src=sys.argv[1] if len(sys.argv)>1 else "data/raw/pubmed_rct20k.csv"
    main(src, "data/processed/train_pairs.jsonl", "data/processed/val_pairs.jsonl")
