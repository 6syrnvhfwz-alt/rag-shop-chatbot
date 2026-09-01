# 学习指南 Day9：Docker —— 把服务打包成容器，搬到哪都能跑

## 一、这一天解决了什么问题？

程序员界最有名的梗：**"在我电脑上明明能跑啊？"**

你的 RAG 服务要跑起来，需要：Python 3.11、四个 pip 包、特定版本、Ollama 地址配置……
换台电脑、换个服务器，环境装错一个版本就可能崩。

Docker 的做法：把**代码 + 运行环境（Python 解释器、依赖包）**一起打包成一个"镜像"。
到任何装了 Docker 的机器上，一条命令就能跑起来，环境完全一致。

```
之前：把 .py 文件发给别人 → 对方装 Python、装依赖、配环境、祈祷不报错
现在：把镜像发给别人 → docker run → 直接跑
```

## 二、核心概念（最重要的一组类比）

| 概念 | 类比 |
|------|------|
| **镜像（Image）** | 菜谱 / 安装光盘 / 类（class）：只读的模板，包含代码+环境 |
| **容器（Container）** | 按菜谱做出来的菜 / 用光盘装好的系统 / 对象（instance）：镜像跑起来的运行实例 |
| **Dockerfile** | 菜谱说明书：告诉 Docker"怎么一步步构建这个镜像" |
| **仓库（Registry）** | 镜像的应用商店：Docker Hub 是官方商店，放着 python、nginx 等基础镜像 |

一个镜像可以同时跑起多个容器（就像一个类可以 new 多个对象）。

## 三、三个关键文件

### 1. Dockerfile（构建说明书，逐行讲解）

```dockerfile
FROM python:3.11-slim              # 第一步：拿一个装好 Python 3.11 的精简 Linux 当底座
WORKDIR /app                        # 容器里的工作目录（相当于 cd /app）
COPY . .                            # 把本机当前目录的所有文件复制进容器的 /app
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
                                    # 构建时执行：装依赖（用清华源加速）
EXPOSE 8000                         # 声明容器用 8000 端口（文档性质）
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
                                    # 容器启动时执行的命令：跑起服务
```

关键点：
- `FROM`：不自己从零装 Python，站在官方镜像肩膀上
- `RUN` 是**构建时**执行（打包进镜像），`CMD` 是**容器启动时**执行
- `--host 0.0.0.0`：必须！让服务监听容器内所有网卡，否则容器外访问不到（只监听 127.0.0.1 等于只接受容器内部访问）

### 2. requirements.txt（依赖清单）
```
fastapi
uvicorn
requests
chromadb
```
把 pip 依赖列清楚，构建时装的就是这几个，换机器不会漏。

### 3. 代码的小改造：环境变量
```python
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
```
- 本地直接跑：没设环境变量，用默认值 localhost
- 容器里跑：通过 `-e` 注入容器专用地址
- **同一份代码，两种环境都能跑**——这就是环境变量的意义（不把配置写死在代码里）

## 四、完整命令流程

```powershell
# 1. 构建镜像（在 Dockerfile 所在目录）
docker build -t rag-chatbot .
#   -t rag-chatbot：给镜像起名；末尾的 . 指"用当前目录的 Dockerfile"

# 2. 跑起容器
docker run -d --name rag-server -p 8000:8000 -e OLLAMA_URL=http://host.docker.internal:11434 rag-chatbot
#   -d              后台运行
#   --name          给容器起名
#   -p 8000:8000    端口映射：宿主机8000 → 容器8000
#   -e KEY=VALUE    注入环境变量

# 3. 看日志
docker logs -f rag-server          # -f 持续跟踪，Ctrl+C 只退出查看、不停容器

# 日常管理
docker ps                          # 看正在跑的容器
docker stop rag-server             # 停止
docker start rag-server            # 再次启动（电脑重启后用这个，不用重新 run）
docker rm rag-server               # 删除容器（要先 stop）
docker images                      # 看本机所有镜像
```

## 五、两个必踩的坑（都踩过）

### 坑1：拉不动 Docker Hub 镜像
```
ERROR: failed to fetch anonymous token ... auth.docker.io ... 连接超时
```
Docker Hub 在国外。解决：Docker Desktop → Settings → Docker Engine 加国内镜像加速：
```json
"registry-mirrors": [
  "https://docker.m.daocloud.io",
  "https://docker.1panel.live",
  "https://docker.nju.edu.cn"
]
```
Apply & restart 后重新 build。（pip 装依赖同理，Dockerfile 里用了清华源）

### 坑2：容器里连不上宿主机的 Ollama
容器是隔离的小 Linux，它里面的 `localhost` 指**容器自己**，不是你的电脑！

两个设置缺一不可：
1. **宿主机 Ollama 放开监听**：设环境变量 `OLLAMA_HOST=0.0.0.0:11434` 后重启 Ollama
   （默认只监听 127.0.0.1，拒绝外部连接；0.0.0.0 表示允许所有网卡）
   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
   ```
2. **容器里用特殊域名访问宿主机**：`host.docker.internal`
   ```powershell
   -e OLLAMA_URL=http://host.docker.internal:11434
   ```
   这是 Docker 提供的域名，容器内自动解析成宿主机 IP。

## 六、端口映射图解

```
浏览器访问 127.0.0.1:8000（宿主机）
        │
        ▼
  宿主机 8000 端口  ──(-p 8000:8000)──▶  容器 8000 端口（uvicorn 在监听）
```
不做 `-p` 映射，容器里的服务对外完全不可见（容器网络是隔离的）。

## 七、词汇表

- **镜像（Image）**：只读模板，代码+运行环境打包在一起（类比：类 / 光盘）
- **容器（Container）**：镜像运行起来的实例（类比：对象 / 装好的系统）
- **Dockerfile**：构建镜像的说明书（FROM/COPY/RUN/CMD 等指令）
- **docker build**：按 Dockerfile 构建镜像
- **docker run**：用镜像启动容器
- **端口映射（-p）**：把宿主机端口转发到容器端口，外部才能访问容器服务
- **环境变量（-e）**：启动容器时注入配置，同一份镜像在不同环境用不同配置
- **host.docker.internal**：容器内访问宿主机的特殊域名
- **镜像加速（registry-mirrors）**：国内拉 Docker Hub 镜像慢，配置国内中转站
- **0.0.0.0**：监听所有网卡的地址（对比 127.0.0.1 只接受本机内部访问）
