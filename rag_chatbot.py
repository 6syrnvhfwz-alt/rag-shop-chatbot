"""
第 2 周 Day 5 · RAG 智能客服知识库问答
=========================================
让 AI 客服基于你店铺的私有资料回答问题（开卷考试）。

流程：
  1. 读取 知识库.txt，按【标题】切成段落
  2. 用 Ollama 的嵌入模型把每个段落转成向量，存进 Chroma 向量库
  3. 客户提问 → 问题转成向量 → 从库里找最相似的 3 段资料
  4. 把"资料 + 问题"一起发给 qwen2:7b → AI 照着资料回答

前置准备（PowerShell 里跑）：
  pip install chromadb requests
  ollama pull nomic-embed-text      # 嵌入模型（把文字转成语义数字）

运行：
  python rag_chatbot.py

你只需要填 3 个 TODO 任务。
"""

import requests
import chromadb

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2:7b"              # 负责"说话"的模型
EMBED_MODEL = "nomic-embed-text"  # 负责"把文字转向量"的模型


def get_embedding(text):
    """调用 Ollama 嵌入模型，把一段文字转成向量（一串数字）。
    语义相近的文字，向量也相近——这就是'语义搜索'的原理。"""
    resp = requests.post(f"{OLLAMA_URL}/api/embeddings", json={
        "model": EMBED_MODEL,
        "prompt": text
    })
    return resp.json()["embedding"]


def load_knowledge(filename="知识库.txt"):
    """读取知识库，按【标题】切成一段段。返回 [{"title":..., "content":...}, ...]"""
    with open(filename, encoding="utf-8") as f:
        text = f.read()

    sections = []
    current_title = "店铺信息"
    current_lines = []

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("【") and line.endswith("】"):
            # 遇到新标题，把之前攒的内容存起来
            if current_lines:
                sections.append({
                    "title": current_title,
                    "content": "\n".join(current_lines)
                })
            current_title = line.strip("【】")
            current_lines = []
        elif line:
            current_lines.append(line)

    if current_lines:
        sections.append({
            "title": current_title,
            "content": "\n".join(current_lines)
        })
    return sections


def build_vector_db(sections):
    """把每个段落转向量，存进 Chroma 向量库。"""
    client = chromadb.Client()
    # 每次重建一个全新的集合，避免旧数据干扰
    try:
        client.delete_collection("shop_faq")
    except Exception:
        pass
    collection = client.create_collection("shop_faq")

    for i, sec in enumerate(sections):
        full_text = f"{sec['title']}：{sec['content']}"
        embedding = get_embedding("search_document: " + full_text)
        collection.add(
            ids=[f"sec_{i}"],
            embeddings=[embedding],
            documents=[full_text],
            metadatas=[{"title": sec["title"]}]
        )
    return collection


# ============================================
# 任务 1：检索相关资料
# ============================================
def search_relevant(collection, question, top_k=4):
    # 第一步：向量检索，先捞出 6 段候选（语义相近）
    q_embedding = get_embedding("search_query: " + question)
    results = collection.query(query_embeddings=[q_embedding], n_results=6)
    docs = results['documents'][0]

    # 第二步：关键词重排——把问题拆成二字词，统计在资料里出现的次数
    # 比如"关税是谁出"拆出"关税"，关税段里出现多次，得分就高
    stop_chars = set("的是了吗呢吧我你他她它们？?，,。！!谁啊呀哪怎什么么有在和与不也都很还会个")
    def keyword_score(doc):
        score = 0
        for i in range(len(question) - 1):
            bigram = question[i:i+2]
            if any(c in stop_chars for c in bigram):
                continue
            score += doc.count(bigram) * 10  # 关键词命中权重高
        return score

    # 关键词命中的排前面，其余按向量顺序兜底
    docs_sorted = sorted(docs, key=keyword_score, reverse=True)

    # 去重后取前 top_k 段
    picked = []
    for d in docs_sorted:
        if d not in picked:
            picked.append(d)
        if len(picked) == top_k:
            break
    return "\n\n".join(picked)

  

# ============================================
# 任务 2：让 AI 基于资料回答
# ============================================
def ask_ai(question, context):
    prompt = f"""你是跨境电商店铺的客服助手。请严格根据下面的店铺资料回答客户问题。
资料里有的就简洁回答；资料里没有的信息，就说"这个问题我需要帮您转人工客服确认"，不要自己编造。

【店铺资料】
{context}

【客户问题】
{question}"""

    resp = requests.post(f"{OLLAMA_URL}/api/generate", json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    })
    return resp.json()["response"]



# ============================================
# 任务 3（进阶）：对话循环
# ============================================
def main():
    print("=" * 55)
    print("🛍️  环球好物跨境专营店 · AI 客服（RAG 知识库版）")
    print("=" * 55)

    print("\n📖 正在加载知识库...")
    sections = load_knowledge()
    print(f"   已读取 {len(sections)} 个知识板块")

    print("🔢 正在构建向量库（把资料转成语义向量，约需几十秒）...")
    collection = build_vector_db(sections)
    print("   向量库构建完成！\n")

    print("-" * 55)
    print("客服已上线！输入你的问题，输入 q 退出。")
    print("试试问：几天发货？ / 关税谁交？ / 质量问题退货运费谁出？")
    print("-" * 55)

    # TODO：实现对话循环
    while True:
        question = input("\n你：").strip()
        if question.lower() in ('q', 'quit', '退出'):
            print("客服：感谢咨询，再见！")
            break
        if not question:
            continue
    
        # 1. 检索相关资料
        context = search_relevant(collection, question)
    
        # （可选）打印检索到的资料，帮你理解 RAG 在干什么
        print(f"   🔍 检索到的资料：{context[:60]}...")
    
        # 2. AI 基于资料回答
        print("客服：", end="", flush=True)
        answer = ask_ai(question, context)
        print(answer)


if __name__ == "__main__":
    main()
