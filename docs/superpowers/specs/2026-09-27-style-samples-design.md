# Independent Style Samples and Visual Acceptance

Date: 2026-09-27

## Approved Objective

Provide a distinct, accurate image for each of the 42 concrete built-in styles,
and check actual generation using a shared subject. Existing user prompts,
reference images, and historical works must remain intact.

## Audit Findings

- The catalog contains 42 concrete styles plus a separate automatic choice.
- The current asset folder contains 30 PNG files, including the automatic image.
- A name-based frontend override masks several shared catalog preview IDs.
- The override for gongbi points to a missing gongbi.png file.
- Commercial presets still borrow images representing other styles.
- The local preview builder produces illustrative swatches, not model samples.
- Commercial presets combine art direction with use cases. This pass will label
  them as commercial scene presets, not redesign generation settings or break IDs.

## Design

1. Preserve all style IDs. Associate validated samples with IDs, not Chinese names.
   A manifest records the sample path, model, generation parameters, date, prompt
   digest, source type, and human visual review outcome. Do not store credentials.
2. Use one synthetic subject across all styles: a small desktop plant, a watering
   can, and a person caring for the plant. Exact short Chinese copy describes
   observation, checking soil, and watering as needed. Do not invent sales,
   testimonials, guarantees, or product specifications.
3. Request one 2K portrait sample per style with the same selected model and
   parameters. Use existing application prompt assembly so the sample tests the
   product's style constraints, not an unrelated drawing prompt. Run serially.
4. Preserve raw model output. Review subject fidelity, distinguishing style
   characteristics, Chinese text, readability, and unwanted fabricated claims.
   Failed or unreviewed images must not be advertised as approved samples.
5. Keep a clear distinction between illustrative references, actual model
   samples, and user-uploaded references. An actual sample demonstrates only its
   recorded model and settings, not all available models.
6. Use approved samples in both the creation selector and prompt manager. Keep
   click-to-enlarge, show whole images without misleading cropping, and display a
   visible unavailable state if loading fails.
7. User-uploaded references take precedence. Edited or custom prompts must not
   inherit a claim of testing merely because their names match built-in styles.

## Cost and Failure Controls

Live generation requires confirmation of using the configured image service for
42 requests. Cost cannot be quoted without reliable service billing information.
No automatic paid retries, no parallel requests, and no replacement of user works.
Stop on rate limits, quota errors, or authentication failures. Persist successful
outputs and resume only missing items after resolving the cause.

## Acceptance

- 42 distinct approved sample files, each associated with the correct stable ID.
- Valid image bytes, recorded dimensions and unique image hashes.
- No missing style files, name-dependent redirects, or shared substitute images.
- Source and review status are accurate in both UI entry points.
- Regression tests cover custom-reference priority, missing images, and stable IDs.
- Desktop/mobile browser checks verify enlargement, containment, and labels.
- Document failures or pending samples rather than marking the entire set passed.
