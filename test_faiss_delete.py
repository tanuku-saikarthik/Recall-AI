import faiss
import numpy as np

base_index = faiss.IndexFlatIP(10)
index = faiss.IndexIDMap(base_index)

# Add 2 vectors
v1 = np.random.rand(1, 10).astype('float32')
v2 = np.random.rand(1, 10).astype('float32')
index.add_with_ids(v1, np.array([1], dtype=np.int64))
index.add_with_ids(v2, np.array([2], dtype=np.int64))

print("Total before:", index.ntotal)

# Remove vector 1
index.remove_ids(np.array([1], dtype=np.int64))
print("Total after remove:", index.ntotal)
