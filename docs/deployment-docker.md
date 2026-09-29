# IdeaGen Docker 云端部署说明

适用日期：2026-09-27。目标为一台 Linux 服务器，Docker Engine + Compose 插件，
单套 SQLite 数据，Web 与图片后处理 worker 共用持久化目录。
不需要在宿主机安装 Node.js、Python 或 ExifTool，镜像构建会安装。
首次构建需要访问 Docker 镜像仓库、Debian 包源、npm 和 Python 包源。

## 1. 准备发布文件

开发机项目根目录执行 `python pack_deploy.py`，上传 `ideagen_deploy.zip` 后
解压至服务器 `/opt/ideagen`。部署包是源码安装包，不含用户作品或密钥。
Windows Docker Desktop 也可用此 Compose，但必须切换到 Linux 容器并启动引擎。

```bash
cd /opt/ideagen
docker version
docker compose version
test -f .env || cp .env.example .env
test -f image_providers.yaml || cp image_providers.yaml.example image_providers.yaml
test -f text_providers.yaml || cp text_providers.yaml.example text_providers.yaml
mkdir -p data history output user_configs
```

编辑 `.env`，不要留空，不要用文档示例作为真实密码：

- `DJANGO_SECRET_KEY`：随机、至少50字符，创建后妥善保存，不随升级更换。
- `ADMIN_PASSWORD`：至少12字符，只作用于首次创建 `admin`，不会重置旧账号。
- `DJANGO_ALLOWED_HOSTS`：例如 `127.0.0.1,localhost,你的域名`，不能用 `*`，
  不含协议或端口；保留127.0.0.1供健康检查。
- `BIND_ADDRESS=127.0.0.1`：默认仅服务器本机，供 HTTPS 反向代理访问。
- `APP_PORT=12398`：宿主机端口。若修改，反向代理也要修改。
- `IDEAGEN_UID=10001`、`IDEAGEN_GID=10001`：容器非 root 用户，绑定目录需允许其读写。

可用 `openssl rand -hex 32` 生成随机密钥；密码可独立生成。编辑两个服务商 YAML，
填写实际可用的接口、模型及 API Key，或首次登录后在设置里完成。
缺少配置文件会直接失败，不再让 Docker 把文件路径误建为目录。

Linux 权限（在确认 `/opt/ideagen` 是本应用目录后执行）：

```bash
sudo chown -R 10001:10001 data history output user_configs
sudo chown 10001:10001 image_providers.yaml text_providers.yaml
chmod 600 .env
sudo chmod 600 image_providers.yaml text_providers.yaml
```

两个 YAML 挂载为可写，以便管理员从网页保存配置。只有服务器管理员应有宿主机访问权限。
Windows Docker Desktop 不执行 chown；确保目录已共享、当前用户可写。

## 2. 构建与启动

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 ideagen image-worker
curl --fail http://127.0.0.1:12398/api/health
```

启动时自动迁移、初始化管理员，然后启动 Web；Web 健康后才启动 worker。
Compose 的 `.env` 会自动读取；不要公开 `docker compose config` 的完整输出，里面有密钥。
默认健康检查只是 HTTP 可用性，不代表第三方模型额度或所有生成能力已验证。

查看本机页面：`http://127.0.0.1:12398`。远程首次测试可使用 SSH 隧道：

```bash
ssh -L 12398:127.0.0.1:12398 your-user@your-server
```

然后在自己的浏览器打开上述本机地址。不要为了测试把弱密码服务直接暴露公网。
若显式设置 `BIND_ADDRESS=0.0.0.0`，必须先配置安全组和防火墙限制来源。

## 3. 域名、HTTPS 与反向代理

将域名解析到服务器，开放443及证书签发需要的80端口，12398保持仅本机访问。
`deploy/nginx.conf.example` 是 HTTP 代理基础模板，需替换域名，
通过服务器面板或证书工具配置 TLS 证书、443监听及 HTTP 跳转，才可正式开放登录。
不能把 HTTP 示例直接当作已完成 HTTPS 部署。

