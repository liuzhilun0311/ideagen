# Relay Text Model Setup

In Models > Text Generation > Add, set:

| Field | Value |
| --- | --- |
| Provider | A unique local name |
| Type | OpenAI compatible |
| Base URL | `https://code.heihuzi.ai` |
| Model | The exact model ID enabled for your key, for example the user-supplied `gpt-6-astra` |
| API protocol | Responses |
| API endpoint | `/v1/responses` |
| API Key | Enter a newly issued key directly in the application |

The example model ID is opaque configuration, not a claim that the relay currently offers it.
Revoke any key exposed in chat before configuring a replacement. Never commit keys.
Configuration uses the application's existing server-side provider storage; blank keys on edit preserve the stored key.

Test Connection sends one real text request and may consume relay quota. Save the provider,
then select it independently for outline generation and publishing copy in the creation views.
Development preview uses mock data; use the normal application for real configuration.

## Compatibility

- Responses text generation and connection tests use the same adapter.
- Legacy configurations remain Chat Completions unless their endpoint ends in `/responses`.
- Explicit `api_protocol` takes precedence. The selector updates standard paths; manually edited paths are preserved on submission.
- Responses sends `model`, `input`, and `stream: false`. Reference images use `input_image` entries.
- Only final text is accepted. Empty, refused, failed, unfinished, and unexpected streaming responses are errors.
- Temperature and output token limits from the existing generation signature are intentionally not sent in Responses mode. The relay's documented minimal contract does not guarantee these fields; upstream defaults apply.
- A real text smoke request and a five-page outline succeeded on September 9, 2026. This does not guarantee future model availability or quota.
- Images use a separate provider configuration and Images adapter, not Responses image tools. Claude Messages and streaming Responses remain unsupported.

## Images

The relay image provider uses `gpt-image-2` at `/v1/images/generations`, with the same relay Base URL.
Image generation uses `size` and `output_format`; byte references are uploaded as multipart to `/v1/images/edits`.
Existing non-GPT image providers retain their previous contracts.

The existing local `heihuzi` image provider was updated to these fields, preserving its key and other providers.
The verification request on September 9, 2026 returned **HTTP 403**. No actual image was generated.
The relay operator must check the key's group and image-generation permission; working text access does not verify image access.
Do not repeatedly retry a denied image request.

Model-list connection checks show a warning: they verify authentication/connectivity only.
Image errors are shown on the failed page and in the diagnostic error panel.
Ambiguous image POST failures are not automatically retried because the upstream may still charge for the first attempt.

## Workspace Pages

- `/workspace`: image production, page structure and image settings.
- `/workspace/copy`: publication titles, body and tags with copy controls.
- Both URLs refer to the same current work. Navigation preserves edits and the current task;
  another generation cannot start while the workspace is already generating.

## Deployment

Requests originate from the Django backend, so desktop and mobile browsers use the same adapter.
No additional dependency or service is needed. Deploy the updated frontend build and backend together.
Protect provider storage and backups, use HTTPS, and keep API keys out of frontend bundles and container images.
