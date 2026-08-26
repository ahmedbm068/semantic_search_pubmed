import json
import os
import sys

os.environ["TRANSFORMERS_NO_TF"]="1"
os.environ["USE_TF"]="0"
os.environ["TRANSFORMERS_NO_TORCHVISION"]="1"

import platform

import torch
from sentence_transformers import InputExample, SentenceTransformer, losses
from sentence_transformers.evaluation import InformationRetrievalEvaluator
from torch.utils.data import DataLoader, Dataset


class PairDS(Dataset):
    def __init__(self, path):
        self.items=[json.loads(x) for x in open(path, encoding="utf-8")]
    def __len__(self):
        return len(self.items)
    def __getitem__(self, i):
        x=self.items[i]
        return InputExample(texts=[x["query"], x["doc"]])

def build_ir_eval(path, sample=1000):
    items=[json.loads(x) for x in open(path, encoding="utf-8")]
    items=items[:sample] if sample else items
    queries={}
    corpus={}
    rel={}
    for i,x in enumerate(items):
        qid=f"q{i}"
        did=f"d{i}"
        queries[qid]=x["query"]
        corpus[did]=x["doc"]
        rel[qid]={did:1}
    return InformationRetrievalEvaluator(queries, corpus, rel, name="pubmed_val")

def main(
    train_path, val_path, out_dir, model_name,
    batch_size, epochs, lr, num_workers, eval_sample,
):
    if platform.system() == "Windows":
        num_workers = 0

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.backends.cudnn.benchmark = True
    try:
        torch.set_float32_matmul_precision("high")
    except (AttributeError, RuntimeError):
        pass

    train_ds = PairDS(train_path)
    train_dl = DataLoader(
        train_ds,
        shuffle=True,
        batch_size=batch_size,
        drop_last=True,
        num_workers=num_workers,  # forced to 0 on Windows
        pin_memory=torch.cuda.is_available(),
        persistent_workers=False           # important with workers
    )

    model = SentenceTransformer(model_name, device=device)
    loss = losses.MultipleNegativesRankingLoss(model)
    evaluator = build_ir_eval(val_path, sample=eval_sample) if os.path.exists(val_path) else None

    warmup_steps = max(1, int(len(train_dl) * epochs * 0.1))
    fit_kwargs = dict(
        train_objectives=[(train_dl, loss)],
        epochs=epochs,
        warmup_steps=warmup_steps,
        output_path=out_dir,
        save_best_model=True,
        use_amp=torch.cuda.is_available(),
        show_progress_bar=True
    )
    if evaluator is not None:
        fit_kwargs["evaluator"] = evaluator
        fit_kwargs["evaluation_steps"] = max(10, len(train_dl)//5)

    model.fit(**fit_kwargs)
    print("saved", out_dir)

if __name__=="__main__":
    train_path=sys.argv[1] if len(sys.argv)>1 else "data/processed/train_pairs.jsonl"
    val_path=sys.argv[2] if len(sys.argv)>2 else "data/processed/val_pairs.jsonl"
    out_dir=sys.argv[3] if len(sys.argv)>3 else "models/biomed-miniLM"
    model_name=os.getenv("BASE_EMB","sentence-transformers/all-MiniLM-L6-v2")
    batch_size=int(os.getenv("BATCH_SIZE","64"))
    epochs=int(os.getenv("EPOCHS","1"))
    lr=float(os.getenv("LR","2e-5"))
    num_workers=int(os.getenv("NUM_WORKERS","2"))
    eval_sample=int(os.getenv("EVAL_SAMPLE","1000"))
    os.makedirs(out_dir, exist_ok=True)
    main(
        train_path, val_path, out_dir, model_name,
        batch_size, epochs, lr, num_workers, eval_sample,
    )
