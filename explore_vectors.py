"""
RAG 细节探索：打开黑盒，看看向量和相似度到底长什么样
======================================================
不写客服功能，只做三个实验，看懂 RAG 的地基：
  实验1：文字变成的向量，到底是个啥？
  实验2：AI 凭什么判断哪段资料最相关？（距离分数）
  实验3：查询改写到底有没有用？（同一意图两种问法，分数对比）

运行：python explore_vectors.py
"""

import requests
import chromadb

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"


def get_embedding(text):
    resp = requests.post(f"{OLLAMA_URL}/api/embeddings", json={
        "model": EMBED_MODEL,
        "prompt": text
    })
    return resp.json()["embedding"]


# ============================================
# 实验 1：向量长什么样
# ============================================
print("=" * 60)
print("实验 1：文字变成的向量，到底是个啥？")
print("=" * 60)

vec = get_embedding("退换货运费谁承担")
print(f"'退换货运费谁承担' 这句话，被 AI 变成了 {len(vec)} 个数字")
print(f"前 10 个数字：{[round(x, 4) for x in vec[:10]]}")
print("→ AI 眼里没有'文字'，只有这串数字（可以理解成 768 维空间里的一个坐标）")
print()

# ============================================
# 实验 2：相似度距离分数
# ============================================
print("=" * 60)
print("实验 2：AI 凭什么判断哪段资料最相关？")
print("=" * 60)

texts = [
    "退换货政策：质量问题退货运费由本店承担，非质量问题由买家承担",
    "关税说明：海外直邮商品可能产生进口关税，5000元以内店铺代缴",
    "物流时效：海外直邮7-15个工作日送达，保税仓3-7个工作日",
    "会员权益：注册会员首单95折，积分可抵扣现金",
    "尺码问题：服装测量可能有1-3厘米误差，尺码不合适可7天内换货",
]

# metadata 指定用"余弦距离"：0=完全相同，2=完全相反，越小越相似
client = chromadb.Client()
col = client.create_collection(
    "explore", metadata={"hnsw:space": "cosine"})

for i, t in enumerate(texts):
    col.add(
        ids=[f"t{i}"],
        embeddings=[get_embedding("search_document: " + t)],
        documents=[t]
    )

def show_scores(question):
    print(f"\n问题：{question}")
    results = col.query(
        query_embeddings=[get_embedding("search_query: " + question)],
        n_results=5
    )
    for doc, dist in zip(results["documents"][0], results["distances"][0]):
        bar = "█" * int((1.2 - dist) * 30) if dist < 1.2 else ""
        print(f"  距离 {dist:.4f}  {bar:<25} {doc[:22]}...")
    print("  ↑ 距离越小 = 方向越一致 = 语义越接近")

# 注意第2题：说的是"邮费"不是"运费"，"退货"不是"退换货"——看关键词不同能不能命中
show_scores("关税谁来交？")
show_scores("退货要自己出邮费吗")
show_scores("几天能到货")

# ============================================
# 实验 3：查询改写的价值（同一意图，两种问法）
# ============================================
print("\n" + "=" * 60)
print("实验 3：查询改写到底有没有用？")
print("=" * 60)
print("Day7 客户的半截话 vs 改写后的完整问题，对比分数：")

show_scores("那尺码不合适算哪种？")
show_scores("尺码不合适退换货运费谁承担")

print("\n看出来了吗：")
print("- 第1种问法，'退换货政策'段的距离是多少？")
print("- 第2种问法（改写后），它的距离变小了还是变大了？排名呢？")
print("- 这就是 Day7 改写的意义——不是靠感觉，是分数真的变了")
