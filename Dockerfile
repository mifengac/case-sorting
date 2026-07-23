# 笔录 OCR 离线镜像：纯 pip 依赖，无需 apt
FROM python:3.10-slim

WORKDIR /app

# 先装依赖（利用构建缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --default-timeout=100 --retries 5 \
 && pip uninstall -y opencv-python \
 && pip install --no-cache-dir opencv-python-headless \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --default-timeout=100 --retries 5
# 说明：slim 镜像没有 libGL/libxcb 等图形库，opencv-python 会 import 失败，
# 必须换成不需要图形库的 headless 版（功能一样，仅去掉 GUI 部分）。

# 再拷代码、模型、启动脚本
COPY app/ app/
COPY models/ models/
COPY run.sh .

ENV BILU_OCR_HOST=0.0.0.0 \
    BILU_OCR_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
