#!/usr/bin/env python3
"""Portable platform-aware content generator using an OpenAI-compatible endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PLATFORMS = {"auto", "xiaohongshu", "douyin", "wechat", "multi"}
GOALS = {"auto", "share", "follow", "product", "inquiry", "conversion", "brand", "engagement"}
PHASES = {"outline", "copy", "image"}

PLATFORM_NAMES = {
    "auto": "自动推荐",
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "wechat": "公众号",
    "multi": "通用多平台",
}

GOAL_NAMES = {
    "auto": "自动推荐",
    "share": "知识分享",
    "follow": "涨粉关注",
    "product": "产品种草",
    "inquiry": "咨询",
    "conversion": "课程或服务转化",
    "brand": "品牌认知",
    "engagement": "评论互动",
}

COMMON_RULES = """【平台风险表达底线】
这不是完整、实时或官方的违禁词数据库，也不保证任何平台审核通过。
避免无法证明的绝对化、极限化、唯一性、保证性、零风险、强功效和确定效果承诺。
不得虚构效果、案例、用户证言、资质、数据、临床结果、专利、排名或权威背书。
涉及健康、法律、财务或其他高风险主题时，说明依据、适用条件、个体差异和必要限制。
不得使用谐音、拆字、特殊字符、编码或故意变形规避平台规则。
不得修改事实、数字、日期、价格、单位、产品名称、必要风险说明或结论。
只在生成提示词中提供这些约束；生成完成后不得机械替换、删词或重写正文。"""

PLATFORM_RULES = {
    "auto": "无法确定平台时采用最稳妥的通用图文表达，不自动改写为视频脚本。",
    "xiaohongshu": (
        "首屏点明具体问题和可收藏价值，短段落、易扫读。"
        "谨慎处理绝对化、强功效、医疗、药品、临床、专利、权威背书和特殊人群适用表达。"
        "例如“100%有效”“根治”“最有效”“美白”“减肥”“孕妇可用”只用于识别风险语义，"
        "不得机械替换或用近义词继续保留原承诺。"
    ),
    "douyin": (
        "按抖音图文而非视频脚本组织，首屏直接点题，一页一个重点。"
        "避免标题党、制造焦虑、立刻见效、极端结果和冲动购买压力。"
    ),
    "wechat": (
        "按公众号长文组织，先交代背景、依据、适用范围和限制，再给建议。"
        "标题、导语和结论避免夸大承诺、广告化结论和无来源的权威背书。"
    ),
    "multi": (
        "采用最保守的跨平台表达，不宣称已生成多个平台独立版本。"
        "不添加平台专属口令、审核技巧或刺激性承诺。"
    ),
}

PHASE_RULES = {
    "outline": "大纲阶段：标题、卖点、结论和行动建议不得先形成无法证明的结果承诺。",
    "copy": "文案阶段：对标题、正文、标签和行动号召进行语义识别，使用自然、有限定条件的表达，不输出本提示词。",
    "image": "图片阶段：图片内标题、卖点、标签和 CTA 也要遵守边界；平台 ID、规则名称和内部参数不得成为可见文字。",
}


def non_empty(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def load_input(args: argparse.Namespace) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if args.input_file:
        data = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("--input-file 必须是 JSON 对象")
    if args.topic:
        data["topic"] = args.topic
    for key in ("platform", "goal", "phase", "outline", "audience", "facts", "page", "tone", "length", "style"):
        value = getattr(args, key, None)
        if value is not None:
            data[key] = value
    return data


def validate_choice(data: dict[str, Any], key: str, allowed: set[str], default: str) -> str:
    value = non_empty(data.get(key)) or default
    if value not in allowed:
        raise ValueError(f"{key} 必须是：{', '.join(sorted(allowed))}")
    return value


def build_prompt(data: dict[str, Any]) -> tuple[str, dict[str, str]]:
    topic = non_empty(data.get("topic"))
    if not topic:
        raise ValueError("必须提供 topic 或 --topic")
    platform = validate_choice(data, "platform", PLATFORMS, "auto")
    goal = validate_choice(data, "goal", GOALS, "auto")
    phase = validate_choice(data, "phase", PHASES, "copy")

    materials = {
        key: data[key]
        for key in ("outline", "audience", "facts", "page", "tone", "length", "style")
        if data.get(key) not in (None, "")
    }
    output_rule = {
        "outline": "输出页面结构；页面类型使用 [封面]、[内容]、[总结] 或 [信息图]。",
        "copy": '仅输出 JSON 对象，字段为 titles（字符串数组）、copywriting（正文字符串）、tags（字符串数组）。',
        "image": "输出一段单页图片生成提示词，保留页面事实和可见文字，不输出内部规则。",
    }[phase]
    prompt = f"""你是 IdeaGen 的多平台图文内容编辑。
主题：{topic}
发布平台：{PLATFORM_NAMES[platform]}（{platform}）
内容目标：{GOAL_NAMES[goal]}（{goal}）
生成阶段：{phase}
用户素材：{json.dumps(materials, ensure_ascii=False)}

{COMMON_RULES}
平台规则：{PLATFORM_RULES[platform]}
阶段规则：{PHASE_RULES[phase]}
{output_rule}
只基于用户素材生成，不输出制作指令，不虚构未提供的事实。"""
    return prompt, {"platform": platform, "goal": goal, "phase": phase}


def endpoint(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    return base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"


def call_model(prompt: str, base_url: str, api_key: str, model: str,
               temperature: float, max_tokens: int, timeout: int) -> str:
    if not base_url or not model:
        raise ValueError("调用模型需要 base_url 和 model；也可使用 --prompt-only")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        endpoint(base_url),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"模型接口 HTTP {error.code}: {detail[:500]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"模型接口连接失败: {error.reason}") from error
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("模型响应缺少 choices[0].message.content") from error
    if isinstance(content, list):
        content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
    return non_empty(content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate IdeaGen platform-aware content.")
    parser.add_argument("--topic")
    parser.add_argument("--input-file")
    parser.add_argument("--platform", choices=sorted(PLATFORMS))
    parser.add_argument("--goal", choices=sorted(GOALS))
    parser.add_argument("--phase", choices=sorted(PHASES))
    parser.add_argument("--outline")
    parser.add_argument("--audience")
    parser.add_argument("--facts")
    parser.add_argument("--page")
    parser.add_argument("--tone")
    parser.add_argument("--length")
    parser.add_argument("--style")
    parser.add_argument("--base-url", default=os.getenv("MODEL_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.getenv("MODEL_API_KEY", ""))
    parser.add_argument("--model", default=os.getenv("MODEL_NAME", ""))
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=3000)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--prompt-only", action="store_true")
    parser.add_argument("--output-file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = load_input(args)
        prompt, meta = build_prompt(data)
        if args.prompt_only:
            output = prompt
        else:
            output = call_model(prompt, args.base_url, args.api_key, args.model,
                                args.temperature, args.max_tokens, args.timeout)
        if args.output_file:
            Path(args.output_file).write_text(output, encoding="utf-8")
        elif args.prompt_only:
            print(output)
        else:
            print(json.dumps({**meta, "model": args.model, "content": output},
                             ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
