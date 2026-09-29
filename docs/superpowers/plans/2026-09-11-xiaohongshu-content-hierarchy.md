# 小红书图文内容层次 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the bundled default prompts so IdeaGen generates structured Xiaohongshu image cards and scan-friendly publishing copy while retaining the existing API and page-text formats.

**Architecture:** Keep the current text protocol of `上图文字` and `画面描述`; use the outline prompt to instruct page roles and information components rather than adding persisted fields. Both image prompt variants interpret that protocol identically and receive the final selected style through the existing style wrapper. The publishing-copy prompt consumes the same outline but organizes it independently for Xiaohongshu.

**Tech Stack:** Django 5.2 prompt services and `SimpleTestCase`; plaintext prompt templates; Vue frontend verification through pnpm/Vite.

## Global Constraints

- Modify only bundled default prompts and their tests/documentation; do not change API response fields, database models, migrations, page data, or frontend editor data.
- Preserve the current page separators (`<page>`) and page blocks (`[封面]`, `[内容]`, `[总结]`, `上图文字：`, `画面描述：`).
- Preserve `titles`, `copywriting`, and `tags` for publishing-copy output.
- User-created, copied, shared, and manually edited prompts must not be rewritten.
- Final user-selected image style remains higher priority than topic wording, old outline style hints, references, or generic style language.
- Do not make paid upstream text or image calls during tests.
- Use ASCII for code and paths; Chinese is required in user-facing prompt and documentation text.
- Run verification commands from repository root `F:\02_ai_tools_projects\IdeaGen`.

---

### Task 1: Protect the Prompt Contract and Create a Reversible Baseline

**Files:**
- Create: `data/prompt-backups/2026-09-11-xiaohongshu-content-hierarchy/outline_prompt.txt`
- Create: `data/prompt-backups/2026-09-11-xiaohongshu-content-hierarchy/image_prompt.txt`
- Create: `data/prompt-backups/2026-09-11-xiaohongshu-content-hierarchy/image_prompt_short.txt`
- Create: `data/prompt-backups/2026-09-11-xiaohongshu-content-hierarchy/content_prompt.txt`
- Modify: `backend/generation/test_prompt_consistency.py`

**Interfaces:**
- Consumes: Existing template placeholders: `{topic}`, `{outline}`, `{page_content}`, `{page_type}`, `{full_outline}`, `{user_topic}`.
- Produces: A regression-test contract for all four bundled prompts and an exact source backup before template contents change.
- Depends on: `Path` and `SimpleTestCase` already used by `backend/generation/test_prompt_consistency.py`.

- [ ] **Step 1: Write the failing prompt-hierarchy tests**

Add the following class below `DefaultPromptConsistencyTests` in `backend/generation/test_prompt_consistency.py`:

```python
class DefaultPromptHierarchyTests(SimpleTestCase):
    root = Path(__file__).parent / 'prompts'

    def _source(self, name):
        return (self.root / name).read_text(encoding='utf-8')

    def _render(self, name):
        return self._source(name).format(
            topic='提升生活质量的 6 个小习惯',
            outline='[内容]\n上图文字：\n标题：规律作息\n正文：固定一个可执行的入睡时间。\n画面描述：日夜节奏关系图',
            page_content='[内容]\n上图文字：\n标题：规律作息\n正文：固定一个可执行的入睡时间。\n画面描述：日夜节奏关系图',
            page_type='content',
            full_outline='封面\n<page>\n规律作息\n<page>\n总结',
            user_topic='提升生活质量的 6 个小习惯',
        )

    def test_outline_prompt_requires_page_roles_components_and_visual_anchor(self):
        text = self._render('outline_prompt.txt')
        for phrase in ('页面角色', '至少使用三种页面结构', '短标签', '视觉主体'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_image_prompt_variants_keep_visible_text_and_layout_contract(self):
        for name in ('image_prompt.txt', 'image_prompt_short.txt'):
            with self.subTest(name=name):
                text = self._render(name)
                for phrase in ('上图文字', '画面描述', '主结构', '视觉主体', '最终风格'):
                    self.assertIn(phrase, text)
                self.assertIn('不得成为可见文字', text)
                self.assertIn('提升生活质量的 6 个小习惯', text)
                self.assertIn('规律作息', text)

    def test_content_prompt_supports_xiaohongshu_scan_structure_without_breaking_json(self):
        source = self._source('content_prompt.txt')
        text = self._render('content_prompt.txt')
        for phrase in ('小红书', '4至7个短段落', '只采用一种信息标记方式', '0至3个', 'titles', 'copywriting', 'tags'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn('{{', source)
        self.assertIn('"titles"', text)
        self.assertNotIn('{topic}', text)
        self.assertNotIn('{outline}', text)
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe backend\manage.py test generation.test_prompt_consistency.DefaultPromptHierarchyTests -v 2
```

