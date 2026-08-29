# 多阶段构建：阶段1 前端（Vue 3），阶段2 后端（Django）

# ============ 阶段1: 构建前端 ============
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============ 阶段2: 最终镜像（Django + 前端产物） ============
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=False

# 系统依赖（Pillow 需要的底层库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo zlib1g libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 项目代码（后端在 backend/，前端源码在 frontend/）
COPY . .

# 前端产物（从阶段1拷贝）
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 运行时数据目录（挂载/持久化）
RUN mkdir -p history output user_configs data

EXPOSE 12398

# 迁移 + 建 admin + 启动（后端代码在 backend/，先进去再执行）
CMD ["sh", "-c", "cd backend && python manage.py migrate --noinput && python manage.py initadmin && gunicorn config.wsgi:application --bind 0.0.0.0:12398 --workers 2 --threads 8 --timeout 600"]
