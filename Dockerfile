# 笔录 OCR 离线镜像：纯 pip 依赖，无需 apt
FROM python:3.10-slim

WORKDIR /app

# 先装依赖（利用构建缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷代码、模型、启动脚本
COPY app/ app/
COPY models/ models/
COPY run.sh .

ENV BILU_OCR_HOST=0.0.0.0 \
    BILU_OCR_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
