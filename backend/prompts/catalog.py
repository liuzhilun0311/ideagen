"""Durable prompt directory. Authorization and optimistic revisions live here."""
import re
import unicodedata
import uuid
from django.db import transaction
from accounts.models import User
from library.locking import serialized
from library.models import LibraryOrder
from .models import PromptEntry, PromptVersion
from .catalog_defaults import CATEGORIES, builtin_entries, validate_builtin_layout_previews

FIELDS = ("module", "category", "name", "description", "content", "metadata", "legacy_value",
          "builtin", "enabled", "visibility", "allowed_users")
RESERVED_NAMES = frozenset(("自动", "自动判断", "自动匹配", "自动推荐", "自动选择", "自定义", "自定义受众"))
PLACEHOLDER_RULES = {
    "outline": ({"topic"}, {"topic", "reference_content", "platform_name"}),
    "image": ({"page_content"}, {"page_content", "page_type", "full_outline", "user_topic", "growth_rules"}),
    "content": ({"topic", "outline"}, {"topic", "outline"}),
}


class CatalogError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def actor(user_id):
    user = User.objects.filter(pk=user_id).first()
    if not user:
        raise CatalogError("请重新登录", 401)
    return user


def editable(user, entry):
    return user.is_admin or (not entry.builtin and entry.owner_id == user.pk)


def visible(user, entry):
    return (user.is_admin or entry.owner_id == user.pk or entry.visibility == "public"
            or (entry.visibility == "selected" and user.pk in entry.allowed_users))


def usable(user, entry):
    return entry.enabled and visible(user, entry)


def entry_snapshot(entry):
    return {key: getattr(entry, key) for key in FIELDS}


def serialize(entry, user):
    return {"id": entry.pk, **entry_snapshot(entry), "owner_id": entry.owner_id,
            "owner_name": entry.owner.username if entry.owner_id else "系统",
            "revision": entry.revision, "updated_at": entry.updated_at.isoformat(),
            "can_edit": editable(user, entry), "can_use": usable(user, entry)}


@serialized
@transaction.atomic
def seed():
    defaults = builtin_entries(current_base=False)
    validate_builtin_layout_previews(defaults)
    existing = set(PromptEntry.objects.values_list("pk", flat=True))
    missing = [data for data in defaults if data["id"] not in existing]
    # Also backfill newly added descriptive metadata for already-seeded styles.
    by_id = {data["id"]: data for data in defaults}
    for entry in PromptEntry.objects.filter(builtin=True):
        data = by_id.get(entry.pk)
        if not data:
            continue
        description = data.get("description", "")
        old_default = (entry.default_snapshot or {}).get("description", "")
        if description and entry.description == old_default and entry.description != description:
            entry.description = description
            entry.revision += 1
            entry.save(update_fields=["description", "revision", "updated_at"])
            PromptVersion.objects.create(entry=entry, number=entry.revision, snapshot=entry_snapshot(entry))
        if old_default != description:
            entry.default_snapshot = {**(entry.default_snapshot or {}), "description": description}
            entry.save(update_fields=["default_snapshot"])
        merged = {**data.get("metadata", {}), **(entry.metadata or {})}
        if merged != (entry.metadata or {}):
            entry.metadata = merged
            entry.save(update_fields=["metadata", "updated_at"])
    if not missing:
        return
    from .services import get_base_prompt
    for data in missing:
        key = data["id"]
        values = {k: v for k, v in data.items() if k != "id"}
        current = dict(values)
        if data["category"] == "base":
            current["content"] = get_base_prompt(data["module"])
        entry, created = PromptEntry.objects.get_or_create(
            pk=key, defaults={**current, "default_snapshot": values})
        if created:
            PromptVersion.objects.create(entry=entry, number=1, snapshot=current)


def entries_for(user, manage=False):
    seed()
    return [entry for entry in PromptEntry.objects.select_related("owner")
            if visible(user, entry) and
            (entry.enabled or (manage and (user.is_admin or entry.owner_id == user.pk)))]


