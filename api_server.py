"""
第 7 周 Day 1 · 把 RAG 客服变成 HTTP 接口服务（FastAPI）
========================================================
之前的客服是命令行程序：只有你自己在黑窗口里能用。
变成 API 服务后：网页、小程序、别人的系统，都能通过网络调用你的客服。

四个新概念：
  1. API（接口）：一个网址，POST 一段 JSON 过去，返回一段 JSON
  2. 启动时只建一次向量库（全局变量），所有请求复用——
     绝不能每次请求都重建（建一次要几十秒，接口会慢死）
  3. 无状态：服务本身不记对话，history 由调用方每次传进来
     （命令行版 history 存在程序里；API 版靠请求传——企业标准做法）
  4. FastAPI 自带交互文档：启动后浏览器开 http://127.0.0.1:8000/docs

运行：python api_server.py
然后浏览器打开 http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# 直接复用 v3 里写好的全部 RAG 函数
# （v3 的 main() 有 if __name__ == "__main__" 保护，import 时不会运行）
from rag_chatbot_v3 import (
    load_knowledge, build_vector_db,
    search_relevant, rewrite_query, chat_with_memory
)

app = FastAPI(title="跨境电商AI客服API", version="1.0")

# ===== 全局变量：服务启动时建好，之后所有请求共用 =====
print("📖 服务启动中：加载知识库、构建向量库（只做一次）...")
_sections = load_knowledge()
collection = build_vector_db(_sections)
print(f"✅ 就绪！{len(_sections)} 个知识板块已入库\n")


# ===== 约定数据格式：请求长什么样、响应长什么样 =====
# FastAPI 会自动校验：question 没传、传成数字，都会直接报错
class ChatRequest(BaseModel):
    question: str          # 客户这一轮的问题（必填）
    history: list = []     # 历史对话 [{"role":"user","content":"..."}, ...]


class ChatResponse(BaseModel):
    answer: str            # 客服回答
    search_question: str   # 实际用于检索的问题（首轮=原话，之后=改写后）
    sources: list[str]     # 检索到的资料段落（回答的依据，可展示给客户看）


# ===== 接口：POST /chat =====
# 别人往 http://127.0.0.1:8000/chat 发 JSON，就进这个函数
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # 1. 查询改写（首轮没有历史，不改写）
    if req.history:
        search_question = rewrite_query(req.history, req.question)
    else:
        search_question = req.question

    # 2. 检索资料
    context = search_relevant(collection, search_question)

    # 3. 生成回答
    answer = chat_with_memory(req.history, req.question, context)

    # 4. 返回结构化 JSON（sources 按段落拆开，调用方可以展示"回答依据"）
    return ChatResponse(
        answer=answer,
        search_question=search_question,
        sources=context.split("\n\n")
    )


# ===== 静态文件托管：浏览器访问 http://127.0.0.1:8000 直接进聊天网页 =====
# 放在最后，避免截获上面的 /chat 路由
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000)