关键配置：`proxy_buffering off`、`proxy_cache off`、900秒读取超时和32MB上传上限。
生成进度使用流式响应，开启代理缓冲会出现“生成中一直没进度”。
示例访问日志只记录路径、不记录查询参数，避免图片 URL 中的鉴权参数落入日志。
仅对可信本机代理开放应用端口；不要在应用前放允许任意 Host 的开放代理。

修改模板后运行 `sudo nginx -t`，成功后重载。配置好域名后将它加入
`.env` 的 `DJANGO_ALLOWED_HOSTS`，执行 `docker compose up -d` 使环境变量更新。

## 4. 备份与恢复

备份应包括 `data history output user_configs .env image_providers.yaml text_providers.yaml`。
其中含密码、API Key、参考素材和作品，应加密、限制权限并异地保管。
备份前等待生成结束，停止 Web 和 worker，避免 SQLite 与图片文件不一致。
下面备份不会停止其他 Docker 项目：

```bash
cd /opt/ideagen
docker compose stop
umask 077
sudo tar -czf /opt/ideagen-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
  data history output user_configs .env image_providers.yaml text_providers.yaml
# 确认 tar 成功后再继续；失败则检查空间和权限
docker compose up -d
```

恢复时先停止服务，在新的/已备份好的应用目录中解压指定备份，
恢复上述目录，重新检查 UID/GID 读写权限，然后启动同版本应用并验证。
不要将备份解压到其他项目目录；不要在进程运行时覆盖数据库。
跨版本回滚时必须同时恢复对应版本代码和升级前的数据，不能只换旧镜像。
示例：

```bash
cd /opt/ideagen
docker compose stop
sudo tar -xzf /opt/ideagen-backup-实际时间.tar.gz -C /opt/ideagen
# 重新执行第1节权限检查
docker compose up -d
```

从本机迁移已有数据也按这份清单复制；不要迁移 `.venv`、node_modules、
缓存或 Windows 的可执行文件，Linux 环境由镜像重建。

## 5. 更新与停止

1. 等待正在进行的生成结束，按上一节备份并确认备份可读取。
2. 更新代码时保留持久化目录、`.env` 和两个真实 YAML。
3. 先 `docker compose build`；失败时旧服务仍可继续使用。
4. 成功后 `docker compose stop`，再 `docker compose up -d`。
   不要让旧 worker 与执行新迁移的 Web 同时写库。
5. 查看健康状态、登录、历史作品、参考图片和样图；必要时先试生成一页，
   此操作会消耗实际模型额度。

停止：`docker compose stop`。删除服务容器：`docker compose down`。
绑定的宿主机业务目录会保留，但这不能替代备份；不要删除 data/history。
不要执行全局 `docker system prune` 或清空本机所有容器来解决本项目问题。

## 6. 常见故障

| 现象 | 检查方式 |
| --- | --- |
| 无法连接 Docker daemon | 启动 Docker Engine/Desktop，先确认 `docker version` 有 Server 信息 |
| 环境变量缺失 | 填写 `.env`，用 `docker compose config --quiet` 验证 |
| permission denied / readonly database | 核对4个目录和2个 YAML 的 UID/GID，SQLite 目录也必须可写 |
| YAML 是一个目录 | 停止服务，确认后移走误建空目录，创建真实配置文件 |
| 页面正常但后处理不动 | 查看 image-worker 日志、任务状态及共享目录权限 |
| 生成 429/额度不足 | 处理服务商限流/余额；重启容器不能增加额度 |
| 生成无进度、代理超时 | 关闭代理缓冲，增加读取超时，检查外层 CDN 限制 |
| 400 Invalid HTTP_HOST | 将访问域名加入 allowed hosts，不使用星号掩盖问题 |
| 磁盘增长 | 业务图片和备份需要定期归档；容器日志已限制大小，不能随意清空作品目录 |

本方案适用于单机部署，未实现多机共享队列或数据库。需要多实例时应另行设计迁移，
不要直接将 Compose 副本数调大。