Expected: FAIL because the current prompts do not yet contain page-role, visual-anchor, final-style, and Xiaohongshu structural requirements.

- [ ] **Step 3: Create the exact prompt backup directory and copy all four source templates**

Run:

```powershell
$backup = 'data\prompt-backups\2026-09-11-xiaohongshu-content-hierarchy'
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item 'backend\generation\prompts\outline_prompt.txt' "$backup\outline_prompt.txt"
Copy-Item 'backend\generation\prompts\image_prompt.txt' "$backup\image_prompt.txt"
Copy-Item 'backend\generation\prompts\image_prompt_short.txt' "$backup\image_prompt_short.txt"
Copy-Item 'backend\generation\prompts\content_prompt.txt' "$backup\content_prompt.txt"
```

Verify all four backups exist and differ from no source at this point:

```powershell
Get-FileHash `
  'backend\generation\prompts\outline_prompt.txt', `
  'backend\generation\prompts\image_prompt.txt', `
  'backend\generation\prompts\image_prompt_short.txt', `
  'backend\generation\prompts\content_prompt.txt', `
  'data\prompt-backups\2026-09-11-xiaohongshu-content-hierarchy\outline_prompt.txt', `
  'data\prompt-backups\2026-09-11-xiaohongshu-content-hierarchy\image_prompt.txt', `
  'data\prompt-backups\2026-09-11-xiaohongshu-content-hierarchy\image_prompt_short.txt', `
  'data\prompt-backups\2026-09-11-xiaohongshu-content-hierarchy\content_prompt.txt'
```

- [ ] **Step 4: Run the existing format contract test before prompt changes**

Run:

```powershell
.\.venv\Scripts\python.exe backend\manage.py test generation.test_prompt_consistency.DefaultPromptConsistencyTests -v 2
```

Expected: PASS. This establishes that the baseline templates format correctly before replacing their text.

- [ ] **Step 5: Commit the test contract and backup baseline**

Run:

```powershell
git add -- `
  backend/generation/test_prompt_consistency.py `
  data/prompt-backups/2026-09-11-xiaohongshu-content-hierarchy
git commit -m "test: lock prompt hierarchy contract"
```

Expected: one commit containing only the prompt tests and four backup files.

### Task 2: Generate Component-Based Page Outlines and Hierarchical Image Cards

**Files:**
- Modify: `backend/generation/prompts/outline_prompt.txt`
- Modify: `backend/generation/prompts/image_prompt.txt`
- Modify: `backend/generation/prompts/image_prompt_short.txt`
- Test: `backend/generation/test_prompt_consistency.py`

**Interfaces:**
- Consumes: Existing outline request fields and `recommendation_instruction()` appended in `backend/generation/services/outline.py`.
- Produces: The same existing page protocol plus independent style recommendation metadata; both image prompt variants consume `{page_content}`, `{page_type}`, `{full_outline}`, and `{user_topic}`.
- Must preserve: `OutlineService._parse_outline()` compatibility with `[封面]`, `[内容]`, `[总结]` and `<page>` only.

- [ ] **Step 1: Replace the outline template with the component-based instruction**

Replace `backend/generation/prompts/outline_prompt.txt` with the following content:

