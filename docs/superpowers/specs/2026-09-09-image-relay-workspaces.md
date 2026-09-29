# Image Relay and Separate Workspaces

Approved direction: fix image relay integration, then separate image production and publishing copy into independently addressable pages.

## Image Contract

Add a GPT Image adapter behind the existing image generator. Select it for model IDs beginning `gpt-image-`; leave existing Seedream and chat-image contracts unchanged. Use JSON `model,prompt,n,size,output_format` at `/v1/images/generations`; upload byte references with multipart `image[]` to `/v1/images/edits`. Generate one image per existing page job. Use explicit pixel sizes preserving the requested aspect ratio, not the old `image_size` alias.

Reject a Responses endpoint in an image provider before sending credentials. Model-list checks are only credential/connectivity checks, not successful image tests. Surface a warning and distinguish it from generation. Preserve safe HTTP status and error category without echoing raw provider bodies or secrets. Do not retry paid image requests after ambiguous network failure.

Correct only the user's existing `heihuzi` image provider to `gpt-image-2` and `/v1/images/generations`, preserving its key, name, ownership and unrelated fields. This follows the user's approval to fix that integration. Do not alter text providers or other image providers. Verify a single low-resolution real image and inspect decoded pixels; no bulk production run.

## Independent Pages

Image production remains `/workspace`; publishing copy has its own `/workspace/copy` URL and route guard. Keep a single workspace controller for both routes so task ownership and unsaved edits survive navigation. Put shared navigation above the content, not as tabs inside the page editor. Images page includes page structure, image editor and image settings only; copy page includes copy editor and text settings only. Keep primary generation actions visible and scoped to their page. Do not permit a second generation while another task owns the shared workspace, but permit navigation.

## Verification

Mock image generation and edits contract, wrong endpoints, HTTP failures and invalid image bytes. Check image test warning payload and existing text behavior. Frontend tests cover routes, scoped controls and preserved state. Run backend tests, frontend tests/types/build, desktop/mobile browser checks and live server health. Real provider permission failures are reported honestly, not replaced by a connectivity success claim.
