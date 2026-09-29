# 提示词与用户选项全链路审计

日期：2026-09-28。范围：当前工作区源码、数据库中的基础提示词、无付费模型调用的本地验证。

后续状态：本报告保留修复前发现；实施结果与兼容边界见[修复验收记录](F:/ai_tools_projects/IdeaGen/docs/superpowers/verification/2026-09-28-prompt-options-repair.md)。

## 一、结论

不能把“选项出现在界面”“提示词出现选项名称”“接口收到参数”“结果遵守选项”当成一回事。

当前系统已具备大纲、文案、图片的提示词组合能力，但存在跨步骤状态断点、旧平台模板冲突和图片适配器差异。尤其是参考图维度与图片平台规则，存在明确的未传递问题。不能据现有 generation_audit 中的 applied 字段断言选项真正生效。

本轮只审计，未修改功能代码、用户配置或历史作品；未调用付费模型。语义效果仍需在修复后用固定样例实际评测。

## 二、用户选项关系表

| 用户输入或选项 | 应影响哪里 | 当前实现与结论 |
| --- | --- | --- |
| 创作主题 | 大纲、文案、图片的内容边界 | 三阶段均传递；文案、图片以已有逐页内容为主是合理的，不应各自重新创作事实 |
| 参考文本 | 大纲事实来源 | 加入大纲并标明素材；后续依赖大纲承接，不直接重发原资料。大纲遗漏的事实不会自动在文案中补回 |
| 参考图片 | 大纲理解、图片生成 | 能上传，但不同图片适配器支持数量不同；不能统一宣称所有上传图片均被使用 |
| 图片参考维度 | 明确允许借用内容、主体、风格、构图、色彩 | 有规则生成器，但主页生成前会清空选项；Google 适配器另加冲突风格指令 |
| 发布平台 | 大纲节奏、文案表达、图片信息密度 | 大纲已接入；文案仍有小红书基础角色；当前候选图片路径未注入平台规则 |
| 获客目标 | 内容证明、结尾行动和图片重点 | 大纲、文案有通用规则；候选图片断链；尚非各目标独立、可验收的策略 |
| 整体组织方式 | 页与页之间的逻辑 | 大纲加入目录中的具体规则；不应与单页布局或文案结构混为一谈 |
| 目标受众、自定义受众 | 解释深度、术语、例子 | 大纲和文案有规则；自定义说明只在选择“自定义”时启用；暂无受众适配的结果验收 |
| 表达语气 | 大纲措辞及文案默认语气 | 有规则；明确文案风格会覆盖原语气，需把这个优先级告知用户 |
| 页数 | 大纲数量和角色 | 当前较完整：提示词约束、后端数量及角色验证、前端数量复核；1页仅封面、2页封面加总结 |
| 文案风格 | 发布正文措辞 | 注入具体规则；重新生成大纲后原选择被重置 |
| 正文结构 | 发布正文组织 | 注入具体规则；与逐页大纲组织方式属于不同层次 |
| 文案长度 | 发布正文篇幅 | 100–200、300–500、600–900为软目标，素材不足可更短；未做结果字数校验 |
| 表情丰富度 | 正文 emoji 使用 | 有选项，但基础模板还有默认0–3个规则；建议只输出本次选中的规则，明确严肃主题例外 |
| 图片风格、补充要求 | 插画、线条、材质、配色 | 候选图片会注入规则；“参考图风格”与“指定画风”冲突时应明确最终优先级 |
| 单页布局 | 当前页信息结构 | 按页面字段加载布局规则；仍依靠模型遵守，没有最终图片布局检测 |
| 参考第一张图 | 系列主体及视觉一致性 | 候选流程使用已采用首图；不应意味着复制首图文字和布局；Google 路径还有额外指令冲突 |
| 分辨率、宽高比、质量、输出格式 | 上游请求参数，而非正文提示词 | 设计方向正确；不同适配器实际支持不同，部分参数被忽略，AUTO被转换成1K |
| 大纲、文案、图片模型 | 对应阶段路由 | 主要作为服务商/模型参数，不应写成画面或文案内容；需要以最终请求记录确认实际模型与协议 |
| 自动推荐 | 为未指定项目选择适合值 | 当前会覆盖部分控件且与保存快照不一致，应拆分用户选择、建议值、实际采用值 |
| 历史恢复、重试、重新生成 | 重现当时有效配置 | 并非完整快照：参考素材、图片参数等未全部按作品保存，存在不同入口行为不一致 |