```text
你是面向小红书知识图文的内容编辑。将用户的想法整理成一套清晰、可信、适合手机阅读的逐页内容。目标不是堆砌“爆款”措辞，而是让读者一眼看到重点、按页理解逻辑。

用户要求：
{topic}

工作原则：
1. 先理解读者、主题和目的，再安排页面。教程按步骤，清单按分类，解释按概念到例子，对比按同一维度；不要把所有主题都套成同一种结构。
2. 用户明确要求的页数、语言和语气优先；否则默认5页，信息不足时可缩减，通常2至18页。不要为了凑页数重复内容或编造事实。
3. 第一页是封面，标题说明主题与真实价值；最后一页做必要总结，中间每页一个核心重点。封面的数量、结论和承诺必须由正文兑现。
4. 不编造价格、地址、开放时间、统计、功效、人物证言或亲身经历。缺少依据的具体断言应省略或明确为假设，不把常识性建议包装成用户亲测。
5. 上图文字是图片和发布文案共用的内容依据。整套的名称、数字、步骤、单位、观点保持一致。
6. 画面描述只负责表达内容，不新增事实。不要把插画中的虚构人物、场景或道具写成真实经历。
7. 按主题、读者与信息结构推荐整套视觉风格，推荐通过独立元数据返回，不写入页面内容。推荐不是最终决定，图片生成时服从用户最终选择。画面描述保持媒介中立，只描述主体与信息关系，不固定为摄影、漫画或某种配色。

页面角色与信息层次：
8. 先为每页选择一个页面角色，再写上图文字和画面描述。可用角色包括：封面、清单、步骤、对比、分类、关系、例子、总结。不要新增机器字段；通过上图文字和画面描述体现页面角色。
9. 每页只使用一种主结构。清单用2至4个短要点；步骤必须有先后关系和必要判断条件；对比必须使用同一维度；分类按类别、场景、优先级或象限组织；关系仅在存在真实组成、因果或流程关系时使用箭头；总结给一个可执行的下一步，不新增结论。
10. 整套至少使用三种页面结构；相邻正文页优先采用不同结构。封面和总结不要写成普通列表页。
11. 正文页默认控制在35至90个汉字左右。单个信息组件优先使用“短标签：一句具体解释”，通常2至4个组件。必须保留的限定条件优先于字数限制；内容过密时拆页，不缩小字体，不静默删掉关键信息。
12. 每页必须有一个服务于内容的视觉主体，例如主体插图、实物组合、关系图、步骤路径、对比区域或分类布局。画面描述说明视觉主体、阅读顺序和信息关系，不写最终画风、固定配色或会被误印的制作说明。
13. 每页只突出1至2个关键词、数字或结论。非必要不加emoji，不重复口号或机械互动引导。

必须严格遵守输出格式：
- 输出逐页大纲，以及请求末尾约定的独立风格推荐元数据；不输出分析、解释或代码围栏。
- 使用 <page> 分隔页面。每页第一行是 [封面]、[内容] 或 [总结]。
- 每页必须有“上图文字：”与“画面描述：”两个分区。
- 上图文字给出最终可直接印在图片上的标题、短标签、正文或要点，不写“请设计”“建议放置”“使用图标”等制作指令。
- 画面描述说明本页的视觉主体、阅读顺序、信息关系和图解方式，不重复整段正文，不把分区名称或提示词印在图中。
- 不使用竖线表格。

格式示例（只学习结构，不照搬主题和事实）：
[封面]
上图文字：
标题：整理桌面，从三个区域开始
副标题：常用、备用、待处理
画面描述：
以三个清楚的桌面区域作为视觉主体，标题位于干净留白处，阅读顺序从标题到三个区域。

<page>
[内容]
上图文字：
标题：常用物品留在顺手处
要点：
常用：每天使用的物品集中摆放
备用：不常用的物品另外收纳
画面描述：
以“常用”和“备用”并列分区作为视觉主体，两组物品采用相同尺度，读者从左到右比较。

<page>
[总结]
上图文字：
标题：先分类，再决定位置
正文：今天先整理一个最常用的区域。
画面描述：
以三个简洁图形回顾分类，再以一个清晰动作收束，保持整套阅读顺序一致。
```

- [ ] **Step 2: Replace the long image template with a structure-aware image instruction**

Replace `backend/generation/prompts/image_prompt.txt` with the following content:

