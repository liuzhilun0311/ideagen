from django.db import migrations


DIRECTIONS = {
    "chat-proof": (
        "评论与聊天截图风，以消息气泡、评论上下文和隐私遮挡表达互动证据。不得伪造聊天记录、头像、昵称、时间或用户评价。",
        "抽象聊天气泡排版，不是人物插画海报，也不是真实软件截图。画面四分之三以上必须用于大号、左右交错的带尾角消息气泡及气泡间的留白：第一条居左、第二条居右、第三条居左，形成纵向阅读的对话结构。每个要点独占一个气泡，不要把三个气泡排成同侧的项目列表。标题独立置顶。画面描述中的人物和物品仅作为气泡内的小附件，总面积不得超过画面十分之一，禁止大幅人物和背景场景。只使用提供的文字，不补写问答、昵称、时间或评价，不添加头像、状态栏、平台标识。没有真实来源时仅呈现抽象消息排版；真实来源需遮挡隐私。",
    ),
    "tech-brand": (
        "SaaS科技品牌视觉，使用网格、清晰模块、冷静配色和轻量数据感表达产品价值。只展示正文提供的界面、数据和功能，不伪造截图。",
        "SaaS科技品牌视觉，以精密可见的细线网格、对齐的模块化信息面板、统一线性图标和清楚的连接关系作为主要视觉语言。采用白色或浅灰底，蓝色与青色克制点缀，深色无衬线标题；不是把普通人物插画简单染成蓝色。提供的要点分别成为有秩序的模块，配图缩成局部小型场景或抠图，人物不能占满画面。只表现已提供的文字、事实、界面和功能；没有产品截图时使用抽象信息架构，禁止捏造真实软件界面、统计图、数字指标、功能按钮或品牌。",
    ),
}
FIELDS = (
    "module", "category", "name", "description", "content", "metadata",
    "legacy_value", "builtin", "enabled", "visibility", "allowed_users",
)


def calibrate(apps, schema_editor):
    Entry = apps.get_model("prompts", "PromptEntry")
    Version = apps.get_model("prompts", "PromptVersion")
    alias = schema_editor.connection.alias
    for style_id, (old, new) in DIRECTIONS.items():
        entry = Entry.objects.using(alias).filter(pk=f"image.style.{style_id}", builtin=True).first()
        if not entry:
            continue
        # Only replace the exact shipped default, never an administrator's edit.
        if entry.content == old:
            entry.content = new
            entry.revision += 1
            entry.save(using=alias, update_fields=["content", "revision", "updated_at"])
            Version.objects.using(alias).create(
                entry=entry, number=entry.revision,
                snapshot={key: getattr(entry, key) for key in FIELDS},
            )
        if (entry.default_snapshot or {}).get("content") == old:
            entry.default_snapshot = {**entry.default_snapshot, "content": new}
            entry.save(using=alias, update_fields=["default_snapshot"])


class Migration(migrations.Migration):
    dependencies = [("prompts", "0001_initial")]
    operations = [migrations.RunPython(calibrate, migrations.RunPython.noop)]
