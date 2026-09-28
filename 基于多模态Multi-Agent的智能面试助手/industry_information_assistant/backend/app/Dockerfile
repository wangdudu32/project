# 从 industry_information_assistant/backend 构建：
# docker build -f app/Dockerfile -t industry-backend .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./
EXPOSE 8001
CMD ["uvicorn", "app_main:app", "--host", "0.0.0.0", "--port", "8001"]
