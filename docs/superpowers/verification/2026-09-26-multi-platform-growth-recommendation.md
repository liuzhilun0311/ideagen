# 多平台获客推荐兼容回归验证

验证日期：2026-09-26

## 已执行

### 前端定向回归

命令：

```text
pnpm exec vitest run tests/studio/platformRecommendations.test.ts tests/studio/catalogPreview.test.ts tests/studio/outline.test.ts tests/generation/restore.test.ts
```

结果：通过。

- 4 个测试文件
- 34 个测试
- 0 个失败

覆盖内容：

- 旧状态缺少 `platform` / `goal` 时回退为 `auto`
- 平台与获客目标契约
- 布局和风格目录元数据、样图路径和缺图占位
- 大纲生成流程读取推荐结果
- 历史记录恢复流程

### 前端全量基线

曾执行一次全量 Vitest。结果为 40 个测试文件中 33 个通过、7 个失败，共 424 个测试中 410 个通过、14 个失败。

本次没有继续重跑全量测试。

## 失败列表

以下失败来自全量基线，不属于 Task 7 定向回归：

1. `tests/models/workspace.test.ts`
   - 3 个模型复制相关断言失败。
   - 与平台、获客目标、目录兼容回归无直接关系。

2. `tests/studio/copyOptions.test.ts`
   - 旧断言未包含默认 `emoji_level: "克制"`。
   - 属于现有文案选项默认值变化。

3. `tests/studio/imageStyle.test.ts`
   - 目录数量仍断言 31，但当前目录已有 43 项。
   - 该断言受新增获客型风格影响，属于目录扩展后的陈旧数量断言。
   - 另有单页重绘调用参数形状断言失败，与 Task 7 文件无关。

4. `tests/studio/postprocessing.test.ts`
   - 旧断言期望去 AI 化强度为 `light`，实际默认值为 `medium`。
   - 属于既有默认值调整，与本次 Task 7 无关。

5. `tests/studio/promptCatalog.test.ts`
   - 旧断言仍期望 31 个图片风格，实际为 43 个。
   - 与目录扩展有关，属于陈旧数量断言，不是兼容逻辑崩溃。

6. `tests/studio/studio.test.ts`
   - 内容生成调用参数包含新增的 `emoji_level`，旧断言未更新。
   - 与本次平台/目录兼容回归无直接关系。

7. `tests/studio/workspace.test.ts`
   - 4 个界面控制查找断言失败。
   - 与 Task 7 指定的历史恢复、目录完整性和推荐读取无直接关系。

## 后端状态

使用项目根目录的 `.venv`，从 `backend` 目录执行了后端回归：

```text
..\.venv\Scripts\python.exe manage.py test generation prompts history -v 1
```

结果：172 项测试中 171 项通过，1 项失败。失败是既有的
`test_seed_preserves_current_admin_base_and_independent_restore_default` 查询数量断言，
实际执行 4 条查询而断言期望 3 条；没有业务断言失败。

本次新增相关专项测试均通过：

- 平台与推荐协议
- 布局与风格目录
- 文案与图片一致性
- 大纲服务和历史恢复

## 结论

- Task 7 指定的前端兼容回归：通过。
- 前端已验证旧历史记录默认恢复 `auto`，并能读取 `growth_recommendation`。
- 前端目录新增布局/风格元数据和缺图状态：通过。
- 未发现由 Task 7 兼容逻辑直接导致的定向测试失败。
- 后端 generation/prompts/history 回归为 171/172 通过，剩余 1 项为既有查询数量断言。
- 未修改业务代码，未提交 commit。
