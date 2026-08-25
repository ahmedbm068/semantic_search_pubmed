def split_text(t, size, overlap):
    chunks=[]
    i=0
    n=len(t)
    step=max(1, size-overlap)
    while i<n:
        chunks.append(t[i:i+size])
        i+=step
    return chunks