def get_entry(user, key, edit=False):
    if not isinstance(key, str) or not key or len(key) > 100:
        raise CatalogError("提示词编号无效")
    entry = PromptEntry.objects.select_related("owner").filter(pk=key).first()
    if not entry or not visible(user, entry):
        raise CatalogError("提示词不存在或无权访问", 404)
    if edit and not editable(user, entry):
        raise CatalogError("无权编辑此提示词", 403)
    return entry


def check_revision(entry, data):
    if type(data.get("revision")) is not int or data["revision"] != entry.revision:
        raise CatalogError("提示词已被修改，请重新加载后再编辑", 409)


def validate(user, data, entry=None):
    if not isinstance(data, dict):
        raise CatalogError("提示词格式无效")
    output = {}
    for key in ("module", "category", "name", "description", "content"):
        value = data.get(key, getattr(entry, key) if entry else "")
        if not isinstance(value, str):
            raise CatalogError(f"{key} 必须是文本")
        output[key] = value.strip()
    if (output["module"], output["category"]) not in {
            (item["module"], item["category"]) for item in CATEGORIES}:
        raise CatalogError("请选择有效分类")
    if entry and (output["module"], output["category"]) != (entry.module, entry.category):
        raise CatalogError("已创建的提示词不能跨分类移动，请复制到新分类")
    if not output["name"] or len(output["name"]) > 50:
        raise CatalogError("名称需要1至50个字符")
    if len(output["description"]) > 500:
        raise CatalogError("适用场景不能超过500字")
    if not output["content"] or len(output["content"]) > 20000:
        raise CatalogError("提示词内容需要1至20000个字符")
    normalized_name = unicodedata.normalize("NFKC", output["name"]).casefold()
    system_entry = bool(entry and entry.builtin and
                        (entry.legacy_value in RESERVED_NAMES or entry.legacy_value == "auto"))
    if system_entry and output["name"] != entry.name:
        raise CatalogError("系统行为名称不可修改")
    if not system_entry and (normalized_name in RESERVED_NAMES or normalized_name in {"auto", "custom"}):
        raise CatalogError("此名称为系统行为保留名称")
    # Only base templates are interpolated. JSON examples are literal content,
    # whereas identifier-like brace expressions must be supported placeholders.
    tokens = re.findall(r"\{([^{}\n]+)\}", output["content"])
    fields = {token for token in tokens if re.match(r"\w", token)}
    allowed = PLACEHOLDER_RULES[output["module"]][1] if output["category"] == "base" else set()
    if fields - allowed:
        raise CatalogError("存在未知或无效占位符：" + "、".join(sorted(fields - allowed)))
    if output["category"] == "base":
        if not entry or not entry.builtin or not user.is_admin:
            raise CatalogError("基础规则仅由管理员编辑，每个模块保留一份", 403)
        required, allowed = PLACEHOLDER_RULES[output["module"]]
        found = set(re.findall(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})", output["content"]))
        if not required <= found:
            raise CatalogError("缺少必要占位符：" + "、".join(sorted(required - found)))
        if found - allowed:
            raise CatalogError("存在未知占位符：" + "、".join(sorted(found - allowed)))
    output["enabled"] = data.get("enabled", entry.enabled if entry else True)
    if type(output["enabled"]) is not bool:
        raise CatalogError("启用状态无效")
    output["visibility"] = data.get("visibility", entry.visibility if entry else "private")
    if output["visibility"] not in ("private", "selected", "public"):
        raise CatalogError("共享范围无效")
    if output["visibility"] == "public" and not user.is_admin and (not entry or entry.visibility != "public"):
        raise CatalogError("只有管理员可以设为所有用户可用", 403)
    if entry and entry.category == "base" and (not output["enabled"] or output["visibility"] != "public"):
        raise CatalogError("基础规则必须启用且对所有用户可用")
    output["allowed_users"] = data.get("allowed_users", entry.allowed_users if entry else [])
    if (not isinstance(output["allowed_users"], list) or len(output["allowed_users"]) > 500
            or any(not isinstance(x, str) or not x or len(x) > 64 for x in output["allowed_users"])):
        raise CatalogError("用户列表无效")
    output["allowed_users"] = list(dict.fromkeys(output["allowed_users"]))
    allowed_ids = set(User.objects.filter(pk__in=output["allowed_users"])
                      .values_list("pk", flat=True))
    if set(output["allowed_users"]) - allowed_ids:
        raise CatalogError("指定用户不存在，请刷新用户列表")
    if output["visibility"] != "selected":
        output["allowed_users"] = []
    metadata = data.get("metadata", entry.metadata if entry else {})
    if not isinstance(metadata, dict) or len(metadata) > 18:
        raise CatalogError("附加信息格式无效")
    permitted = {
        "color", "group", "detail", "scenes", "caution", "preview", "preview_alt",
        "reference_asset_id", "platforms", "goals", "aspect_ratios", "text_density", "summary",
        "layout_group", "media", "mood", "business_use",
    }
    array_fields = {"platforms", "goals", "aspect_ratios", "business_use"}
    for key, value in metadata.items():
        if key not in permitted:
            raise CatalogError("附加信息包含无效字段")
        if key in array_fields:
            if (not isinstance(value, list) or not value or len(value) > 12
                    or any(not isinstance(item, str) or not item or len(item) > 40 for item in value)):
                raise CatalogError("附加信息包含无效字段")
        elif not isinstance(value, str) or len(value) > 500:
            raise CatalogError("附加信息包含无效字段")
    if metadata and (output["module"] != "image" or output["category"] not in ("layout", "style")):
        raise CatalogError("附加信息仅适用于图片布局或图片风格")
    if "color" in metadata and not re.fullmatch(r"#[0-9a-fA-F]{6}", metadata["color"]):
        raise CatalogError("颜色需要六位十六进制值")
    if "layout_group" in metadata and metadata["layout_group"] not in {"role", "information", "growth", "media"}:
        raise CatalogError("单页布局分类无效")
    if "preview" in metadata and not re.fullmatch(r"[a-z0-9-]{1,50}", metadata["preview"]):
        raise CatalogError("样图标识无效")
    if "preview" in metadata:
        previews = {item["metadata"].get("preview") for item in builtin_entries(current_base=False)}
        if metadata["preview"] not in previews:
            raise CatalogError("样图标识不存在")
    if "reference_asset_id" in metadata and not re.fullmatch(r"[0-9a-fA-F-]{36}", metadata["reference_asset_id"]):
        raise CatalogError("参考样图标识无效")
    output["metadata"] = metadata
    owner_id = entry.owner_id if entry else user.pk
    if PromptEntry.objects.filter(module=output["module"], category=output["category"],
                                  owner_id=owner_id, name=output["name"]).exclude(pk=entry.pk if entry else "").exists():
        raise CatalogError("同一分类下已有同名提示词")
    return output


