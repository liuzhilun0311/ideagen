# IdeaGen 本地与常规部署说明

适用日期：2026-09-27。命令默认从项目根目录执行。
云服务器优先使用 [Docker 部署](deployment-docker.md)；本文件覆盖 Windows 本机和 Linux 非 Docker 部署。

## 1. 依赖与数据

基准环境：Python 3.11、Node.js 22、pnpm 10.19.0。
Python 依赖版本定义在 `backend/requirements.txt`，根目录 requirements 引用它，
不要对开发机直接 `pip freeze` 覆盖项目依赖。间接依赖由 pip 解析。

还需 ExifTool：它不是 pip 包，用于图片后处理的元数据清理。
Windows 从 ExifTool 官方发行安装，确保 `exiftool.exe` 在 PATH 中；
Linux Debian/Ubuntu 使用 `sudo apt-get install libimage-exiftool-perl`。
没有 ExifTool 时图像处理可能仍运行，但元数据清理不完整。

保留以下目录和文件：

| 路径 | 用途 |
| --- | --- |
| `data/` | SQLite、参考素材、运行数据及备份 |
| `history/` | 作品图片及后处理结果 |
| `output/` | 输出与模型样图生成记录 |
| `user_configs/` | 用户私有配置、模板 |
| 两个 `*_providers.yaml` | 真实服务商配置与密钥 |
| `.env` | 云端运行环境配置 |

不要只迁移数据库而漏掉图片目录。不得让 Windows 进程和 Linux 容器同时写同一套数据。

## 2. Windows 首次安装

在 PowerShell 中进入项目根目录：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
npm install --global pnpm@10.19.0
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
exiftool -ver
```

不需要激活虚拟环境。Gunicorn 仅在非 Windows 系统安装；
Windows 本地使用 Django runserver，不能把它作为公网生产服务。

仅在真实配置文件不存在时复制模板，已有配置不要覆盖：

```powershell
if (-not (Test-Path image_providers.yaml)) {
    Copy-Item image_providers.yaml.example image_providers.yaml
}
if (-not (Test-Path text_providers.yaml)) {
    Copy-Item text_providers.yaml.example text_providers.yaml
}
$env:ADMIN_PASSWORD = Read-Host '设置首次管理员密码（至少12位）'
.\.venv\Scripts\python.exe backend/manage.py migrate --noinput
.\.venv\Scripts\python.exe backend/manage.py initadmin
```

编辑配置文件里的模型、协议、地址和 API Key，或登录后在服务商管理中配置。
模板中的服务商仅是示例，不保证你的账号有对应模型权限。
初始用户名是 `admin`。`ADMIN_PASSWORD` 只在首次创建管理员时生效，不会重置已有密码。
注意：直接启动开发模式且不设置该变量会沿用旧的开发默认密码；不要如此用于公网。

两个终端分别启动：

```powershell
# 终端一：仅允许本机访问
.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:12399
```

```powershell
# 终端二：图片后处理，不是图片模型调用服务
.\.venv\Scripts\python.exe backend/manage.py process_images
```

浏览器打开 `http://127.0.0.1:12399`。也可以使用现有 `start_dev.bat`，
它会启动后台 Web 和 worker；其 Web 监听所有网卡，仅应在可信本地网络使用。
不要重复启动 worker。前端改动后运行 `pnpm --dir frontend build`，刷新浏览器。

### 前端开发模式

终端一启动后端 `127.0.0.1:12398`；终端二运行 `pnpm --dir frontend dev`；
浏览器使用 `http://localhost:5173`。Vite 的 `/api` 代理指向 12398，
与构建版访问 12399 的方式不同，不要混用端口。

## 3. Linux 常规部署

以下假设代码位于 `/opt/ideagen`，已安装 Python 3.11（含 venv 模块）、
Node.js 22 和 pnpm 10.19.0。发行版包名可能不同，先确认 `python3.11 --version`。

```bash
cd /opt/ideagen
sudo apt-get update
sudo apt-get install -y libimage-exiftool-perl libjpeg62-turbo zlib1g libfreetype6
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
test -f image_providers.yaml || cp image_providers.yaml.example image_providers.yaml
test -f text_providers.yaml || cp text_providers.yaml.example text_providers.yaml
test -f .env || cp .env.example .env
```

编辑 `.env`：设置随机 `DJANGO_SECRET_KEY`（至少50字符）、首次管理员密码（至少12字符），
`DJANGO_ALLOWED_HOSTS` 填实际域名/IP，保留 `127.0.0.1`。
该文件的简单 `KEY=value` 格式可供 systemd 使用。不要向聊天、日志或代码仓库暴露它。

```bash
# 生成随机值，分别填入 .env，不使用示例值
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(50))"
```

创建专用用户（已存在则跳过），设置权限并启用提供的 systemd 服务：

```bash
id ideagen >/dev/null 2>&1 || sudo useradd --system --home /opt/ideagen --shell /usr/sbin/nologin ideagen
sudo chown -R ideagen:ideagen /opt/ideagen
sudo chmod 600 /opt/ideagen/.env /opt/ideagen/image_providers.yaml /opt/ideagen/text_providers.yaml
sudo cp deploy/ideagen-web.service deploy/ideagen-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ideagen-web
curl --fail http://127.0.0.1:12398/api/health
sudo systemctl enable --now ideagen-worker
sudo systemctl status ideagen-web ideagen-worker
```

Web 启动器自动迁移、初始化管理员及收集管理后台静态文件，再启动 Gunicorn；
worker 只处理队列。systemd 会加载 `.env`，普通 `python` 命令不会自动加载它。
首次必须等 Web 健康后再启 worker；更新时先停两个服务。
默认单 Web 进程、8线程；不要自行横向扩容 SQLite 或增加 Web 进程。

日志：`journalctl -u ideagen-web -u ideagen-worker -n 100 --no-pager`。
云端必须设置 HTTPS 反向代理，并禁止外网直接访问12398，配置参考 Docker 说明。
应用自身的用户管理位于前端；Django 原生 `/django-admin/` 不是本产品的账户管理入口。

## 4. 验证与常见问题

```bash
.venv/bin/python -m pip check
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py showmigrations
curl --fail http://127.0.0.1:12398/api/health
```

- 只有 API 信息、没有界面：检查 `frontend/dist/index.html`，重新构建前端。
- 页面打开但生成失败：核对模型配置、权限、网络、额度；健康检查不会调用付费模型。
- 后处理一直排队：检查 worker 和 ExifTool；别误以为只启动 Web 就够了。
- 提示数据库锁定：避免多套进程写同一数据，不要放网络共享盘上。
- pip 安装失败：核对 Python 版本和包索引可达性，不要直接删除版本约束。
- 备份与恢复：参照 Docker 说明的数据清单；常规部署先用 systemctl 停止两服务，
  备份完成后按 Web 健康、worker 的顺序启动。
