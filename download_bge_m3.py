from sentence_transformers import SentenceTransformer

print("开始加载 BGE-M3...")

model = SentenceTransformer("BAAI/bge-m3")

texts = [
    "员工报销需要在30天内提交发票。",
    "SKU A12-BK-XL 的包装尺寸是 30cm x 20cm x 5cm。"
]

print("开始生成向量...")

embeddings = model.encode(texts, normalize_embeddings=True)

print("BGE-M3 加载成功")
print("向量数量:", len(embeddings))
print("向量维度:", len(embeddings[0]))
