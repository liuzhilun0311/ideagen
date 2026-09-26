"""
Django 项目设置 — AI 图文生成器 Django 版
"""
from pathlib import Path
import os

# 代码根目录（backend/，config/settings.py 的上级的上级）
BASE_DIR = Path(__file__).resolve().parent.parent
# 项目根目录（backend/ 的上级，含 frontend/、data/、history/ 等运行时数据）
PROJECT_ROOT = BASE_DIR.parent

# ---- 安全 ----
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'ideagen-django-dev-secret-key-change-me')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('1', 'true', 'yes')
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# ---- 应用 ----
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'accounts',
    'history',
    'generation',
    'providers',
    'prompts',
    'library',
    'postprocessing',
    'reference_assets',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'config.middleware.SkipCsrfForApi',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
# API 使用无尾斜杠路径（与前端一致），关闭自动补斜杠
APPEND_SLASH = False

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---- 数据库（SQLite，文件在项目根 data/ 目录） ----
DATA_DIR = PROJECT_ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
        'OPTIONS': {
            # Generation workers and history syncs can overlap briefly.
            # Let SQLite wait instead of failing immediately on a write lock.
            'timeout': 60,
            'transaction_mode': 'IMMEDIATE',
        },
    }
}

# ---- 密码与鉴权 ----
# 使用与 Flask 版一致的 PBKDF2 哈希格式，兼容旧数据迁移
AUTH_PASSWORD_VALIDATORS = []

# ---- 时区 ----
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = False

# ---- 静态文件 ----
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---- CORS（开发模式：前端 Vite 5173 / 3000） ----
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:3000',
]
CORS_ALLOW_HEADERS = ['*']
CORS_ALLOW_METHODS = ['*']

# ---- 业务配置 ----
# 运行端口（与 Flask 版保持一致，前端请求 /api 前缀）
SERVER_PORT = int(os.environ.get('DJANGO_PORT', '12398'))
HOST = os.environ.get('DJANGO_HOST', '0.0.0.0')

# 初始管理员密码（首次运行 initadmin 时创建）
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# 历史记录与图片数据目录（与 Flask 版结构一致：history/<user_id>/<task_id>/）
# 注意：这些是运行时数据，放在项目根目录（backend/ 外面），与代码分开
HISTORY_ROOT = PROJECT_ROOT / 'history'
OUTPUT_ROOT = PROJECT_ROOT / 'output'
USER_CONFIGS_ROOT = PROJECT_ROOT / 'user_configs'
for _p in (HISTORY_ROOT, OUTPUT_ROOT, USER_CONFIGS_ROOT):
    _p.mkdir(parents=True, exist_ok=True)

# A lease must outlive the bounded script invocation and publication work.
POSTPROCESSING_TIMEOUT_SECONDS = 300
POSTPROCESSING_LEASE_SECONDS = 360
POSTPROCESSING_MAX_ATTEMPTS = 3
