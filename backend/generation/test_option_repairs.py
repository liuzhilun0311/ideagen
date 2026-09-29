from types import SimpleNamespace
from django.test import SimpleTestCase
from .image_prompt import render_page_prompt
from .copy_prompt import build_copy_prompt
from .parameters import apply_image_parameters
from .reference_roles import reference_instruction
from .generation_context import effective_preferences
from .image_output import encode_output
from unittest.mock import Mock, patch
import io
from PIL import Image


class OptionRepairTests(SimpleTestCase):
    def test_candidate_prompt_has_effective_platform_and_goal(self):
        prompt = render_page_prompt(
            {"index": 0, "type": "cover", "content": "上图文字：主题"},
            "主题", {"preset": "auto"},
            generation_preferences={"platform": "douyin", "goal": "follow"},
        )
        self.assertIn("douyin", prompt)
        self.assertIn("follow", prompt)

    def test_copy_has_no_competing_platform_role(self):
        prompt, _, _ = build_copy_prompt({
            "topic": "收纳", "outline": "上图文字：归类",
            "generation_preferences": {"platform": "douyin"},
            "copy_preferences": {"emoji_level": "无"},
        })
        self.assertNotIn("小红书", prompt)
        self.assertIn("douyin", prompt)
        self.assertNotIn("丰富：", prompt)

    def test_request_updates_legacy_cached_size(self):
        original = SimpleNamespace(provider_config={}, generator=SimpleNamespace(config={}, image_size="4K"))
        changed = apply_image_parameters(original, {"resolution": "2K"})
        self.assertEqual(changed.generator.image_size, "2K")
        self.assertEqual(original.generator.image_size, "4K")

    def test_empty_roles_forbid_text_extraction(self):
        self.assertIn("文字", reference_instruction(1, []))

    def test_recommendations_only_resolve_automatic_fields(self):
        self.assertEqual(effective_preferences(
            {"platform": "wechat", "goal": "auto"}, {"platform": "douyin", "goal": "follow"}),
            {"platform": "wechat", "goal": "follow"})

    def test_output_encoding_is_real_and_reports_dimensions(self):
        source = io.BytesIO()
        Image.new("RGB", (40, 60), "white").save(source, "PNG")
        for format in ("png", "jpeg", "webp"):
            result, metadata = encode_output(source.getvalue(), format)
            with Image.open(io.BytesIO(result)) as image:
                self.assertEqual(image.format.lower(), format)
                self.assertEqual(image.size, (40, 60))
            self.assertEqual(metadata["format"], format)

    def test_unsupported_quality_fails_before_generation(self):
        service = SimpleNamespace(provider_config={"type": "google_genai", "model": "image-model"},
                                  generator=SimpleNamespace(config={}))
        with self.assertRaisesRegex(ValueError, "质量"):
            apply_image_parameters(service, {"quality": "high"})

    def test_google_sends_all_references_without_rewriting_prompt(self):
        from .generators.google_genai import GoogleGenAIGenerator
        generator = GoogleGenAIGenerator.__new__(GoogleGenAIGenerator)
        generator.config = {"image_size": "2K"}
        generator.is_vertexai = False
        generator.safety_settings = []
        generator.client = Mock()
        image = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(image, "PNG")
        chunk = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
            SimpleNamespace(inline_data=SimpleNamespace(data=image.getvalue(), mime_type="image/png"), text=None)
        ]))])
        generator.client.models.generate_content_stream.return_value = [chunk]
        generator.generate_image("ONLY THE COMPILED PROMPT", reference_images=[image.getvalue(), image.getvalue()])
        call = generator.client.models.generate_content_stream.call_args.kwargs
        parts = call["contents"][0].parts
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[-1].text, "ONLY THE COMPILED PROMPT")
        self.assertEqual(call["config"].image_config.image_size, "2K")

    def test_explicit_provider_does_not_initialize_default_client(self):
        from .services.outline import OutlineService
        with patch("generation.services.outline.load_text_providers_config", return_value={}), \
             patch.object(OutlineService, "_get_client", side_effect=ValueError("invalid default")) as default:
            OutlineService("user")
        default.assert_not_called()

    def test_copy_validation_rejects_forbidden_emoji_without_changing_content(self):
        from .copy_validation import validate_copy_result
        with self.assertRaises(ValueError):
            validate_copy_result({"copywriting": "内容\U0001f600"}, {"emoji_level": "无"})
        result = validate_copy_result({"copywriting": "简短但可信"}, {"length": "详细"})
        self.assertTrue(result["warnings"])
        self.assertFalse(result["facts_verified"])

    def test_each_platform_has_distinct_rules_in_every_phase(self):
        from .generation_context import growth_prompt_rules, PLATFORM_RULES, GOAL_RULES
        for platform, rule in PLATFORM_RULES.items():
            for phase in ("outline", "copy", "image"):
                self.assertIn(rule, growth_prompt_rules(platform, "follow", phase))
        for goal, rule in GOAL_RULES.items():
            self.assertIn(rule, growth_prompt_rules("douyin", goal, "copy"))
