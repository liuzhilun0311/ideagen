"""Automatic image direction shared by page trials and request previews."""
from django.http import JsonResponse
from common.api import require_auth, json_body, api_error_response
from prompts.services import get_base_prompt
from .catalog import catalog_request
from .outline_prompt import catalog_base, catalog_option, prompt_scope
from .styles import style_prompt, format_image_prompt, resolve_style, FrozenImageTemplate
from .structure import image_page_content
from .parameters import normalize_image_parameters, validate_provider_parameters
from .generators.gpt_images import image_size
from .reference_roles import reference_instruction, validate_reference_roles
from .generation_context import build_generation_context
from .palettes import image_reference_roles
from .reference_images import validate_reference_count


def automatic_image_template(style, reference_count=0, cover_reference=False, reference_roles=None, generation_preferences=None):
    base = catalog_base("image").replace(
        '参考图只保留必要的主体关系，按最终风格重新绘制。',
        '用户参考图仅按用户明确选择的维度使用，按最终风格重新绘制。',
    )
    context = build_generation_context("", "", generation_preferences, {}, style)
    template = style_prompt(base, style, generation_context=context)
    roles = image_reference_roles(style, reference_roles)
    template += reference_instruction(reference_count, roles)
    if cover_reference:
        template += '\n另附本作品第一张已采用图片作为一致性参考。继承其主体外观、配色与线条语言，不复制其文字、布局或无关元素；当前页面的文字、布局、独立配色和明确指定的风格优先。'
    return FrozenImageTemplate(template, generation_context=context)


def render_page_prompt(page, topic, style, reference_count=0, cover_reference=False, reference_roles=None, generation_preferences=None):
    return format_image_prompt(automatic_image_template(style, reference_count, cover_reference, reference_roles, generation_preferences), {
        "page_content": image_page_content(page), "page_type": page["type"],
        "user_topic": topic or "未提供", "full_outline": "",
    })


@require_auth
@catalog_request
def preview(request):
    if request.method != "POST":
        return api_error_response("请求方法不支持", status=405)
    try:
        data = json_body(request)
        page = data.get("page")
        if not isinstance(page, dict) or not isinstance(page.get("content"), str) or not page["content"].strip():
            raise ValueError("请先填写本页内容。")
        if page.get("type") not in ("cover", "content", "summary", "infographic"):
            raise ValueError("页面类型无效。")
        count = data.get("reference_count", 0)
        validate_reference_count(count)
        use_reference = data.get("use_reference", False)
        if type(use_reference) is not bool:
            raise ValueError("参考第一张图必须为布尔值。")
        cover = None
        if use_reference:
            from .candidates import authorized, cover_reference, snapshot
            record = authorized(request, data.get("record_id"))
            snapshot(record, page.get("index"))
            cover = cover_reference(record, page["index"], True)
        topic = data.get("topic", "")
        if not isinstance(topic, str):
            raise ValueError("主题格式无效。")
        style = resolve_style(data.get("image_style"))
        roles = image_reference_roles(style, data.get("reference_roles"))
        prompt = render_page_prompt(page, topic, style, count, bool(cover), roles, data.get("generation_preferences"))
        parameters = normalize_image_parameters(data.get("image_parameters"))
        provider_name = data.get("provider_name")
        provider = {}
        if provider_name:
            from providers.config import get_image_provider_config
            provider = get_image_provider_config(provider_name, request.user_id)
            validate_provider_parameters(provider, parameters)
        gpt_images = str(provider.get("model", "")).startswith("gpt-image-")
        response = JsonResponse({
            "success": True, "prompt": prompt,
            "image_style": style, "parameters": parameters,
            "gpt_images_parameters": {
                "size": image_size(parameters["aspect_ratio"], parameters["resolution"]),
                "quality": parameters["quality"], "output_format": parameters["output_format"], "n": 1,
            },
            "references": {"count": count + int(bool(cover)), "user_count": count, "cover_count": int(bool(cover)),
                           "mode": "reference" if count or cover else "text_to_image", "roles": roles},
            "provider": {"name": provider_name, "model": provider.get("model"),
                         "gpt_images": gpt_images, "quality_applied": gpt_images,
                         "output_format_stage": "stored_artifact", "output_verified": False},
        })
        response["Cache-Control"] = "no-store"
        return response
    except PermissionError as error:
        return api_error_response(str(error), status=403)
    except (ValueError, TypeError, AttributeError) as error:
        return api_error_response(str(error), status=400)
