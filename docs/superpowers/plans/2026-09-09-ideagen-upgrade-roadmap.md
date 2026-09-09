# IdeaGen 升级分阶段路线

关联设计：`docs/superpowers/specs/2026-09-09-ideagen-product-upgrade-design.md`。

本文件是整体范围与验收映射，不冒充逐文件实施计划。按照 writing-plans 的范围检查，将整体升级拆为三个能够独立评审的子项目。第一阶段的逐步代码和测试见同目录 `2026-09-09-generation-reliability.md`；第二、三阶段在前置接口稳定后各自产生实施计划。

## 当前基线

2026-09-09 本机检查：

- `frontend` 中 `npm run typecheck`：退出码 0。
- 根目录 `.venv\Scripts\python.exe backend/manage.py check`：无问题。
- `docker version`：客户端与服务端均返回版本信息。
- 系统 Python 缺少 `corsheaders`，后端验证必须使用项目 `.venv`。
- UI/UX 技能目录仅含说明文件，缺少 `scripts/search.py`，因此设计系统搜索未运行成功；采用已读取的技能规范。
- 既有未提交文件：`.dockerignore`、`docker-compose.yml`、两个供应商 example 文件，实施时保留其内容。
- 本轮没有进行业务代码修改、付费生成、生产构建或容器启动验证。

## 阶段 1：生成可靠性

交付：保留现有页面与 API，先使图片进度和任务结束状态可靠。

责任文件：

- `frontend/src/stores/generator.ts`：进度幂等、结束状态、取消保留结果。
- `frontend/src/composables/useGenerationRestore.ts`：创建记录失败时显式报错。
- `frontend/src/composables/useGenerationRunner.ts`：等待请求完成、拒绝重复启动、忽略旧回调、识别没有 finish 的断流。
- `frontend/tests/generation/`：离线单元测试，不使用真实供应商。

边界：这一阶段不宣称解决后端跨进程取消、草稿覆盖或完整 SSE 语法解析。它们分别由阶段 3 和阶段 2 的接口任务承担。

完成门槛：新增回归用例先失败后通过；类型检查和生产构建通过；现有界面仍能使用。

## 阶段 2：响应式创作产品

执行顺序与文件归属：

1. 全局外壳与设计系统：`frontend/src/App.vue`、`frontend/src/assets/css/{variables,base,components}.css`，新增 `frontend/src/components/layout/AppShell.vue`。统一 Lucide 图标、焦点、间距与移动导航；主操作使用实色蓝，青绿用于成功，橙色只标警告，紫色不作为大面积背景。
2. 极简首页与真实参数：`frontend/src/views/HomeView.vue`、`frontend/src/components/home/ComposerInput.vue`、`frontend/src/assets/css/home.css`，新增 `frontend/src/features/templates/catalog.ts`。首页动作实际触发一次大纲请求，成功后进入工作台；模板默认仅启用已实现的图文套装。比例和风格只有在后端适配器真正消费时才展示为可操作控件，不放无效选项。
3. 创作工作台：新增 `frontend/src/views/WorkspaceView.vue`、`frontend/src/components/workspace/{PageList,PageEditor,GenerationPanel}.vue`，修改 `frontend/src/router/index.ts`。旧 `/outline`、`/generate` 兼容跳转，保留历史记录恢复与来源信息。桌面三栏；768px 双栏；375/390px 结构、编辑、生成分区。
4. 文案与草稿契约：现有 `Page` 只有 `index/type/content`，标题、正文、标签属于整套作品，不伪装成每页已有字段。当前页编辑大纲与配图，整套发布文案用独立标签页编辑。新增 `frontend/src/composables/useDraftSave.ts`，修改 `backend/history/views.py`、`backend/history/services.py`，序列化保存请求并使用版本冲突检测，旧响应不能覆盖新编辑；跨设备冲突提示重新加载或另存副本。
5. 图片与页面对应：大纲重新排序、删除或插入后不得仅改数组索引导致图片错配。新草稿引入稳定页面 ID，API 调用映射为旧 index；历史记录读写兼容无 ID 数据。未完成此映射前禁用带生成结果的结构变更，提供明确确认与失效处理。
6. 恢复与 SSE：`frontend/src/api/client.ts`、`frontend/src/api/image.ts`、`frontend/src/stores/generator.ts`。使用经过验证的 SSE 解析库覆盖 CRLF、跨块 UTF-8、多行 data、正常 EOF 与缺少 finish；刷新把旧 running 转为中断可恢复，按服务端任务状态恢复。草稿按用户 ID 隔离，退出登录清理内存与当前用户引用，参考 File 刷新丢失时明确提示重新选择。
7. 结果与交付：`frontend/src/views/ResultView.vue`、`frontend/src/components/result/ContentDisplay.vue`、`frontend/src/composables/useDeaiDownload.ts`。作品原图可检查、文案可复制、下载可重试；手机和不支持目录选择的浏览器走 ZIP。去 AI 化只是图像处理选项，不承诺通过检测或匿名化。
8. 次要模块：`frontend/src/views/{HistoryView,SettingsView,PromptManageView,UsersView,LoginView}.vue` 及现有 settings/common 组件。保留权限、搜索分页、共享规则和模型选择行为，统一确认弹窗和错误反馈，不重写无关供应商协议。

