from importlib import import_module
from django.db import migrations

FIELDS = import_module("prompts.migrations.0003_platform_aware_outline").FIELDS
OLD_RULES = (
    "医疗、法律、财务和严肃风险主题默认不使用emoji",
    "医疗、法律、财务和严肃风险主题不使用emoji",
)
NEW_RULE = (
    "医疗、法律、财务和严肃风险主题避免搞笑、夸张或淡化风险的表情；"
    "未选择“无”时允许中性编号和提示符号，不以符号代替风险说明或暗示效果保证"
)


def upgrade_content(content):
    for old in OLD_RULES:
        content = content.replace(old, NEW_RULE)
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
        Version.objects.using(alias).create(
            entry=entry, number=entry.revision,
            snapshot={key: getattr(entry, key) for key in FIELDS},
        )
    default = entry.default_snapshot or {}
    if "content" in default:
        entry.default_snapshot = {**default, "content": upgrade_content(default["content"])}
        entry.save(using=alias, update_fields=["default_snapshot"])


class Migration(migrations.Migration):
    dependencies = [("prompts", "0004_platform_neutral_copy")]
    operations = [migrations.RunPython(migrate_copy, migrations.RunPython.noop)]
