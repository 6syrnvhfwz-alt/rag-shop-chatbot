"""
第 2 周 Day 7 · RAG 智能客服 · 查询改写版
================================================
在 Day 6（多轮记忆）基础上加"查询改写"：
检索之前，先让 AI 把客户的半截话、指代词补全成完整问题，
再拿去向量库检索——解决多轮对话里"搜不准"的问题。

完整流程（比 v2 多了第 0 步）：
  0. 查询改写：客户原话 + 历史对话 → AI 改写成意思完整的检索问题
  1. 向量检索：用改写后的问题去知识库找资料
  2. 组织回答：原始问题 + 历史 + 资料 一起发给 AI 回答

为什么需要改写？
  客户说"那尺码不合适算哪种？"——没有"运费"二字，
  直接检索会搜到"尺码表"。改写后变成
  "尺码不合适退换货运费谁承担？"，才能精准命中。

运行：python rag_chatbot_v3.py
"""

import os
import requests
import chromadb

# 本地运行默认连本机 Ollama；Docker 里通过环境变量改成 host.docker.internal
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = "qwen3:8b"
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


# ============================================
# 新知识点：查询改写
# ============================================
def rewrite_query(history, question):
    """
    查询改写：把客户的半截话补全成完整检索问题。
    关键坑（实测踩过）：不能把客服回答记录放在 assistant 角色里喂给改写模型——
    小模型会模仿"前辈"的行为，跟着回答问题，而不是改写。
    解法：历史对话整理成纯文本，连同新问题一起放进 user 消息。
    """
    # 1. 历史对话 → 纯文本
    transcript_lines = []
    for msg in history:
        role = "客户" if msg["role"] == "user" else "客服"
        transcript_lines.append(f"{role}：{msg['content']}")
    transcript = "\n".join(transcript_lines)

    system_prompt = """你是检索查询改写助手。你的唯一任务：把客户最后一句问话，
改写成意思完整、可以独立用于检索的问题。
严格规则：
1. 补全"这个/那个/这种/呢"等指代所指的具体内容
2. 禁止回答问题，禁止解释，禁止出现句号
3. 只输出改写后的问题本身，不超过20个字

示例：
对话历史：
客户：退换货运费谁承担？
客服：质量问题店铺承担，非质量问题买家承担。
客户最后一句：那尺码不合适算哪种？
输出：尺码不合适退换货运费谁承担
"""

    def call(extra_warning=""):
        user_prompt = f"""对话历史：
{transcript}

客户最后一句：{question}
{extra_warning}
输出改写后的问题："""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        resp = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "temperature": 0.1,
            "think": False
        })
        return resp.json()["message"]["content"].strip()

    def is_valid(t):
        return len(t) <= 30 and t.count("。") == 0 \
               and t.count("？") + t.count("?") <= 1

    rewritten = call()
    if is_valid(rewritten):
        return rewritten

    print(f"   ⚠️ 第1次改写不合规，它输出的是：{rewritten[:60]}")
    rewritten = call(extra_warning="\n警告：你上次错误地回答了问题！这次只输出改写后的短问题，禁止回答，禁止句号。")
    if is_valid(rewritten):
        return rewritten

    print(f"   ⚠️ 第2次还是不合规：{rewritten[:60]}，本轮用原问题检索")
    return question


def chat_with_memory(history, question, context):
    """带记忆的回答：历史 + 新问题 + 本轮资料 一起发给 AI"""
    messages = [
        {"role": "system", "content": f"""你是跨境电商店铺的客服助手。请严格根据下面的店铺资料回答客户问题。
资料里有的就简洁口语化回答；资料里没有的信息，就说"这个问题我需要帮您转人工客服确认"，不要编造。
只回答客户当前问的内容，资料里与问题无关的信息不要主动提，不要画蛇添足。
回答要结合对话上下文，客户可能用"那""这个""它"指代上一轮聊过的内容。

【店铺资料】
{context}"""}
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    resp = requests.post(f"{OLLAMA_URL}/api/chat", json={
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False 
    })
    return resp.json()["message"]["content"]


def main():
    print("=" * 55)
    print("🛍️  环球好物跨境专营店 · AI 客服（查询改写版）")
    print("=" * 55)

    print("\n📖 正在加载知识库...")
    sections = load_knowledge()
    print(f"   已读取 {len(sections)} 个知识板块")
    print("🔢 正在构建向量库（约几十秒）...")
    collection = build_vector_db(sections)
    print("   向量库构建完成！\n")

    print("-" * 55)
    print("客服已上线！输入问题开始对话，输入 q 退出。")
    print("重点观察 ✏️ 改写后 那一行——看 AI 怎么把半截话补全")
    print("-" * 55)

    history = []

    while True:
        question = input("\n你：").strip()
        if question.lower() in ('q', 'quit', '退出'):
            print("客服：感谢咨询，再见！")
            break
        if not question:
            continue

        # 0. 查询改写：第一轮没有历史，不用改写；之后每轮都先改写
        if history:
            search_question = rewrite_query(history, question)
            print(f"   ✏️ 改写后：{search_question}")
        else:
            search_question = question

        # 1. 用【改写后的问题】检索资料（v2 是用原话检索，这是关键区别）
        context = search_relevant(collection, search_question)
        print(f"   🔍 检索到：{context[:50]}...")

        # 2. 带着记忆 + 资料回答
        print("客服：", end="", flush=True)
        answer = chat_with_memory(history, question, context)
        print(answer)

        # 3. 记入历史
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()