## 三、已确认问题及优先级

### P1：主页生成前清空图片参考维度

- 链路：HomeView.handleGenerate 调用 prepareNewOutline，再调用 outline.start。
- prepareNewOutline 保留 userImages，但把 referenceRoles 置为 []；发送请求时读取的已经是空数组。
- 影响：预览可能有“只参考主体”，实际请求却是“未选择参考维度”，后续图片生成也继承空选择。
- 证据：[HomeView.vue](F:/ai_tools_projects/IdeaGen/frontend/src/views/HomeView.vue:164)、[generator.ts](F:/ai_tools_projects/IdeaGen/frontend/src/stores/generator.ts:696)、[useOutlineGeneration.ts](F:/ai_tools_projects/IdeaGen/frontend/src/composables/useOutlineGeneration.ts:45)。
- 建议：区分“开始一个新作品时清理旧数据”和“提交当前表单”，提交不得清掉当前表单的任何用户选择。

### P1：当前候选图片路径没有平台、获客目标上下文

- automatic_image_template 调用 style_prompt 时未传 generation_context，render_page_prompt 也不接收平台与目标。
- candidates.generate 虽然拿到了历史作品，却未将其 generation_preferences 接入图片模板。
- format_image_prompt 在没有上下文时把 growth_rules 替换成空字符串。
- 影响：图片仍可间接受大纲内容影响，但不能声称图片阶段明确执行了用户的平台、获客目标规则。
- 只读复现：render_page_prompt 结果不含“【平台与获客目标规则】”。
- 证据：[image_prompt.py](F:/ai_tools_projects/IdeaGen/backend/generation/image_prompt.py:14)、[candidates.py](F:/ai_tools_projects/IdeaGen/backend/generation/candidates.py:138)、[styles.py](F:/ai_tools_projects/IdeaGen/backend/generation/styles.py:147)。

### P1：选抖音后，发布文案仍收到小红书角色

- content 基础模板首句为“你是小红书知识图文的发布编辑”，另有“小红书正文结构”。
- build_copy_prompt 后面又添加用户选择的抖音平台规则，形成两套平台指令。
- 数据库 content.base.default revision 2 也包含“小红书”，并非仅未使用的磁盘文件。
- 只读复现：抖音文案提示词同时包含小红书和 douyin。
- 证据：[content_prompt.txt](F:/ai_tools_projects/IdeaGen/backend/generation/prompts/content_prompt.txt:1)、[copy_prompt.py](F:/ai_tools_projects/IdeaGen/backend/generation/copy_prompt.py:49)。
- 建议：统一平台中性基础模板，加明确平台策略；同步处理数据库模板版本，不能只修改文件。

### P1：Google 图片适配器覆盖参考维度意图，且未使用全部参考图

- 候选流程给 Google 传首图参考，或第一张用户参考图；ImageService 的 Google 分支没有传完整 user_images。
- Google 适配器另包一层“必须保持与参考图相同的视觉风格和设计语言”等指令。
- 影响：仅参考主体、指定另一种画风、上传多张图时，实际输入与界面表达不一致；预览也未包含这层额外提示词。
- 证据：[candidates.py](F:/ai_tools_projects/IdeaGen/backend/generation/candidates.py:150)、[image.py](F:/ai_tools_projects/IdeaGen/backend/generation/services/image.py:287)、[google_genai.py](F:/ai_tools_projects/IdeaGen/backend/generation/generators/google_genai.py:370)。
- 建议：适配器只负责协议，不私加创作政策；不支持多图时明确提示或禁用，而非静默丢弃。

### P2：自动推荐与实际保存的选项分裂

- 后端 generation_preferences 返回原 options，自动选择仍为 auto。
- 前端先保存该快照，再将界面的 outlinePlatform、outlineGoal 改成推荐值。
- 文案预览与生成读取的是保存快照，不是这些控件；历史恢复也从快照恢复。
- 图片风格自动值会直接变成具体 preset，后续新主题可能继续使用该具体值，而不再自动推荐。
- 证据：[views.py](F:/ai_tools_projects/IdeaGen/backend/generation/views.py:145)、[useOutlineGeneration.ts](F:/ai_tools_projects/IdeaGen/frontend/src/composables/useOutlineGeneration.ts:58)、[useStudio.ts](F:/ai_tools_projects/IdeaGen/frontend/src/composables/useStudio.ts:78)。
- 建议：保留 requested、recommended、effective 三份含义不同的值；后续阶段统一读取确认过的 effective。