def record_version(entry, user):
    PromptVersion.objects.create(entry=entry, number=entry.revision,
                                 snapshot=entry_snapshot(entry), actor=user)


@serialized
@transaction.atomic
def save(user, data):
    if not isinstance(data, dict):
        raise CatalogError("提示词格式无效")
    entry = get_entry(user, data["id"], edit=True) if "id" in data else None
    if entry:
        check_revision(entry, data)
    values = validate(user, data, entry)
    if entry:
        for key, value in values.items():
            setattr(entry, key, value)
        entry.revision += 1
        entry.save()
    else:
        entry = PromptEntry.objects.create(id=str(uuid.uuid4()), owner=user, **values)
    record_version(entry, user)
    return serialize(entry, user)


@serialized
@transaction.atomic
def copy(user, data):
    if not isinstance(data, dict):
        raise CatalogError("提示词格式无效")
    source = get_entry(user, data.get("id", ""))
    if source.category == "base":
        raise CatalogError("基础规则使用版本管理，不能复制为第二份生效规则")
    if not usable(user, source):
        raise CatalogError("此提示词已停用，不能复制", 403)
    if "revision" in data:
        check_revision(source, data)
    name = source.name[:40] + " 副本"
    index = 2
    while PromptEntry.objects.filter(owner=user, module=source.module, category=source.category, name=name).exists():
        name = source.name[:36] + f" 副本 {index}"
        index += 1
    entry = PromptEntry.objects.create(
        id=str(uuid.uuid4()), owner=user, module=source.module, category=source.category,
        name=name, description=source.description, content=source.content, metadata=source.metadata)
    record_version(entry, user)
    row, _ = LibraryOrder.objects.get_or_create(user=user, resource="prompt-center", kind=f"{entry.module}.{entry.category}")
    current = ordered_ids(user, entry.module, entry.category, row.order)
    current = [key for key in current if key != entry.pk]
    position = current.index(source.pk) + 1 if source.pk in current else len(current)
    current.insert(position, entry.pk)
    row.order, row.revision = current, row.revision + 1
    row.save()
    return serialize(entry, user)


