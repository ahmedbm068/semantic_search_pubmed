import argparse
import json
import os

KEYS_POS = ["positive","pos","passage","doc","document","text","body","abstract","content"]
KEYS_NEG = ["negative","neg","hard_negative","hard_neg","difficult"]

def iter_jsonl(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue

def pick_first(d, keys):
    for k in keys:
        if k in d and isinstance(d[k], str) and d[k].strip():
            return d[k].strip()
    return None

def collect_texts(paths, include_neg=True, min_len=10):
    seen = set()
    out = []
    for p in paths:
        for obj in iter_jsonl(p):
            for keyset in (KEYS_POS, KEYS_NEG if include_neg else []):
                if not keyset:
                    continue
                t = pick_first(obj, keyset)
                if not t:
                    continue
                if len(t) < min_len:
                    continue
                if t not in seen:
                    seen.add(t)
                    out.append(t)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", default="src/app/data/raw/corpus.txt")
    ap.add_argument("--include-neg", action="store_true")
    ap.add_argument("--min-len", type=int, default=10)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    texts = collect_texts(args.inputs, include_neg=args.include_neg, min_len=args.min_len)
    with open(args.out, "w", encoding="utf-8") as f:
        for t in texts:
            f.write(t.replace("\n"," ").strip() + "\n")
    print("wrote", args.out, "lines", len(texts))

if __name__ == "__main__":
    main()
