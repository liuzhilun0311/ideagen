---
name: ideagen-platform-content
description: Generate platform-aware Chinese social content and image prompts with prompt-only risk-expression guidance. Use when the user wants Xiaohongshu, Douyin, WeChat Official Account, or cross-platform content and can provide an OpenAI-compatible model configuration.
---

# IdeaGen Platform Content

Use this skill to generate a platform-adapted outline, publishing copy, or image prompt. It is portable: do not assume the caller has the IdeaGen Django/Vue application installed.

## Required Inputs

Accept the following user settings as arguments or environment variables:

- `topic`: the subject to create.
- `platform`: `auto`, `xiaohongshu`, `douyin`, `wechat`, or `multi`; default `auto`.
- `goal`: `auto`, `share`, `follow`, `product`, `inquiry`, `conversion`, `brand`, or `engagement`; default `auto`.
- `phase`: `outline`, `copy`, or `image`; default `copy`.
- Model settings: `base_url`, `api_key`, and `model`. They may be supplied as CLI flags or `MODEL_BASE_URL`, `MODEL_API_KEY`, and `MODEL_NAME`.

Optional inputs include `outline`, `audience`, `facts`, `page`, `tone`, `length`, and `style`. Pass structured inputs in a JSON file with `--input-file`.

## Workflow

1. Normalize the platform, goal, and phase. Reject unsupported values instead of silently selecting a different platform.
2. Read [references/platform-rules.md](references/platform-rules.md) when choosing or explaining platform-specific wording.
3. Run `scripts/generate_content.py` with `--prompt-only` first when the user wants to inspect the prompt or when model configuration is incomplete.
4. Otherwise call the configured OpenAI-compatible chat endpoint and return the model response without post-generation word substitution.
5. Preserve user facts, numbers, dates, prices, units, product names, limitations, and conclusions. Never add evidence, certifications, testimonials, results, or credentials that were not supplied.

## Model Configuration

The script uses the OpenAI-compatible `POST {base_url}/chat/completions` contract. Examples:

```text
python scripts/generate_content.py --topic "整理桌面的步骤" --phase copy --platform xiaohongshu --goal share --base-url https://example.com/v1 --api-key "$MODEL_API_KEY" --model my-model
```

For prompt inspection without a network request:

```text
python scripts/generate_content.py --topic "整理桌面的步骤" --phase copy --platform xiaohongshu --prompt-only
```

When the caller already has a JSON input file:

```text
python scripts/generate_content.py --input-file input.json --base-url "$MODEL_BASE_URL" --api-key "$MODEL_API_KEY" --model "$MODEL_NAME"
```

The script uses only Python's standard library. It does not install packages, persist API keys, or send requests unless the model settings are complete and `--prompt-only` is absent.

## Output Rules

- `outline`: produce a clear page sequence. Use `[封面]`, `[内容]`, `[总结]`, or `[信息图]` page labels when appropriate.
- `copy`: return JSON with `titles`, `copywriting`, and `tags` unless the caller requests another format.
- `image`: produce a single-page image-generation prompt. Keep platform IDs, rule names, and internal parameters out of visible image text.
- Risk guidance is prompt-only. Do not mechanically replace, delete, encode, homophonically disguise, or rewrite generated copy after the model responds.
- The guidance is not a complete or real-time prohibited-word database and does not guarantee platform review approval.

## Validation

Run:

```text
python scripts/generate_content.py --topic "测试" --prompt-only
python scripts/generate_content.py --topic "测试" --platform douyin --phase outline --prompt-only
```

The first command should succeed without model credentials. The second prompt should contain the selected platform's rules and should not contain a network response.
