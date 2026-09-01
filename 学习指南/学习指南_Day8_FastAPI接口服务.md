# 学习指南 Day8：FastAPI —— 把程序变成 HTTP 接口服务

## 一、这一天解决了什么问题？

Day5-7 的 RAG 客服，只能你自己在终端里 `python rag_chatbot_v3.py` 跑着玩。
但真实工作中，客服系统是给**别人**用的：网页前端、小程序、别的同事的程序……
它们不可能在你电脑上运行 Python 脚本，它们只会一件事：**发 HTTP 请求**。

FastAPI 做的事：把你的 Python 函数包装成一个 HTTP 接口（API），
别人通过网址 + JSON 数据就能调用，就像调用一个远程函数。

```
之前：python 脚本 → 终端里自己问自己答
现在：python 脚本 → 启动后常驻 → 任何程序都能通过 HTTP 调用
```

## 二、核心概念

| 概念 | 通俗理解 |
|------|---------|
| **API（接口）** | 程序对外提供服务的"窗口"。别人不用知道你内部怎么实现，按格式发请求就能拿结果 |
| **HTTP 接口** | 最常见的 API 形式：一个网址（URL）+ 一种请求方法（GET/POST）+ JSON 数据 |
| **FastAPI** | Python 的 Web 框架，专门用来快速写接口。自带接口文档、自动校验数据 |
| **uvicorn** | Web 服务器，负责真正监听端口、收发 HTTP 请求。FastAPI 是"应用"，uvicorn 是"跑应用的容器" |
| **Swagger 文档** | FastAPI 自动生成的接口说明书（/docs），能在浏览器里直接填参数测试 |
| **端口（8000）** | 一台电脑上跑很多网络程序，靠端口号区分。8000 是我们给服务占的"门牌号" |

## 三、代码结构（api_server.py）

### 1. 复用，不重写
```python
from rag_chatbot_v3 import chat_with_memory, rewrite_query, search_knowledge, ...
```
Day5-7 写好的所有函数直接 import 进来用。**工程化不是重写，是包装**。

### 2. 启动时建好向量库（全局只建一次）
```python
app = FastAPI()
collection = None

@app.on_event("startup")
def startup():
    global collection
    collection = init_vector_db()   # 服务启动时建一次，之后所有请求共用
```
向量库加载要时间，不能每个请求都重建——放全局。

### 3. 用 Pydantic 模型规定"收发格式"
```python
class ChatRequest(BaseModel):
    question: str                    # 客户这一轮的问题
    history: list = []               # 历史对话（调用方传进来）

class ChatResponse(BaseModel):
    answer: str
    search_question: str
    sources: list
```
FastAPI 会**自动校验**：你传的 question 不是字符串、少了字段，它直接报错，不用你写检查代码。

### 4. 一个装饰器 = 一个接口
```python
@app.post("/chat")
def chat(req: ChatRequest):
    result = chat_with_memory(req.question, req.history, collection)
    return ChatResponse(...)
```
- `@app.post("/chat")`：当有人用 POST 方法访问 `/chat` 这个网址，就执行下面的函数
- 函数收到的是解析好的 ChatRequest 对象，返回的对象自动转成 JSON

### 5. 客户端（client_demo.py）
```python
resp = requests.post("http://127.0.0.1:8000/chat", json={
    "question": "那尺码不合适算哪种？",
    "history": history   # 客户端自己维护历史，每次请求带上
})
data = resp.json()
history.append({"role": "user", "content": question})
history.append({"role": "assistant", "content": data["answer"]})
```

## 四、这一天最重要的认知：服务无状态

**服务端不记任何对话历史。** 每个请求都是独立的，服务端收到 question + history，处理完返回，然后"失忆"。

历史由**客户端**（网页、App、调用方）自己存着，每次请求完整带上。

为什么这么设计？
- 服务端要同时接待成千上万个客户，如果每个客户的对话都记在服务端内存里，内存会爆、客户换台设备记录就丢了
- 无状态服务可以随意重启、扩容（开 10 个一样的服务轮着用），请求发给谁都一样
- 这是互联网服务的标准做法（HTTP 协议本身就是无状态的）

```
客户端窗口：存了 4 条历史记录
服务端窗口：零记忆——下一个客户来，又是全新接待
```

## 五、HTTP 状态码（面试常问）

| 状态码 | 含义 | 我们的场景 |
|--------|------|-----------|
| **200** | 成功 | 接口正常返回答案 |
| **422** | 请求格式不对 | FastAPI 自动校验失败（比如 question 传了数字） |
| **500** | 服务内部出错 | 代码抛异常了 |
| 404 | 网址不存在 | 打错路径 |

## 六、常用命令

```powershell
pip install fastapi uvicorn        # 安装
python api_server.py               # 启动服务（窗口常驻，Ctrl+C 停止）
# 浏览器打开 http://127.0.0.1:8000/docs  → Swagger 可视化测试
```

## 七、词汇表

- **API / 接口**：程序对外提供服务的窗口，按格式调用即可，不用关心内部实现
- **HTTP 请求**：网络上程序之间对话的标准格式（URL + 方法 + JSON 数据）
- **GET / POST**：GET 用来"取数据"（参数在网址上），POST 用来"提交数据"（数据在请求体里）。我们的聊天用 POST
- **JSON**：网络数据交换的通用格式，长得像 Python 字典
- **无状态（stateless）**：服务端不保存客户端的任何上下文，每次请求自包含全部信息
- **端口**：电脑上网络程序的门牌号（如 8000）
- **localhost / 127.0.0.1**：指"本机自己"
- **Pydantic**：FastAPI 用来做数据校验和序列化的库，BaseModel 子类定义数据结构