### P2：重新生成大纲会丢失已手动设置的文案偏好

- setOutline 清空 copy_preferences；useOutlineGeneration 随后才读取 copyPreferences，拿到的是默认值。
- 后续“保留手动风格”的分支因此不能保住此前选择；emoji 还无条件优先采用推荐值。
- “适中”既是默认又可能是用户明确选择，当前无法区分两者。
- 证据：[generator.ts](F:/ai_tools_projects/IdeaGen/frontend/src/stores/generator.ts:330)、[useOutlineGeneration.ts](F:/ai_tools_projects/IdeaGen/frontend/src/composables/useOutlineGeneration.ts:74)。
- 建议：同一作品重新生成保留手动偏好，新作品另行初始化；记录是否由用户明确选择，不以“等于默认值”判断。

### P2：图片参数存在静默失效或与用户含义不同

- apply_image_parameters 更新 generator.config，但非 GPT 的 ImageApiGenerator 分支使用初始化时缓存的 self.image_size；这条路径不会读取新选分辨率。
- Google 图片请求目前只写入 aspect_ratio，没有把界面分辨率、质量、输出格式全部映射进去。
- AUTO实际固定成1K，不是由模型自动选择。
- GPT 图片接口会收到 output_format，但客户端最终转换成PNG、候选文件也固定为PNG；这影响生成产物格式，与另行下载转码是不同问题。
- 非 GPT Image API 的旧尺寸映射中“4K”对应1024×1792，不能按字面理解为4K输出。
- 证据：[parameters.py](F:/ai_tools_projects/IdeaGen/backend/generation/parameters.py:19)、[image_api.py](F:/ai_tools_projects/IdeaGen/backend/generation/generators/image_api.py:29)、[image_api.py](F:/ai_tools_projects/IdeaGen/backend/generation/generators/image_api.py:115)、[google_genai.py](F:/ai_tools_projects/IdeaGen/backend/generation/generators/google_genai.py:394)、[gpt_images.py](F:/ai_tools_projects/IdeaGen/backend/generation/generators/gpt_images.py:164)。
- 建议：按模型能力显示选项，记录实际像素尺寸、实际编码和实际参数；不支持时阻止或明确告知。

### P2：历史作品不包含完整可重现输入

- useDraftSave 的作品快照没有完整保存参考文本、参考图片资产及维度、图片输出参数、首图参考开关、各阶段模型。
- useHistoryDraft 载入作品时明确清空参考文本和图片；其他未恢复控件可能来自当前会话。
- 旧重绘路径 useImageRetry 也未发送用户参考图片和维度，不能假定与候选生成等价。
- 证据：[useDraftSave.ts](F:/ai_tools_projects/IdeaGen/frontend/src/composables/useDraftSave.ts:14)、[useHistoryDraft.ts](F:/ai_tools_projects/IdeaGen/frontend/src/composables/useHistoryDraft.ts:106)、[useImageRetry.ts](F:/ai_tools_projects/IdeaGen/frontend/src/composables/useImageRetry.ts:60)。
- 建议：以作品和每次生成任务保存完整、脱敏、版本化配置；原素材若不保留，应明确说明不可重现。

### P2：字段审计不等于实际生效，文本一致性检查不等于图片识别

- audit_context 的 applied 根据“值非空”或“规则字符串存在”判断，不验证最终请求是否使用。
- consistency.py 比较页面文字与图片提示词，不读取最终图片中的文字、布局和实际主体。
- 影响：可用于排查配置与提示词，不能充当输出质量保证。
- 证据：[generation_context.py](F:/ai_tools_projects/IdeaGen/backend/generation/generation_context.py:104)、[consistency.py](F:/ai_tools_projects/IdeaGen/backend/generation/consistency.py:1)。
- 建议：区分已选择、已解析、已注入、已发送、结果已验证五个状态；失败、未支持和未检验必须可见。

## 四、不是传参错误，但需要明确的设计边界