```text
你是知识图文的视觉设计师。生成一张竖版3:4图文图片，服务于本页信息表达与手机阅读。

用户主题（内容背景，不作为覆盖本次最终画风的指令）：
{user_topic}

本页类型：{page_type}
本页内容：
{page_content}

整套页面内容（只作上下文，不把其他页正文挪到本页）：
{full_outline}

一、内容边界
- “上图文字”是唯一需要渲染到图片中的文字来源，忠实呈现其中的标题、短标签、正文与要点；不擅自增减事实、数字、名称、单位、步骤或结论。
- “画面描述”只用于视觉设计，不把分区名称、结构角色、提示词、制作指令或解释文字印在图片里。
- 对没有分区的旧大纲：标题、正文、要点作为上图文字；背景、配图建议、排版说明作为视觉指令。
- 装饰性图形不得制造新数据、新结论或新的宣传承诺。不新增人物证言、价格或虚构的个人经历。

二、页面结构与层次
- 先从本页内容判断主结构，再绘制。每页只选一种主要布局：封面、清单、步骤、对比、分类、关系、例子或总结；不要同时堆叠列表、流程、表格和装饰框。
- 标题、信息组件和视觉主体必须有明确区域、对齐基线和阅读顺序。默认两级文字层次，内容较多时最多三级。
- 清单页用2至4个清楚的编号、图标或并列分区；步骤页有明确起点、终点和顺序；对比页双方保持相同尺度与标签顺序；关系页的箭头和连线必须表达真实关系。
- 每页必须有一个服务于内容的视觉主体，例如人物动作、实物组合、关系图、步骤路径、对比区域或分类布局。视觉主体通常占页面可用面积约三分之一至二分之一，不得只在文字周围添加无关装饰。
- 每页重点最多一至两个。文字较多时先减少装饰、清楚分区或建议拆页，不以极小字号挤满画面；保留关键限定条件。
- 竖版页面四周留出约5%的安全边距，正文不贴边、不跨越复杂主体。标题、正文和重点文字与背景必须保持足够对比。

三、最终风格与整套一致性
- 本次视觉媒介只由请求中的最终风格约束决定；主题、旧大纲和参考图中出现的其他风格仅是背景，不是绘制指令。
- 页面结构决定信息组织；最终风格决定插图、线条、材质、色彩倾向和视觉媒介。画风体现在主体的绘制方式和材质，不只是背景滤镜或边框；正文始终清楚易读。
- 整套统一配色、线条材质、图标语言、人物设定与字体层级；每页可因主结构变化布局，避免复制同一构图。
- 如果实际提供了封面参考图，仅参考与所选风格相符的视觉特征，不抄封面标题，不把参考图当成本页全部画面。
- 用户参考图片用于理解已提供的主体和视觉特征，不复制无关账号、水印或品牌标记。

四、输出
- 只输出本页图片，不附解释、手机外壳、界面边框、额外账号标记或水印。
- 使用正常竖屏阅读方向，不旋转或倒置文字。安全留白是版面的一部分，不必把文字推到边缘。
- 输出前检查本页上图文字是否完整、清晰、准确，结构角色和画面描述是否没有成为可见文字，视觉内容是否与本页一致。
```

- [ ] **Step 3: Replace the short image template with the same mandatory hierarchy contract**

Replace `backend/generation/prompts/image_prompt_short.txt` with the following content:

