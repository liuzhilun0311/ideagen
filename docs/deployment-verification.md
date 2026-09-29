# 部署验收与清理记录

日期：2026-09-27。

## 已交付

- 根目录 requirements 入口，Windows 不安装 Gunicorn。
- pnpm 锁文件构建、多阶段 Docker 镜像、非 root 运行。
- Web + worker 共用持久化目录，明确生产密钥及初始密码要求。
- Linux systemd 模板、Nginx 流式反向代理模板。
- Windows/Linux 常规部署、Docker、权限、HTTPS、备份、恢复、更新说明。
- 安全部署包：`ideagen_deploy.zip`，不含真实配置、数据库、用户作品和依赖缓存。
- 删除重复且已过时的 `frontend/package-lock.json`，统一采用 pnpm。

## 实际验证

- `pip check`：无依赖冲突。
- `pip install --dry-run --ignore-installed -r requirements.txt`：Windows/Python3.11
  的全新依赖解析成功。没有替换现有环境里的包；这不等同 Linux 安装实测。
- pnpm10.19.0 frozen-lockfile 校验通过。
- 前端生产构建通过；仍有既有大包体积提醒。
- 后端278项测试：277通过、1跳过，包含打包排除与生产启动配置检查。
- 使用临时非真实环境变量执行 `docker compose config --quiet` 通过。
- ZIP 完整性检查通过；部署所需文件、84份样图原图/缩略图都在包中，
  未包含已知敏感配置路径、业务数据路径、node_modules、虚拟环境及截图缓存。
- 原本本地服务12399仍通过 readiness 检查。

## 尚未完成

### 容器实测

尝试启动 Docker Desktop，60秒后超时；随后 `docker build` 因缺少
`dockerDesktopLinuxEngine` 管道失败。镜像构建、容器启动和 Linux 运行
尚未实测，不能将配置检查等同于容器验收。

在 Docker 引擎恢复后，应在独立部署目录使用空数据及测试配置运行 build/up，
验证登录、42种样图、布局目录、数据库迁移和 worker 启动。
不要直接挂载正在被本地 Windows 服务写入的业务数据。
测试生成一页需额外消耗真实模型额度，不属于无费用部署检查。

### 临时目录删除

批量删除操作被执行环境拒绝，未执行；没有绕过限制。以下仍保留：

| 路径 | 文件数 | 大小 |
| --- | ---: | ---: |
| 根目录 `__pycache__/` | 1 | 3,917字节 |
| `frontend/test-results/` | 12 | 2,160,708字节 |
| `.superpowers/brainstorm/` | 4 | 8,542字节 |
| backend/tests/deai-image/deploy 下的 `__pycache__/` | 193 | 1,368,334字节 |

这些约3.4MiB临时内容已经从 Docker 上下文和部署包排除。
其中旧测试截图被先前验收文档引用，删除只影响回看截图，不影响应用运行。
用户可在资源管理器确认路径后删除；Python 缓存后续运行会重新产生。

## 明确保留

所有作品、上传素材、用户配置、数据库与备份、42张正式样图、生成原始记录、
源代码及测试、当前 `.venv`、node_modules、`frontend/dist`。
后面三项仍用于当前本地运行，不因云端打包而删除。
