from django.db import migrations


OLD_ROLE = "你是面向小红书知识图文的内容编辑。"
NEW_ROLE = "你是面向{platform_name}图文创作的内容编辑。"
FIELDS = (
    "module", "category", "name", "description", "content", "metadata",
    "legacy_value", "builtin", "enabled", "visibility", "allowed_users",
)


def upgrade_content(content):
    # Replace only the shipped role and topic heading, not administrator additions.
    if content.startswith(OLD_ROLE):
        content = NEW_ROLE + content[len(OLD_ROLE):]
    for newline in ("\r\n", "\n"):
        content = content.replace(
            f"{newline}用户要求：{newline}{{topic}}",
            f"{newline}用户创作的主题：{newline}{{topic}}", 1,
        )
    return content


def update_outline(apps, schema_editor):
    Entry = apps.get_model("prompts", "PromptEntry")
    Version = apps.get_model("prompts", "PromptVersion")
    alias = schema_editor.connection.alias
    entry = Entry.objects.using(alias).filter(pk="outline.base.default", builtin=True).first()
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
    default = (entry.default_snapshot or {}).get("content", "")
    updated_default = upgrade_content(default)
    if default != updated_default:
        entry.default_snapshot = {**entry.default_snapshot, "content": updated_default}
        entry.save(using=alias, update_fields=["default_snapshot"])


class Migration(migrations.Migration):
    dependencies = [("prompts", "0002_calibrate_style_directions")]
    operations = [migrations.RunPython(update_outline, migrations.RunPython.noop)]