设计补充原则：

- 首页是可操作创作入口，不是营销落地页；真实模板示例或已有作品作为视觉资源，无装饰渐变背景。
- 新增教程不占用界面，控件使用简短业务标签和必要状态提示。
- 上传限制沿用最多 5 张；文件类型和大小在服务端、前端均校验，错误可读。
- 生成状态模型分大纲、图片、文案，禁止全局单一 busy 覆盖独立任务；取消不能误伤其他任务。
- 只交付浅色主题；不新增一个未经测试的暗色开关。

验收：375、390、768、1024、1440 宽度截图；键盘导航、触控、无横向溢出；参考图、预览图实际加载；离线模拟供应商 E2E 覆盖成功、失败、取消、恢复、保存和下载。真实 API 验证单独报告，不用 mock 通过替代。

## 阶段 3：Docker 生产部署

责任文件：`Dockerfile`、`docker-compose.yml`、`.dockerignore`、新增 `deploy/nginx.conf`、`deploy/entrypoint.sh`、`.env.example`、`docs/deployment.md`；修改 `backend/config/settings.py`、`backend/generation/services/task_cancel.py` 及其调用点。

实施约束：

- Compose 单应用实例 + Nginx，同域 `/api` 与 SPA；后端仅在内部网络暴露。
- 使用 Gunicorn 生产进程。现有两个 worker 与进程内取消集合不兼容：改为 SQLite 持久化、按用户和任务运行 ID 记录取消状态，所有 worker 读取同一个运行记录；禁止靠减少 worker 将问题隐藏。
- 生成 API、取消 API、重试 API 传递运行 ID，并验证所有权。取消旧任务不能影响新任务或其他生成类别。
- Nginx 对 API/SSE 关闭缓冲并设置超时；`history`、供应商 YAML、数据库不作为公开静态目录。
- 将 Django secret、管理员初始密码和 allowed hosts 改为生产必填，拒绝示例默认值；日志不记录 token、API Key、含 token 查询串。
- `data`、`history`、`output`、`user_configs` 与供应商配置持久化。供应商配置需要应用读写，不能错误挂只读后又允许设置页修改。
- 使用白名单 COPY 构建镜像，避免私钥、YAML 实际配置、历史图片、数据库和 `.venv` 进入镜像。
- 支持 HTTPS 证书挂载与续期文档；未提供域名证书时只验收本地 HTTP，不能宣称公网 HTTPS 已验证。
- SQLite 默认定位单服务器轻量使用；通过生成期间并发保存、取消、历史读取测试检查锁冲突。多实例扩容另行设计数据库与队列。
- SQLite 使用一致性备份方式，禁止直接复制活跃数据库文件当作可靠备份；同时备份作品和配置，并在临时目录恢复验证。
- 健康检查通过不等于功能通过：还需要通过 Nginx 验证 SSE、取消、静态资源、鉴权图片、SPA 深链刷新和 ZIP 下载。
- 所有部署测试使用独立 Compose project 和临时测试数据目录，不挂载用户当前生产资料运行初始化或迁移。

完成门槛：`docker compose config --quiet`、镜像构建、隔离容器启动、健康检查、持久化重启、双 worker 取消回归、备份恢复通过。真实云域名部署需要用户提供服务器访问方式，不在没有访问权限时宣称完成。

## 设计覆盖映射

| 设计要求 | 负责阶段 | 验证证据 |
| --- | --- | --- |
| 首页极简、模板扩展 | 2.1-2.2 | 表单与参数 E2E、截图 |
| 连续工作台与图文编辑 | 2.3-2.5 | 历史恢复、稳定 ID、编辑持久化测试 |
| 状态、取消、重试 | 1、2.6、3 | 单测、断流 E2E、跨 worker 集成测试 |
| 结果预览、下载、去 AI 化 | 2.7 | 原图检查、ZIP 内容验证、下载失败重试 |
| 历史、设置、提示词、用户 | 2.8 | 权限和主要操作回归 |
| 响应式、图标、无障碍 | 2 全阶段 | 五档视口、键盘、对比度检查 |
| Docker、SSE、持久化、HTTPS | 3 | 隔离部署及代理集成测试 |
| 日志与备份说明 | 3 | 脱敏检查、恢复演练 |

## 执行方式

推荐子代理分任务执行，主代理检查 diff、运行验证再进入下一任务。若所需执行技能不可用，应如实说明并采用当前会话逐任务执行，不声称调用过缺失技能。三阶段均不得回退用户原有改动。
