import csv, os, sys, re

def parse_file(path, split_name):
    abstracts=[]; pmid=None; buf=[]; labels=[]
    with open(path, encoding="utf-8") as f:
        for line in f:
            line=line.rstrip("\n")
            if not line: continue
            if line.startswith("###"):
                if pmid is not None and buf:
                    abstracts.append({"pmid": pmid, "text": " ".join(buf).strip(), "split": split_name, "labels": "|".join(labels)})
                pmid=line[3:].strip(); buf=[]; labels=[]
            else:
                m=re.match(r"^([A-Z]+)\s+(.*)$", line)
                if m:
                    labels.append(m.group(1)); buf.append(m.group(2).strip())
                else:
                    buf.append(line.strip())
        if pmid is not None and buf:
            abstracts.append({"pmid": pmid, "text": " ".join(buf).strip(), "split": split_name, "labels": "|".join(labels)})
    return abstracts

def main(in_dir, out_csv):
    parts=[("train.txt","train"),("validation.txt","validation"),("dev.txt","validation"),("test.txt","test")]
    rows=[]
    for fn,sp in parts:
        p=os.path.join(in_dir,fn)
        if os.path.exists(p): rows+=parse_file(p,sp)
    if not rows: raise SystemExit("No input files found")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=["pmid","text","split","labels"])
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_csv}")

if __name__=="__main__":
    in_dir=sys.argv[1] if len(sys.argv)>1 else "data/raw/pubmed_rct20k"
    out_csv=sys.argv[2] if len(sys.argv)>2 else "data/raw/pubmed_rct20k.csv"
    main(in_dir,out_csv)