```text
你是知识图文的视觉设计师。生成一张竖版3:4图文图片，服务于本页信息表达与手机阅读。

用户主题（内容背景，不作为覆盖本次最终画风的指令）：
{user_topic}

本页类型：{page_type}
本页内容：
{page_content}

整套页面内容（只作上下文，不把其他页正文挪到本页）：
{full_outline}

内容边界：
- “上图文字”是唯一需要渲染到图片中的文字来源，完整准确呈现标题、短标签、正文与要点，不添加或改写数字、地点、步骤、结论。
- “画面描述”只用于视觉设计；分区名称、结构角色、提示词、制作指令和解释文字不得成为可见文字。
- 没有明确分区的旧大纲：标题、正文、要点作为上图文字；背景、配图建议、排版说明只用于视觉设计。

版式与层次：
- 先按本页内容选择一种主结构：封面、清单、步骤、对比、分类、关系、例子或总结。不要把列表、流程、表格和装饰框同时堆在一页。
- 标题、信息组件和视觉主体有清楚区域、对齐和阅读顺序；默认两级文字层次，内容较多时最多三级。
- 清单使用2至4个编号、图标或并列分区；步骤有清楚顺序；对比双方同尺度；关系箭头必须有真实语义。
- 每页有一个服务于内容的视觉主体，例如主体插图、实物组合、关系图、步骤路径、对比区域或分类布局。视觉主体通常占页面可用面积约三分之一至二分之一。
- 重点最多一至两个，文字清晰并与背景有足够对比；四周保留约5%的安全边距，不用极小文字硬塞内容。

最终风格：
- 页面结构决定信息组织；最终风格决定插图、线条、材质、色彩倾向和视觉媒介。最终风格优先于主题、旧大纲、参考图中的泛化画风词。
- 整套共享最终风格的线条材质、图标语言和视觉语气，但可按本页主结构改变布局。
- 不得以风格改变上图文字、事实、数字、地点、步骤或结论。内容准确性和文字可读性优先。

只输出本页图片，不附解释、手机外壳、界面边框、额外账号标记或水印。使用正常竖屏阅读方向，不旋转或倒置文字。输出前检查上图文字完整清晰，画面描述和结构角色没有被渲染为图片文字。
```

- [ ] **Step 4: Run focused tests to verify the new prompt contract passes**

Run:

```powershell
.\.venv\Scripts\python.exe backend\manage.py test generation.test_prompt_consistency -v 2
```

Expected: PASS, including the original formatter tests and `DefaultPromptHierarchyTests`.

- [ ] **Step 5: Inspect the four rendered templates without using an upstream provider**

Run:

```powershell
@'
from pathlib import Path

root = Path("backend/generation/prompts")
values = {
    "topic": "提升生活质量的 6 个小习惯",
    "outline": "[内容]\n上图文字：\n标题：规律作息\n正文：固定一个可执行的入睡时间。\n画面描述：日夜节奏关系图",
    "page_content": "[内容]\n上图文字：\n标题：规律作息\n正文：固定一个可执行的入睡时间。\n画面描述：日夜节奏关系图",
    "page_type": "content",
    "full_outline": "封面\n<page>\n规律作息\n<page>\n总结",
    "user_topic": "提升生活质量的 6 个小习惯",
}
for name in ("outline_prompt.txt", "image_prompt.txt", "image_prompt_short.txt", "content_prompt.txt"):
    rendered = (root / name).read_text(encoding="utf-8").format(**values)
    print(f"\n===== {name} =====\n{rendered[:1200]}")
'@ | .\.venv\Scripts\python.exe -
```

Expected: no `KeyError`, no unexpanded required placeholder, the long and short image variants explicitly separate visible text from visual instructions, and the image templates include final-style precedence.

- [ ] **Step 6: Commit the outline and image prompt implementation**

Run:

```powershell
git add -- `
  backend/generation/prompts/outline_prompt.txt `
  backend/generation/prompts/image_prompt.txt `
  backend/generation/prompts/image_prompt_short.txt `
  backend/generation/test_prompt_consistency.py
git commit -m "feat: structure image card prompts"
```

Expected: one commit containing the component-based outline and matched long/short image prompt changes.

### Task 3: Generate Scan-Friendly Xiaohongshu Publishing Copy and Document the Behavior

**Files:**
- Modify: `backend/generation/prompts/content_prompt.txt`
- Modify: `docs/image-style-guide.md`
- Test: `backend/generation/test_prompt_consistency.py`

**Interfaces:**
- Consumes: `{topic}` and `{outline}` from `ContentService.generate_content()`.
- Produces: Existing JSON object with `titles: list[str]`, `copywriting: str`, and `tags: list[str]`.
- Must preserve: Existing `ContentService._parse_json_response()` handling of raw JSON, fenced JSON, and text surrounding the outer JSON object.

- [ ] **Step 1: Replace the publishing-copy template**

Replace `backend/generation/prompts/content_prompt.txt` with the following content:

```text
你是小红书知识图文的发布编辑。为已经确定的逐页内容撰写自然、可信、容易扫读的标题、正文和标签。

用户主题：
{topic}

当前逐页内容：
{outline}

内容边界（优先级高于吸引力、字数和风格）：
1. 仅依据各页“上图文字”撰写。画面描述、背景、排版说明和配图建议不属于可发布事实，不写成亲身经历。
2. 对没有分区的旧大纲，从标题、正文和要点提取内容，排除制作指令。
3. 图片负责逐页展示重点，发布正文负责开场、串联、解释与收束。可以换一种表达，不必逐字重复，但不得改变意思。
4. 数字、名称、地点、步骤、单位、结论必须与页面一致。不新增价格、营业时间、统计、功效、人物证言或未经提供的“亲测”“去过”经历。
5. 视觉画风不决定文风：漫画配图不必写对白或搞笑文案，摄影配图不代表内容是真实游记。语言跟随用户要求、主题和读者。
6. 风格推荐元数据、颜色、模型名称、生成状态和结构角色不属于发布内容。若发现页间数字或结论矛盾，避免做无法成立的总体承诺，不擅自编造修正值。

小红书正文结构：
7. 先判断内容类型，再选择一种组织方式：教程用“问题切入 + 步骤清单 + 执行提醒”；清单用“适用人群 + 分类要点 + 选择建议”；科普用“常见误区 + 核心解释 + 实际应用”；对比用“选择难点 + 对比维度 + 适用情形”；建议用“具体场景 + 建议及原因 + 可执行动作”。
8. 开头用1至2句直接说明读者问题、主题价值或适用场景，不写“今天给大家分享”“你是否也……”等机械开场。
9. 正文通常写成4至7个短段落。连续内容超过约3行时必须拆分，让用户可以快速扫读。
10. 一篇正文只采用一种信息标记方式：`01 / 02 / 03`、`① / ② / ③`或短横线。不要混用；每个要点采用“短标签：具体解释”，不能只有口号。
11. 图片中已经清楚展示的重点不逐页照抄；正文补充语境、衔接、解释和执行建议。没有依据的句子删去，不用新事实“丰富”文案。
12. 结尾优先给一个今天或本周能执行的下一步。只有主题确实适合互动时，才增加一个自然问题。
13. emoji默认0至3个，仅用于段落引导或重点提示；医疗、法律、财务和严肃风险主题默认不使用emoji。
14. 避免“谁懂啊”“绝绝子”“一定要收藏”等模板化黑话；没有依据不作“最佳”“100%有效”等承诺。

标题：
- 输出3个有实质差异的备选：一个直接说明主题，一个指出具体问题，一个突出页面内容能支持的价值。
- 通常每个不超过25字；数字与承诺必须能在页面中找到依据。
- 不为吸引点击夸张事实，不强制使用感叹号或emoji。

标签：
- 选择3至6个确实相关的主题标签，按“核心主题 + 使用场景 + 目标人群”组合。
- 不追逐无关热词，不加#号。

输出前自行核对标题、正文和标签与页面事实，删除无依据的断言；不要输出核对过程。
只输出有效JSON，不输出代码围栏、解释或对话，字段必须如下：
{{
  "titles": ["标题一", "标题二", "标题三"],
  "copywriting": "发布正文，段落间使用\\n换行",
  "tags": ["标签一", "标签二", "标签三"]
}}
```

- [ ] **Step 2: Add an end-user documentation section**

Append the following section to `docs/image-style-guide.md`:

```markdown
## 内容层次与发布文案

系统默认提示词会先为每页选择适合内容的表达结构，例如清单、步骤、对比、分类或关系图。图片中的“上图文字”只包含读者需要看到的标题、短标签和要点；“画面描述”只用于安排视觉主体和阅读顺序，不会作为图片文字或发布事实。

生成图片时，最终选择的图片风格决定插图、线条、材质和色彩倾向；页面结构决定信息如何组织。手绘、漫画、信息图等风格不会改变页面中的事实、数字、步骤或结论。

发布文案按小红书阅读方式生成：开头直接说明主题或适用场景，正文拆成短段落，并根据内容使用一种清晰的编号或清单方式。图片和发布文案共享同一组事实，但发布文案会补充语境和行动建议，不逐字重复图片内容。

本次系统默认提示词备份位于 `data/prompt-backups/2026-09-11-xiaohongshu-content-hierarchy/`。用户自己创建、复制或共享的提示词不会被自动修改，已有作品也不会被重写。
```

