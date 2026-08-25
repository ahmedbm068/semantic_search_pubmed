from datasets import load_dataset

dataset = load_dataset("PubMed", split="train[:5]")  # les 5 premiers abstracts pour tester
print(dataset[0])
