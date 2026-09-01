"""
API 客户端：演示"别的程序"怎么调用你的客服接口
================================================
api_server.py 是服务端（一直运行），本文件是调用方（用完即走）。
真实场景里，网页、小程序、其他系统，都是这样调用你的客服的。

注意看：调用代码你 Day 1 就会了——requests.post(url, json=...)
你之前一直在调用 Ollama 的 API（localhost:11434），
现在你自己的服务跑在 localhost:8000，轮到别人调用你了。
角色互换，这就是"接口"的本质。

操作：
  1. 服务端保持运行（python api_server.py 的窗口不要关）
  2. 新开一个 PowerShell 窗口，运行：python client_demo.py
"""

import requests

API_URL = "http://127.0.0.1:8000/chat"

# 关键：对话历史由【调用方】自己维护，服务端不记
history = []


def ask(question):
    # 发请求：POST 一段 JSON 到 /chat
    resp = requests.post(API_URL, json={
        "question": question,
        "history": history
    })
    data = resp.json()  # 拿到返回的 JSON

    print(f"\n你：{question}")
    print(f"🔍 实际检索用的问题：{data['search_question']}")
    print(f"客服：{data['answer']}")
    print(f"📚 回答依据了 {len(data['sources'])} 段资料")

    # 把这一轮追加进历史，下一轮请求时带上（记忆就这么实现的）
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": data["answer"]})


# 模拟一个客户连续问两轮
ask("退换货运费谁承担？")
ask("那尺码不合适算哪种？")

print("\n" + "=" * 50)
print(f"对话结束。客户端本地存了 {len(history)} 条历史记录，")
print("服务端？它什么都没记住——下一个客户来，它又是全新接待。")
