"""
RAG 智能客服 · 多轮对话记忆版
"""

import requests
import chromadb

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2:7b"
EMBED_MODEL = "nomic-embed-text"


def get_embedding(text):
    resp = requests.post(f"{OLLAMA_URL}/api/embeddings", json={
        "model": EMBED_MODEL,
        "prompt": text
    })
    return resp.json()["embedding"]


def load_knowledge(filename="知识库.txt"):
    with open(filename, encoding="utf-8") as f:
        text = f.read()
    sections = []
    current_title = "店铺信息"
    current_lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("【") and line.endswith("】"):
            if current_lines:
                sections.append({"title": current_title,
                                 "content": "\n".join(current_lines)})
            current_title = line.strip("【】")
            current_lines = []
        elif line:
            current_lines.append(line)
    if current_lines:
        sections.append({"title": current_title,
                         "content": "\n".join(current_lines)})
    return sections


def build_vector_db(sections):
    client = chromadb.Client()
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


def search_relevant(collection, question, top_k=4):
    """混合检索：向量海选 6 段 + 关键词重排"""
    q_embedding = get_embedding("search_query: " + question)
    results = collection.query(query_embeddings=[q_embedding], n_results=6)
    docs = results['documents'][0]

    stop_chars = set("的是了吗呢吧我你他她它们？?，,。！!谁啊呀哪怎什么么有在和与不也都很还会个")
    def keyword_score(doc):
        score = 0
        for i in range(len(question) - 1):
            bigram = question[i:i+2]
            if any(c in stop_chars for c in bigram):
                continue
            score += doc.count(bigram) * 10
        return score

    docs_sorted = sorted(docs, key=keyword_score, reverse=True)
    picked = []
    for d in docs_sorted:
        if d not in picked:
            picked.append(d)
        if len(picked) == top_k:
            break
    return "\n\n".join(picked)


def chat_with_memory(history, question, context):
    """每次把 system设定 + 全部历史 + 新问题 一起发给 AI"""
    messages = [
        {"role": "system", "content": f"""你是跨境电商店铺的客服助手。请严格根据下面的店铺资料回答客户问题。
资料里有的就简洁口语化回答；资料里没有的信息，就说"这个问题我需要帮您转人工客服确认"，不要编造。
回答要结合对话上下文，客户可能用"那""这个""它"指代上一轮聊的内容。

【店铺资料】
{context}"""}
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    resp = requests.post(f"{OLLAMA_URL}/api/chat", json={
        "model": MODEL,
        "messages": messages,
        "stream": False
    })
    return resp.json()["message"]["content"]


def main():
    print("=" * 55)
    print("  环球好物跨境专营店 · AI 客服（RAG + 记忆版）")
    print("=" * 55)

    print("\n正在加载知识库...")
    sections = load_knowledge()
    print(f"   已读取 {len(sections)} 个知识板块")
    print("正在构建向量库（约几十秒）...")
    collection = build_vector_db(sections)
    print("   向量库构建完成！\n")

    print("-" * 55)
    print("客服已上线！输入问题开始对话，输入 q 退出。")
    print("测试：第1轮问「退换货运费谁承担？」")
    print("      第2轮问「那尺码不合适算哪种？」← 考验记忆")
    print("-" * 55)

    history = []

    while True:
        question = input("\n你：").strip()
        if question.lower() in ('q', 'quit', '退出'):
            print("客服：感谢咨询，再见！")
            break
        if not question:
            continue

        context = search_relevant(collection, question)
        print(f"   [检索到] {context[:50]}...")

        print("客服：", end="", flush=True)
        answer = chat_with_memory(history, question, context)
        print(answer)

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()