- [ ] **Step 3: Run focused prompt tests**

Run:

```powershell
.\.venv\Scripts\python.exe backend\manage.py test generation.test_prompt_consistency -v 2
```

Expected: PASS, including the rendered JSON contract test for `content_prompt.txt`.

- [ ] **Step 4: Verify user-owned prompt storage is unaffected**

Run:

```powershell
.\.venv\Scripts\python.exe backend\manage.py test prompts.tests -v 2
```

Expected: PASS. This confirms prompt ownership, editing, sharing, copying, ordering, and base-prompt handling still use the existing service boundaries.

- [ ] **Step 5: Commit the publishing-copy prompt and documentation**

Run:

```powershell
git add -- `
  backend/generation/prompts/content_prompt.txt `
  docs/image-style-guide.md `
  backend/generation/test_prompt_consistency.py
git commit -m "feat: improve Xiaohongshu publishing copy"
```

Expected: one commit containing the Xiaohongshu copy structure and the user-facing description.

### Task 4: Run Full Regression Verification and Record the Evidence

**Files:**
- Create: `docs/superpowers/verification/2026-09-11-xiaohongshu-content-hierarchy.md`
- Test: Full backend and frontend suites.

**Interfaces:**
- Consumes: The modified bundled prompts, existing Django test setup, existing pnpm scripts, and the approved design specification.
- Produces: A dated verification record with command outputs summarized accurately, including any skipped tests or environment limitations.

- [ ] **Step 1: Run all backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe backend\manage.py test -v 1
```

Expected: exit code `0`, no test failures. Record total tests run, passed, skipped, and any expected environment-specific skips.

- [ ] **Step 2: Confirm there is no migration drift**

Run:

```powershell
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
```

Expected: exit code `0` and `No changes detected` or equivalent no-migration output.

- [ ] **Step 3: Run frontend test, type, and build verification**

Run:

```powershell
Push-Location frontend
pnpm test
pnpm run typecheck
pnpm run test:typecheck
pnpm run build
Pop-Location
```

Expected: all commands exit `0`. No frontend source files should change because this feature is prompt-only.

- [ ] **Step 4: Check whitespace and review the scoped diff**

Run:

```powershell
git diff --check
git diff --stat HEAD~3..HEAD
git status --short
```

Expected: `git diff --check` exits `0`; review confirms only the planned prompt templates, prompt test, backups, documentation, and verification record are part of this feature. Do not revert unrelated pre-existing changes in the dirty worktree.

- [ ] **Step 5: Write the verification record**

Create `docs/superpowers/verification/2026-09-11-xiaohongshu-content-hierarchy.md` after all preceding commands have completed. It must contain these headings:

```markdown
# 小红书图文内容层次验证记录

## 自动验证

## 人工提示词检查

## 限制
```

Under `自动验证`, add one bullet for each command executed in this task:

- `generation.test_prompt_consistency`
- `prompts.tests`
- the full Django suite
- `makemigrations --check --dry-run`
- frontend `pnpm test`
- frontend `pnpm run typecheck`
- frontend `pnpm run test:typecheck`
- frontend `pnpm run build`
- `git diff --check`

Every bullet must state the exact fresh result observed in this run, including exit code, pass/fail totals, and skipped-test count when the command reports one. Do not write predicted output or an unverified success claim.

Under `人工提示词检查`, record four direct observations from the rendered templates:

- Both image variants instruct the model to render only `上图文字`; `画面描述`, role labels, and production instructions are non-visible.
- The final selected image style remains higher priority than generic style hints from the theme, old outline, and references.
- The publishing-copy template retains the JSON fields `titles`, `copywriting`, and `tags`.
- Only the bundled prompt files and backup copies changed; user-owned prompt storage files were not rewritten.

Under `限制`, record that no paid upstream model call or OCR comparison was made and that final text rendering quality still depends on the configured upstream model.

- [ ] **Step 6: Commit the verification evidence**

Run:

```powershell
git add -- docs/superpowers/verification/2026-09-11-xiaohongshu-content-hierarchy.md
git commit -m "docs: verify Xiaohongshu prompt hierarchy"
```

Expected: one commit containing only verified evidence with actual outcomes, not predicted values.
