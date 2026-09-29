from importlib import import_module
from django.db import migrations

FIELDS = import_module("prompts.migrations.0003_platform_aware_outline").FIELDS
REPLACEMENTS = (
    ("你是小红书知识图文的发布编辑。", "你是图文内容的发布编辑，发布平台以本次平台规则为准。"),
    ("小红书正文结构：", "发布正文结构："),
    ("emoji默认0至3个，仅用于段落引导或重点提示；医疗、法律、财务和严肃风险主题默认不使用emoji。",
     "emoji按本次表情丰富度执行，仅用于段落引导或重点提示；医疗、法律、财务和严肃风险主题不使用emoji。"),
)


def upgrade_content(content):
    for old, new in REPLACEMENTS:
        content = content.replace(old, new)
    return content


def migrate_copy(apps, schema_editor):
    Entry = apps.get_model("prompts", "PromptEntry")
    Version = apps.get_model("prompts", "PromptVersion")
    alias = schema_editor.connection.alias
    entry = Entry.objects.using(alias).filter(pk="content.base.default", builtin=True).first()
    if entry is None:
        return
    content = upgrade_content(entry.content)
    if content != entry.content:
        entry.content = content
        entry.revision += 1
        entry.save(using=alias, update_fields=["content", "revision", "updated_at"])
        Version.objects.using(alias).create(entry=entry, number=entry.revision,
            snapshot={key: getattr(entry, key) for key in FIELDS})
    default = entry.default_snapshot or {}
    if "content" in default:
        entry.default_snapshot = {**default, "content": upgrade_content(default["content"])}
        entry.save(using=alias, update_fields=["default_snapshot"])


class Migration(migrations.Migration):
    dependencies = [("prompts", "0003_platform_aware_outline")]
    operations = [migrations.RunPython(migrate_copy, migrations.RunPython.noop)]
