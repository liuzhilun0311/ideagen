# IdeaGen

多平台 AI 图文创作工具：Django 后端、Vue 前端、SQLite 数据库及独立图片后处理任务。

## 部署入口

- [本地与 Linux 常规部署](docs/deployment-local.md)
- [Docker 云端部署、更新、备份与恢复](docs/deployment-docker.md)
- Python 依赖：根目录 `requirements.txt`（引用 `backend/requirements.txt`）。
- 前端依赖：`frontend/package.json` 与 `frontend/pnpm-lock.yaml`，统一使用 pnpm。
- 生产配置模板：`.env.example`；服务商模板：两个 `*_providers.yaml.example`。
- Windows 本地已有依赖和前端构建时，可运行 `start_dev.bat`。
- [项目当前审计状态与未完成项](docs/project-status-2026-09-29.md)
- 可移植 Skill：`skills/ideagen-platform-content/`；打包文件：`ideagen-platform-content.zip`。

## 部署包

```text
python pack_deploy.py
```

生成 `ideagen_deploy.zip`，包含部署说明、源码、正式样图及配置模板，
不包含真实 API Key、环境文件、用户数据、虚拟环境和 node_modules。
首次安装需要联网下载依赖。部署包不是业务数据备份。

不要直接把整个工作目录上传公共仓库；真实配置、数据库和上传素材应单独保管。
默认 Docker 端口仅绑定服务器本机，公网通过 HTTPS 反向代理访问。

## GitHub 与云端 Docker 快速流程

上传前确认真实配置没有被 Git 跟踪：

```bash
git status --short
git ls-files image_providers.yaml text_providers.yaml .env
```

第二条命令应无输出。然后在 GitHub 新建仓库并上传当前项目源码。
云端执行：

```bash
git clone <你的仓库地址> /opt/ideagen
cd /opt/ideagen
cp .env.example .env
cp image_providers.yaml.example image_providers.yaml
cp text_providers.yaml.example text_providers.yaml
mkdir -p data history output user_configs
# 编辑 .env 和两个 YAML，填入真实配置
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:12398/api/health
```

详细的权限、HTTPS、备份、更新和故障处理见
[Docker 云端部署说明](docs/deployment-docker.md)。

## 可移植 Skill

`skills/ideagen-platform-content/` 是独立标准 Skill，只依赖 Python 标准库。
使用时传入 `--base-url`、`--api-key`、`--model`，或设置
`MODEL_BASE_URL`、`MODEL_API_KEY`、`MODEL_NAME`，即可调用 OpenAI-compatible
的 `/chat/completions` 接口。没有模型配置时可使用 `--prompt-only` 只生成提示词。
