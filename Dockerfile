# Dockerfile：打包"RAG客服"的菜谱
# docker build 时照着这个文件一步步做出镜像

# 基础镜像：官方精简版 Python 3.11（箱子里先装好 Python）
FROM python:3.11-slim

# 容器里的工作目录（后续命令都在这下面执行）
WORKDIR /app

# 先只复制依赖清单并安装——Docker 有缓存，代码改动时不用重装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 再复制全部项目代码
COPY . .

# 声明容器对外用 8000 端口
EXPOSE 8000

# 容器启动命令：host 必须是 0.0.0.0（不能写 127.0.0.1，否则容器外访问不到）
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