@serialized
@transaction.atomic
def restore(user, data):
    if not isinstance(data, dict):
        raise CatalogError("提示词格式无效")
    entry = get_entry(user, data.get("id", ""), edit=True)
    check_revision(entry, data)
    if "version" not in data:
        if not entry.builtin:
            raise CatalogError("自定义提示词没有内置默认版本")
        old = entry.default_snapshot
    elif type(data.get("version")) is int and data["version"] > 0:
        version = PromptVersion.objects.filter(entry=entry, number=data["version"]).first()
        if not version:
            raise CatalogError("历史版本不存在", 404)
        old = version.snapshot
    else:
        raise CatalogError("历史版本编号无效")
    # Restore editorial fields, never restore old sharing or status.
    values = validate(user, {key: old[key] for key in ("name", "description", "content", "metadata")}, entry)
    for key, value in values.items():
        setattr(entry, key, value)
    entry.revision += 1
    entry.save()
    record_version(entry, user)
    return serialize(entry, user)


def ordered_ids(user, module, category, saved):
    visible_ids = list(PromptEntry.objects.filter(module=module, category=category).select_related("owner"))
    ids = [entry.pk for entry in visible_ids if visible(user, entry)
           and (entry.enabled or user.is_admin or entry.owner_id == user.pk)]
    allowed = set(ids)
    return list(dict.fromkeys([key for key in saved if key in allowed] + ids))


@serialized
@transaction.atomic
def reorder(user, data):
    if not isinstance(data, dict):
        raise CatalogError("排序格式无效")
    module, category = data.get("module"), data.get("category")
    if not isinstance(module, str) or not isinstance(category, str):
        raise CatalogError("模块和分类格式无效")
    if category == "base" or (module, category) not in {(c["module"], c["category"]) for c in CATEGORIES}:
        raise CatalogError("此分类不能排序")
    row, _ = LibraryOrder.objects.get_or_create(user=user, resource="prompt-center", kind=f"{module}.{category}")
    if type(data.get("revision")) is not int or row.revision != data["revision"]:
        raise CatalogError("排序已改变，请刷新后重试", 409)
    ids = data.get("ids")
    if (not isinstance(ids, list) or len(ids) > 1000
            or any(type(key) is not str or not key or len(key) > 100 for key in ids)
            or len(ids) != len(set(ids))):
        raise CatalogError("排序列表无效")
    current = ordered_ids(user, module, category, row.order)
    if set(ids) != set(current):
        raise CatalogError("提示词列表已变化，请刷新后重试", 409)
    row.order, row.revision = ids, row.revision + 1
    row.save()
    return row.revision
