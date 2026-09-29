# 小红书图文内容层次验证记录

## 自动验证

- `.\.venv\Scripts\python.exe backend\manage.py test generation.test_prompt_consistency -v 2`：退出码 0，5 项通过，0 项跳过。
- `.\.venv\Scripts\python.exe backend\manage.py test prompts.tests -v 2`：退出码 0，7 项通过，0 项跳过。
- `..\.venv\Scripts\python.exe manage.py test -v 1`（在 `backend` 目录执行）：退出码 0，148 项通过，1 项跳过。
- `.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run`：退出码 0，输出 `No changes detected`。
- `pnpm test`（在 `frontend` 目录执行）：退出码 0，29 个测试文件通过，375 项测试通过。
- `pnpm run typecheck`（在 `frontend` 目录执行）：退出码 0。
- `pnpm run test:typecheck`（在 `frontend` 目录执行）：退出码 0。
- `pnpm run build`（在 `frontend` 目录执行）：退出码 0，Vite 生产构建完成，转换 1949 个模块。
- `git diff --check`：退出码 0，无空白错误；Git 输出已有工作区文件的 LF/CRLF 转换预警。
- 直接使用模板占位符渲染 `outline_prompt.txt`、`image_prompt.txt`、`image_prompt_short.txt` 和 `content_prompt.txt`：退出码 0，四份模板均未留下必需占位符。

## 人工提示词检查

- 长短两套图片模板均明确只有“上图文字”可见；“画面描述”、结构角色和制作指令不得成为图片文字。
- 两套图片模板均把最终选择的图片风格置于主题、旧大纲和参考图中的泛化画风提示之前。
- 发布文案模板仍输出 `titles`、`copywriting` 和 `tags` 三个 JSON 字段。
- 本次仅改动系统默认提示词，并在 `data/prompt-backups/2026-09-11-xiaohongshu-content-hierarchy/` 保存四份修改前副本；用户创建、复制和共享的提示词存储未被重写。

## 限制

- 本次未调用任何付费上游文本或图片模型，也未进行 OCR 或实际生成图像的视觉对比。
- 图片文字渲染、构图和最终文案质量仍取决于当前配置的上游模型；本次验证覆盖模板协议、结构约束与本地回归测试。