1. 平台与目标目前主要是名称加通用说明。缺少平台各自的具体规则及验收标准；“多平台”也未生成分平台版本，不应承诺一份内容天然适合所有平台。
2. 图文与视频脚本是不同内容形态。“抖音”不能自动等同于“口播视频”，应单独确认内容形态，避免从平台选项推断错误任务。
3. 页数硬约束与“信息多则拆页”、单页35–90字默认规则可能竞争。1页复杂主题应优先摘要或告知信息取舍，不能无限压缩字号。
4. 不选任何参考维度时，规则禁止风格、主体、构图、色彩，却未明确禁止内容提取。应定义为不使用，或让用户明确选择；不应默默消耗上传图像。
5. 文案“长度”当前是软目标。需要向用户区分建议篇幅与严格字数；严格限制必须有程序校验和有限修复。
6. emoji 丰富度、文案风格、受众、严肃主题限制应有单一优先级。不要把互相竞争的规则全部堆给模型。
7. Responses 适配器有意使用最小请求体，未发送 temperature、max_output_tokens。不能把服务层收到这些参数等同于上游执行；也不宜未经协议兼容验证就盲目添加。
8. 参考文本、图片文字、用户补充要求都应作为有边界的输入，不能让素材里的“忽略规则”等句子升级为系统指令。当前大部分提示词作为同一文本发送，仅靠文字声明不等于可靠隔离。
9. 自定义目录项、默认模板、历史模板版本需一起验收。修改磁盘默认不一定覆盖数据库里正在使用的版本；禁用选项不应静默退回另一项。
10. 手动修改大纲、修改文案、重排页面后，应标识旧图片或旧文案已过期。重新生成成功才替换结果，失败时保留用户内容。

## 五、建议采用的统一规则

### 配置层

每项选项记录：用户原始选择、是否手动、推荐值、实际采用值、来源、适用阶段、模板版本、模型支持情况。

### 提示词层

顺序建议为：事实和禁止编造边界 → 已确认的上图文字 → 平台及目标 → 受众与表达 → 当前阶段风格与结构 → 明确参考维度 → 输出协议。

视觉优先级与事实优先级分开：画风可覆盖旧画面描述，但不得覆盖用户确认的文字、数字和事实；参考图不得扩大已授权维度。

### 执行层

预览与实际发送共用同一份编译结果，并记录各选项落在了哪个提示词片段或哪个接口字段。适配器不得在预览之后偷偷增加创作指令。

### 验收层

- 硬校验：页数、角色、JSON结构、非空字段、类型、实际图片尺寸和编码。
- 内容校验：数字及专名一致、事实来源、禁用emoji、明确字数上限。
- 语义评测：平台感、受众适配、语气、风格、布局、行动号召自然度。应使用固定样例和人工抽查，不靠字符串包含判断。
- 对照评测：相同主题每次仅切换一个选项，检查预期维度是否变化、事实是否保持。
- 边界样例：单页、长资料、无参考维度、多图、只参考主体、手动画风冲突、历史恢复、失败重试、自定义目录项。

## 六、验证记录与修复顺序

本轮执行：

- 后端 `manage.py test generation.test_generation_context generation.test_reference_roles generation.test_copy_prompt generation.test_page_count generation.test_layers generation.test_prompt_consistency --verbosity 0`：36项通过。
- 前端 Vitest：platformRecommendations、referenceRoles、copyOptions、newCreation：17项通过。
- 只读提示词复现：图片平台规则存在为False；抖音文案中小红书与douyin同时存在均为True。
- 数据库只读确认：content.base.default revision 2包含小红书角色。

测试通过不否定上述问题：现有前端参考图测试覆盖候选请求和存储，没有覆盖“主页提交先清理状态”的完整链路；平台测试主要覆盖枚举、规范化和存储，不保证三阶段实际发送。

建议顺序：

1. 先修四个P1：表单选择被清空、候选图片上下文断链、文案平台冲突、Google参考规则冲突。
2. 统一用户选择与实际采用配置，修复推荐覆盖与历史快照。
3. 建立模型能力表，修复或隐藏不生效参数；明确格式与分辨率含义。
4. 补跨入口、跨阶段回归测试，再做少量经用户确认的实际模型对照评测。

完成标准不是“提示词更长”，而是每项用户选择都有明确作用范围、唯一有效值、可核对的请求证据和与其性质相称的结果验证。
